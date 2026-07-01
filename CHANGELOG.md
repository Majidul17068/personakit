# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.4.1a1] — 2026-07-01

Live observability — you can now *watch* an ``Agent.analyze`` call happen in
the terminal, with per-provider-call latency, tokens, and cost estimates.

### Added

- **`ConsoleTracer`** (`personakit.observability`) — zero-dependency ``Tracer``
  implementation that renders each of the three built-in spans
  (`personakit.analyze`, `personakit.provider.complete`, `personakit.tool.invoke`)
  as coloured one-line status output. TTY-autodetected colour, ``live=True``
  mode prints on span open + close so long LLM calls announce themselves
  immediately. ``show_cost`` / ``show_tokens`` toggles for compact runs.
- **`SessionMetrics`** and **`CallRecord`** (`personakit.metrics`) —
  cumulative session ledger. Every ``Agent.analyze`` invocation is recorded;
  aggregate via `total_calls`, `total_tokens`, `total_cost_usd`,
  `total_duration_ms`, `by_specialist()`, `by_model()`, and a printable
  `.summary()` table.
- **`Agent.metrics`** — every ``Agent`` now exposes a `SessionMetrics`
  ledger. Populated automatically at the end of each ``analyze()`` call.
- **`Agent(verbose=True)` now auto-attaches `ConsoleTracer`** — if no explicit
  ``tracer=`` is supplied, verbose mode gets you full trace output on the
  terminal for free.

### Tests

- `tests/test_console_tracer.py` — 8 tests covering protocol conformance,
  analyze/provider/tool span rendering, live vs. non-live mode, nested
  indentation, exception capture, and TTY colour autodetection.
- `tests/test_session_metrics.py` — 9 tests covering recording, aggregation
  properties, missing usage, Anthropic-shape usage, per-specialist and
  per-model grouping, reset, summary content, and `Agent.metrics`
  initialisation.

## [0.4.0a2] — 2026-07-01

### Fixed

- **`personakit.__version__`** — hotfix so the runtime version constant
  matches the wheel metadata (was `0.3.0a4`, now `0.4.0a2`).

## [0.4.0a1] — 2026-07-01

Phase 1 of the v0.4 *GraphRAG* cycle: **universal graph retrieval**.
personakit specialists can now query knowledge graphs through a single,
backend-agnostic interface — no more per-project driver code.

### Added

- **`personakit.graphrag`** — new optional subpackage. Install with
  `pip install personakit[graphrag]` to pull in the Neo4j driver.
- **`GraphStore` protocol** — `typing.Protocol` (`@runtime_checkable`)
  defining `.query(cypher, **parameters) -> QueryResult` and `.close()`.
  Any Cypher-capable backend (Neo4j, Memgraph, AuraDB, Neptune with
  openCypher) can plug in by satisfying it.
- **`Neo4jGraphStore`** — reference implementation. Holds a single
  persistent driver, serialises `Node` / `Relationship` / `Path` results
  into JSON-safe dicts, never raises on Cypher errors (returns
  `QueryResult(status="error", ...)` instead).
- **`QueryResult`** — frozen value object with `status`, `records`,
  `duration_ms`, `error`, `ok` property, and `__len__`.
- **`build_graph_query_tool(store, *, name, description, max_records)`** —
  factory that wraps a `GraphStore` as a `personakit.Tool`. The LLM sees
  a single `cypher` argument; oversized result sets are truncated with a
  `truncated=True` marker so the model's context window stays safe.
- **`graphrag` optional extra** — `pip install personakit[graphrag]` pulls
  in `neo4j>=5.20`. Also included in the `all` bundle.

### Tests

- `tests/test_graphrag_store.py` — `QueryResult` defaults, protocol
  conformance via an in-memory fake, and the "neo4j not installed" error
  path.
- `tests/test_graphrag_tool.py` — success payload shape, error
  propagation, record truncation, disabled cap, OpenAI schema generation,
  custom name / description, and the `TypeError` when the input is not a
  `GraphStore`.

## [0.3.0a2] — 2026-06-11

Phase 2 of the v0.3 *audit-grade moat* cycle: **versioned specialists**.
Every `AnalyzeResult` is now traceable to the exact Specialist definition
that produced it, and you can diff two YAML specs from the command line.

### Added

- **`Specialist.checksum() -> str`** — stable SHA-256 over the declarative
  content of a Specialist. Identical specs produce identical checksums; any
  field change produces a different checksum.
