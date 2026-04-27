# personakit — Roadmap

Living document. Updated when we ship, change direction, or learn something.
Version targets are intent, not commitments. Priorities shift based on user
feedback and real-world use.

**Current:** `v0.2.1` — live on PyPI. 93 tests passing, `mypy --strict` clean
across 29 source files, ruff clean, 7 optional extras.

---

## 🎯 North star

personakit is **the declarative agent builder**. One `Specialist` object = one
agent. Anyone — engineer or domain expert — authors specialists. Other
libraries (LangChain, CrewAI, LangGraph) wire calls, orchestrate, and branch;
personakit describes *who the agent is*.

Everything on this roadmap should answer: **does this make personakit better
at declaratively describing specialist expertise?** If not, it doesn't belong.

---

## 📦 Shipped

### v0.1.x — Foundation (closed)

| Release | Headline |
|---|---|
| `v0.1.0` (2026-04-24) | Initial release — Specialist + Agent + 3 bundled examples |
| `v0.1.1` | `@tool` annotation fix + 4 new bundled specialists (code reviewer, fintech, support, scrum) |
| `v0.1.2` | Removed defensive competitor framing |
| `v0.1.3` | "Not a personality classifier" disambiguation in PyPI summary |
| `v0.1.4` | `mypy --strict`: 12 errors → 0 |
| `v0.1.5` | `LiteLLMProvider` — 100+ providers via one extra |
| `v0.1.6` | Domain-neutral "Why personakit?" — kill four-example pigeonhole |
| `v0.1.7` | Logo + professional README rewrite |
| `v0.1.8` | Real-time web knowledge (`personakit[web]`) + multi-turn tool loop |

### v0.2.x — Production basics (closed)

| Release | Headline |
|---|---|
| `v0.2.0` (2026-04-27) | Streaming + OpenTelemetry + token cost tracking + conversational sessions |
| `v0.2.1` | README synced fully to v0.2 (no code changes) |

What v0.2 closed (the four "table-stakes" gaps that kept personakit behind
LangChain / CrewAI on basics):

- ✅ `Agent.analyze_stream()` — live event stream across all providers
- ✅ `Tracer` Protocol + `OpenTelemetryTracer` (3 span points)
- ✅ `result.estimated_cost_usd` with 30-model pricing table
- ✅ `ConversationalAgent` + `Session` with serialisable history
- ✅ Multi-turn tool loop with cross-provider format normalisation

---

## 🔥 Immediate (this week — non-coding)

Launch follow-ups that don't require new code, but make the v0.2 release
look properly maintained.

- [ ] **Rotate PyPI tokens to project-scoped** — old "Entire account" tokens
      were exposed in chat earlier in development. Project-scoped tokens
      reduce blast radius. Memory note exists.
- [ ] **GitHub Releases** for v0.1.0 through v0.2.1 (11 tags) with the
      relevant CHANGELOG section as the body. Either via `gh release create`
      after `gh auth login`, or via the web UI.
- [ ] **GitHub repo topics** — `llm`, `agent`, `agent-builder`, `persona`,
      `declarative`, `specialist-agents`, `red-flags`, `fintech`,
      `code-review`, `scrum`, `prompt-engineering`, `ai-agents`.
- [ ] **CI workflow** — matrix test on Python 3.10 / 3.11 / 3.12 / 3.13 on
      every PR. Steps: `ruff check`, `mypy --strict src`, `pytest --cov`.
- [ ] **Trusted Publishing via GitHub Actions** — follow `publishing.md §9`
      to set up OIDC trusted publishing. After that, future releases are
      "create a GitHub Release → workflow publishes to PyPI", no tokens.
- [ ] **Launch post drafts** — Show HN, r/LocalLLaMA, r/Python, LinkedIn,
      Twitter thread. Drafts already written in earlier conversation; just
      need a publish day (recommended: Tuesday 9 AM PT for HN).

---

## 🚀 v0.3.0 — Audit-grade moat (next active development)

*Target: ~2 weeks after v0.2.1.*

**Theme:** double down on the unique-to-personakit features that no
competitor has. Make personakit the *only* agent framework that gives
buyers in clinical / legal / fintech / compliance an audit trail by
construction.

### Strict mode

- [ ] `Specialist.strict: bool = False` flag. When `True`:
  - Every recommendation MUST cite at least one declared `Framework`
  - Every red flag in the input MUST trigger one of: matched, evidence quoted, or explicitly considered-and-rejected
  - Output schema validation is fail-closed instead of fail-soft
  - Token / cost ceilings can be enforced
- [ ] `Specialist.compliance_mode` — sister flag for regulated domains
- [ ] Strict-mode failures raise `StrictValidationError` with structured
      reasons so the caller can decide retry / escalate / log

### Audit replay

