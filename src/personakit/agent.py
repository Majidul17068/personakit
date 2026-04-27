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
import time
from collections.abc import AsyncIterator
from typing import Any, cast

from .errors import CitationMissingError, OutputParseError
from .matching import merge_post, pre_match
from .observability import NullTracer, Tracer
from .prompt_builder import PromptBuilder
from .providers.base import LLMProvider, Message
from .result import AnalyzeResult, Recommendation, StreamEvent
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
        max_tool_iterations: int = 6,
        tracer: Tracer | None = None,
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
        self.max_tool_iterations = max_tool_iterations
        self.tracer: Tracer = tracer or NullTracer()

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
            max_tool_iterations=self.max_tool_iterations,
            tracer=self.tracer,
        )

    async def analyze(
        self,
        input_text: str,
        *,
        selected_themes: list[str] | None = None,
        extra_context: str | None = None,
    ) -> AnalyzeResult:
        """Run the specialist's full analysis pipeline against `input_text`.

        If the Agent has tools attached and the underlying LLM emits tool calls,
        the loop:

          1. Receives the LLM's `tool_calls` in its response
          2. Invokes each tool locally with the parsed arguments
          3. Appends the assistant message + tool result messages to the history
          4. Calls the LLM again with the augmented history

        The loop continues until the LLM stops emitting `tool_calls`, or until
        `max_tool_iterations` is reached. Token usage is accumulated across
        iterations.
        """
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

        tools_payload = _tool_payload(self.tools) if self.tools else None
        tools_by_name = {t.name: t for t in self.tools if hasattr(t, "name")}

        response: Any = None
        accumulated_usage: dict[str, Any] = {}

        with self.tracer.start_span(
            "personakit.analyze",
            specialist=self.specialist.name,
            model=self.model or getattr(self.provider, "default_model", ""),
            provider=self.provider.name,
            input_chars=len(input_text),
            tools_count=len(self.tools),
        ) as analyze_span:
            for _iteration in range(self.max_tool_iterations):
                with self.tracer.start_span(
                    "personakit.provider.complete",
                    iteration=_iteration,
                    provider=self.provider.name,
                    message_count=len(messages),
                ) as provider_span:
                    response = await self.provider.complete(
                        messages,
                        model=self.model,
                        response_schema=schema,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        tools=tools_payload,
                    )
                    for key, value in response.usage.items():
                        if isinstance(value, (int, float)):
                            accumulated_usage[key] = (
                                accumulated_usage.get(key, 0) + value
                            )
                            provider_span.set_attribute(f"usage.{key}", value)
                    provider_span.set_attribute(
                        "tool_calls_count", len(response.tool_calls)
                    )

                if not response.tool_calls:
                    break

                # Append the assistant turn that asked for tool(s)
                messages.append(
                    Message(
                        role="assistant",
                        content=response.text or "",
                        tool_calls=response.tool_calls,
                    )
                )

                # Execute each tool call and append a tool-result message per call
                for call in response.tool_calls:
                    tool_id = call.get("id") or ""
                    tool_name = call.get("name") or ""
                    args_raw = call.get("arguments")

                    if isinstance(args_raw, str):
                        try:
                            args = json.loads(args_raw) if args_raw else {}
                        except json.JSONDecodeError:
                            args = {}
                    elif isinstance(args_raw, dict):
                        args = args_raw
                    else:
                        args = {}

                    tool_obj = tools_by_name.get(tool_name)
                    with self.tracer.start_span(
                        "personakit.tool.invoke",
                        tool=tool_name,
                        known=tool_obj is not None,
                    ) as tool_span:
                        if tool_obj is None:
                            result_str = json.dumps(
                                {"error": f"Unknown tool requested by LLM: {tool_name!r}"}
                            )
                            tool_span.set_attribute("error", "unknown_tool")
                        else:
                            try:
                                invocation = await tool_obj.invoke(**args)
                                result_str = json.dumps(invocation, default=str)
                            except Exception as exc:
                                result_str = json.dumps(
                                    {"error": f"Tool {tool_name!r} raised: {exc!r}"}
                                )
                                tool_span.set_attribute("error", repr(exc))

                    messages.append(
                        Message(role="tool", content=result_str, tool_call_id=tool_id)
                    )
            else:
                # for-else: ran max iterations without break — the LLM kept calling tools.
                # response is still set to the most recent provider response.
                pass

            for key, value in accumulated_usage.items():
                analyze_span.set_attribute(f"usage.{key}", value)

        parsed = _parse_json(response.text) if response and response.text else {}
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
            raw_output=response.text if response else "",
            usage=accumulated_usage,
            model=getattr(response, "model", "") if response else (self.model or ""),
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

    async def analyze_stream(
        self,
        input_text: str,
        *,
        selected_themes: list[str] | None = None,
        extra_context: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Streaming variant of `analyze()`.

        Yields `StreamEvent` objects as the analysis progresses:

          - `red_flag_pre_match` — fired immediately for any deterministic
            regex/keyword matches against the input. Available before the
            LLM has even started.
          - `text_delta` — text fragments as the LLM streams its response.
            Concatenate these to display a live typing animation.
          - `tool_call` — the LLM requested a tool. Carries `tool_name` and
            parsed `tool_arguments`.
          - `tool_result` — the tool finished. Carries the result and
            `duration_ms`.
          - `iteration_complete` — one tool-loop iteration finished.
          - `complete` — the analysis finished. Carries the full
            `AnalyzeResult` in `event.result`.
          - `error` — something failed during streaming.

        Usage:

            async for event in agent.analyze_stream(case_text):
                if event.type == "text_delta":
                    print(event.text, end="", flush=True)
                elif event.type == "red_flag_pre_match":
                    print(f"\\n[pre-match] {event.red_flag.trigger}")
                elif event.type == "complete":
                    final = event.result  # full AnalyzeResult
        """
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

        # Emit pre-match red flags up front — they're deterministic, no LLM needed.
        pre = pre_match(self.specialist, input_text)
        for triggered in pre:
            yield StreamEvent(type="red_flag_pre_match", red_flag=triggered)

        tools_payload = _tool_payload(self.tools) if self.tools else None
        tools_by_name = {t.name: t for t in self.tools if hasattr(t, "name")}

        accumulated_usage: dict[str, Any] = {}
        accumulated_text = ""
        final_tool_calls: list[dict[str, Any]] = []
        final_finish_reason: str | None = None
        model_seen: str = self.model or ""

        for iteration in range(self.max_tool_iterations):
            iteration_text = ""
            iteration_tool_calls: list[dict[str, Any]] = []
            iteration_finish_reason: str | None = None

            try:
                stream_iter = self.provider.stream(
                    messages,
                    model=self.model,
                    response_schema=schema,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    tools=tools_payload,
                )
                async for chunk in stream_iter:
                    if chunk.model:
                        model_seen = chunk.model
                    if chunk.text_delta:
                        iteration_text += chunk.text_delta
                        yield StreamEvent(type="text_delta", text=chunk.text_delta)
                    if chunk.is_final:
                        iteration_tool_calls = list(chunk.tool_calls)
                        iteration_finish_reason = chunk.finish_reason
                        for key, value in chunk.usage.items():
                            if isinstance(value, (int, float)):
                                accumulated_usage[key] = (
                                    accumulated_usage.get(key, 0) + value
                                )
            except Exception as exc:
                yield StreamEvent(type="error", error=f"Stream failed: {exc}")
                return

            accumulated_text = iteration_text
            final_tool_calls = iteration_tool_calls
            final_finish_reason = iteration_finish_reason

            if not iteration_tool_calls:
                yield StreamEvent(
                    type="iteration_complete",
                    iteration=iteration,
                )
                break

            messages.append(
                Message(
                    role="assistant",
                    content=iteration_text,
                    tool_calls=iteration_tool_calls,
                )
            )

            for call in iteration_tool_calls:
                tool_id = call.get("id") or ""
                tool_name = call.get("name") or ""
                args_raw = call.get("arguments")

                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw) if args_raw else {}
                    except json.JSONDecodeError:
                        args = {}
                elif isinstance(args_raw, dict):
                    args = args_raw
                else:
                    args = {}

                yield StreamEvent(
                    type="tool_call",
                    tool_name=tool_name,
                    tool_arguments=args,
                )

                tool_obj = tools_by_name.get(tool_name)
                started = time.perf_counter()
                if tool_obj is None:
                    invocation: Any = {"error": f"Unknown tool: {tool_name!r}"}
                    result_str = json.dumps(invocation)
                else:
                    try:
                        invocation = await tool_obj.invoke(**args)
                        result_str = json.dumps(invocation, default=str)
                    except Exception as exc:
                        invocation = {"error": f"Tool {tool_name!r} raised: {exc!r}"}
                        result_str = json.dumps(invocation)
                duration_ms = (time.perf_counter() - started) * 1000.0

                yield StreamEvent(
                    type="tool_result",
                    tool_name=tool_name,
                    tool_result=invocation,
                    duration_ms=duration_ms,
                )

                messages.append(
                    Message(role="tool", content=result_str, tool_call_id=tool_id)
                )

            yield StreamEvent(type="iteration_complete", iteration=iteration)

        # Build the final AnalyzeResult from the accumulated stream output.
        parsed = _parse_json(accumulated_text) if accumulated_text else {}
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
            for r in recommendations:
                citations_used.extend(r.citations)
            if not citations_used:
                yield StreamEvent(
                    type="error",
                    error=(
                        f"Specialist {self.specialist.name!r} requires citations "
                        "but the response produced none."
                    ),
                )
                return

        # Note: final_tool_calls / final_finish_reason are tracked above but not
        # surfaced in AnalyzeResult; they're available via the raw_output.
        del final_tool_calls
        del final_finish_reason

        result = AnalyzeResult(
            specialist_name=self.specialist.name,
            summary=parsed.get("summary", "") or "",
            probes_answered=probes_answered,
            probes_unanswered=probes_unanswered,
            red_flags_triggered=merged,
            recommendations=recommendations,
            priorities_status=parsed.get("priorities_status", []) or [],
            citations_used=citations_used,
            raw_output=accumulated_text,
            usage=accumulated_usage,
            model=model_seen,
        )
        yield StreamEvent(type="complete", result=result)

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
        return cast(dict[str, Any], json.loads(candidate))
    except json.JSONDecodeError as original:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end > start:
            try:
                return cast(dict[str, Any], json.loads(candidate[start : end + 1]))
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
