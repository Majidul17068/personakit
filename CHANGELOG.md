# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/) and this
project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