- **`Specialist.diff(other) -> SpecialistDiff`** — structured diff between
  two Specialists. Items in `frameworks`, `probes`, `red_flags`, and
  `themes` are aligned by identity field so reorders aren't reported as
  add/remove cycles. The result has `.to_markdown()` for human-readable
  output and `.model_dump_json()` for machine-readable consumption.
- **`diff_specialists(a, b)`** — same as `Specialist.diff`, callable as a
  free function.
- **`SpecialistDiff`, `FieldDiff`, `CollectionItemChange`** — frozen
  pydantic models exposed as public API.
- **`AnalyzeResult.specialist_checksum`** — new field, populated
  automatically by `Agent.analyze()` from the source Specialist. Defaults
  to `""` for backward compat when results are constructed manually.
- **`personakit diff <a.yaml> <b.yaml>`** — new CLI command. Exit code
  `0` if the specs match, `1` if they differ, `2` on invocation error.
  `--json` for machine-readable output, `--quiet` to suppress stdout and
  rely on the exit code. Console script registered via `[project.scripts]`.
- **`python -m personakit`** — alternative invocation via a new
  `__main__.py` shim.

### Tests

- `tests/test_versioning.py` — 14 tests covering checksum stability,
  every structural change case, markdown rendering, and AnalyzeResult
  population.
- `tests/test_cli.py` — 7 tests covering the `personakit diff` CLI
  exit codes, JSON output, quiet mode, missing-file handling, and the
  no-command help fallback.

### Numbers

- 123 tests passing (was 102)
- `mypy --strict` clean across 33 source files (was 30)
- `ruff` clean

## [0.3.0a1] — 2026-06-11

First alpha of the v0.3 *audit-grade moat* cycle. Phase 1 of 5: **built-in
logging**. Previous versions emitted zero output by default — users had to
install `personakit[otel]` and configure exporters to get any visibility. This
release adds a standard Python `logging` integration that's silent by default
but trivially opt-in.

### Added

- **`personakit._logging` module** — central logger setup using the standard
  Python `logging` module. A `NullHandler` is attached to the
  `personakit` logger at import time so library users never see "no handler"
  warnings.
- **`enable_verbose_logging(level="INFO", *, stream=None, fmt=None)`** — public
  helper that attaches a `StreamHandler` to the personakit logger.
  Idempotent (safe to call twice) and accepts either an `int` or
  case-insensitive `str` level. Defaults to `sys.stderr`.
- **`get_logger(name)`** — public helper returning the personakit logger,
  optionally namespaced (`get_logger("agent")` → `personakit.agent`).
- **`Agent(..., verbose: bool = False)`** — convenience flag. `verbose=True`
  calls `enable_verbose_logging("INFO")` automatically.
- **Lifecycle log events** in `Agent.analyze()`:
  - `INFO`  — Agent constructed, analyze started, analyze done (with duration,
                token count, recommendation count, red-flag count).
  - `INFO`  — pre-match red flag hits (with the matched triggers).
  - `DEBUG` — every provider call (iteration, provider name, model, message
                count, duration, usage, tool_calls_count).
  - `DEBUG` — every tool invocation (name, known flag, duration).
  - `WARNING` — unknown tool requested by LLM, or tool raised an exception.
- **`pythonpath = ["src"]`** added to `[tool.pytest.ini_options]` so tests run
  reliably even when macOS occasionally re-flags the editable `.pth` file as
  hidden.

### Tests

- `tests/test_logging.py` — 9 new tests covering: NullHandler attached by
  default, `get_logger` namespacing, `enable_verbose_logging` writes to the
  provided stream, idempotency, int/string level acceptance, invalid level
  rejection, `Agent.__init__` emits an INFO log, `verbose=True` attaches a
  handler, and `analyze()` emits the started / provider call / done lifecycle
  logs.

### Numbers

- 102 tests passing (was 93)
- `mypy --strict` clean across **30** source files (was 29)
- `ruff` clean

## [0.2.1] — 2026-04-27

### Changed

- **README brought fully into sync with v0.2.** Stale references that had
  accumulated across the v0.1.x cycle (test counts, version numbers, source
  file counts, the `dev` extras list) were all updated. No code changes —
  this release exists purely so the corrected README renders on PyPI.
- The "What personakit IS" block now lists the v0.2 production wiring
  (streaming, OpenTelemetry hooks, cost tracking, conversational sessions,
  multi-turn tool loop, web knowledge tools) up front so first-time PyPI
  visitors see the production story before scrolling.
