# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
