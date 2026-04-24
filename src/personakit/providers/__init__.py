"""Provider adapters.

Import the provider you need; optional SDK dependencies are loaded lazily.
"""

from __future__ import annotations

from .anthropic import AnthropicProvider
from .base import LLMProvider, LLMResponse, Message
from .mock import MockProvider
from .openai import OpenAIProvider

__all__ = [
    "AnthropicProvider",
    "LLMProvider",
    "LLMResponse",
    "Message",
    "MockProvider",
    "OpenAIProvider",
]


def provider_for_model(model: str) -> LLMProvider:
    """Best-effort provider inference from a model name.

    Used when the user passes `Agent(specialist=..., model="gpt-4o")` without
    an explicit provider. Falls through to OpenAI for unknown models because
    most OpenAI-compatible endpoints use OpenAI-style naming.
    """
    lower = model.lower()
    if lower.startswith(("claude", "anthropic/")):
        return AnthropicProvider(default_model=model)
    return OpenAIProvider(default_model=model)
