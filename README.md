# personakit

**The declarative agent builder.** Encode any specialist's expertise — persona,
frameworks, probes, red flags, recommendation themes — as data. Get a
production-grade LLM agent with structured output, citations, and safety
triggers. Works for **any domain**: engineering, fintech, customer support,
product, legal, clinical, education — one library, one pattern.

> Created by **[Majidul Islam](https://github.com/Majidul17068)**.

```bash
pip install personakit
```

---

## Why personakit

**LangChain** is for wiring LLM calls. **CrewAI** is for orchestrating agent teams.
**LangGraph** is for branching control flow. They're all *engineer-facing composition frameworks*.

**personakit is for encoding specialist expertise — declaratively.** A code
reviewer, a fintech compliance officer, a customer-support triage agent, a
scrum master — each is a single `Specialist(...)` object. No chain wiring. No
graph building. Domain experts can author specialists in YAML and hand them to
engineers.

The distinctive primitives:

| Concept      | What it gives you                                                      |
| ------------ | ---------------------------------------------------------------------- |
| **Specialist** | Frozen dataclass — the entire agent definition, authorable in YAML   |
| **Framework**  | Body of knowledge with a citation key, cited in output               |
| **Probe**      | Diagnostic question; becomes a typed field in the structured response |
| **RedFlag**    | Trigger → severity → action → citation, matched deterministically AND semantically |
| **Theme**      | User-selectable recommendation category                              |
| **Priority**   | Always-on checks reported as met / unmet / unknown                   |
| **Tool (optional)** | `@tool` decorator — opt-in for external memory, DB, APIs         |

Core has just two runtime deps: **`pydantic`** and **`httpx`**.

---

## Quickstart — any domain in 20 lines

```python
import asyncio
from personakit import Agent, Specialist, Framework, Probe, RedFlag, Severity, Theme

product_manager = Specialist(
    name="product_manager",
    display_name="Senior Product Manager",
    persona="You are a senior B2B SaaS PM. You sharpen feature specs and find edge cases.",
    frameworks=[Framework(name="Jobs-to-be-Done"), Framework(name="RICE scoring")],
    probes=[
        Probe(question="What is the user's job-to-be-done?"),
        Probe(question="What is the current workaround cost?", value_type="string"),
        Probe(question="Is there a measurable success metric proposed?",
              value_type="boolean", weight="high"),
    ],
    red_flags=[
        RedFlag(
            trigger="No success metric defined",
            severity=Severity.HIGH,
            action="Block PRD review. Require a quantitative success metric before scoping.",
        ),
    ],
    themes=[Theme(name="Refinements"), Theme(name="Edge cases"), Theme(name="Open questions")],
)

agent = Agent(specialist=product_manager, model="gpt-4o-mini")

async def main():
    result = await agent.analyze(
        "PRD: Add a 'dark mode' toggle to settings. Shipping next quarter."
    )
    print(result.pretty())

asyncio.run(main())
```

## Bundled specialists across domains

```python
from personakit.examples import (
    CODE_REVIEWER,                  # engineering — PRs, OWASP, SOLID
    CONTRACT_REVIEWER,              # legal — M&A redlines, GDPR
    CUSTOMER_SUPPORT_TRIAGE,        # support — SaaS B2C, refund policy, escalation
    FALLS_PREVENTION_NURSE,         # clinical — NICE guidelines, post-fall protocol
    FINTECH_TRANSACTION_REVIEWER,   # finance — AML/fraud, OFAC, FATF typologies
    MATH_TUTOR,                     # education — Socratic, minimal shape
    SCRUM_MASTER,                   # delivery — sprint health, blockers, WIP limits
)
```

Each one is a template. Copy, edit, ship your own.

## Real agent types you can build in one file

| You want an agent that... | Define these concepts |
| ------------------------- | --------------------- |
| Reviews pull requests for security and correctness | `Framework(OWASP)`, `RedFlag(sql_injection, hardcoded_secret)`, `Theme(Security, Performance)` |
| Screens fintech transactions for AML / sanctions | `Framework(BSA/AML, OFAC)`, `RedFlag(sanctioned_counterparty, structuring)`, typology `Theme`s |
| Triages customer support messages | `Probe(order_id, sentiment)`, `RedFlag(chargeback_language)`, `Theme(Resolution, Escalation)` |
| Coaches a sprint team as a scrum master | `Framework(Scrum Guide, DORA)`, `RedFlag(scope_creep, external_blocker)`, `Theme(At-risk stories, Retro candidates)` |
| Reviews M&A contracts for legal risk | `Framework(English common law, UCC)`, `RedFlag(unlimited_liability)`, `Theme(Liability, IP)` |
| Runs a post-fall clinical assessment | `Framework(NICE NG161, NICE CG176)`, `RedFlag(LOC, head_contact_on_anticoagulant)`, clinical probes |
| Writes product specs against JTBD | `Framework(Jobs-to-be-Done, RICE)`, `RedFlag(no_success_metric)`, `Theme(Edge cases, Open questions)` |
| Tutors a student without giving away answers | `Theme(Concept check, Next hint, Common pitfall)`, `Constraint(no direct answer first)` |
| Does equity research on a public SaaS name | `Framework(DCF, Rule of 40)`, `RedFlag(NDR_below_100, negative_fcf_plus_decel)`, `Theme(Thesis, Risks)` |

## YAML authoring — hand off to a domain expert

```yaml
name: code_reviewer
persona: Senior staff engineer reviewing PRs. Correctness, security, perf, in that order.
frameworks: [OWASP Top 10, SOLID, 12-Factor App]
probes:
  - question: Does the change include tests?
    key: has_tests
    value_type: boolean
    weight: high
red_flags:
  - trigger: Hard-coded secret or API key
    severity: critical
    action: BLOCK merge. Rotate the secret. Move to a secret manager.
    match: both
    patterns: ['sk-[A-Za-z0-9]{20,}', 'AKIA[0-9A-Z]{16}']
themes: [Correctness, Security, Performance, Maintainability, Tests]
```

```python
from personakit import Specialist, Agent

spec = Specialist.from_yaml("code_reviewer.yaml")
agent = Agent(specialist=spec, model="claude-sonnet-4-6")
```

## Red flags — the feature no-one else has

Every RedFlag is a **trigger → severity → action → citation** contract,
matched in two phases:

1. **Deterministic pre-match** — regex / keywords on raw input. Fast, offline, quotable.
2. **Semantic post-match** — the LLM evaluates whether the trigger applies
   in context. Catches paraphrase, synonyms, implicit meaning.

Results merge, with deterministic evidence winning on ties:

```python
RedFlag(
    trigger="Hard-coded secret, token, or credential",
    severity=Severity.CRITICAL,
    action="BLOCK merge. Rotate secret. Move to secret manager.",
    citation="OWASP A02:2021",
    match=MatchMode.BOTH,
    patterns=[r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}"],
)
```

## Structured output — derived from the Specialist

You never write a JSON schema by hand. The probes, red flags, and themes
**are** the schema:

```python
result = await agent.analyze(input_text)

result.summary                # narrative summary
result.probes_answered        # {probe_key: typed_value_or_null}
result.probes_unanswered      # list[Probe] — next-round questions
result.red_flags_triggered    # list[TriggeredRedFlag] with evidence + source
result.recommendations        # themed list with citations
result.citations_used         # framework citation keys referenced
result.priorities_status      # per-priority met / unmet / unknown
result.has_urgent             # convenience boolean
```

## Tools — opt-in, for external memory & APIs

Core has zero coupling to tool calling. When you want tools, decorate functions
and attach:

```python
from personakit.tools import tool

@tool
def lookup_order(order_id: str) -> dict:
    """Fetch an order from the order database."""
    return order_db.get(order_id)

@tool
def search_knowledge_base(query: str, top_k: int = 5) -> list[str]:
    """Semantic search against the internal KB — your vector store."""
    return kb.search(query, k=top_k)

support_agent = Agent(specialist=CUSTOMER_SUPPORT_TRIAGE, model="gpt-4o-mini")
support_agent = support_agent.with_tools([lookup_order, search_knowledge_base])
```

OpenAI and Anthropic tool-calling happen through the same interface. Schemas
are auto-built from your function signatures and docstrings.

## Registry — one app, many specialists

```python
from personakit import SpecialistRegistry

registry = SpecialistRegistry.from_directory("personas/")

# Route by domain
engineering_agents = registry.by_domain("engineering")
finance_agents = registry.by_domain("finance")

# Route by name
support = registry.get("support_triage")
```

## Providers

| Extra                   | Install                   | Default model         |
| ----------------------- | ------------------------- | --------------------- |
| `personakit[openai]`    | `openai>=1.0`             | `gpt-4o-mini`         |
| `personakit[anthropic]` | `anthropic>=0.20`         | `claude-sonnet-4-6`   |
| `personakit[yaml]`      | `pyyaml>=6.0`             | —                     |
| `personakit[all]`       | all of the above          | —                     |

`MockProvider` ships in the core for offline testing — no API key needed:

```python
from personakit.testing import MockProvider
provider = MockProvider(responses={"summary": "...", "recommendations": [...]})
```

## Testing helpers

```python
from personakit.testing import assert_triggered, assert_cited

result = await agent.analyze("Customer: 'I want to chargeback this transaction.'")
assert_triggered(result, "legal_or_chargeback_language_attorney_lawsuit_chargeback_small_claims_bbb")
```

## Design principles

1. **Specialist is pure data.** No behaviour, no side effects, serializable.
2. **Schema is derived.** Probes, red flags, themes *are* the output contract.
3. **Deterministic where possible, semantic where needed.** Red flags run both.
4. **Tools are opt-in.** Core has zero coupling to tool calling.
5. **Minimal dependencies.** `pydantic` + `httpx`. Everything else is an extra.
6. **Domain-neutral.** Engineering, support, fintech, legal, clinical, education, delivery, product — one library.
7. **Provider-agnostic.** Same Specialist, any model.

## Status

Alpha — API may evolve. See [`CHANGELOG.md`](./CHANGELOG.md).

## Author

**Majidul Islam** — [@Majidul17068](https://github.com/Majidul17068)

personakit is an independent open-source project. Contributions welcome.

## License

MIT © 2026 Majidul Islam.
