# personakit

**Declarative specialist agents for LLMs.** Encode a role's expertise —
persona, frameworks, probes, red flags, recommendation themes — as data.
Get a production agent that produces structured, cited, safety-aware output.

> Created by **[Majidul Islam](https://github.com/Majidul17068)**.

```bash
pip install personakit[openai]
```

---

## Why

LangChain is for wiring LLM calls. CrewAI is for orchestrating agent teams.
LangGraph is for branching control flow.

**personakit is for encoding specialist expertise declaratively.** A nurse, a
lawyer, an analyst, or a PM can author a specialist in Python or YAML and hand
it to engineers. No prompt engineering, no chain wiring.

The distinctive pieces:

| Concept | What it gives you |
|---|---|
| **Specialist** | A frozen dataclass — the entire agent definition |
| **Framework** | Body of knowledge + citation key, enforced in output |
| **Probe** | Diagnostic question; becomes a field in the structured response |
| **RedFlag** | Trigger → action → citation; matched deterministically AND semantically |
| **Theme** | User-selectable recommendation category |
| **Priority** | Always-on checks reported as met / unmet / unknown |
| **Tool (optional)** | `@tool` decorator; opt-in for external memory or API calls |

Core has just two runtime deps: **pydantic** and **httpx**.

---

## Quickstart

```python
import asyncio
from personakit import Agent, Specialist, Framework, Probe, RedFlag, Severity, Theme

specialist = Specialist(
    name="contract_reviewer",
    display_name="M&A Contract Reviewer",
    persona="You are a senior M&A attorney. Flag risks. Propose redlines.",
    frameworks=[Framework(name="UCC"), Framework(name="English contract law")],
    probes=[
        Probe(question="What's the governing jurisdiction?"),
        Probe(question="Is there an unlimited liability clause?",
              value_type="boolean", weight="high"),
    ],
    red_flags=[
        RedFlag(
            trigger="Unlimited liability",
            severity=Severity.CRITICAL,
            action="Negotiate a cap — 12 months' fees is market standard.",
            patterns=[r"unlimited liability", r"uncapped"],
        ),
    ],
    themes=[Theme(name="Liability & indemnities"), Theme(name="IP & licensing")],
    constraints=["Never give conclusive legal advice"],
)

agent = Agent(specialist=specialist, model="gpt-4o-mini")

async def main():
    result = await agent.analyze(
        "The service provider accepts unlimited liability for indirect damages."
    )
    print(result.pretty())
    for rf in result.red_flags_triggered:
        print(f"[{rf.severity.value.upper()}] {rf.trigger} -> {rf.action}")

asyncio.run(main())
```

## YAML authoring — hand off to domain experts

```yaml
name: falls_prevention_nurse
persona: You have 20+ years of UK care home experience...
frameworks: [NICE NG161, NICE CG176, Morse Fall Scale]
probes:
  - Did the resident strike their head?
  - Is the resident on anticoagulants?
red_flags:
  - trigger: Head contact in an anticoagulated resident
    severity: urgent
    action: GP/111 contact within 2 hours; CT head may be required.
    citation: "NICE CG176 §1.4.11"
    match: semantic
themes: [Neurological observation, GP contact, Medication review]
citations_required: true
```

```python
from personakit import Specialist, Agent

spec = Specialist.from_yaml("falls_nurse.yaml")
agent = Agent(specialist=spec, model="claude-sonnet-4-6")
```

## Red flags — the distinctive feature

Every RedFlag is a **trigger → severity → action → citation** contract:

```python
RedFlag(
    trigger="Loss of consciousness",
    severity=Severity.URGENT,
    action="Call 999. Document LOC duration.",
    citation="NICE CG176",
    match=MatchMode.BOTH,                # regex AND semantic
    patterns=[r"\bLOC\b", r"unconscious"],
)
```

Two-phase matching:

1. **Deterministic pre-match** (regex / keywords) — fast, offline, quotable.
2. **Semantic post-match** (LLM) — catches paraphrase and context.

Results are merged and de-duplicated. Deterministic evidence always wins.

## Structured output — derived from the Specialist

You never write a JSON schema by hand. The probes, red flags, and themes *are*
the schema:

```python
result = await agent.analyze(case_text)

result.summary                # narrative summary
result.probes_answered        # {probe_key: value_or_null}
result.probes_unanswered      # list[Probe] — feeds interview mode
result.red_flags_triggered    # list[TriggeredRedFlag] with evidence
result.recommendations        # themed list with citations
result.citations_used         # frameworks referenced
result.priorities_status      # per-priority met / unmet / unknown
result.has_urgent             # convenience flag
```

## Tools — opt-in, for external memory

Core is tool-free. When you want a tool, decorate a function and attach:

```python
from personakit.tools import tool

@tool
def lookup_patient(patient_id: str) -> dict:
    """Fetch a patient record from the EHR."""
    return ehr.get(patient_id)

agent_with_memory = agent.with_tools([lookup_patient])
```

Providers that support tool calling (OpenAI, Anthropic) see the schema
automatically. Providers that don't, ignore it.

## Registry — for apps with many specialists

```python
from personakit import SpecialistRegistry

registry = SpecialistRegistry.from_directory("personas/")
clinical = registry.by_domain("healthcare.clinical")
fall_nurse = registry.get("falls_prevention_nurse")
```

## Bundled examples

```python
from personakit.examples import (
    FALLS_PREVENTION_NURSE,    # clinical — rich
    CONTRACT_REVIEWER,         # legal
    MATH_TUTOR,                # education — minimal shape
)
```

## Providers

| Extra | Install | Default model |
|---|---|---|
| `personakit[openai]` | `openai>=1.0` | `gpt-4o-mini` |
| `personakit[anthropic]` | `anthropic>=0.20` | `claude-sonnet-4-6` |
| `personakit[yaml]` | `pyyaml>=6.0` | — |
| `personakit[all]` | all of the above | — |

The `MockProvider` is always available for offline testing:

```python
from personakit.testing import MockProvider
provider = MockProvider(responses={"summary": "...", ...})
```

## Testing helpers

```python
from personakit.testing import assert_triggered, assert_cited

result = await agent.analyze("Patient on warfarin, fell and struck head.")
assert_triggered(result, "head_contact_in_an_anticoagulated_resident")
assert_cited(result, "NICE CG176")
```

## Design principles

1. **Specialist is pure data.** No behaviour, no side effects, serializable.
2. **Schema is derived.** Probes, red flags, and themes *are* the output contract.
3. **Deterministic where possible, semantic where needed.** Red flags run both.
4. **Tools are opt-in.** Core has zero coupling to tool calling.
5. **Minimal dependencies.** `pydantic` + `httpx` for the core. Everything else is an extra.
6. **Domain-neutral.** Healthcare, legal, finance, education, support, product. One library.
7. **Provider-agnostic.** Same Specialist, any model.

## Status

Early alpha — API may evolve. See `CHANGELOG.md` for release notes.

## Author

**Majidul Islam** — [@Majidul17068](https://github.com/Majidul17068)

personakit is an independent open-source project. Contributions welcome.

## License

MIT © 2026 Majidul Islam.