- FAQ expanded with five new entries: streaming, observability stack
  integration, cost tracking, multi-turn conversations, and an updated
  "is it production-ready?" answer reflecting the new state.
- Contributing section's quality-gate snippet updated to "93 passing /
  29 source files" and the dev-extras command now includes `web,otel`.
- Status section now reads "v0.2.0 — alpha" with the actual production
  posture instead of a generic "alpha — API may evolve."

## [0.2.0] — 2026-04-27

The first MINOR release. Closes the four "table-stakes" gaps that were
keeping personakit behind the broader ecosystem on basics. Together they
make the package genuinely production-ready alongside its differentiating
features (red flags, declarative specialists, audit-grade output).

### Added

#### Streaming — `Agent.analyze_stream(text)`

Live, event-driven analysis. Yields a typed `StreamEvent` stream:

- `red_flag_pre_match` — fires immediately for deterministic regex hits
- `text_delta` — text fragments as the LLM streams its response
- `tool_call` / `tool_result` — wrap each tool invocation in the loop
- `iteration_complete` — marks each tool-loop round
- `complete` — carries the full `AnalyzeResult` at the end
- `error` — surfaces stream-level failures

Native streaming on **OpenAI**, **Anthropic** (with `tool_use` /
`tool_result` content-block translation), **LiteLLM** (100+ providers),
and **MockProvider** (chunk-based simulation for tests).

#### OpenTelemetry hooks — `personakit.observability`

Three tracer span points wrap every `Agent.analyze` call:

  - `personakit.analyze` — the top-level invocation
  - `personakit.provider.complete` — every LLM round-trip
  - `personakit.tool.invoke` — every tool execution

`Tracer` is a Protocol — write your own (~30 lines) or plug in
`OpenTelemetryTracer` via the new `personakit[otel]` extra. Default is
`NullTracer` (no-op). Spans carry attributes for specialist name, provider,
token usage, tool name, and known/unknown tool flag.

#### Token cost tracking — `personakit.cost`

`AnalyzeResult.estimated_cost_usd` returns a USD float (or `None` for
unknown models). Pricing tables shipped for ~25 popular models across
OpenAI, Anthropic, Google Gemini, Groq, DeepSeek, Mistral, plus zero-cost
entries for Ollama / local models.

`register_pricing(model, input_per_1m, output_per_1m)` lets callers add
custom or self-hosted rates. Prefix-matching means dated model ids like
`gpt-4o-2024-08-06` resolve correctly to the base `gpt-4o` rate.

`AnalyzeResult.model` is now populated for cost lookup.

#### Conversational sessions — `ConversationalAgent` + `Session`

Multi-turn agents with persistent history. `Session.send(message)` wraps
each `analyze` call with the prior conversation as context.
`Session.serialize()` / `Session.deserialize()` for caller-managed
persistence (Redis / Postgres / file — your choice). `Session.chat()` for
free-form replies that bypass the structured-output pipeline.

`max_history_turns` configurable per agent (default 12). `session.reset()`
clears state.

### New extras

- `pip install 'personakit[otel]'` — opentelemetry-api / opentelemetry-sdk

### Public API additions

```python
from personakit import (
    # Streaming
    StreamEvent,
    # Observability
    Tracer, NullTracer, OpenTelemetryTracer,
    # Sessions
    ConversationalAgent, Session, SessionTurn,
)
```

### Tests

- 32 new tests across streaming, observability, cost, sessions
- 93/93 unit tests passing (up from 61)
- Mock-driven: zero network, zero API keys required

### Quality

- mypy --strict: Success on 29 source files
- ruff: clean
- twine check: PASSED
- No breaking changes — code written against v0.1.x continues to work
  identically. New methods (`analyze_stream`) and parameters (`tracer`,
  `max_history_turns`) are additive.

## [0.1.8] — 2026-04-27

### Added — Real-time web knowledge from URLs

The headline feature: **personakit can now use any URL as an external
knowledge source**, in two complementary patterns, across all providers.

- **Pattern A — pre-fetch.** Fetch a URL yourself with `fetch_url.invoke()`
  and pass the content to `Agent.analyze(extra_context=...)`. Single LLM
  call, deterministic, no token spent on the model deciding whether to fetch.
- **Pattern B — autonomous tool loop.** Attach the web tools via
  `Agent.with_tools([...])` and let the LLM decide when to fetch. The new
  multi-turn tool loop in `Agent.analyze()` invokes the tool, feeds the
  result back, and repeats until the LLM produces the final structured
  response (or `max_tool_iterations` is reached).

