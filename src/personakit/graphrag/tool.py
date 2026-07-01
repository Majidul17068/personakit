"""Tool factory that lets a specialist agent query a ``GraphStore``.

``build_graph_query_tool`` wraps any ``GraphStore`` in a ``personakit.Tool`` so
it can be passed to ``Agent.with_tools(...)``. The LLM sees an OpenAI-style
function schema with a single ``cypher`` argument; each invocation runs against
the injected store and returns JSON-safe records.

This is the lowest-level entrypoint. Later phases will add safer wrappers on
top (e.g. an LLM that only ever emits parameterised, schema-checked Cypher).
"""

from __future__ import annotations

from typing import Any

from ..tools import Tool
from .store import GraphStore, QueryResult

DEFAULT_TOOL_NAME = "graph_query"
DEFAULT_TOOL_DESCRIPTION = (
    "Execute a Cypher query against the connected graph database and return "
    "the result rows. Prefer read-only MATCH/RETURN queries; every row is a "
    "dict of column name -> value with Node/Relationship/Path objects "
    "serialised as plain dicts."
)


def build_graph_query_tool(
    store: GraphStore,
    *,
    name: str = DEFAULT_TOOL_NAME,
    description: str = DEFAULT_TOOL_DESCRIPTION,
    max_records: int | None = 100,
) -> Tool:
    """Build a personakit ``Tool`` that queries ``store``.

    Parameters
    ----------
    store
        Any ``GraphStore`` implementation (e.g. ``Neo4jGraphStore``).
    name
        Tool name reported to the LLM. Defaults to ``"graph_query"``.
    description
        Description surfaced in the tool schema.
    max_records
        Optional cap on the number of records returned per call. Protects the
        model's context window from unexpectedly large result sets. ``None``
        disables the cap.

    Returns
    -------
    Tool
        A ``personakit.Tool`` ready to hand to ``Agent.with_tools(...)``.
    """
    if not isinstance(store, GraphStore):
        raise TypeError(
            "store must satisfy the GraphStore protocol (implements "
            "'query' and 'close')."
        )

    def _query(cypher: str) -> dict[str, Any]:
        result: QueryResult = store.query(cypher)
        records = result.records
        truncated = False
        if max_records is not None and len(records) > max_records:
            records = records[:max_records]
            truncated = True
        payload: dict[str, Any] = {
            "status": result.status,
            "records": records,
            "count": len(records),
            "duration_ms": round(result.duration_ms, 2),
        }
        if truncated:
            payload["truncated"] = True
            payload["truncated_at"] = max_records
        if result.error is not None:
            payload["error"] = result.error
        return payload

    _query.__doc__ = description
    return Tool(_query, name=name, description=description)


__all__ = ["build_graph_query_tool", "DEFAULT_TOOL_NAME", "DEFAULT_TOOL_DESCRIPTION"]