- [ ] `personakit replay <transcript_file>` — given a saved
      `(specialist_version, input_text, expected_output)` triple, prove the
      agent still produces the same output (modulo configurable tolerance).
- [ ] `personakit verify <specialist_dir>` — runs every `.replay` file
      against every specialist; CI-friendly exit codes.
- [ ] Saves: every analyze() call optionally serialises a reproducible
      replay artefact (input, system prompt, response, output).

### Versioned specialists

- [ ] `Specialist.checksum() -> str` — stable hash of the declarative
      definition (excludes runtime metadata).
- [ ] `AnalyzeResult.specialist_checksum` — output is now traceable to the
      exact spec that produced it.
- [ ] `personakit diff <a.yaml> <b.yaml>` — human-readable diff between two
      versions of a specialist (added/removed probes, changed red flags,
      etc.).

### Evidence chain

- [ ] Every recommendation carries an explicit chain:
      `input → probes_answered → frameworks_cited → recommendation`.
- [ ] `result.render_audit_report(format="json"|"html"|"markdown")` —
      reviewer-friendly dump suitable for compliance officers, legal
      review, or IRB submission.
- [ ] Optional structured logging hook (`audit_logger=...`) for shipping
      every analyze invocation to a regulated logging backend.

**Why this wins:** LangChain / CrewAI / LangGraph don't even try to
compete here. Their architectures are the wrong shape for it. We'd be
alone in the audit-grade niche, which is where the high-value buyers are.

---

## 🔌 v0.4.0 — Integration adapters (the adoption multiplier)

*Target: ~2 weeks after v0.3.0.*

**Theme:** be the helpful neighbour, not the rival. Make it trivial to
slot a personakit `Specialist` *inside* someone else's bigger system.

- [ ] **`from personakit.integrations.langchain import to_runnable`** —
      wraps a Specialist as a LangChain `Runnable`. Drop into `prompt |
      retriever | to_runnable(specialist) | output_parser` chains.
- [ ] **`from personakit.integrations.crewai import to_crewai_agent`** —
      `crewai_agent = personakit_specialist.to_crewai_agent()`. The
      Specialist becomes a Crew member with personakit handling its
      internal logic.
- [ ] **`from personakit.integrations.langgraph import to_node`** —
      `graph.add_node("triage", specialist.to_node())`. Specialist
      becomes a graph node returning structured state.
- [ ] **`personakit-specialists` gallery repo** (separate repo, not in
      core) — community-contributed YAML specialists, MIT licensed,
      versioned. `personakit pull legal/contract-redliner@1.2.0`.
- [ ] **Cookbook**: 5–10 short integration examples covering typical
      usage patterns (RAG → Specialist → output, multi-agent crew,
      stateful graph routing on `result.has_urgent`).

---

## 🛠 v0.5.0 — CLI + authoring ergonomics

*Target: ~3 months out.*

- [ ] `personakit run <spec.yaml> "input message"` — analyze in one shot
- [ ] `personakit lint <spec.yaml>` — validate against the schema, suggest
      improvements, catch missing citations
- [ ] `personakit playground <spec.yaml>` — interactive REPL for testing
      a specialist
- [ ] `personakit design` — meta-specialist that interviews the author
      about a role and emits a YAML spec (the LLM-assisted persona designer)
- [ ] `personakit registry list --dir personas/` — inspect a registry
      directory
- [ ] **JSON Schema for specialist YAML** — published, IDE-validateable

---

## 🌟 v1.0.0 — API freeze, production-grade

*Target: when the API has been stable for 2 consecutive minor versions
without breaking changes.*

- [ ] Full typing strict — every public function has complete annotations
- [ ] Deprecation policy — 1 minor version notice, clear migration path
- [ ] Comprehensive docs site (MkDocs + Material → ReadTheDocs)
- [ ] Coverage ≥ 90% on core modules
- [ ] Benchmark suite — cold-start time, throughput, token-accounting overhead
- [ ] At least 3 reference apps using personakit in production (community
      or own)

---

## 🌐 Community & distribution (ongoing)

Not version-gated. Move the needle in parallel with development.

- [ ] **Specialist gallery repo** (kicks off in v0.4) — community-contributed,
      curated, signed, versioned. Categorised by domain.
- [ ] **Integration guides** — LangChain (step in a chain), CrewAI (agent
      definition), LangGraph (node calling `.analyze()`), FastAPI deployment,
      Modal deployment.
- [ ] **Video walkthroughs** — 5-minute domain tours: "build a fintech AML
      agent in 5 minutes", "build a code reviewer", "build a clinical triage
      agent".
- [ ] **Awesome-LLM submissions** — Awesome-LLM, Awesome-AI-Agents,
      Awesome-Python.
- [ ] **Blog posts** — "Persona prompting as a library", "Why declarative
      specialists beat chains for compliance", "Building auditable LLM
      agents".

---

## 🧹 Tech debt / quality (ongoing)

