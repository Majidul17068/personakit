from __future__ import annotations


class PersonakitError(Exception):
    """Base class for all personakit errors."""


class SpecialistValidationError(PersonakitError):
    """Raised when a Specialist fails structural validation."""


class ProviderError(PersonakitError):
    """Raised when an LLM provider call fails or returns malformed content."""


class MissingDependencyError(PersonakitError):
    """Raised when an optional provider dependency is not installed."""


class OutputParseError(PersonakitError):
    """Raised when the LLM output cannot be parsed against the expected schema."""


class CitationMissingError(PersonakitError):
    """Raised when citations_required=True and no citations were produced."""


class RegistryError(PersonakitError):
    """Raised for specialist registry lookup / conflict errors."""


class ToolError(PersonakitError):
    """Raised for tool registration or invocation failures."""
