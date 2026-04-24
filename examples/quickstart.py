"""Three-minute quickstart.

Run:
    pip install -e '.[openai,yaml]'
    export OPENAI_API_KEY=sk-...
    python examples/quickstart.py

If you just want to see the flow without spending tokens, comment out the
OpenAI block at the bottom and run only the MockProvider demo.
"""

from __future__ import annotations

import asyncio
import json

from personakit import Agent, Specialist
from personakit.examples import FALLS_PREVENTION_NURSE
from personakit.testing import MockProvider


CASE = (
    "Resident found on the floor at 03:15 in the bathroom. She's on apixaban "
    "5mg BD, currently conscious, oriented, but mildly confused. She denies "
    "striking her head; no witness was present."
)


async def demo_mock() -> None:
    # A canned LLM response, so you can run offline.
    canned = {
        "summary": "Unwitnessed fall in an anticoagulated resident with new mild confusion. Head injury cannot be excluded.",
        "probes_answered": {
            "witnessed": "unwitnessed",
            "head_strike": None,
            "anticoagulated": True,
            "weight_bearing": None,
            "new_neuro_symptoms": True,
            "pre_fall_activity": "toileting",
            "time_and_lighting": "03:15 — low lighting likely",
            "recent_med_changes": None,
            "recurrent": None,
        },
        "red_flags_detected": [
            {
                "id": "head_contact_in_an_anticoagulated_resident",
                "evidence": "on apixaban 5mg BD; unwitnessed fall; head strike cannot be excluded",
            },
            {
                "id": "unwitnessed_fall_with_unknown_time_on_floor",
                "evidence": "Resident was found on the floor without a witness",
            },
        ],
        "priorities_status": [
            {"priority": "Rule out head injury — assess GCS, pupils, neuro baseline", "status": "unmet"},
        ],
        "recommendations": [
            {"theme": "Neurological observation",
             "text": "Commence neuro obs every 15 minutes for the first 2 hours, then hourly for 4 hours, then 4-hourly for 24 hours.",
             "citations": ["NICE CG176"]},
            {"theme": "GP / 111 contact",
             "text": "Contact GP or 111 within 2 hours given anticoagulation and unwitnessed fall.",
             "citations": ["NICE CG176 §1.4.11"]},
        ],
        "citations_used": ["NICE CG176", "NICE CG176 §1.4.11"],
    }
    provider = MockProvider(responses=canned, model="mock-clinical")
    agent = Agent(specialist=FALLS_PREVENTION_NURSE, provider=provider)
    result = await agent.analyze(CASE)
    print(result.pretty())
    print()
    print("has_urgent:", result.has_urgent)
    print()
    print("Unanswered probes:", [p.key for p in result.probes_unanswered])


async def demo_yaml() -> None:
    spec = Specialist.from_yaml("examples/personas/falls_nurse.yaml")
    print(f"Loaded {spec.effective_display_name}")
    print(f"  frameworks: {len(spec.frameworks)}")
    print(f"  probes: {len(spec.probes)}")
    print(f"  red flags: {len(spec.red_flags)}")


async def demo_real() -> None:
    # Uncomment to try against a real LLM.
    # from personakit.providers import OpenAIProvider
    # agent = Agent(specialist=FALLS_PREVENTION_NURSE,
    #               provider=OpenAIProvider(default_model="gpt-4o-mini"))
    # result = await agent.analyze(CASE)
    # print(result.pretty())
    return


async def main() -> None:
    print("--- demo_mock ---")
    await demo_mock()
    print()
    print("--- demo_yaml ---")
    await demo_yaml()


if __name__ == "__main__":
    asyncio.run(main())
