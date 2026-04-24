# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
