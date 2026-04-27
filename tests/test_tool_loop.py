"""Tests for the multi-turn tool-calling loop in Agent.analyze().

The loop sequence under test:
    1. Provider returns response with `tool_calls` set (no JSON content yet)
    2. Agent invokes the tool locally, appends an assistant + tool message
    3. Provider returns final response with parsed JSON content (no tool_calls)
    4. Agent parses JSON, returns AnalyzeResult

Tests use MockProvider with a queue of LLMResponse-shaped dicts, so they
exercise the real loop logic without any network calls.
"""

from __future__ import annotations

import json

import pytest

from personakit import Agent, Specialist
from personakit.providers import LLMResponse, MockProvider
from personakit.providers.base import Message
from personakit.tools import tool


def _spec() -> Specialist:
    return Specialist(
        name="researcher",
        persona="You research a topic and produce a structured analysis.",
        themes=[{"name": "Findings"}, {"name": "Citations"}],
    )


def _final_json_dict(text: str = "Synthesised the tool result") -> dict:
    return {
        "summary": text,
        "probes_answered": {},
        "red_flags_detected": [],
        "priorities_status": [],
        "recommendations": [
            {"theme": "Findings", "text": text, "citations": ["fetched"]},
        ],
        "citations_used": ["fetched"],
    }


