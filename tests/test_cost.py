"""Tests for the cost-estimation module + AnalyzeResult.estimated_cost_usd."""

from __future__ import annotations

import json

import pytest

from personakit import Agent, Specialist
from personakit.cost import (
    estimate_cost,
    estimate_cost_from_usage,
    known_models,
    register_pricing,
)
from personakit.providers import LLMResponse, MockProvider


def test_known_model_returns_cost() -> None:
    cost = estimate_cost("gpt-4o-mini", input_tokens=1000, output_tokens=500)
    # 1000/1M * 0.15 + 500/1M * 0.60 = 0.00015 + 0.0003 = 0.00045
    assert cost is not None
    assert abs(cost - 0.00045) < 1e-9


def test_unknown_model_returns_none() -> None:
    assert estimate_cost("totally-fake-model-xyz", 100, 100) is None


def test_dated_model_id_falls_back_to_prefix_match() -> None:
    """OpenAI returns dated model ids like `gpt-4o-2024-08-06` — the
    prefix matcher should pick up the base `gpt-4o` pricing."""
    cost = estimate_cost("gpt-4o-2024-08-06", input_tokens=1000, output_tokens=0)
    assert cost is not None
    assert abs(cost - 0.0025) < 1e-9


def test_local_models_cost_zero() -> None:
    assert estimate_cost("ollama/llama3", 1_000_000, 1_000_000) == 0.0


def test_register_pricing_adds_or_overrides() -> None:
    register_pricing("test-custom-model", 1.0, 2.0, "Custom")
    assert "test-custom-model" in known_models()
    cost = estimate_cost("test-custom-model", 1_000_000, 500_000)
    assert cost is not None
    # 1.0 + 0.5 * 2.0 = 2.0
    assert abs(cost - 2.0) < 1e-9


def test_estimate_from_openai_shaped_usage() -> None:
    cost = estimate_cost_from_usage(
        "gpt-4o", {"prompt_tokens": 1000, "completion_tokens": 500}
    )
    assert cost is not None
    # 1000/1M * 2.50 + 500/1M * 10.00 = 0.0025 + 0.005 = 0.0075
    assert abs(cost - 0.0075) < 1e-9


def test_estimate_from_anthropic_shaped_usage() -> None:
    cost = estimate_cost_from_usage(
        "claude-sonnet-4-6", {"input_tokens": 1000, "output_tokens": 500}
    )
    assert cost is not None
    # 1000/1M * 3.00 + 500/1M * 15.00 = 0.003 + 0.0075 = 0.0105
    assert abs(cost - 0.0105) < 1e-9


def test_estimate_from_usage_with_missing_keys_returns_zero_cost() -> None:
    """Empty usage dict still resolves to zero cost (model is known)."""
    assert estimate_cost_from_usage("gpt-4o-mini", {}) == 0.0


def test_estimate_from_usage_with_unknown_model_returns_none() -> None:
    assert estimate_cost_from_usage("nope", {"input_tokens": 100}) is None


def _final_json_dict() -> dict:
    return {
        "summary": "x",
        "probes_answered": {},
        "red_flags_detected": [],
        "priorities_status": [],
        "recommendations": [],
        "citations_used": [],
    }


@pytest.mark.asyncio
async def test_analyze_result_estimated_cost_for_known_model() -> None:
    spec = Specialist(name="cheap", persona="Be brief.")
    provider = MockProvider(
        responses=LLMResponse(
            text=json.dumps(_final_json_dict()),
            model="gpt-4o-mini",
            usage={"prompt_tokens": 1000, "completion_tokens": 500},
        )
    )
    agent = Agent(specialist=spec, provider=provider, model="gpt-4o-mini")
    result = await agent.analyze("test")

    assert result.model == "gpt-4o-mini"
    cost = result.estimated_cost_usd
    assert cost is not None
    # 0.00015 + 0.0003 = 0.00045
    assert abs(cost - 0.00045) < 1e-9


@pytest.mark.asyncio
async def test_analyze_result_estimated_cost_for_unknown_model_is_none() -> None:
    spec = Specialist(name="unknown", persona="x")
    provider = MockProvider(
        responses=LLMResponse(
            text=json.dumps(_final_json_dict()),
            model="some-future-model",
            usage={"prompt_tokens": 100, "completion_tokens": 50},
        )
    )
    agent = Agent(specialist=spec, provider=provider, model="some-future-model")
    result = await agent.analyze("test")
    assert result.estimated_cost_usd is None
