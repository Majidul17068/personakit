"""Observability — Tracer protocol and OpenTelemetry adapter.

personakit emits structured trace events at three points in `Agent.analyze`:

1. `personakit.analyze` — the top-level call (one span per `analyze` invocation)
2. `personakit.provider.complete` — every LLM round-trip
3. `personakit.tool.invoke` — every tool execution

Tracers receive contextual attributes (specialist name, model, token counts,
tool name, duration, etc.). Default behaviour is a no-op `NullTracer`. To get
real traces, plug in `OpenTelemetryTracer` (requires `personakit[otel]`) or
write your own implementation of the `Tracer` protocol.

Custom tracer example:

    class StdoutTracer:
        def start_span(self, name, **attrs):
            from contextlib import contextmanager
            @contextmanager
            def _ctx():
                t0 = time.perf_counter()
                print(f"START {name} {attrs}")
                try:
                    yield self
                finally:
                    dt = (time.perf_counter() - t0) * 1000
                    print(f"END   {name} ({dt:.0f}ms)")
            return _ctx()

        def add_event(self, name, **attrs): pass
        def set_attribute(self, key, value): pass
"""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import IO, Any, Protocol, runtime_checkable

from .cost import estimate_cost_from_usage
from .errors import MissingDependencyError

_ANSI_RESET = "\x1b[0m"
_ANSI = {
    "cyan": "\x1b[36m",
    "yellow": "\x1b[33m",
    "magenta": "\x1b[35m",
    "red": "\x1b[31m",
    "green": "\x1b[32m",
    "grey": "\x1b[90m",
    "bold": "\x1b[1m",
}


def _color(text: str, name: str, enabled: bool) -> str:
    if not enabled or name not in _ANSI:
        return text
    return f"{_ANSI[name]}{text}{_ANSI_RESET}"


@runtime_checkable
class TraceSpan(Protocol):
    """A single in-flight span. Returned by `Tracer.start_span`."""

    def add_event(self, name: str, **attributes: Any) -> None: ...
    def set_attribute(self, key: str, value: Any) -> None: ...
    def __enter__(self) -> TraceSpan: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...


@runtime_checkable
class Tracer(Protocol):
    """A pluggable tracing backend.

    `start_span` should return a context manager that yields a `TraceSpan`.
    """

    def start_span(self, name: str, **attributes: Any) -> Any: ...


class _NullSpan:
    """No-op span returned by NullTracer."""

    def add_event(self, name: str, **attributes: Any) -> None:
        return None

    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def __enter__(self) -> _NullSpan:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        return None


class NullTracer:
    """Default tracer — does nothing. Used when no tracer is configured."""

    @contextmanager
    def start_span(self, name: str, **attributes: Any) -> Iterator[_NullSpan]:
        # Silence "unused" lints; the values flow into nothing on purpose.
        del name, attributes
        yield _NullSpan()


class OpenTelemetryTracer:
    """Adapter that bridges personakit's Tracer protocol to OpenTelemetry.

    Requires `personakit[otel]` extra (installs `opentelemetry-api` and
    `opentelemetry-sdk`). Configure your OTel SDK / exporters as usual; this
    adapter just wraps `tracer.start_as_current_span(...)` and forwards
    attributes.

    Usage:

        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        from opentelemetry import trace

        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)

        from personakit import Agent
        from personakit.observability import OpenTelemetryTracer

        agent = Agent(specialist=..., model="gpt-4o", tracer=OpenTelemetryTracer())
    """

    def __init__(self, instrumentation_name: str = "personakit") -> None:
        try:
            from opentelemetry import trace as _otel_trace
        except ImportError as exc:
            raise MissingDependencyError(
                "OpenTelemetryTracer requires the 'opentelemetry-api' package. "
                "Install with: pip install 'personakit[otel]'"
            ) from exc
        self._otel_trace = _otel_trace
        self._tracer = _otel_trace.get_tracer(instrumentation_name)

    @contextmanager
    def start_span(self, name: str, **attributes: Any) -> Iterator[Any]:
        with self._tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                if value is None:
                    continue
                # OTel only accepts a narrow set of attribute value types.
                if isinstance(value, (str, bool, int, float)):
                    span.set_attribute(key, value)
                else:
                    span.set_attribute(key, str(value))
            yield span


