"""Tests for the streaming pipeline — Agent.analyze_stream() + providers."""

from __future__ import annotations

import json

import pytest

from personakit import Agent, Specialist
from personakit.providers import LLMResponse, MockProvider
from personakit.result import StreamEvent
from personakit.tools import tool


def _spec() -> Specialist:
    return Specialist(
        name="streamer",
        persona="Stream a structured analysis.",
        themes=[{"name": "Findings"}],
    )


def _final_json_dict(text: str = "Done") -> dict:
    return {
        "summary": text,
        "probes_answered": {},
        "red_flags_detected": [],
        "priorities_status": [],
        "recommendations": [{"theme": "Findings", "text": text, "citations": []}],
        "citations_used": [],
    }


@pytest.mark.asyncio
async def test_stream_emits_text_deltas() -> None:
    provider = MockProvider(responses=_final_json_dict("Hello world"))
    agent = Agent(specialist=_spec(), provider=provider, model="mock-1")

    text_pieces = []
    complete_event = None
    async for event in agent.analyze_stream("test"):
        if event.type == "text_delta":
            text_pieces.append(event.text)
        elif event.type == "complete":
            complete_event = event

    assert len(text_pieces) > 1, "Mock should chunk the canned response"
    assert "".join(text_pieces) == json.dumps(_final_json_dict("Hello world"))
    assert complete_event is not None
    assert complete_event.result is not None
    assert "Hello world" in complete_event.result.summary


@pytest.mark.asyncio
async def test_stream_emits_red_flag_pre_match_first() -> None:
    """Pre-match events should arrive before any text deltas."""
    spec = Specialist(
        name="alarmist",
        persona="Watch for ABC.",
        red_flags=[
            {
                "trigger": "ABC mentioned",
                "severity": "high",
                "action": "Investigate",
                "patterns": [r"\bABC\b"],
            }
        ],
    )
    provider = MockProvider(responses=_final_json_dict("nothing"))
    agent = Agent(specialist=spec, provider=provider, model="mock-1")

    seen_pre = False
    pre_came_first = False
    async for event in agent.analyze_stream("the ABC corporation"):
        if event.type == "red_flag_pre_match":
            seen_pre = True
            pre_came_first = True
        elif event.type == "text_delta" and not seen_pre:
            pre_came_first = False
            break
    assert seen_pre, "regex match should produce a pre_match event"
    assert pre_came_first


@pytest.mark.asyncio
async def test_stream_tool_loop_yields_tool_call_and_tool_result() -> None:
    invoked: list[dict] = []

    @tool
    def lookup(key: str) -> dict:
        """Test tool."""
        invoked.append({"key": key})
        return {"value": f"value-of-{key}"}

    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                model="mock-1",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": "lookup",
                        "arguments": json.dumps({"key": "x"}),
                    }
                ],
            ),
            _final_json_dict("got-it"),
        ]
    )
    agent = Agent(specialist=_spec(), provider=provider, model="mock-1").with_tools(
        [lookup]
    )

    events_by_type: dict[str, list[StreamEvent]] = {}
    async for event in agent.analyze_stream("test"):
        events_by_type.setdefault(event.type, []).append(event)

    assert len(events_by_type.get("tool_call", [])) == 1
    assert events_by_type["tool_call"][0].tool_name == "lookup"
    assert events_by_type["tool_call"][0].tool_arguments == {"key": "x"}

    assert len(events_by_type.get("tool_result", [])) == 1
    tr = events_by_type["tool_result"][0]
    assert tr.tool_name == "lookup"
    assert tr.tool_result == {"value": "value-of-x"}
    assert tr.duration_ms is not None and tr.duration_ms >= 0

    complete = events_by_type["complete"][0]
    assert complete.result is not None
    assert "got-it" in complete.result.summary


@pytest.mark.asyncio
async def test_stream_complete_event_carries_full_result() -> None:
    provider = MockProvider(responses=_final_json_dict("final"))
    agent = Agent(specialist=_spec(), provider=provider, model="mock-1")

    complete = None
    async for event in agent.analyze_stream("input"):
        if event.type == "complete":
            complete = event
            break

    assert complete is not None
    result = complete.result
    assert result is not None
    assert result.specialist_name == "streamer"
    assert result.summary == "final"
    assert result.recommendations[0].text == "final"
    assert result.model  # model field populated for cost estimation


@pytest.mark.asyncio
async def test_stream_iteration_complete_marks_each_round() -> None:
    @tool
    def stub() -> dict:
        return {"ok": True}

    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                model="mock-1",
                tool_calls=[{"id": "c1", "name": "stub", "arguments": "{}"}],
            ),
            _final_json_dict("done"),
        ]
    )
    agent = Agent(specialist=_spec(), provider=provider, model="mock-1").with_tools(
        [stub]
    )

    iterations = []
    async for event in agent.analyze_stream("test"):
        if event.type == "iteration_complete":
            iterations.append(event.iteration)
    # Two rounds: one with the tool call, one with the final response
    assert iterations == [0, 1]
