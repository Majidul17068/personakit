"""Tests for LiteLLMProvider — uses a mock client so litellm itself isn't required."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from personakit.errors import MissingDependencyError, ProviderError
from personakit.providers import LiteLLMProvider
from personakit.providers.base import Message


class _MockLiteLLM:
    """Stands in for `litellm` module. Exposes the single method we use."""

    def __init__(self, response: Any | None = None, raises: Exception | None = None) -> None:
        self.response = response
        self.raises = raises
        self.last_payload: dict[str, Any] | None = None

    async def acompletion(self, **kwargs: Any) -> Any:
        self.last_payload = kwargs
        if self.raises is not None:
            raise self.raises
        return self.response


def _openai_shaped(
    text: str,
    model: str = "mock-model",
    tool_calls: list[dict[str, Any]] | None = None,
) -> Any:
    """Build a LiteLLM response object (OpenAI-shaped — same shape litellm returns)."""
    message = SimpleNamespace(content=text, tool_calls=None)
    if tool_calls is not None:
        mock_calls = []
        for tc in tool_calls:
            mock_calls.append(
                SimpleNamespace(
                    id=tc.get("id"),
                    function=SimpleNamespace(
                        name=tc.get("name"),
                        arguments=tc.get("arguments"),
                    ),
                )
            )
        message.tool_calls = mock_calls
    choice = SimpleNamespace(message=message, finish_reason="stop")
    usage = SimpleNamespace(prompt_tokens=12, completion_tokens=34, total_tokens=46)
    return SimpleNamespace(choices=[choice], model=model, usage=usage)


@pytest.mark.asyncio
async def test_basic_completion_round_trip() -> None:
    mock = _MockLiteLLM(response=_openai_shaped("hello from any provider"))
    provider = LiteLLMProvider(default_model="bedrock/anthropic.claude-v2", client=mock)

    response = await provider.complete(
        [Message(role="system", content="sys"), Message(role="user", content="hi")],
        temperature=0.1,
        max_tokens=256,
    )

    assert response.text == "hello from any provider"
    assert response.model == "mock-model"
    assert response.finish_reason == "stop"
    assert response.usage["total_tokens"] == 46
    # Verify the payload LiteLLM actually received
    assert mock.last_payload is not None
    assert mock.last_payload["model"] == "bedrock/anthropic.claude-v2"
    assert mock.last_payload["temperature"] == 0.1
    assert mock.last_payload["max_tokens"] == 256
    assert mock.last_payload["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]


@pytest.mark.asyncio
async def test_explicit_model_overrides_default() -> None:
    mock = _MockLiteLLM(response=_openai_shaped("ok", model="groq/mixtral-8x7b-32768"))
    provider = LiteLLMProvider(default_model="gpt-4o-mini", client=mock)

    await provider.complete(
        [Message(role="user", content="hi")],
        model="groq/mixtral-8x7b-32768",
    )

    assert mock.last_payload is not None
    assert mock.last_payload["model"] == "groq/mixtral-8x7b-32768"


@pytest.mark.asyncio
async def test_response_schema_becomes_json_schema_response_format() -> None:
    mock = _MockLiteLLM(response=_openai_shaped("{}"))
    provider = LiteLLMProvider(client=mock)

    await provider.complete(
        [Message(role="user", content="go")],
        response_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
    )

    assert mock.last_payload is not None
    rf = mock.last_payload["response_format"]
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["name"] == "personakit_output"
    assert rf["json_schema"]["schema"]["type"] == "object"


@pytest.mark.asyncio
async def test_api_key_and_base_forwarded() -> None:
    mock = _MockLiteLLM(response=_openai_shaped("x"))
    provider = LiteLLMProvider(
        default_model="openai/gpt-4o-mini",
        api_key="sk-test",
        api_base="https://proxy.internal:4000",
        client=mock,
    )
    await provider.complete([Message(role="user", content="hi")])

    assert mock.last_payload is not None
    assert mock.last_payload["api_key"] == "sk-test"
    assert mock.last_payload["api_base"] == "https://proxy.internal:4000"


@pytest.mark.asyncio
async def test_extra_defaults_flow_through() -> None:
    mock = _MockLiteLLM(response=_openai_shaped("x"))
    provider = LiteLLMProvider(
        default_model="azure/deploy-1",
        api_version="2024-06-01",
        azure_deployment="deploy-1",
        client=mock,
    )
    await provider.complete([Message(role="user", content="hi")])

    assert mock.last_payload is not None
    assert mock.last_payload["api_version"] == "2024-06-01"
    assert mock.last_payload["azure_deployment"] == "deploy-1"


@pytest.mark.asyncio
async def test_tool_calls_extracted() -> None:
    mock = _MockLiteLLM(
        response=_openai_shaped(
            "",
            tool_calls=[
                {"id": "call_1", "name": "lookup_order", "arguments": '{"order_id": "ORD-1"}'}
            ],
        )
    )
    provider = LiteLLMProvider(client=mock)

    response = await provider.complete([Message(role="user", content="hi")])

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["id"] == "call_1"
    assert response.tool_calls[0]["name"] == "lookup_order"


@pytest.mark.asyncio
async def test_upstream_exception_becomes_provider_error() -> None:
    mock = _MockLiteLLM(raises=RuntimeError("upstream timeout"))
    provider = LiteLLMProvider(client=mock)

    with pytest.raises(ProviderError) as exc_info:
        await provider.complete([Message(role="user", content="hi")])
    assert "upstream timeout" in str(exc_info.value)


def test_missing_dependency_raises_when_litellm_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirm the helpful error message fires if the user forgets the extra."""
    import builtins

    original_import = builtins.__import__

    def _blocked_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "litellm":
            raise ImportError("mocked missing litellm")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    with pytest.raises(MissingDependencyError) as exc_info:
        LiteLLMProvider(default_model="gpt-4o-mini")
    assert "personakit[litellm]" in str(exc_info.value)
