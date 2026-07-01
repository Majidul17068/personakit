"""Tests for ``build_graph_query_tool``.

The factory wraps a ``GraphStore`` in a ``personakit.Tool``. The tool exposes
an OpenAI-style function schema with a single ``cypher`` argument and returns
a JSON-safe payload that a specialist can hand back to the model.
"""

from __future__ import annotations

from typing import Any

import pytest

from personakit.graphrag import (
    DEFAULT_TOOL_DESCRIPTION,
    DEFAULT_TOOL_NAME,
    QueryResult,
    build_graph_query_tool,
)
from personakit.tools import Tool


class _FakeStore:
    def __init__(self, result: QueryResult) -> None:
        self._result = result
        self.last_cypher: str | None = None

    def query(self, cypher: str, **_: Any) -> QueryResult:
        self.last_cypher = cypher
        return self._result

    def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_tool_returns_success_payload_with_records():
    result = QueryResult(
        status="success",
        records=[{"name": "ACME"}, {"name": "GLOBEX"}],
        query="MATCH (c:Company) RETURN c.name AS name",
        duration_ms=4.321,
    )
    store = _FakeStore(result)
    graph_tool = build_graph_query_tool(store)

    payload = await graph_tool.invoke(cypher="MATCH (c:Company) RETURN c.name AS name")

    assert payload["status"] == "success"
    assert payload["count"] == 2
    assert payload["records"][0]["name"] == "ACME"
    assert payload["duration_ms"] == 4.32
    assert "truncated" not in payload
    assert store.last_cypher == "MATCH (c:Company) RETURN c.name AS name"


@pytest.mark.asyncio
async def test_tool_propagates_error_from_store():
    result = QueryResult(
        status="error",
        records=[],
        query="MATCH BAD",
        duration_ms=0.5,
        error="SyntaxError: MATCH BAD",
    )
    graph_tool = build_graph_query_tool(_FakeStore(result))

    payload = await graph_tool.invoke(cypher="MATCH BAD")

    assert payload["status"] == "error"
    assert payload["error"] == "SyntaxError: MATCH BAD"
    assert payload["records"] == []


@pytest.mark.asyncio
async def test_tool_truncates_large_result_sets():
    result = QueryResult(
        status="success",
        records=[{"i": i} for i in range(250)],
        query="MATCH (n) RETURN n",
    )
    graph_tool = build_graph_query_tool(_FakeStore(result), max_records=100)

    payload = await graph_tool.invoke(cypher="MATCH (n) RETURN n")

    assert payload["count"] == 100
    assert payload["truncated"] is True
    assert payload["truncated_at"] == 100
    assert payload["records"][-1] == {"i": 99}


@pytest.mark.asyncio
async def test_tool_respects_disabled_cap_when_max_records_none():
    result = QueryResult(
        status="success",
        records=[{"i": i} for i in range(500)],
        query="MATCH (n) RETURN n",
    )
    graph_tool = build_graph_query_tool(_FakeStore(result), max_records=None)

    payload = await graph_tool.invoke(cypher="MATCH (n) RETURN n")

    assert payload["count"] == 500
    assert "truncated" not in payload


def test_tool_reports_openai_schema_with_cypher_parameter():
    graph_tool = build_graph_query_tool(_FakeStore(QueryResult(status="success")))
    schema = graph_tool.to_openai_schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == DEFAULT_TOOL_NAME
    assert "cypher" in schema["function"]["parameters"]["properties"]
    assert schema["function"]["parameters"]["properties"]["cypher"]["type"] == "string"
    assert "cypher" in schema["function"]["parameters"]["required"]


def test_tool_uses_custom_name_and_description():
    graph_tool = build_graph_query_tool(
        _FakeStore(QueryResult(status="success")),
        name="fraud_query",
        description="Query the fraud graph.",
    )

    assert isinstance(graph_tool, Tool)
    assert graph_tool.name == "fraud_query"
    assert graph_tool.description == "Query the fraud graph."


def test_default_description_mentions_cypher_semantics():
    assert "Cypher" in DEFAULT_TOOL_DESCRIPTION
    assert "MATCH" in DEFAULT_TOOL_DESCRIPTION


def test_tool_requires_graphstore_protocol():
    with pytest.raises(TypeError, match="GraphStore protocol"):
        build_graph_query_tool(object())  # type: ignore[arg-type]
