"""Token cost estimation for common LLM providers.

`estimate_cost(model, input_tokens, output_tokens)` returns an estimated cost
in USD, or `None` if the model isn't in our pricing table. Pricing is in
**USD per 1M tokens** and reflects publicly listed rates as of early 2026 —
update as needed via `register_pricing(...)` for new models or custom rates.

The pricing table is intentionally kept small and conservative — we cover the
most-used models from each major provider. For local models (Ollama, vLLM,
LM Studio, etc.), cost is `0.0` since they run on the user's hardware.
"""

from __future__ import annotations

from typing import NamedTuple


class ModelPricing(NamedTuple):
    """Pricing for one model. Values are USD per 1,000,000 tokens."""

    input_per_1m: float
    output_per_1m: float
    name: str = ""


# Pricing snapshot — early 2026 public rates. PRs welcome.
_PRICING: dict[str, ModelPricing] = {
    # OpenAI — official rates
    "gpt-4o":            ModelPricing(2.50,  10.00, "OpenAI GPT-4o"),
    "gpt-4o-mini":       ModelPricing(0.15,  0.60,  "OpenAI GPT-4o mini"),
    "gpt-4-turbo":       ModelPricing(10.00, 30.00, "OpenAI GPT-4 Turbo"),
    "gpt-4":             ModelPricing(30.00, 60.00, "OpenAI GPT-4"),
    "gpt-3.5-turbo":     ModelPricing(0.50,  1.50,  "OpenAI GPT-3.5 Turbo"),
    "o1":                ModelPricing(15.00, 60.00, "OpenAI o1"),
    "o1-mini":           ModelPricing(3.00,  12.00, "OpenAI o1-mini"),
    "o3-mini":           ModelPricing(1.10,  4.40,  "OpenAI o3-mini"),

    # Anthropic
    "claude-opus-4-7":     ModelPricing(15.00, 75.00, "Claude Opus 4.7"),
    "claude-sonnet-4-6":   ModelPricing(3.00,  15.00, "Claude Sonnet 4.6"),
    "claude-haiku-4-5":    ModelPricing(0.80,  4.00,  "Claude Haiku 4.5"),
    "claude-3-5-sonnet":   ModelPricing(3.00,  15.00, "Claude 3.5 Sonnet"),
    "claude-3-5-haiku":    ModelPricing(0.80,  4.00,  "Claude 3.5 Haiku"),
    "claude-3-opus":       ModelPricing(15.00, 75.00, "Claude 3 Opus"),

    # Google Gemini
    "gemini-2.0-flash":      ModelPricing(0.10, 0.40, "Gemini 2.0 Flash"),
    "gemini-1.5-pro":        ModelPricing(1.25, 5.00, "Gemini 1.5 Pro"),
    "gemini-1.5-flash":      ModelPricing(0.075, 0.30, "Gemini 1.5 Flash"),

    # Groq (cheap fast inference)
    "groq/llama-3.1-70b":              ModelPricing(0.59, 0.79, "Groq Llama 3.1 70B"),
    "groq/llama-3.1-8b-instant":       ModelPricing(0.05, 0.08, "Groq Llama 3.1 8B"),
    "groq/mixtral-8x7b-32768":         ModelPricing(0.24, 0.24, "Groq Mixtral 8x7B"),

    # DeepSeek
    "deepseek-chat":   ModelPricing(0.27, 1.10, "DeepSeek Chat"),
    "deepseek-coder":  ModelPricing(0.27, 1.10, "DeepSeek Coder"),

    # Mistral (via official API)
    "mistral-large":   ModelPricing(2.00, 6.00, "Mistral Large"),
    "mistral-small":   ModelPricing(0.20, 0.60, "Mistral Small"),

    # Local models — free
    "ollama/llama3":           ModelPricing(0.0, 0.0, "Ollama Llama 3 (local)"),
    "ollama/llama3.1":         ModelPricing(0.0, 0.0, "Ollama Llama 3.1 (local)"),
    "ollama/mistral":          ModelPricing(0.0, 0.0, "Ollama Mistral (local)"),
    "ollama/qwen2.5":          ModelPricing(0.0, 0.0, "Ollama Qwen 2.5 (local)"),

    # Mock provider — used in tests
    "mock-1":      ModelPricing(0.0, 0.0, "personakit MockProvider"),
    "mock-model":  ModelPricing(0.0, 0.0, "personakit MockProvider"),
}


def register_pricing(model: str, input_per_1m: float, output_per_1m: float, name: str = "") -> None:
    """Add or override pricing for a model. Useful for self-hosted or custom rates.

    Args:
        model: model identifier as it appears in `LLMResponse.model`.
        input_per_1m: USD per 1,000,000 input (prompt) tokens.
        output_per_1m: USD per 1,000,000 output (completion) tokens.
        name: optional human-readable name.
    """
    _PRICING[model] = ModelPricing(input_per_1m, output_per_1m, name or model)


def estimate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> float | None:
    """Estimate USD cost for a given (model, token counts) pair.

    Returns the dollar cost as a float. Returns `None` if the model isn't in
    the pricing table — surface that to the user so they know the cost is
    unknown rather than zero.

    Matching is exact first, then by case-insensitive prefix (e.g. an actual
    model id like `gpt-4o-2024-08-06` will match the entry for `gpt-4o`).
    """
    pricing = _PRICING.get(model)
    if pricing is None:
        # Fall back to prefix match — providers sometimes return dated ids.
        lower = model.lower()
        for key, pr in _PRICING.items():
            if lower.startswith(key.lower()):
                pricing = pr
                break
    if pricing is None:
        return None
    return (
        (input_tokens / 1_000_000.0) * pricing.input_per_1m
        + (output_tokens / 1_000_000.0) * pricing.output_per_1m
    )


def estimate_cost_from_usage(
    model: str,
    usage: dict[str, int | float],
) -> float | None:
    """Convenience wrapper — pull token counts from an LLMResponse.usage dict.

    Recognises both OpenAI-shaped (`prompt_tokens`/`completion_tokens`) and
    Anthropic-shaped (`input_tokens`/`output_tokens`) usage dicts.
    """
    input_tokens = int(
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or 0
    )
    output_tokens = int(
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or 0
    )
    return estimate_cost(model, input_tokens, output_tokens)


def known_models() -> list[str]:
    """Return the list of model identifiers we have pricing for."""
    return sorted(_PRICING.keys())


__all__ = [
    "ModelPricing",
    "estimate_cost",
    "estimate_cost_from_usage",
    "known_models",
    "register_pricing",
]
