"""Central logging setup for personakit.

personakit follows Python library best practices:

1. A single logger named ``personakit`` (plus per-module child loggers like
   ``personakit.agent``, ``personakit.providers.openai``).
2. The root ``personakit`` logger is silent by default — it attaches a
   ``NullHandler`` so users who don't configure logging don't get the dreaded
   ``No handlers could be found for logger "personakit"`` warning.
3. Users opt in to seeing logs via one of three paths:

   a. The convenience helper::

          from personakit import enable_verbose_logging
          enable_verbose_logging()           # INFO to stderr
          enable_verbose_logging("DEBUG")    # DEBUG to stderr

   b. The per-Agent flag::

          agent = Agent(specialist=spec, model="gpt-4o", verbose=True)

   c. Standard Python logging configuration::

          import logging
          logging.getLogger("personakit").setLevel(logging.DEBUG)
          logging.basicConfig(level=logging.DEBUG)

What gets logged (and at what level):

- ``INFO``  — high-level lifecycle events:
              Agent constructed, analyze() started/completed with summary stats,
              red-flag matches, fatal errors during analysis.
- ``DEBUG`` — fine-grained details:
              every provider call (model, tokens, latency), every tool
              invocation (name, duration), every pre-match attempt.

These messages form the audit trail that v0.3 builds on. Strict-mode failures
and evidence-chain records (later phases) will go through this same logger.
"""

from __future__ import annotations

import logging
import sys
from typing import IO, Final

__all__ = [
    "enable_verbose_logging",
    "get_logger",
]

_ROOT_NAME: Final[str] = "personakit"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the personakit logger, optionally namespaced by sub-module name.

    ``get_logger()`` returns the root ``personakit`` logger.
    ``get_logger("agent")`` returns ``personakit.agent`` (best practice for
    per-module loggers — keeps the call site visible in handlers).
    """
    if not name:
        return logging.getLogger(_ROOT_NAME)
    return logging.getLogger(f"{_ROOT_NAME}.{name}")


# Attach a NullHandler at import time so library users never see
# "no handler" warnings even if they never call enable_verbose_logging.
_root = logging.getLogger(_ROOT_NAME)
if not _root.handlers:
    _root.addHandler(logging.NullHandler())


def enable_verbose_logging(
    level: str | int = "INFO",
    *,
    stream: IO[str] | None = None,
    fmt: str | None = None,
) -> logging.Logger:
    """Turn on console logging for personakit.

    Idempotent — calling twice doesn't add duplicate handlers. Returns the
    configured logger so callers can chain or inspect.

    Parameters
    ----------
    level
        Logging level. Accepts an int (``logging.INFO``, 20, etc.) or a
        case-insensitive string (``"INFO"``, ``"debug"``, ``"warning"``).
    stream
        Destination stream. Defaults to ``sys.stderr``.
    fmt
        Custom format string. Defaults to a concise ``[personakit] LEVEL
        message`` layout that's easy to grep in CI logs.
    """
    logger = get_logger()

    # Normalize level: accept str or int.
    if isinstance(level, str):
        level_int = logging.getLevelName(level.upper())
        if not isinstance(level_int, int):
            raise ValueError(f"Unknown logging level: {level!r}")
    else:
        level_int = int(level)

    logger.setLevel(level_int)

    # Do nothing if a non-NullHandler StreamHandler is already attached.
    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.NullHandler
        ):
            handler.setLevel(level_int)
            return logger

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setLevel(level_int)
    handler.setFormatter(
        logging.Formatter(fmt or "[personakit] %(levelname)-5s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    # Keep messages from also bubbling to the root logger (avoids duplicate
    # output if the user already configured the root logger via basicConfig).
    logger.propagate = False
    return logger