Items worth doing whenever we're in the relevant file.

- [ ] **Tool schema for `dict[str, int]`** — currently maps to generic
      `{"type": "object"}`; should emit `patternProperties` or
      `additionalProperties`.
- [ ] **Regex timeout** on red-flag pre-match — long inputs + pathological
      patterns could starve. Use `regex` module with timeout.
- [ ] **Async thread-pool for sync tools** — `tool.invoke()` currently
      awaits if awaitable, else runs inline. Should run sync tools in
      `asyncio.to_thread` for true async behaviour.
- [ ] **PII-aware summary** — when `citations_required=True`, add a mode
      where the summary is stripped of anything flagged by an optional
      PII guardrail.
- [ ] **macOS pth-file workaround** in dev setup — document the
      `chflags nohidden` step needed when pytest can't find personakit
      after an editable install on macOS.

---

## ❌ Explicitly NOT building (resist the gravitational pull)

The competitive comparison table will tempt these — don't take the bait.
Each would dilute the wedge instead of sharpening it.

- ❌ **Multi-agent orchestration** — CrewAI owns this. We compose with it.
- ❌ **Stateful memory abstractions** — mature ecosystems exist. Document
      how to wire them.
- ❌ **Multi-step chains** — that's LangChain's whole product. Slot into
      a chain instead.
- ❌ **Visual workflow tools** — separate product category.
- ❌ **Built-in RAG** — stay BYO. Vector stores are a religious choice.
- ❌ **LangSmith-equivalent observability product** — ship hooks (already
      done), don't build a product.

---

## 📋 Decision log

Short record of why we chose what we chose. Don't re-litigate.

| Date       | Decision                                                                                          | Reason |
|------------|---------------------------------------------------------------------------------------------------|--------|
| 2026-04-24 | `Specialist` as a single class, not Persona/Specialist pair                                       | The simple case collapses naturally; a two-class hierarchy adds weight without clarity. |
| 2026-04-24 | Tools as opt-in extra, not in core                                                                | Core pitch is "no required tool infra"; tools are for when you need external memory. |
| 2026-04-24 | Red flags match both regex AND semantic by default                                                | Deterministic quoteable evidence plus LLM paraphrase handling — each catches what the other misses. |
| 2026-04-24 | Drop direct LangChain/CrewAI/LangGraph comparison from README lead                                | Professional positioning. They're complementary tools, not competitors. (v0.1.2) |
| 2026-04-24 | PyPI owner `Murad68`; GitHub `Majidul17068`; no company attribution                              | Project is personal OSS; no tulip-tech branding. |
| 2026-04-24 | Add `LiteLLMProvider` instead of separate Google/Ollama/OpenAI-compatible adapters                | One extra unlocks 100+ providers; the original Phase-2 plan to ship 3 separate adapters is obsolete. (v0.1.5) |
| 2026-04-24 | "Not a personality classifier" explicit in PyPI summary                                            | External reviewers had been confusing personakit with `pypersonality`/`persai`. (v0.1.3) |
| 2026-04-24 | "Why personakit?" comes BEFORE quickstart in README                                                | Reader-journey ordering. Skim → evaluate → adopt → contribute. Why earns the right to be read. (v0.1.7) |
| 2026-04-27 | Tool loop runs across providers via translation, not lowest-common-denominator                    | Anthropic's `tool_use` content blocks ↔ OpenAI's `tool_calls` array. Translating preserves rich provider behaviour. (v0.1.8) |
| 2026-04-27 | OpenTelemetry as opt-in extra, not core dep                                                        | OTel adds 100+ MB of optional packages. `Tracer` Protocol stays in core; OTel adapter ships in `personakit[otel]`. (v0.2.0) |
| 2026-04-27 | Conversational sessions don't ship a database                                                      | Caller serialises history themselves (Redis / Postgres / file — their choice). No persistence opinion in the library. (v0.2.0) |
| 2026-04-27 | `AnalyzeResult.estimated_cost_usd` returns `None` for unknown models, not zero                    | Distinguishes "we don't have pricing" from "this is free". (v0.2.0) |
| 2026-04-27 | v0.3 focuses on audit-grade moat, not on closing more comparison-table gaps                       | Strategic — playing the breadth race is unwinnable. Doubling down on the niche LangChain can't reach is the wedge. |

---

## 🗓 How to use this file

- **Before starting work**, check "Immediate" — if something there is still
  undone, do it first.
- **When shipping a version**, move completed items out of the version
  section into "Shipped" with the release date. Add notable design choices
  to the Decision log.
- **When priorities change**, edit in place. Don't let this document rot.
- **If an item has been on the roadmap for 2+ versions without movement**,
  cut it. Either it wasn't actually valuable, or we weren't honest about it.

---

*Last updated: 2026-04-27 (after shipping v0.2.1).*