#### `personakit.web` module — opt-in via `personakit[web]`

```bash
pip install 'personakit[web]'
```

Four ready-made tools:

| Tool | Purpose |
| --- | --- |
| `fetch_url(url, max_chars=8000)` | HTTP GET + text extraction (BeautifulSoup) |
| `extract_article(url, max_chars=12000)` | Smart article extraction (trafilatura) |
| `tavily_search(query, max_results=5)` | LLM-optimised web search (Tavily API) |
| `serper_search(query, max_results=5)` | Google SERP search (Serper API) |

All four are typed, documented, gracefully handle missing API keys, and
return structured dicts.

#### Multi-turn tool-calling loop in `Agent.analyze()`

Previously the Agent forwarded tool schemas to the LLM but did not auto-loop
the execution. v0.1.8 closes that gap with a real loop:

1. Provider returns `tool_calls` in the response
2. Agent looks up each tool by name in `self.tools`
3. Parses arguments, invokes locally (sync or async)
4. Appends an assistant message (with `tool_calls`) and one `role="tool"`
   message per result to the conversation history
5. Calls the provider again with the augmented history
6. Repeats until no `tool_calls` are emitted, or `max_tool_iterations` is
   reached

Tool errors and unknown-tool requests are reported back to the LLM as
structured error payloads — they don't crash the agent. Token usage is
accumulated across iterations and surfaced via `result.usage`.

The loop is **identical across providers**:

- **OpenAI** — native `tool_calls` array
- **LiteLLM** — same OpenAI shape (so 100+ providers work)
- **Anthropic** — translated to and from `tool_use` / `tool_result` content
  blocks. New `_to_anthropic_message()` and `_to_anthropic_tools()` helpers
  in `providers/anthropic.py` handle the format conversion bidirectionally.
- **MockProvider** — extended to accept `LLMResponse` instances and
  `tool_calls`-shaped dicts in its response queue, so multi-turn tool-call
  scenarios are testable without a network.

#### `Message.tool_calls` field

The provider-agnostic `Message` model now includes an optional `tool_calls`
list to carry the LLM's tool requests through the conversation. Backward
compatible — `content` retains its default of `""`, and existing code that
doesn't set `tool_calls` continues to work unchanged.

#### `Agent(max_tool_iterations=6)`

New constructor parameter (and `Agent.with_tools()` propagates it). Caps the
tool-loop iterations to prevent runaway cost if the LLM keeps requesting
tools. Default 6.

### Tests

- 7 new tests in `tests/test_tool_loop.py` covering: 2-turn flow, unknown
  tool resilience, tool exception resilience, max iterations cap, usage
  accumulation, no-tools-attached compatibility, async tool support.
- 10 new tests in `tests/test_web_tools.py` covering: `fetch_url`
  extraction / truncation / HTTP error handling / schema correctness;
  `tavily_search` and `serper_search` endpoint correctness, missing-API-key
  errors, max_results clamping; cross-tool exports.
- All HTTP calls are mocked at the `httpx` level — tests run offline in
  CI, no real network.
- 61/61 unit tests passing (up from 44).

### Changed

- `MockProvider.responses` now accepts `LLMResponse` instances directly,
  alongside strings and dicts. This lets tests construct precise multi-turn
  tool-call scenarios.
- `pyproject.toml`: new optional extra `personakit[web]` requiring
  `beautifulsoup4>=4.12` and `trafilatura>=1.6`. Added to the `all` extra.

### Compatibility

No breaking changes. Code written against v0.1.7 continues to work
identically — the tool loop only kicks in when tools are attached to the
Agent and the LLM emits tool_calls. Single-shot behaviour is preserved
when `tools=[]` (the no-tools case bypasses the loop after one iteration).

## [0.1.7] — 2026-04-27

### Added
- **Logo.** A new `assets/logo.png` ships with the repository (the layered
  hexagon mark in navy + teal + coral). It's referenced from the README via
  a raw GitHub URL so it renders correctly on the PyPI project page.
- **Centered hero block** at the top of the README — logo, tagline, badges,
  and a quick-link nav row (Why · Quickstart · Specialists · Providers ·
  FAQ · GitHub).
- **`Contributing` section** with concrete dev-setup commands, quality
  gates (pytest, mypy --strict, ruff, build), and a list of high-leverage
  contribution areas (new bundled specialists, bug reports, docs).
