"""personakit — declarative specialist agents for LLMs.

The public API is intentionally small. Most users need:

    from personakit import Specialist, Agent

Specialists are pure data. Agents are the runtime. Tools, loaders, provider
adapters, and testing helpers are available under their submodules.

Created by Majidul Islam (https://github.com/Majidul17068).
Licensed under MIT.
"""

from __future__ import annotations

from . import loaders as _loaders  # noqa: F401  — attaches classmethods to Specialist
from .agent import Agent
from .errors import (
    CitationMissingError,
    MissingDependencyError,
    OutputParseError,
    PersonakitError,
    ProviderError,
    RegistryError,
    SpecialistValidationError,
    ToolError,
)
from .observability import NullTracer, OpenTelemetryTracer, Tracer
from .prompt_builder import PromptBuilder
from .registry import SpecialistRegistry
from .result import AnalyzeResult, Recommendation, StreamEvent, TriggeredRedFlag
from .session import ConversationalAgent, Session, SessionTurn
from .specialist import (
    FocusAreas,
    Framework,
    MatchMode,
    Probe,
    RedFlag,
    Severity,
    Specialist,
    Theme,
)

__version__ = "0.2.0"
__author__ = "Majidul Islam"
__email__ = "contact.majidul.islam@gmail.com"
__license__ = "MIT"

__all__ = [  # noqa: RUF022 - grouped logically, not alphabetically
    # Core data
    "Specialist",
    "Framework",
    "Probe",
    "RedFlag",
    "Severity",
    "MatchMode",
    "Theme",
    "FocusAreas",
    # Runtime
    "Agent",
    "ConversationalAgent",
    "Session",
    "SessionTurn",
    "PromptBuilder",
    "SpecialistRegistry",
    # Results
    "AnalyzeResult",
    "Recommendation",
    "TriggeredRedFlag",
    "StreamEvent",
    # Observability
    "Tracer",
    "NullTracer",
    "OpenTelemetryTracer",
    # Errors
    "PersonakitError",
    "SpecialistValidationError",
    "ProviderError",
    "MissingDependencyError",
    "OutputParseError",
    "CitationMissingError",
    "RegistryError",
    "ToolError",
    # Meta
    "__version__",
]