@pytest.mark.asyncio
async def test_loop_invokes_tool_then_returns_final_json() -> None:
    """The classic two-turn flow: tool_call → tool runs → final JSON."""
    invocations: list[dict] = []

    @tool
    def fetch_fact(topic: str) -> dict:
        """Return a fact about the topic."""
        invocations.append({"topic": topic})
        return {"fact": f"key fact about {topic}", "source": "https://example.com/{topic}"}

    # Turn 1: LLM emits a tool_call. Turn 2: LLM emits final JSON.
    provider = MockProvider(
        responses=[
            {
                "tool_calls": [
                    {
                        "id": "call_001",
                        "name": "fetch_fact",
                        "arguments": json.dumps({"topic": "personakit"}),
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
            _final_json_dict("personakit is a declarative agent builder"),
        ]
    )

    agent = Agent(specialist=_spec(), provider=provider, model="mock-1").with_tools(
        [fetch_fact]
    )
    result = await agent.analyze("What is personakit?")

    assert len(invocations) == 1
    assert invocations[0]["topic"] == "personakit"
    assert "personakit is a declarative agent builder" in result.summary
    # The provider should have been called twice (once for tool_calls, once for final)
    assert len(provider.calls) == 2

    # The second call should include the assistant tool-call message + tool result
    second_call = provider.calls[1]
    roles = [m.role for m in second_call]
    assert roles == ["system", "user", "assistant", "tool"]
    assistant_msg = second_call[2]
    assert assistant_msg.tool_calls
    assert assistant_msg.tool_calls[0]["id"] == "call_001"
    tool_msg = second_call[3]
    assert tool_msg.tool_call_id == "call_001"
    assert "key fact about personakit" in tool_msg.content


@pytest.mark.asyncio
async def test_loop_handles_unknown_tool_gracefully() -> None:
    """If the LLM hallucinates a tool name, the loop reports an error to it
    and keeps going — does not crash."""

    @tool
    def real_tool(query: str) -> dict:
        """A real tool the agent has registered."""
        return {"hits": [query]}

    provider = MockProvider(
        responses=[
            {
                "tool_calls": [
                    {
                        "id": "call_bad",
                        "name": "tool_that_does_not_exist",
                        "arguments": "{}",
                    }
                ]
            },
            _final_json_dict("recovered from unknown-tool error"),
        ]
    )

    agent = Agent(specialist=_spec(), provider=provider, model="mock-1").with_tools(
        [real_tool]
    )
    result = await agent.analyze("query")

    # Loop continued and reached the final response
    assert "recovered from unknown-tool error" in result.summary
    # The tool message in the second call should contain an error payload
    tool_msg = provider.calls[1][3]
    payload = json.loads(tool_msg.content)
    assert "error" in payload
    assert "tool_that_does_not_exist" in payload["error"]


@pytest.mark.asyncio
async def test_loop_handles_tool_exception_gracefully() -> None:
    """If the tool itself raises, we capture the exception and feed it back
    to the LLM rather than propagating to the caller."""

    @tool
    def flaky_tool(query: str) -> dict:
        """This tool raises."""
        raise RuntimeError("upstream timeout")

    provider = MockProvider(
        responses=[
            {
                "tool_calls": [
                    {
                        "id": "call_e",
                        "name": "flaky_tool",
                        "arguments": json.dumps({"query": "x"}),
                    }
                ]
            },
            _final_json_dict("recovered from tool exception"),
        ]
    )

    agent = Agent(specialist=_spec(), provider=provider, model="mock-1").with_tools(
        [flaky_tool]
    )
    result = await agent.analyze("test")
    assert "recovered from tool exception" in result.summary
    payload = json.loads(provider.calls[1][3].content)
    assert "error" in payload
    assert "upstream timeout" in payload["error"]


@pytest.mark.asyncio
async def test_loop_respects_max_tool_iterations() -> None:
    """If the LLM keeps requesting tools forever, the loop bounds the cost."""

    @tool
    def echo(text: str) -> dict:
        return {"echoed": text}

    # Always return tool_calls — the loop must terminate via max_tool_iterations
    # Use a handler so the same response repeats indefinitely.
    def handler(messages: list[Message], _kwargs: dict) -> dict:
        return {
            "tool_calls": [
                {"id": f"call_{len(messages)}", "name": "echo", "arguments": "{}"}
            ]
        }

    provider = MockProvider(handler=handler)

    agent = Agent(
        specialist=_spec(),
        provider=provider,
        model="mock-1",
        max_tool_iterations=3,
    ).with_tools([echo])

    # Should not raise — loop terminates cleanly at the cap
    await agent.analyze("test")

    # The provider should have been called exactly max_tool_iterations times
    assert len(provider.calls) == 3


@pytest.mark.asyncio
async def test_loop_accumulates_usage_across_iterations() -> None:
    """Token usage should be the sum across all loop iterations, not just the final call."""

    @tool
    def stub() -> dict:
        return {"ok": True}

    provider = MockProvider(
        responses=[
            LLMResponse(
                text="",
                model="mock-1",
                tool_calls=[{"id": "c1", "name": "stub", "arguments": "{}"}],
                usage={"input_tokens": 100, "output_tokens": 20},
            ),
            LLMResponse(
                text=json.dumps(_final_json_dict("done")),
                model="mock-1",
                usage={"input_tokens": 200, "output_tokens": 40},
            ),
        ]
    )

    agent = Agent(specialist=_spec(), provider=provider, model="mock-1").with_tools(
        [stub]
    )
    result = await agent.analyze("test")

    # Sum of both turns
    assert result.usage["input_tokens"] == 300
    assert result.usage["output_tokens"] == 60


@pytest.mark.asyncio
async def test_loop_no_tools_attached_is_unchanged() -> None:
    """When no tools are attached, behaviour is identical to v0.1.7 — single-shot."""
    provider = MockProvider(responses=_final_json_dict("simple"))
    agent = Agent(specialist=_spec(), provider=provider, model="mock-1")
    result = await agent.analyze("test")
    assert "simple" in result.summary
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_loop_supports_async_tool() -> None:
    """The loop must await async tool functions correctly."""

    @tool
    async def async_tool(name: str) -> dict:
        """An async tool."""
        return {"hello": name}

    provider = MockProvider(
        responses=[
            {
                "tool_calls": [
                    {
                        "id": "call_a",
                        "name": "async_tool",
                        "arguments": json.dumps({"name": "world"}),
                    }
                ]
            },
            _final_json_dict("async ran"),
        ]
    )

    agent = Agent(specialist=_spec(), provider=provider, model="mock-1").with_tools(
        [async_tool]
    )
    result = await agent.analyze("test")
    assert "async ran" in result.summary
    payload = json.loads(provider.calls[1][3].content)
    assert payload == {"hello": "world"}
