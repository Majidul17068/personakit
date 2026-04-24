# personakit

[![PyPI](https://img.shields.io/pypi/v/personakit.svg)](https://pypi.org/project/personakit/)
[![Python](https://img.shields.io/pypi/pyversions/personakit.svg)](https://pypi.org/project/personakit/)
[![License](https://img.shields.io/pypi/l/personakit.svg)](https://github.com/Majidul17068/personakit/blob/main/LICENSE)
[![Tests](https://img.shields.io/badge/tests-36%20passing-brightgreen.svg)](https://github.com/Majidul17068/personakit/tree/main/tests)
[![Type Checked](https://img.shields.io/badge/mypy-strict-blue.svg)](https://github.com/Majidul17068/personakit/blob/main/pyproject.toml)

**A declarative framework for building role-based LLM agents.** Describe a
specialist — persona, frameworks, probes, red flags, recommendation themes — as
a single data object, and get a typed, cited, safety-aware agent. No chain
wiring, no graph building, no orchestration code.

> Created by **[Majidul Islam](https://github.com/Majidul17068)**.

```bash
pip install personakit
```

---

## What personakit is — and what it is not

**personakit IS** a declarative framework for building *role-based LLM agents*:
code reviewers, compliance officers, clinical triage, support triage, contract
reviewers, scrum masters, and similar domain specialists. You describe the role
as data; personakit produces the runnable agent backed by OpenAI / Anthropic /
your local model.

**personakit is NOT:**

- ❌ **Not a personality classifier** (not MBTI, not Big Five, not trait
  inference). It has nothing to do with `pypersonality`, `persai`, or similar
  trained classifiers.
- ❌ **Not an ML training library.** No feature extraction, no fitted models,
  no datasets. It wraps LLMs you already have access to.
- ❌ **Not a RAG framework.** Bring your own vector store via the optional
  `@tool` system — we don't ship embeddings or retrieval.
- ❌ **Not a chain-orchestration engine.** Composable *alongside* LangChain,
  LangGraph, and CrewAI — personakit owns the specialist layer, they own the
  pipeline layer.

---

## 30-second quickstart

```python
import asyncio
from personakit import Agent, Specialist, Framework, Probe, RedFlag, Severity, Theme

code_reviewer = Specialist(
    name="code_reviewer",
    persona="Senior staff engineer. Correctness, security, perf — in that order.",
    frameworks=[Framework(name="OWASP Top 10"), Framework(name="SOLID")],
    probes=[Probe(question="Does the change include tests?", value_type="boolean")],
    red_flags=[
        RedFlag(
            trigger="Hard-coded secret",
            severity=Severity.CRITICAL,
            action="BLOCK merge. Rotate the secret immediately.",
            patterns=[r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}"],
        ),
    ],
    themes=[Theme(name="Correctness"), Theme(name="Security"), Theme(name="Performance")],
)

agent = Agent(specialist=code_reviewer, model="gpt-4o-mini")
result = asyncio.run(agent.analyze("--- a.py\n+api_key = 'sk-proj-abc123456789012345678'"))

print(result.pretty())              # full structured summary
print(result.red_flags_triggered)   # [TriggeredRedFlag(..., severity=CRITICAL, evidence='sk-proj-...')]
print(result.has_urgent)            # True
```

That's the whole agent. No chain wiring. One `Specialist` dataclass. Typed,
cited, safety-aware output.

---

## How it works

```
┌──────────────────┐    ┌─────────────────────┐    ┌──────────────────────┐
│ Specialist       │ →  │ personakit          │ →  │ Agent.analyze(text)  │
│ (role as data:   │    │ PromptBuilder +     │    │                      │
│  persona,        │    │ auto-derived JSON   │    │ Structured result:   │
│  frameworks,     │    │ schema +            │    │  • summary           │
│  probes,         │    │ red-flag matcher    │    │  • probes_answered   │
│  red flags,      │    │ (regex + semantic)  │    │  • red_flags_triggered│
│  themes)         │    │                     │    │  • recommendations   │
└──────────────────┘    └─────────────────────┘    │  • citations_used    │
         ▲                        │                 └──────────────────────┘
         │                        ▼
         │              ┌─────────────────────┐
         │              │ LLM provider        │
         │              │ (OpenAI / Anthropic │
         │              │  / local / mock)    │
         │              └─────────────────────┘
         │
   Authorable in Python OR YAML — hand the YAML to a domain expert.
```

---

## Bundled specialists — 7 domains, zero boilerplate

Import any of these directly, or read the source as a template:

| Specialist                       | Domain                          | What it does                                                 |
| -------------------------------- | ------------------------------- | ------------------------------------------------------------ |
| `CODE_REVIEWER`                  | `engineering.software.review`   | PR reviewer — OWASP, SOLID, 12-Factor, secret detection      |
| `FINTECH_TRANSACTION_REVIEWER`   | `finance.fintech.aml`           | AML/fraud triage — OFAC, FATF typologies, SAR filing         |
| `CUSTOMER_SUPPORT_TRIAGE`        | `support.saas.b2c`              | SaaS B2C support — refund policy, chargeback, GDPR routing   |
| `SCRUM_MASTER`                   | `engineering.delivery.agile`    | Sprint health — scope creep, WIP limits, blockers            |
| `CONTRACT_REVIEWER`              | `legal.contracts.m_and_a`       | M&A redlining — English common law, UCC, GDPR Art. 28        |
| `FALLS_PREVENTION_NURSE`         | `healthcare.clinical.falls`     | Post-fall clinical triage — NICE NG161, CG176, Morse         |
| `MATH_TUTOR`                     | `education.secondary`           | Socratic GCSE tutor — minimal persona-only specialist        |

```python
from personakit import Agent
from personakit.examples import FINTECH_TRANSACTION_REVIEWER

agent = Agent(specialist=FINTECH_TRANSACTION_REVIEWER, model="gpt-4o-mini")
result = asyncio.run(agent.analyze(transaction_details))
```

---

## FAQ

**Q: Is this a personality classifier (MBTI, Big Five, etc.)?**
No. personakit is an *agent builder*. It has no trained models, no feature
extraction, and no personality taxonomy. If you need MBTI or Big Five, look at
`pypersonality` or `persai` — completely different category of library.

**Q: Can it fetch external knowledge (RAG, vector store, real-time APIs)?**
Yes — via the opt-in `@tool` system. personakit is *bring-your-own-retrieval*:
wrap your vector store (Pinecone, pgvector, Chroma, Qdrant, Weaviate) or any
API in a `@tool` function, and the agent uses it. We don't ship a vector store
because every team already has one they prefer.

**Q: Why not just use LangChain or LangGraph?**
Different problems. LangChain/LangGraph describe **what the agent does**
(imperative chains, graphs). personakit describes **who the agent is**
(declarative role). For role-based agents — compliance, code review, support
triage, clinical — the declarative approach is ~10× less code and lets
non-engineers author specialists in YAML. Use personakit *inside* a LangChain
chain or LangGraph node when you need the chain / graph for orchestration.

**Q: What does it depend on?**
Just two runtime dependencies: **`pydantic`** and **`httpx`**. Providers
(`openai`, `anthropic`, `pyyaml`) ship as optional extras — install only what
you need. Total transitive footprint on a fresh venv: ~12 packages.

**Q: Is it production-ready?**
It's v0.1.3 — **alpha**. API may evolve before v1.0. 36 tests pass; `mypy
--strict` clean; no unreleased breaking changes. Used in the wild but you
should pin the minor version in production.

---

## The idea

A specialist agent is rarely about *retrieval* — it's about **role, tone,
knowledge frameworks, diagnostic questions, safety triggers, and output
shape**. All of that can be captured declaratively:

- A **code reviewer** has frameworks (OWASP, SOLID), probes (does it have tests? what's the blast radius?), and red flags (hard-coded secrets, SQL injection).
- A **fintech compliance officer** has frameworks (AML/BSA, OFAC, FATF typologies), probes (amount, country pair, velocity), and red flags (sanctioned counterparty, structuring).
- A **customer support triage agent** has frameworks (refund policy, escalation matrix), probes (order ID, sentiment), and red flags (chargeback language, data request).
- A **scrum master** has frameworks (Scrum Guide, DORA), probes (days remaining, WIP count), and red flags (scope creep, external blocker without owner).

personakit turns that shape into a library. One `Specialist` object = one
declarative agent. Ship it via Python, or hand a YAML file to a domain expert
and let them author without touching any chain code.

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

## Works alongside the rest of the LLM toolchain

personakit focuses on **declarative specialist definition**. It intentionally
does not try to be:

- a chain-composition library — use **LangChain** when you need to wire up
  complex multi-step LLM pipelines
- a multi-agent orchestration framework — use **CrewAI** when you need a
  team of agents collaborating on a shared goal
- a branching control-flow engine — use **LangGraph** when you need
  conditional routing and loops across nodes

They compose nicely. A LangChain chain can invoke a personakit `Agent` as one
of its steps. A CrewAI crew member can be a personakit `Specialist`. A
LangGraph node can call `agent.analyze()` and route on `result.has_urgent`.

Use personakit for what it's best at — the *declarative specialist layer* —
and reach for the others when the problem actually needs chains, crews, or
graphs.

## Status

Alpha — API may evolve. See [`CHANGELOG.md`](./CHANGELOG.md).

## Author

**Majidul Islam** — [@Majidul17068](https://github.com/Majidul17068)

personakit is an independent open-source project. Contributions welcome.

## License

MIT © 2026 Majidul Islam.
