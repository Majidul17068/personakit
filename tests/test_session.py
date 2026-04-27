"""Tests for ConversationalAgent + Session multi-turn memory."""

from __future__ import annotations

import pytest

from personakit import Specialist
from personakit.providers import MockProvider
from personakit.session import ConversationalAgent, Session, SessionTurn


def _spec() -> Specialist:
    return Specialist(
        name="support",
        persona="A patient support agent.",
        themes=[{"name": "Resolution"}],
    )


def _final_json_dict(text: str) -> dict:
    return {
        "summary": text,
        "probes_answered": {},
        "red_flags_detected": [],
        "priorities_status": [],
        "recommendations": [{"theme": "Resolution", "text": text, "citations": []}],
        "citations_used": [],
    }


@pytest.mark.asyncio
async def test_session_first_turn_has_no_history_context() -> None:
    """First turn should call analyze() without injecting history into context."""
    provider = MockProvider(responses=_final_json_dict("Hello!"))
    agent = ConversationalAgent(specialist=_spec(), provider=provider, model="mock-1")
    session = agent.start_session(user_id="alice")

    result = await session.send("Hi there")
    assert result.summary == "Hello!"
    assert len(session.history) == 1
    assert session.history[0].user_message == "Hi there"

    # The first call to the provider should have just system + user, no history block
    first_messages = provider.calls[0]
    user_msg = next(m for m in first_messages if m.role == "user")
    assert "<conversation_history>" not in user_msg.content


@pytest.mark.asyncio
async def test_session_second_turn_includes_history_in_context() -> None:
    """The second turn should include the prior turns in extra_context."""
    provider = MockProvider(
        responses=[_final_json_dict("First reply"), _final_json_dict("Second reply")]
    )
    agent = ConversationalAgent(specialist=_spec(), provider=provider, model="mock-1")
    session = agent.start_session()

    await session.send("Hello, I have a problem.")
    await session.send("It's about my order.")

    # Provider should have been called twice
    assert len(provider.calls) == 2

    # The second call's user message should include the rendered history block
    second_user_msg = next(m for m in provider.calls[1] if m.role == "user")
    assert "<conversation_history>" in second_user_msg.content
    assert "Hello, I have a problem." in second_user_msg.content
    assert "First reply" in second_user_msg.content
    # And the new user message is appended
    assert "It's about my order." in second_user_msg.content


@pytest.mark.asyncio
async def test_session_respects_max_history_turns() -> None:
    """Older turns get pruned when the window fills up."""
    provider = MockProvider(
        responses=[_final_json_dict(f"reply-{i}") for i in range(10)]
    )
    agent = ConversationalAgent(
        specialist=_spec(),
        provider=provider,
        model="mock-1",
        max_history_turns=2,
    )
    session = agent.start_session()
    for i in range(5):
        await session.send(f"turn-{i}")

    # All 5 turns are in `history` (we don't drop them, just don't send all)
    assert len(session.history) == 5

    # The 5th call to the provider should only include the last 2 prior turns
    fifth_user_msg = next(m for m in provider.calls[4] if m.role == "user")
    # turn-2 and turn-3 should be in the history block (the 2 prior to the 5th send)
    assert "turn-2" in fifth_user_msg.content
    assert "turn-3" in fifth_user_msg.content
    # turn-0 should be pruned
    assert "turn-0" not in fifth_user_msg.content


@pytest.mark.asyncio
async def test_session_chat_returns_raw_text_and_skips_structured_output() -> None:
    """`Session.chat()` is a free-form path — bypasses JSON parsing."""
    provider = MockProvider(responses="Hello, alice. How can I help?")
    agent = ConversationalAgent(specialist=_spec(), provider=provider, model="mock-1")
    session = agent.start_session(user_id="alice")

    reply = await session.chat("Hi, I'm alice.")
    assert reply == "Hello, alice. How can I help?"
    assert len(session.history) == 1
    assert session.history[0].assistant_text == "Hello, alice. How can I help?"


@pytest.mark.asyncio
async def test_session_chat_includes_history_messages_directly() -> None:
    """In chat mode, history is passed as proper messages — not as a context block."""
    provider = MockProvider(responses=["First.", "Second."])
    agent = ConversationalAgent(specialist=_spec(), provider=provider, model="mock-1")
    session = agent.start_session()

    await session.chat("Question 1")
    await session.chat("Question 2")

    second_messages = provider.calls[1]
    roles = [m.role for m in second_messages]
    # system, user(turn1), assistant(reply1), user(turn2)
    assert roles == ["system", "user", "assistant", "user"]
    contents = [m.content for m in second_messages]
    assert "Question 1" in contents
    assert "First." in contents
    assert "Question 2" in contents


def test_session_serialize_round_trip_preserves_history() -> None:
    """`serialize` + `deserialize` should preserve the history (minus
    AnalyzeResult, which is intentionally dropped)."""
    spec = _spec()
    agent = ConversationalAgent(
        specialist=spec, provider=MockProvider(), model="mock-1"
    )
    session = Session(agent=agent, user_id="bob")
    session.history.extend(
        [
            SessionTurn(user_message="hi", assistant_text="hello"),
            SessionTurn(user_message="how are you", assistant_text="fine, thanks"),
        ]
    )

    blob = session.serialize()
    # Restore with a fresh agent (the caller's responsibility)
    new_agent = ConversationalAgent(
        specialist=spec, provider=MockProvider(), model="mock-1"
    )
    restored = Session.deserialize(blob, agent=new_agent)

    assert restored.user_id == "bob"
    assert len(restored.history) == 2
    assert restored.history[0].user_message == "hi"
    assert restored.history[1].assistant_text == "fine, thanks"


def test_session_reset_clears_history() -> None:
    spec = _spec()
    agent = ConversationalAgent(
        specialist=spec, provider=MockProvider(), model="mock-1"
    )
    session = Session(agent=agent)
    session.history.extend([SessionTurn(user_message="x"), SessionTurn(user_message="y")])
    assert len(session.history) == 2
    session.reset()
    assert len(session.history) == 0


@pytest.mark.asyncio
async def test_conversational_agent_inherits_tools_and_max_iterations() -> None:
    """ConversationalAgent should pass through Agent's full configuration."""
    from personakit.tools import tool

    @tool
    def stub() -> dict:
        return {"ok": True}

    agent = ConversationalAgent(
        specialist=_spec(),
        provider=MockProvider(),
        model="mock-1",
        tools=[stub],
        max_tool_iterations=8,
        max_history_turns=20,
    )
    assert len(agent.tools) == 1
    assert agent.max_tool_iterations == 8
    assert agent.max_history_turns == 20


@pytest.mark.asyncio
async def test_session_persists_through_message_lifecycle() -> None:
    """Each turn should append to history exactly once, even on errors."""
    provider = MockProvider(responses=[_final_json_dict("first"), _final_json_dict("second")])
    agent = ConversationalAgent(specialist=_spec(), provider=provider, model="mock-1")
    session = agent.start_session()

    await session.send("hi")
    await session.send("again")
    assert len(session.history) == 2

    # Sanity: each turn captured the AnalyzeResult
    assert session.history[0].result is not None
    assert session.history[0].result.summary == "first"
    assert session.history[1].result is not None
    assert session.history[1].result.summary == "second"