- **`Privacy` section** — explicit statement that personakit collects no
  telemetry and makes no network calls outside the LLM provider you
  configure. Trust signal for compliance-sensitive adopters.
- **Downloads badge** added to the badges row.
- FAQ expanded from 5 to 9 entries — added "Does it work with LiteLLM?",
  "Do I need to be a Python expert?", "Is there commercial support?", and
  "Can I contribute?". Stale numbers updated (44 tests, 25 source files).

### Changed
- **README narrative reordered.** "Why personakit?" promoted from buried
  position #8 to position #3, immediately after the IS / IS-NOT block —
  readers now see the value proposition before the quickstart, matching
  professional reader-journey flow (skim → evaluate → adopt → contribute).
  FAQ moved from position #5 to position #15 (it's reference, not pitch).

### Polished
- Visual hierarchy throughout — proper section spacing, aligned tables,
  consistent code-block language tags. The README now reads as a product
  page rather than a developer's notes.

No code changes. README / metadata patch only. 44 tests still pass; mypy
--strict clean.

## [0.1.6] — 2026-04-24

### Changed
- **README — domain-neutral repositioning of the "why" section.** External
  reviewers had been reading personakit as a tool for "code review, fintech,
  customer support, or scrum" because the same four examples kept appearing
  in multiple sections. The new "Why personakit?" section foregrounds the
  universal pattern (a role + knowledge bodies + diagnostic questions +
  safety triggers + output categories) that applies to *any* specialist
  domain, and lists ten different role-types in a single sweeping sentence
  ("legal review, clinical triage, financial audit, research evaluation,
  product spec, engineering review, customer support, content moderation,
  sales qualification, coursework grading, and any of a thousand other
  roles") so no single domain dominates.
- Removed the "How it works" ASCII-diagram section. The data flow it showed
  was already implicit in the 30-second quickstart, the "What personakit IS"
  block, and the "Why personakit?" section — the diagram was redundant and
  read as low-effort compared to the surrounding sections.

No code changes. README / metadata only.

## [0.1.5] — 2026-04-24

### Added
- **`LiteLLMProvider`** — a new provider adapter that wraps
  [LiteLLM](https://github.com/BerriAI/litellm) and unlocks 100+ LLM
  providers through a single extra: OpenAI, Anthropic, Azure OpenAI, AWS
  Bedrock, Google Vertex AI, Cohere, Mistral, Hugging Face, Ollama,
  DeepSeek, Together AI, Groq, Fireworks, Anyscale, and any
  OpenAI-compatible endpoint. Install with `pip install 'personakit[litellm]'`.
  Switching providers is a one-line change to the model string.
- New optional extra `personakit[litellm]` requiring `litellm>=1.40`.
- `litellm.*` added to the mypy `ignore_missing_imports` override so the
  core still type-checks without the optional SDK installed.
- 8 new tests in `tests/test_providers_litellm.py` using a mock client —
  exercises basic round-trip, model override, response-schema forwarding,
  api_key / api_base routing, extra defaults passthrough, tool-call
  extraction, upstream-exception wrapping, and the missing-dependency error.
- README gains a "100+ providers via LiteLLM" section with concrete
  examples for Bedrock, Azure, Vertex AI, Ollama, and Groq.

### Tests
- 44/44 unit tests passing (up from 36).

## [0.1.4] — 2026-04-24

### Fixed
- **`mypy --strict` now passes with zero errors** (was 12 errors in 7 files).
  No runtime behaviour changes — purely type-hint cleanups:
  - `specialist.py` — `_check_unique_keys` now filters `None` before `sorted()`
    so the error-message construction is well-typed. The set of duplicates was
    already guaranteed to be non-`None` via `_fill_key` / `_fill_id` validators,
    but mypy couldn't see that — explicit filter makes it provable.
  - `prompt_builder.py` — `probe_props[p.key]` now uses `cast(str, p.key)`
    since the Probe validator guarantees the key is non-null at runtime.
  - `providers/base.py` — `LLMProvider.complete` Protocol signature widened to
    `model: str | None = None`. This matches every concrete implementation
    (`OpenAIProvider`, `AnthropicProvider`, `MockProvider`) — they already
    handle `None` by falling back to their configured `default_model`. The
    Protocol was just stricter than reality.
  - `agent.py` — `_parse_json` now uses `cast(dict[str, Any], json.loads(...))`
    at the two return sites, since `json.loads` returns `Any`.
  - `tools.py` — `_annotation_to_json` wraps `get_args(annotation)` in
    `list(...)` for the list branch, matching the `list[Any]` type previously
    inferred by the union branch.
  - `loaders.py`, `providers/openai.py`, `providers/anthropic.py` — removed
    three redundant `# type: ignore` comments. The same modules are already
    covered by `[[tool.mypy.overrides]] ignore_missing_imports = true` in
    `pyproject.toml`.

### Tests
- 36/36 unit tests passing (unchanged — no behaviour delta).

## [0.1.3] — 2026-04-24

### Changed
- **PyPI description** rewritten to disambiguate from personality classifiers
  (MBTI, Big Five). The new line leads with "A declarative framework for
  building role-based LLM agents — code reviewers, compliance officers,
  clinical triage, support triage. Not a personality classifier; an agent
  builder." External reviewers had been confusing personakit with
  `pypersonality` / `persai`-class libraries.
- **README opening** restructured for scannability: badges row, a
  "What personakit IS / what it is NOT" block, a 30-second quickstart
  above the fold, an ASCII architecture flow diagram, a 7-row bundled
  specialists table, and a FAQ section covering the top three external
  questions (is this a personality classifier? / RAG? / vs LangChain?).
- Removed duplicated Quickstart and Bundled Specialists sections lower in
  the README; top-of-page versions are authoritative.

No code changes. README / metadata patch only.

## [0.1.2] — 2026-04-24

### Changed
- README rewritten with a value-forward opening. The package is now introduced
  by what it does, not in comparison to LangChain / CrewAI / LangGraph. A
  "Works alongside" section at the bottom positions those libraries as
  complementary tools rather than competitors.
- PyPI short description reworked into platform framing — emphasises "build
  any specialist agent" rather than listing specific verticals. No more
  implicit domain bias.

No code changes. Metadata-only patch release.

## [0.1.1] — 2026-04-24

### Added
- `CODE_REVIEWER` — senior staff engineer, PR review. OWASP + SOLID + 12-Factor.
- `FINTECH_TRANSACTION_REVIEWER` — AML / fraud transaction analyst. BSA/AML,
  OFAC, FATF typologies, FinCEN SAR filing guidance.
- `CUSTOMER_SUPPORT_TRIAGE` — SaaS B2C support triage with refund policy,
  chargeback escalation, and data-request routing.
- `SCRUM_MASTER` — sprint health reviewer. Scope creep, WIP limits, blockers,
  carryover trends, ceremonies.
- Regression tests in `tests/test_tools.py` covering stringified annotations
  (PEP 563 / `from __future__ import annotations`) and PEP 604 unions.

### Fixed
- **`@tool` decorator now correctly resolves stringified type annotations**
  (`from __future__ import annotations`). Previously, `int`, `float`, `bool`,
  and `list[...]` params serialised as `{"type": "string"}` because
  `inspect.Parameter.annotation` returned the raw string rather than the
  resolved type. Now uses `typing.get_type_hints()` for correct JSON schema.
- `@tool` with PEP 604 `X | None` union syntax now correctly produces
  `"nullable": True` (previously only recognised `typing.Union[X, None]`).

### Changed
- README rewritten around the domain-neutral pitch. Engineering, fintech,
  customer support, product, scrum, legal, clinical, and education examples
  are all first-class in the docs — no single domain leads.
- PyPI description and keywords expanded to cover all supported domains
  (`fintech`, `code-review`, `customer-support`, `scrum`, `aml`, etc.).

## [0.1.0] — 2026-04-24

### Added
- `Specialist` — declarative agent definition with persona, frameworks, probes,
  red flags, recommendation themes, priorities, taxonomies, and focus areas.
- `Probe`, `Framework`, `RedFlag`, `Theme`, `Severity`, `FocusAreas` primitives.
- `Agent` runtime with async `analyze()` and `chat()` entry points.
- Red flag matching in two phases: deterministic regex/keyword pre-match and
  LLM semantic post-match. Results are merged and de-duplicated.
- `PromptBuilder` — deterministic translation from `Specialist` to an XML-style
  system prompt plus an auto-derived JSON output schema.
- Provider adapters: `OpenAIProvider`, `AnthropicProvider`, `MockProvider`.
- `SpecialistRegistry` for multi-specialist applications.
- YAML / JSON / dict loaders — authorable by non-coders.
- Opt-in `@tool` decorator and `ToolBox` — zero coupling when unused.
- Testing helpers: `MockProvider`, structural assertions.
- Bundled examples: falls prevention nurse, contract reviewer, math tutor.
