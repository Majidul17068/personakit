# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
