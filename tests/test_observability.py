"""Tests for the Tracer protocol + OTel adapter wiring."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any

import pytest

from personakit import Agent, Specialist
from personakit.observability import NullTracer
from personakit.providers import MockProvider


class RecordingTracer:
    """Tracer that captures every span name + attributes for assertions."""

    def __init__(self) -> None:
        self.spans: list[dict[str, Any]] = []

    @contextmanager
    def start_span(self, name: str, **attributes: Any):
        record = {"name": name, "attributes": dict(attributes), "events": [], "set_attrs": {}}
        self.spans.append(record)

        class _Span:
            def add_event(_self, ename: str, **eattrs: Any) -> None:
                record["events"].append({"name": ename, "attrs": eattrs})

            def set_attribute(_self, key: str, value: Any) -> None:
                record["set_attrs"][key] = value

            def __enter__(_self):
                return _self

            def __exit__(_self, *_args: Any) -> None:
                return None

        yield _Span()


def _final_json_dict(text: str = "Done") -> dict:
    return {
        "summary": text,
        "probes_answered": {},
        "red_flags_detected": [],
        "priorities_status": [],
        "recommendations": [],
        "citations_used": [],
    }


def _spec() -> Specialist:
    return Specialist(name="traced", persona="Be traced.")


@pytest.mark.asyncio
async def test_null_tracer_is_default_and_does_nothing() -> None:
    provider = MockProvider(responses=_final_json_dict())
    agent = Agent(specialist=_spec(), provider=provider, model="mock-1")
    assert isinstance(agent.tracer, NullTracer)
    # Should run without errors.
    await agent.analyze("hi")


@pytest.mark.asyncio
async def test_tracer_records_analyze_and_provider_spans() -> None:
    tracer = RecordingTracer()
    provider = MockProvider(responses=_final_json_dict())
    agent = Agent(
        specialist=_spec(), provider=provider, model="mock-1", tracer=tracer
    )
    await agent.analyze("input text here")

    span_names = [s["name"] for s in tracer.spans]
    assert "personakit.analyze" in span_names
    assert "personakit.provider.complete" in span_names

    analyze_span = next(s for s in tracer.spans if s["name"] == "personakit.analyze")
    assert analyze_span["attributes"]["specialist"] == "traced"
    assert analyze_span["attributes"]["provider"] == "mock"
    assert analyze_span["attributes"]["input_chars"] == len("input text here")


@pytest.mark.asyncio
async def test_tracer_records_tool_invoke_span() -> None:
    from personakit.tools import tool

    @tool
    def stub() -> dict:
        return {"ok": True}

    from personakit.providers import LLMResponse

    tracer = RecordingTracer()
    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                model="mock-1",
                tool_calls=[{"id": "c1", "name": "stub", "arguments": "{}"}],
            ),
            _final_json_dict(),
        ]
    )
    agent = Agent(
        specialist=_spec(), provider=provider, model="mock-1", tracer=tracer
    ).with_tools([stub])
    await agent.analyze("hi")

    tool_spans = [s for s in tracer.spans if s["name"] == "personakit.tool.invoke"]
    assert len(tool_spans) == 1
    assert tool_spans[0]["attributes"]["tool"] == "stub"
    assert tool_spans[0]["attributes"]["known"] is True


@pytest.mark.asyncio
async def test_tracer_records_unknown_tool_attribute() -> None:
    """When the LLM hallucinates a tool, we still emit the span and set
    `error=unknown_tool` on it for visibility."""
    from personakit.providers import LLMResponse

    tracer = RecordingTracer()
    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                model="mock-1",
                tool_calls=[
                    {"id": "c1", "name": "fake_tool", "arguments": "{}"}
                ],
            ),
            _final_json_dict(),
        ]
    )
    agent = Agent(
        specialist=_spec(), provider=provider, model="mock-1", tracer=tracer
    )
    await agent.analyze("hi")

    tool_spans = [s for s in tracer.spans if s["name"] == "personakit.tool.invoke"]
    assert len(tool_spans) == 1
    assert tool_spans[0]["set_attrs"].get("error") == "unknown_tool"


@pytest.mark.asyncio
async def test_with_tools_propagates_tracer() -> None:
    tracer = RecordingTracer()
    provider = MockProvider(responses=_final_json_dict())
    agent = Agent(
        specialist=_spec(), provider=provider, model="mock-1", tracer=tracer
    )
    extended = agent.with_tools([])
    assert extended.tracer is tracer


def test_otel_adapter_raises_helpful_error_when_otel_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The OTel adapter should give a clear MissingDependencyError if
    opentelemetry isn't installed."""
    import builtins

    from personakit.errors import MissingDependencyError
    from personakit.observability import OpenTelemetryTracer

    real_import = builtins.__import__

    def _block_otel(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("opentelemetry"):
            raise ImportError("mocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_otel)

    with pytest.raises(MissingDependencyError) as exc_info:
        OpenTelemetryTracer()
    assert "personakit[otel]" in str(exc_info.value)


@pytest.mark.asyncio
async def test_provider_span_records_token_usage() -> None:
    from personakit.providers import LLMResponse

    tracer = RecordingTracer()
    provider = MockProvider(
        responses=LLMResponse(
            text=json.dumps(_final_json_dict()),
            model="mock-1",
            usage={"input_tokens": 100, "output_tokens": 25},
        )
    )
    agent = Agent(
        specialist=_spec(), provider=provider, model="mock-1", tracer=tracer
    )
    await agent.analyze("hi")

    provider_spans = [
        s for s in tracer.spans if s["name"] == "personakit.provider.complete"
    ]
    assert len(provider_spans) == 1
    assert provider_spans[0]["set_attrs"]["usage.input_tokens"] == 100
    assert provider_spans[0]["set_attrs"]["usage.output_tokens"] == 25
