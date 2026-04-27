<p align="center">
  <img src="https://raw.githubusercontent.com/Majidul17068/personakit/main/assets/logo.png" alt="PersonaKit" width="420" />
</p>

<p align="center">
  <strong>A declarative framework for building role-based LLM agents.</strong><br />
  Describe a specialist as data — persona, frameworks, probes, red flags, themes —<br />
  and get a typed, cited, safety-aware agent. No chain wiring. No graph building.
</p>

<p align="center">
  <a href="https://pypi.org/project/personakit/"><img src="https://img.shields.io/pypi/v/personakit.svg" alt="PyPI version" /></a>
  <a href="https://pypi.org/project/personakit/"><img src="https://img.shields.io/pypi/pyversions/personakit.svg" alt="Python versions" /></a>
  <a href="https://pypi.org/project/personakit/"><img src="https://img.shields.io/pypi/dm/personakit.svg" alt="Downloads" /></a>
  <a href="https://github.com/Majidul17068/personakit/blob/main/LICENSE"><img src="https://img.shields.io/pypi/l/personakit.svg" alt="License" /></a>
  <a href="https://github.com/Majidul17068/personakit/tree/main/tests"><img src="https://img.shields.io/badge/tests-93%20passing-brightgreen.svg" alt="Tests" /></a>
  <a href="https://github.com/Majidul17068/personakit/blob/main/pyproject.toml"><img src="https://img.shields.io/badge/mypy-strict-blue.svg" alt="mypy strict" /></a>
</p>

<p align="center">
  <a href="#why-personakit">Why</a>
  ·
  <a href="#30-second-quickstart">Quickstart</a>
  ·
  <a href="#bundled-specialists--7-domains-zero-boilerplate">Specialists</a>
  ·
  <a href="#providers">Providers</a>
  ·
  <a href="#faq">FAQ</a>
  ·
  <a href="https://github.com/Majidul17068/personakit">GitHub</a>
</p>

```bash
pip install personakit
```

