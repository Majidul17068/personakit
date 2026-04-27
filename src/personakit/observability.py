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

from collections.abc import Iterator
from contextlib import contextmanager
from types import TracebackType
from typing import Any, Protocol, runtime_checkable

from .errors import MissingDependencyError


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


__all__ = [
    "NullTracer",
    "OpenTelemetryTracer",
    "TraceSpan",
    "Tracer",
]