class _ConsoleSpan:
    """Live span used by ``ConsoleTracer`` — records attributes and prints on close."""

    def __init__(
        self,
        tracer: ConsoleTracer,
        name: str,
        attributes: dict[str, Any],
    ) -> None:
        self._tracer = tracer
        self._name = name
        self._attributes = dict(attributes)
        self._extras: dict[str, Any] = {}
        self._started = time.perf_counter()
        self._depth = tracer._depth
        self._error: str | None = None

    def add_event(self, name: str, **attributes: Any) -> None:
        del name, attributes

    def set_attribute(self, key: str, value: Any) -> None:
        self._extras[key] = value

    def __enter__(self) -> _ConsoleSpan:
        if self._tracer._live:
            self._tracer._render_open(self)
        self._tracer._depth += 1
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._tracer._depth = max(0, self._tracer._depth - 1)
        duration_ms = (time.perf_counter() - self._started) * 1000
        if exc_val is not None:
            self._error = f"{type(exc_val).__name__}: {exc_val}"
        self._tracer._render_close(self, duration_ms)


class ConsoleTracer:
    """Zero-dependency ``Tracer`` that renders each span as a coloured line.

    Wire it into any ``Agent`` (or accept the default when passing
    ``verbose=True``) to see the three built-in personakit spans surface as
    they happen:

    * ``personakit.analyze`` — top-level analyze call
    * ``personakit.provider.complete`` — every LLM round-trip
    * ``personakit.tool.invoke`` — every tool execution

    Parameters
    ----------
    stream
        Output stream. Defaults to ``sys.stdout``.
    color
        Force colour on / off. ``None`` (default) auto-detects from
        ``stream.isatty()``.
    show_cost
        When true (default), estimates USD cost per provider call using
        ``personakit.cost.estimate_cost_from_usage`` and shows it inline.
    show_tokens
        When true (default), shows ``prompt→completion`` token counts.

    Example
    -------

        from personakit import Agent
        from personakit.observability import ConsoleTracer

        agent = Agent(specialist=spec, model="gpt-4o", tracer=ConsoleTracer())
        await agent.analyze("...")
        # → [analyze] specialist=code_reviewer model=gpt-4o 1420ms
        #     → provider openai iter=0 msgs=2 542→318 tok $0.00485
    """

    def __init__(
        self,
        *,
        stream: IO[str] | None = None,
        color: bool | None = None,
        show_cost: bool = True,
        show_tokens: bool = True,
        live: bool = True,
    ) -> None:
        self._stream: IO[str] = stream or sys.stdout
        if color is None:
            color = bool(getattr(self._stream, "isatty", lambda: False)())
        self._color = color
        self._show_cost = show_cost
        self._show_tokens = show_tokens
        self._live = live
        self._depth = 0

    @contextmanager
    def start_span(self, name: str, **attributes: Any) -> Iterator[_ConsoleSpan]:
        span = _ConsoleSpan(self, name, attributes)
        with span:
            yield span

    def _render_open(self, span: _ConsoleSpan) -> None:
        indent = "  " * span._depth
        line = self._format_open(span._name, span._attributes)
        print(f"{indent}{line}", file=self._stream, flush=True)

    def _render_close(self, span: _ConsoleSpan, duration_ms: float) -> None:
        indent = "  " * span._depth
        merged: dict[str, Any] = {**span._attributes, **span._extras}
        line = self._format_close(span._name, merged, duration_ms, span._error)
        print(f"{indent}{line}", file=self._stream, flush=True)

    def _format_open(self, name: str, attrs: dict[str, Any]) -> str:
        arrow = _color("▶", "grey", self._color)
        if name in ("personakit.analyze", "personakit.chat"):
            tag = "analyze" if name == "personakit.analyze" else "chat"
            label = _color(f"[{tag}]", "cyan", self._color)
            return (
                f"{arrow} {label} specialist={attrs.get('specialist','?')} "
                f"model={attrs.get('model') or '(default)'}"
            )
        if name == "personakit.provider.complete":
            label = _color("provider", "yellow", self._color)
            return (
                f"{arrow} {label} {attrs.get('provider','?')} "
                f"iter={attrs.get('iteration', 0)}"
            )
        if name == "personakit.tool.invoke":
            label = _color("tool", "magenta", self._color)
            return f"{arrow} {label} {attrs.get('tool','?')}"
        return f"{arrow} [{name}]"

    def _format_close(
        self,
        name: str,
        attrs: dict[str, Any],
        duration_ms: float,
        error: str | None,
    ) -> str:
        arrow = _color("◀", "grey", self._color)
        if name in ("personakit.analyze", "personakit.chat"):
            tag = "analyze" if name == "personakit.analyze" else "chat"
            label = _color(f"[{tag}]", "cyan", self._color)
            tail = _color(f"{duration_ms:.0f}ms", "grey", self._color)
            body = f"{arrow} {label} done  {tail}"
            if error:
                body += "  " + _color(f"ERROR {error}", "red", self._color)
            return body

        if name == "personakit.provider.complete":
            label = _color("provider", "yellow", self._color)
            provider = attrs.get("provider", "?")
            iteration = attrs.get("iteration", 0)
            msg_count = attrs.get("message_count", 0)
            in_tok = int(
                attrs.get("usage.input_tokens")
                or attrs.get("usage.prompt_tokens")
                or 0
            )
            out_tok = int(
                attrs.get("usage.output_tokens")
                or attrs.get("usage.completion_tokens")
                or 0
            )
            parts = [arrow, label, provider, f"iter={iteration}", f"msgs={msg_count}"]
            if self._show_tokens and (in_tok or out_tok):
                parts.append(f"{in_tok}→{out_tok} tok")
            if self._show_cost:
                model = attrs.get("model") or attrs.get("_model") or ""
                if model and (in_tok or out_tok):
                    cost = estimate_cost_from_usage(
                        model,
                        {"prompt_tokens": in_tok, "completion_tokens": out_tok},
                    )
                    if cost is not None:
                        parts.append(f"${cost:.5f}")
            parts.append(_color(f"{duration_ms:.0f}ms", "grey", self._color))
            tool_calls = int(attrs.get("tool_calls_count") or 0)
            if tool_calls:
                parts.append(
                    _color(f"tool_calls={tool_calls}", "magenta", self._color)
                )
            if error:
                parts.append(_color(f"ERROR {error}", "red", self._color))
            return "  ".join(parts)

        if name == "personakit.tool.invoke":
            label = _color("tool", "magenta", self._color)
            tool = attrs.get("tool", "?")
            known = attrs.get("known", True)
            status = "ok" if known and not error and not attrs.get("error") else "err"
            colour = "green" if status == "ok" else "red"
            parts = [
                arrow,
                label,
                tool,
                _color(status, colour, self._color),
                _color(f"{duration_ms:.0f}ms", "grey", self._color),
            ]
            if error:
                parts.append(_color(error, "red", self._color))
            return "  ".join(parts)

        parts = [arrow, _color(f"[{name}]", "grey", self._color)]
        if attrs:
            parts.append(" ".join(f"{k}={v}" for k, v in attrs.items()))
        parts.append(_color(f"{duration_ms:.0f}ms", "grey", self._color))
        if error:
            parts.append(_color(error, "red", self._color))
        return "  ".join(parts)


__all__ = [
    "ConsoleTracer",
    "NullTracer",
    "OpenTelemetryTracer",
    "TraceSpan",
    "Tracer",
]
