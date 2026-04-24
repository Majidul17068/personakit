"""The Agent runtime — glues a Specialist to an LLM provider.

The Agent is stateless by default. Give it a Specialist plus either an explicit
provider or a model string, and call `analyze()` or `chat()`.

`analyze()` is the power feature: it asks the LLM to fill in the structured
schema derived from the Specialist's probes / red_flags / themes / priorities,
runs deterministic red-flag matching on the input, merges the two sets of
triggered flags, and returns a typed `AnalyzeResult`.

`chat()` is the lightweight path for conversational agents that don't need the
full structured output.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from .errors import CitationMissingError, OutputParseError
from .matching import merge_post, pre_match
from .prompt_builder import PromptBuilder
from .providers.base import LLMProvider, Message
from .result import AnalyzeResult, Recommendation
from .specialist import Probe, Specialist


class Agent:
    """A Specialist + a provider = a runnable agent."""

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
    ) -> None:
        if provider is None:
            if model is None:
                raise ValueError("Agent requires either `provider` or `model`.")
            from .providers import provider_for_model

            provider = provider_for_model(model)
        self.specialist = specialist
        self.provider = provider
        self.model = model
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools = list(tools) if tools else []

    def with_tools(self, tools: list[Any]) -> Agent:
        """Return a new Agent with the given tools attached."""
        return Agent(
            specialist=self.specialist,
            provider=self.provider,
            model=self.model,
            prompt_builder=self.prompt_builder,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=(self.tools + list(tools)) if tools else self.tools,
        )

    async def analyze(
        self,
        input_text: str,
        *,
        selected_themes: list[str] | None = None,
        extra_context: str | None = None,
    ) -> AnalyzeResult:
        """Run the specialist's full analysis pipeline against `input_text`."""
        system_prompt = self.prompt_builder.build_system_prompt(
            self.specialist, selected_themes=selected_themes
        )
        schema = self.prompt_builder.build_output_schema(
            self.specialist, selected_themes=selected_themes
        )

        user_content = input_text
        if extra_context:
            user_content = f"{input_text}\n\n<context>\n{extra_context}\n</context>"

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content),
        ]

        pre = pre_match(self.specialist, input_text)

        response = await self.provider.complete(
            messages,
            model=self.model,
            response_schema=schema,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=_tool_payload(self.tools) if self.tools else None,
        )

        parsed = _parse_json(response.text)
        llm_hits = parsed.get("red_flags_detected", []) or []
        merged = merge_post(self.specialist, pre, llm_hits)

        probes_answered = parsed.get("probes_answered", {}) or {}
        probes_unanswered = _unanswered_probes(self.specialist.probes, probes_answered)

        recommendations = [
            Recommendation(
                theme=r.get("theme", ""),
                text=r.get("text", ""),
                citations=r.get("citations", []) or [],
                priority=r.get("priority"),
            )
            for r in parsed.get("recommendations", []) or []
        ]

        citations_used = parsed.get("citations_used", []) or []
        if self.specialist.citations_required and not citations_used:
            # Derive from recommendations if the LLM omitted the top-level list.
            for r in recommendations:
                citations_used.extend(r.citations)
            if not citations_used:
                raise CitationMissingError(
                    f"Specialist {self.specialist.name!r} requires citations "
                    "but the response produced none."
                )

        return AnalyzeResult(
            specialist_name=self.specialist.name,
            summary=parsed.get("summary", "") or "",
            probes_answered=probes_answered,
            probes_unanswered=probes_unanswered,
            red_flags_triggered=merged,
            recommendations=recommendations,
            priorities_status=parsed.get("priorities_status", []) or [],
            citations_used=citations_used,
            raw_output=response.text,
            usage=response.usage,
        )

    def analyze_sync(
        self,
        input_text: str,
        *,
        selected_themes: list[str] | None = None,
        extra_context: str | None = None,
    ) -> AnalyzeResult:
        """Synchronous wrapper around `analyze()`."""
        return asyncio.run(
            self.analyze(
                input_text,
                selected_themes=selected_themes,
                extra_context=extra_context,
            )
        )

    async def chat(self, message: str, *, history: list[Message] | None = None) -> str:
        """Lightweight conversational call — no structured output."""
        system_prompt = self.prompt_builder.build_system_prompt(self.specialist)
        messages: list[Message] = [Message(role="system", content=system_prompt)]
        if history:
            messages.extend(history)
        messages.append(Message(role="user", content=message))
        response = await self.provider.complete(
            messages,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=_tool_payload(self.tools) if self.tools else None,
        )
        return response.text

    def chat_sync(self, message: str, *, history: list[Message] | None = None) -> str:
        return asyncio.run(self.chat(message, history=history))


_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _parse_json(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    candidate = text.strip()
    match = _JSON_BLOCK_RE.search(candidate)
    if match:
        candidate = match.group(1)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as original:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError as exc:
                raise OutputParseError(
                    f"Could not parse JSON from LLM output: {exc}"
                ) from exc
        raise OutputParseError("LLM response did not contain JSON.") from original


def _unanswered_probes(
    probes: list[Probe], answered: dict[str, Any]
) -> list[Probe]:
    out: list[Probe] = []
    for p in probes:
        if p.key not in answered or answered[p.key] is None:
            out.append(p)
    return out


def _tool_payload(tools: list[Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for t in tools:
        if hasattr(t, "to_openai_schema"):
            payload.append(t.to_openai_schema())
        elif isinstance(t, dict):
            payload.append(t)
    return payload
