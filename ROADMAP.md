# personakit — Roadmap

Living document. Updated when we ship, change direction, or learn something.
Version targets are intent, not commitments. Priorities shift based on user
feedback and real-world use.

**Current:** `v0.1.2` — live on PyPI since 2026-04-24.

---

## 🎯 North star

personakit is **the declarative agent builder**. One `Specialist` object = one
agent. Anyone — engineer or domain expert — authors specialists. Other
libraries (LangChain, CrewAI, LangGraph) wire calls, orchestrate, and branch;
personakit describes *who the agent is*.

Everything on this roadmap should answer: **does this make personakit better
at declaratively describing specialist expertise?** If not, it doesn't belong.

---

## 🔥 Immediate (this week)

These are follow-ups to the v0.1.x release — short, high-value.

- [ ] **Rotate PyPI tokens to project-scoped** — delete the "Entire account"
      tokens created during launch; create tokens scoped to `personakit`
      only. Update `~/.pypirc`. Memory note exists.
- [ ] **GitHub Releases** for v0.1.0 / v0.1.1 / v0.1.2 with CHANGELOG content
      pasted in (or via `gh release create`). Makes the repo look maintained.
- [ ] **Add topic tags on the GitHub repo** — `llm`, `agent`, `ai-agent`,
      `persona`, `declarative`, `fintech`, `code-review`, `scrum`,
      `customer-support`, `prompt-engineering`.
- [ ] **Trusted publishing via GitHub Actions** — follow `publishing.md §9`
      to set up OIDC trusted publishing. After that, future releases are
      "create a GitHub Release → workflow publishes to PyPI", no tokens.
- [ ] **CI workflow** — matrix test on Python 3.10 / 3.11 / 3.12 / 3.13 on
      every PR. `ruff`, `mypy --strict`, `pytest --cov`.
- [ ] **Launch post** — Show HN + r/LocalLLaMA + r/Python. The pitch writes
      itself from the README. Draft lives in `notes/launch-post.md` (todo).

---

## 🚀 v0.2 — Interview mode + real tool loop + more providers

*Target: ~4 weeks after v0.1.2.*

The theme is **interactive agents** and **production readiness**.

### Interactive / conversational

- [ ] **Interview mode.** When `analyze()` leaves probes unanswered, offer an
      `agent.interview(input)` that asks the probes back to the user one at
      a time, carrying context, until enough are filled to produce a result.
- [ ] **Conversational sessions** (`ConversationalAgent`, `Session`). Memory
      persists across turns. Session key → `(specialist_name, user_id)`.
- [ ] **Streaming.** `async for chunk in agent.analyze_stream(text)` yielding
      `PartialResult` objects (summary tokens, probe-by-probe, as they arrive).

### Tools — real LLM loop

- [ ] **End-to-end tool-calling loop.** Currently `@tool` schemas are sent to
      the LLM but the result isn't fed back. Close the loop: LLM requests
      tool → personakit invokes → result goes back as a `tool` message →
      LLM continues.
- [ ] **Error recovery.** Tool raises? Emit structured error back to the
      LLM; retry policy per tool.
- [ ] **Async tool concurrency.** When the LLM requests 3 tool calls, run
      them with `asyncio.gather` if they're independent.

### Providers

- [ ] **Google / Gemini provider.** `personakit[google]` extra.
- [ ] **Ollama provider.** Local models, `personakit[ollama]`.
- [ ] **OpenAI-compatible provider** catch-all — works with vLLM, Together,
      Groq, DeepSeek, Fireworks, Anyscale, LM Studio.

### CLI

- [ ] `personakit run ./specialist.yaml "user input"` — one command to
      analyze with any spec. Output JSON or pretty.
- [ ] `personakit validate ./specialist.yaml` — schema-check without running.
- [ ] `personakit registry list --dir personas/` — inspect a directory of
      specialists.

### More bundled specialists

Keep expanding the domain range so the "any specialist" claim stays credible.

- [ ] `SRE_INCIDENT_COMMANDER` — production incident runbook agent.
- [ ] `SECURITY_ANALYST` — SOC-L1 alert triage (MITRE ATT&CK frameworks).
- [ ] `RECRUITER_SCREEN` — first-pass resume / intro-call triage.
- [ ] `ACADEMIC_RESEARCH_REVIEWER` — peer-review aid (methodology, stats, novelty).

---

## 🛠 v0.3 — Composition, orchestration, observability

*Target: ~3 months out.*

The theme is **scale** — multi-specialist apps, production observability,
power features.

### Composition

- [ ] **`Specialist.extends(parent)`** — full inheritance with field merge
      rules. A `FRAUD_ANALYST_US` extends `FRAUD_ANALYST_BASE`.
- [ ] **Traits.** Reusable personality chunks — `TRAUMA_INFORMED`,
      `EVIDENCE_FIRST`, `SOCRATIC` — compose into any specialist.

### Multi-specialist orchestration

- [ ] **Handoff.** `router = SpecialistRouter([...])`; incoming message is
      routed to the right specialist by embedding similarity + rules.
- [ ] **Debate / consensus.** Two specialists analyse the same input; a
      `Moderator` specialist reconciles differences.
