"""Conversational sessions — multi-turn agents with persistent history.

`Agent.analyze()` is stateless: each call is independent. Many use cases
(customer support, tutoring, clinical interviewing) need the agent to
remember the conversation. `ConversationalAgent` adds that memory layer
without forcing a database — history lives in the `Session` object, which
the caller can serialise and persist however they like (Redis, a row in
Postgres, a JSON file, in-memory dict).

Usage:

    from personakit import ConversationalAgent
    from personakit.examples import CUSTOMER_SUPPORT_TRIAGE

    agent = ConversationalAgent(specialist=CUSTOMER_SUPPORT_TRIAGE,
                                model="gpt-4o-mini")
    session = agent.start_session(user_id="alice")

    reply1 = await session.send("My order ORD-1002 is late.")
    reply2 = await session.send("It's been 3 weeks now.")  # remembers turn 1

    blob = session.serialize()      # caller persists this
    session2 = Session.deserialize(blob)  # caller restores it later
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from .agent import Agent
from .observability import Tracer
from .prompt_builder import PromptBuilder
from .providers.base import LLMProvider, Message
from .result import AnalyzeResult
from .specialist import Specialist


class SessionTurn(BaseModel):
    """One round-trip in a conversation: user message + agent response."""

    user_message: str
    assistant_text: str = ""
    result: AnalyzeResult | None = None


class Session:
    """Stateful container for a multi-turn conversation.

    A Session owns:
      - A reference to the underlying `Agent` (which holds the Specialist + provider)
      - A list of `SessionTurn` objects (the history)
      - An optional `user_id` for caller-side identification

    Sessions are intentionally not async-locked — if you call `send()` from
    multiple tasks concurrently on the same session, results are undefined.
    Use one session per active conversation.
    """

    def __init__(
        self,
        *,
        agent: ConversationalAgent,
        user_id: str | None = None,
        history: list[SessionTurn] | None = None,
        max_history_turns: int = 12,
    ) -> None:
        self.agent = agent
        self.user_id = user_id
        self.history: list[SessionTurn] = list(history) if history else []
        self.max_history_turns = max_history_turns

    async def send(
        self,
        user_message: str,
        *,
        selected_themes: list[str] | None = None,
        extra_context: str | None = None,
    ) -> AnalyzeResult:
        """Send the next user message; returns the typed `AnalyzeResult`."""
        turn = SessionTurn(user_message=user_message)
        result = await self.agent._analyze_with_history(
            user_message=user_message,
            history=self._recent_history(),
            selected_themes=selected_themes,
            extra_context=extra_context,
        )
        turn.assistant_text = result.summary or result.raw_output[:500]
        turn.result = result
        self.history.append(turn)
        return result

    async def chat(
        self,
        user_message: str,
        *,
        extra_context: str | None = None,
    ) -> str:
        """Lightweight chat: returns the assistant's free-form reply text only.

        Bypasses the structured-output pipeline. Useful for casual conversation
        where you don't need the typed AnalyzeResult.
        """
        reply = await self.agent._chat_with_history(
            user_message=user_message,
            history=self._recent_history(),
            extra_context=extra_context,
        )
        self.history.append(
            SessionTurn(user_message=user_message, assistant_text=reply)
        )
        return reply

    def reset(self) -> None:
        """Clear conversation history (does not affect the underlying Agent)."""
        self.history.clear()

    def _recent_history(self) -> list[SessionTurn]:
        """Return at most `max_history_turns` of the most recent turns.

        The system prompt is built fresh each call, so this is purely the
        user/assistant message log.
        """
        if self.max_history_turns <= 0:
            return []
        return self.history[-self.max_history_turns :]

    def serialize(self) -> str:
        """Return a JSON string representing the session for caller-side
        persistence. Pair with `Session.deserialize` to restore.

        The serialised form contains only the history and user_id. The Agent
        (with its Specialist, provider, model, etc.) is *not* serialised —
        the caller is expected to recreate it identically on the read side.
        """
        payload = {
            "user_id": self.user_id,
            "max_history_turns": self.max_history_turns,
            "history": [
                {
                    "user_message": t.user_message,
                    "assistant_text": t.assistant_text,
                    # AnalyzeResult is dropped on serialisation by default — it
                    # can be heavy and contains pydantic types. Callers who
                    # want full results stored should serialise turn.result
                    # themselves with t.result.model_dump().
                }
                for t in self.history
            ],
        }
        return json.dumps(payload)

    @classmethod
    def deserialize(cls, blob: str, *, agent: ConversationalAgent) -> Session:
        """Restore a session from its serialised form.

        The caller must supply a freshly-constructed `ConversationalAgent`
        that matches the original (same Specialist, model, etc.) — Sessions
        do not persist agent configuration.
        """
        data = json.loads(blob)
        history = [
            SessionTurn(
                user_message=t["user_message"],
                assistant_text=t.get("assistant_text", ""),
            )
            for t in data.get("history", [])
        ]
        return cls(
            agent=agent,
            user_id=data.get("user_id"),
            history=history,
            max_history_turns=data.get("max_history_turns", 12),
        )


class ConversationalAgent(Agent):
    """An `Agent` with multi-turn memory via `Session` objects.

    Inherits all of Agent's behaviour (tool loop, streaming, tracer,
    cost tracking) and adds:
      - `start_session(...)` — create a new Session
      - `send(session, message)` — convenience pass-through to `session.send`

    The Specialist is unchanged — it's still pure data. Memory lives in the
    Session, not the Specialist.
    """

    def __init__(
        self,
        *,
        specialist: Specialist,
        provider: LLMProvider | None = None,
        model: str | None = None,
        prompt_builder: PromptBuilder | None = None,
        temperature: float | None = 0.2,
        max_tokens: int | None = None,
        tools: list[Any] | None = None,
        max_tool_iterations: int = 6,
        tracer: Tracer | None = None,
        max_history_turns: int = 12,
    ) -> None:
        super().__init__(
            specialist=specialist,
            provider=provider,
            model=model,
            prompt_builder=prompt_builder,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            max_tool_iterations=max_tool_iterations,
            tracer=tracer,
        )
        self.max_history_turns = max_history_turns

    def start_session(
        self,
        *,
        user_id: str | None = None,
        history: list[SessionTurn] | None = None,
    ) -> Session:
        """Open a fresh Session bound to this agent."""
        return Session(
            agent=self,
            user_id=user_id,
            history=history,
            max_history_turns=self.max_history_turns,
        )

    async def _analyze_with_history(
        self,
        *,
        user_message: str,
        history: list[SessionTurn],
        selected_themes: list[str] | None = None,
        extra_context: str | None = None,
    ) -> AnalyzeResult:
        """Analyse `user_message` with prior turns prepended as conversation
        context. Used by `Session.send`.
        """
        if not history:
            return await self.analyze(
                user_message,
                selected_themes=selected_themes,
                extra_context=extra_context,
            )
        rendered_history = "\n\n".join(
            f"User (turn {i + 1}): {t.user_message}\nAssistant (turn {i + 1}): {t.assistant_text}"
            for i, t in enumerate(history)
        )
        merged_context = f"<conversation_history>\n{rendered_history}\n</conversation_history>"
        if extra_context:
            merged_context = f"{merged_context}\n\n{extra_context}"
        return await self.analyze(
            user_message,
            selected_themes=selected_themes,
            extra_context=merged_context,
        )

    async def _chat_with_history(
        self,
        *,
        user_message: str,
        history: list[SessionTurn],
        extra_context: str | None = None,
    ) -> str:
        """Free-form chat with history — bypasses structured-output parsing."""
        system_prompt = self.prompt_builder.build_system_prompt(self.specialist)
        messages: list[Message] = [Message(role="system", content=system_prompt)]
        for turn in history:
            messages.append(Message(role="user", content=turn.user_message))
            if turn.assistant_text:
                messages.append(Message(role="assistant", content=turn.assistant_text))
        if extra_context:
            messages.append(Message(role="system", content=f"Context:\n{extra_context}"))
        messages.append(Message(role="user", content=user_message))
        response = await self.provider.complete(
            messages,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.text


__all__ = [
    "ConversationalAgent",
    "Session",
    "SessionTurn",
]


# Make the Field import live (used by SessionTurn implicitly via pydantic)
_ = Field
