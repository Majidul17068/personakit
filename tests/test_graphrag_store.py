"""Tests for the ``GraphStore`` protocol and its ``QueryResult`` value object.

These tests exercise the parts of ``personakit.graphrag`` that do not require
a running Neo4j instance. Backend integration (``Neo4jGraphStore.query``
against a real DB) is covered separately in the corporate-intelligence
project's end-to-end suite.
"""

from __future__ import annotations

from typing import Any

import pytest

from personakit.graphrag import GraphStore, QueryResult


class _InMemoryStore:
    """Minimal ``GraphStore`` fake used across the tool + protocol tests."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def query(self, cypher: str, **parameters: Any) -> QueryResult:
        self.calls.append((cypher, parameters))
        return QueryResult(
            status="success",
            records=list(self.rows),
            query=cypher,
            duration_ms=1.23,
        )

    def close(self) -> None:
        self.closed = True


def test_query_result_ok_flag_and_len():
    ok = QueryResult(status="success", records=[{"a": 1}, {"a": 2}])
    assert ok.ok is True
    assert len(ok) == 2

    err = QueryResult(status="error", error="boom")
    assert err.ok is False
    assert len(err) == 0


def test_query_result_defaults_are_safe():
    empty = QueryResult(status="success")
    assert empty.records == []
    assert empty.query == ""
    assert empty.duration_ms == 0.0
    assert empty.error is None


def test_inmemory_store_satisfies_protocol():
    store = _InMemoryStore()
    assert isinstance(store, GraphStore)


def test_inmemory_store_query_records_call_and_returns():
    store = _InMemoryStore(rows=[{"name": "ACME"}])
    result = store.query("MATCH (n) RETURN n LIMIT 1")

    assert result.status == "success"
    assert result.records == [{"name": "ACME"}]
    assert store.calls == [("MATCH (n) RETURN n LIMIT 1", {})]


def test_neo4j_store_missing_dep_raises_helpful_error(monkeypatch):
    """When neo4j is not installed the constructor must fail cleanly."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "neo4j" or name.startswith("neo4j."):
            raise ImportError("neo4j not installed")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from personakit.graphrag import Neo4jGraphStore

    with pytest.raises(ImportError, match="personakit\\[graphrag\\]"):
        Neo4jGraphStore(uri="bolt://localhost:7687", username="x", password="y")