- [ ] **Pipeline.** `result1 -> result2 -> result3` — output of one
      specialist as context for the next.

### Observability

- [ ] **OpenTelemetry tracing.** Every `analyze()` call emits spans with
      specialist name, token counts, tool invocations, red-flag hits.
- [ ] **Cost tracking.** Per-specialist / per-tenant cost aggregation.
      Hook: `Agent(on_usage=lambda usage, meta: ...)`.
- [ ] **Structured logging.** JSON logs with request id, specialist,
      red-flag count, unanswered probes.

### Output / validation

- [ ] **Output caching.** Keyed on `(specialist_hash, input_hash,
      selected_themes)`. In-memory, Redis, or user-provided store.
- [ ] **Deterministic test harness.** `replay(transcript)` replays a
      previous `(input, raw_output)` pair for regression tests without
      hitting an LLM.
- [ ] **Guardrail plugins.** `NoPII`, `CitationRequired`, `OnTopic`,
      `MaxTokens`, `NoPHI`, and a `@guardrail` decorator for custom ones.

### Authoring ergonomics

- [ ] **LLM-assisted persona designer.** A meta-specialist that interviews
      the user about a role and emits a YAML specialist. Ships as a CLI:
      `personakit design`.
- [ ] **`specialist.diff(other)`** — human-readable diff of two
      specialists. Useful for versioning specialists over time.

---

## 🌟 v1.0 — API freeze, production-grade

*Target: when the API has been stable for 2 consecutive minor versions.*

- [ ] Full typing strict — every public function has complete annotations.
- [ ] Deprecation policy — 1 minor version notice, clear migration path.
- [ ] Comprehensive docs site (MkDocs + Material, deployed to ReadTheDocs).
- [ ] Coverage ≥ 90% on core modules.
- [ ] Benchmark suite — cold-start time, throughput, token accounting
      overhead.
- [ ] At least 3 reference apps using personakit in production (community or
      own).

---

## 🌐 Community & distribution

Ongoing. Not version-gated.

- [ ] **Specialist gallery** — a separate repo of community-authored YAML
      specialists, categorised by domain. Contributors add their own.
- [ ] **Persona marketplace.** Hosted index (hugginface-datasets style) of
      specialists. Verified, versioned, searchable. `personakit pull
      legal/contract-reviewer@1.2.0`.
- [ ] **Integration guides** — LangChain (step in a chain), CrewAI (agent
      definition), LangGraph (node that calls `.analyze()`).
- [ ] **Video walkthroughs** — 5-minute domain tours: "build a fintech AML
      agent in 5 minutes", "build a code reviewer".
- [ ] **Hackathon partnerships** — sponsor tracks at AI hackathons; prize
      for the most creative specialist.

---

## 🧹 Tech debt / quality (ongoing)

Items worth doing whenever we're in the relevant file.

- [ ] **Tool schema for `dict[str, int]`** — currently maps to generic
      `{"type": "object"}`; should emit `patternProperties` or `additionalProperties`.
- [ ] **Regex timeout** on red-flag pre-match — long inputs + pathological
      patterns could starve. Use `regex` module with timeout.
- [ ] **Async thread-pool for sync tools** — `tool.invoke()` currently
      awaits if awaitable, else runs inline. Should run sync tools in
      `asyncio.to_thread` for true async behaviour.
- [ ] **Better prompt builder registry** — allow users to register
      alternate `PromptBuilder`s by provider without subclassing.
- [ ] **Specialist YAML schema** — publish a JSON Schema for
      specialists. Enables IDE validation in `.yaml` files.
- [ ] **PII-aware summary** — when citations_required is False, add a mode
      where the summary is stripped of anything flagged by an optional
      PII guardrail.

---

## 📋 Decision log

Short record of why we chose what we chose, so we don't re-litigate.

| Date       | Decision                                       | Reason |
|------------|------------------------------------------------|--------|
| 2026-04-24 | `Specialist` as a single class, not Persona/Specialist pair | The simple case collapses naturally; a two-class hierarchy adds weight without clarity. |
| 2026-04-24 | Tools as opt-in extra, not in core             | Core pitch is "no required tool infra"; tools are for when you need external memory. Users voted on this. |
| 2026-04-24 | Red flags match both regex AND semantic by default | Deterministic quoteable evidence plus LLM paraphrase handling — each catches what the other misses. |
| 2026-04-24 | Drop direct LangChain/CrewAI/LangGraph comparison from README lead | Professional positioning. They're complementary tools, not competitors. (v0.1.2) |
| 2026-04-24 | PyPI owner `Murad68`; GitHub `Majidul17068`; no company attribution | Project is personal OSS; no tulip-tech branding. |

---

## 🗓 How to use this file

- **Before starting work**, check "Immediate" — if something there is still
  undone, do it first.
- **When shipping a version**, update `## Current` at top and move completed
  items out of the version section into the Decision log if they encode
  judgment, or delete them if they were routine.
- **When priorities change**, edit in place. Don't let this document rot.
- **If an item has been on the roadmap for 2+ versions without movement**,
  cut it. Either it wasn't actually valuable, or we weren't honest about it.

---

*Last updated: 2026-04-24 (after shipping v0.1.2).*