> Created by **[Majidul Islam](https://github.com/Majidul17068)** · MIT licensed · Independent open source

---

## What personakit is — and what it is not

**personakit IS** a declarative framework for building *role-based LLM agents*:
code reviewers, compliance officers, clinical triage, support triage, contract
reviewers, scrum masters, and similar domain specialists. You describe the role
as data; personakit produces the runnable agent backed by OpenAI / Anthropic /
your local model.

Production wiring shipped in v0.2:

- ✅ Native streaming with `Agent.analyze_stream()` (OpenAI / Anthropic / LiteLLM / Mock)
- ✅ OpenTelemetry hooks via the `Tracer` protocol — analyze / provider / tool spans
- ✅ Token cost tracking — `result.estimated_cost_usd` with pricing for ~25 popular models
- ✅ Multi-turn conversations with `ConversationalAgent` + serialisable `Session`
- ✅ Multi-turn tool-calling loop — same Specialist works on every provider
- ✅ Real-time web knowledge via `personakit[web]` (`fetch_url`, `tavily_search`, …)

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

## Why personakit?

Building a specialist LLM agent shouldn't take 200 lines of chain wiring.

Every specialist — regardless of domain — has the same anatomy:

- A **role** the agent plays
- **Knowledge bodies** it draws from and cites
- **Diagnostic questions** it asks of any input
- **Safety triggers** demanding immediate action
- **Output categories** organizing what it recommends

That anatomy holds whether your specialist reviews legal documents,
evaluates clinical cases, audits financial transactions, scores research
papers, drafts user stories, scopes engineering work, supports customers,
moderates content, qualifies sales leads, grades coursework, or any of a
thousand other roles. **personakit captures the anatomy.** You bring the
role.

You describe WHO the specialist is, as data. The library produces a typed,
cited, safety-aware agent that runs on any LLM provider — without chain
wiring, graph building, or orchestration code.

**The discipline is the role description.** Everything else — JSON schema
generation, red-flag matching (deterministic + semantic), citation
enforcement, provider routing, structured-output validation — is automatic.

If a domain expert can articulate what they look for, what they ask, and
what they recommend, you can build them an agent in 30 lines.

### The primitives

| Concept             | What it gives you                                                                  |
| ------------------- | ---------------------------------------------------------------------------------- |
| **Specialist**      | Frozen dataclass — the entire agent definition, authorable in YAML                 |
| **Framework**       | Body of knowledge with a citation key, cited in output                             |
| **Probe**           | Diagnostic question; becomes a typed field in the structured response              |
| **RedFlag**         | Trigger → severity → action → citation, matched deterministically AND semantically |
| **Theme**           | User-selectable recommendation category                                            |
| **Priority**        | Always-on checks reported as met / unmet / unknown                                 |
| **Tool (optional)** | `@tool` decorator — opt-in for external memory, DB, APIs                           |

Core has just two runtime deps: **`pydantic`** and **`httpx`**.

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

## Production-ready in v0.2

Four features that turn personakit from "interesting alpha" into something
you can deploy:

### Streaming — `agent.analyze_stream(text)`

```python
async for event in agent.analyze_stream(case_text):
    if event.type == "text_delta":
        print(event.text, end="", flush=True)
    elif event.type == "red_flag_pre_match":
        print(f"\n🚨 {event.red_flag.trigger}")
    elif event.type == "complete":
        result = event.result   # full AnalyzeResult
```

Live event stream with deterministic red flags fired up front, text deltas
as the LLM types, tool-call lifecycles, and a final structured result.
Native streaming on OpenAI, Anthropic, LiteLLM (100+ providers), and
MockProvider.

### OpenTelemetry hooks — `personakit.observability`

```python
from personakit.observability import OpenTelemetryTracer
agent = Agent(specialist=..., model="gpt-4o", tracer=OpenTelemetryTracer())
```

Three span points: `personakit.analyze`, `personakit.provider.complete`,
`personakit.tool.invoke`. Plug in your existing OTel pipeline (LangSmith,
Datadog, Honeycomb, Jaeger) — or implement the `Tracer` Protocol in 30
lines for any other backend. Install: `pip install 'personakit[otel]'`.

### Token cost tracking — `result.estimated_cost_usd`

```python
result = await agent.analyze(text)
print(result.usage)              # {"prompt_tokens": 1200, "completion_tokens": 350}
print(result.estimated_cost_usd) # 0.00465
```

Pricing tables for ~25 models (OpenAI, Anthropic, Gemini, Groq, DeepSeek,
Mistral). Local models (Ollama, vLLM) cost `0.0`. Unknown models return
`None` so callers can distinguish "unknown" from "free". Add custom rates
with `register_pricing(...)`.

### Conversational sessions — `ConversationalAgent` + `Session`

```python
from personakit import ConversationalAgent
from personakit.examples import CUSTOMER_SUPPORT_TRIAGE

agent = ConversationalAgent(specialist=CUSTOMER_SUPPORT_TRIAGE, model="gpt-4o-mini")
session = agent.start_session(user_id="alice")

reply1 = await session.send("My order ORD-1002 is late")
reply2 = await session.send("It's been 3 weeks now")  # remembers turn 1

# Caller-managed persistence — serialise to your choice of store
blob = session.serialize()
restored = Session.deserialize(blob, agent=agent)
```

Multi-turn memory with a configurable history window. No database
required — sessions serialise to a string the caller can stick in
Redis, Postgres, or a JSON file.

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

## Tools — opt-in, with a real multi-turn loop

Core has zero coupling to tool calling. When you want tools, decorate functions
and attach them to an Agent:

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

agent = Agent(specialist=CUSTOMER_SUPPORT_TRIAGE, model="gpt-4o-mini")
agent = agent.with_tools([lookup_order, search_knowledge_base])

result = await agent.analyze("Where is order ORD-1002?")
# Behind the scenes:
#   1. LLM emits tool_calls in its response
#   2. personakit invokes the matching tool locally
#   3. The result is fed back into the conversation
#   4. The LLM produces the final structured analysis
```

The loop runs across **OpenAI**, **Anthropic**, **LiteLLM**, and **MockProvider**
identically — personakit normalises between OpenAI's `tool_calls` array and
Anthropic's `tool_use` / `tool_result` content blocks internally. Schemas are
auto-built from your function signatures and docstrings.

Bound the loop with `Agent(..., max_tool_iterations=6)` to cap cost; defaults
to 6.

## Real-time knowledge from URLs (`personakit[web]`)

For the common case "I want my agent to use a web link as its knowledge
source", personakit ships a small set of ready-made tools:

```bash
pip install 'personakit[web]'
```

```python
from personakit import Agent
from personakit.web import fetch_url, extract_article, tavily_search
from personakit.examples import FINTECH_TRANSACTION_REVIEWER
```

### Pattern A — pre-fetch (deterministic, single LLM call)

Fetch the URL yourself, pass the content as `extra_context`. Best when *you*
know the URL up front (e.g. a user submits a link).

```python
fetched = await fetch_url.invoke(url="https://www.reuters.com/some-article")
result = await agent.analyze(
    "Is the entity in this press release on any sanctions list?",
    extra_context=f"Source: {fetched['final_url']}\n\n{fetched['text']}",
)
```

### Pattern B — LLM decides when to fetch (autonomous)

Attach the tools and let the agent decide. Best when the agent might need
multiple sources or doesn't know in advance whether to fetch.

```python
agent = (
    Agent(specialist=FINTECH_TRANSACTION_REVIEWER, model="gpt-4o-mini")
    .with_tools([fetch_url, tavily_search])
)

result = await agent.analyze(
    "Verify this counterparty against current sanctions lists: ACME Holdings Pte Ltd"
)
# The LLM may call tavily_search first, then fetch_url on a result link,
# then return the final analysis. The tool loop runs all of it.
```

### Available web tools

| Tool | Purpose | Requirements |
|---|---|---|
| `fetch_url(url, max_chars=8000)` | HTTP GET + text extraction (BeautifulSoup) | `personakit[web]` |
| `extract_article(url, max_chars=12000)` | Smarter article extraction (trafilatura) | `personakit[web]` |
| `tavily_search(query, max_results=5)` | LLM-optimised web search | `TAVILY_API_KEY` env var |
| `serper_search(query, max_results=5)` | Google SERP search | `SERPER_API_KEY` env var |

Both Tavily and Serper offer free tiers (1,000 / 2,500 searches/month). All
four work cross-provider — same agent, same tool list, any LLM backend.

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

| Extra                   | Install                   | What you get                                 |
| ----------------------- | ------------------------- | -------------------------------------------- |
| `personakit[openai]`    | `openai>=1.0`                                   | Native OpenAI SDK — `gpt-4o-mini` default    |
| `personakit[anthropic]` | `anthropic>=0.20`                               | Native Anthropic SDK — `claude-sonnet-4-6`   |
| `personakit[litellm]`   | `litellm>=1.40`                                 | **100+ providers via one extra** (see below) |
| `personakit[web]`       | `beautifulsoup4>=4.12`, `trafilatura>=1.6`      | URL fetch + article extraction + search      |
| `personakit[otel]`      | `opentelemetry-api>=1.20`, `-sdk>=1.20`         | OpenTelemetry tracer adapter                 |
| `personakit[yaml]`      | `pyyaml>=6.0`                                   | YAML specialist authoring                    |
| `personakit[all]`       | all of the above                                | Everything                                   |

### 100+ providers via LiteLLM

[LiteLLM](https://github.com/BerriAI/litellm) normalises the APIs of 100+
providers — OpenAI, Anthropic, Azure OpenAI, AWS Bedrock, Google Vertex AI,
Cohere, Mistral, Hugging Face, Ollama, DeepSeek, Together AI, Groq,
Fireworks, Anyscale, and any OpenAI-compatible endpoint — into a single
unified call. `LiteLLMProvider` plugs that into personakit so switching
providers is a one-line change:

```python
from personakit import Agent
from personakit.providers import LiteLLMProvider
from personakit.examples import FINTECH_TRANSACTION_REVIEWER

# Same Specialist, any provider LiteLLM supports — change the model string only.
provider = LiteLLMProvider(default_model="bedrock/anthropic.claude-v2")
# or:  LiteLLMProvider(default_model="azure/my-gpt-4-deployment",
#                       api_key=..., api_version="2024-06-01")
# or:  LiteLLMProvider(default_model="vertex_ai/gemini-pro")
# or:  LiteLLMProvider(default_model="ollama/llama3",
#                       api_base="http://localhost:11434")
# or:  LiteLLMProvider(default_model="groq/mixtral-8x7b-32768")

agent = Agent(specialist=FINTECH_TRANSACTION_REVIEWER, provider=provider)
result = await agent.analyze(transaction_details)
```

Install: `pip install 'personakit[litellm]'`. You can also use LiteLLM's
**proxy mode** with `OpenAIProvider(base_url="http://localhost:4000")` if
you prefer running LiteLLM as a separate gateway.

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
7. **Provider-agnostic.** Native OpenAI + Anthropic adapters, plus **100+ providers via the LiteLLM extra** (Azure, Bedrock, Vertex AI, Cohere, Mistral, Ollama, Groq, and any OpenAI-compatible endpoint). Same Specialist, any model.

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
(declarative role). For role-based agents the declarative approach is ~10×
less code and lets non-engineers author specialists in YAML. Use personakit
*inside* a LangChain chain or LangGraph node when you need the chain / graph
for orchestration.

**Q: Does it work with LiteLLM (Azure, Bedrock, Vertex AI, Ollama, Groq, …)?**
Yes — install with `pip install 'personakit[litellm]'` and use
`LiteLLMProvider(default_model="bedrock/anthropic.claude-v2")` (or any LiteLLM
model string). The `LiteLLMProvider` adapter exposes 100+ providers through
the same `Agent` interface as the native OpenAI / Anthropic adapters.

**Q: What does it depend on?**
Just two runtime dependencies: **`pydantic`** and **`httpx`**. Providers
(`openai`, `anthropic`, `litellm`, `pyyaml`) ship as optional extras —
install only what you need. Total transitive footprint on a fresh venv with
no extras: ~12 packages.

**Q: Do I need to be a Python expert to use it?**
No. The minimum useful Specialist is a name + a persona string. You can
declare more capable specialists in pure YAML — no Python required for the
authoring side. An engineer plugs the YAML into the runtime in 2 lines of code.

**Q: Is it production-ready?**
It's v0.2.0 — **alpha**, but with the production basics in place: streaming
(`Agent.analyze_stream()`), OpenTelemetry hooks (`personakit[otel]`), token
cost tracking (`result.estimated_cost_usd`), and conversational sessions
(`ConversationalAgent`). 93 tests pass; `mypy --strict` clean across 29
source files; no unreleased breaking changes. The API may still evolve
before v1.0 — pin the minor version in production until then.

**Q: Does it support streaming?**
Yes. `Agent.analyze_stream(text)` returns an async iterator yielding
`StreamEvent` objects: `red_flag_pre_match`, `text_delta`, `tool_call`,
`tool_result`, `iteration_complete`, `complete`, `error`. Streaming works
natively on OpenAI, Anthropic (with `tool_use` / `tool_result` content-block
translation), LiteLLM (100+ providers), and `MockProvider`.

**Q: How do I integrate with my existing observability stack
(LangSmith / Datadog / Honeycomb / Jaeger)?**
Plug in `OpenTelemetryTracer` (install via `personakit[otel]`) — three
spans (`personakit.analyze`, `personakit.provider.complete`,
`personakit.tool.invoke`) flow into your existing OTel pipeline. Or
implement the `Tracer` Protocol in ~30 lines for any other backend.

**Q: Does it track token cost?**
Yes. `AnalyzeResult.estimated_cost_usd` returns a USD float for the ~25
models in the bundled pricing table (OpenAI, Anthropic, Gemini, Groq,
DeepSeek, Mistral). Local models (Ollama / vLLM) cost `0.0`. Unknown models
return `None` so callers can distinguish "unknown" from "free". Add custom
rates with `register_pricing(...)`.

**Q: How do I do multi-turn conversation?**
Use `ConversationalAgent` + `Session`. The session tracks history; each
`session.send(message)` includes the prior turns as context. Persist
sessions yourself (`session.serialize()` returns a JSON blob) — no DB
requirement.

**Q: Is there commercial support / a hosted offering?**
No. personakit is an independent open-source project — MIT licensed, no SaaS
tier, no telemetry, no upsell path. Use it freely.

**Q: Can I contribute?**
Yes — see [Contributing](#contributing) below. Bug reports, feature requests,
new bundled specialists, and PRs all welcome.

---

## Contributing

personakit is a solo independent project — every contribution counts.

### Quick start

```bash
git clone https://github.com/Majidul17068/personakit.git
cd personakit
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,openai,anthropic,litellm,yaml,web,otel]'
```

### Quality gates (all must pass before opening a PR)

```bash
pytest                # unit tests — currently 93 passing
mypy --strict src     # zero errors across 29 source files
ruff check src tests  # lint
python -m build       # wheel + sdist build cleanly
```

### What's most useful

- **New bundled specialists** for domains we don't yet cover (`src/personakit/examples/`).
  See `code_reviewer.py` or `fintech_reviewer.py` as templates.
- **Bug reports** with a minimal reproduction — open an [issue](https://github.com/Majidul17068/personakit/issues).
- **Real-world API feedback** — what's clunky, what's missing, where it breaks.
- **Documentation improvements** — clarifications, fixes, examples.

PRs land faster when they include a test for the change.

---

## Privacy

personakit does **not** collect telemetry. No network calls outside the LLM
provider you configure. No analytics, no anonymous usage statistics, no
phoning home. The library is a thin layer over your own LLM API key.

---

## Status

**v0.2.0 — alpha.** All four production basics shipped (streaming,
OpenTelemetry, cost tracking, conversational sessions). 93 tests passing,
`mypy --strict` clean across 29 source files. API may still evolve before
v1.0 — pin the minor version in production. See [`CHANGELOG.md`](./CHANGELOG.md)
for the full release history and [`ROADMAP.md`](./ROADMAP.md) for what's
next.

## Author

**Majidul Islam** — [@Majidul17068](https://github.com/Majidul17068)

personakit is an independent open-source project. Contributions welcome.

## License

MIT © 2026 Majidul Islam.
