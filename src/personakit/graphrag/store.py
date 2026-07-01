"""Graph store abstraction + default Neo4j backend for personakit GraphRAG.

The ``GraphStore`` protocol defines the contract every backend must satisfy:
execute a Cypher query, return serialisable records, close cleanly. Any
Cypher-capable graph database (Neo4j, Memgraph, AuraDB, Amazon Neptune with
openCypher) can plug in by implementing this protocol.

``Neo4jGraphStore`` is the reference implementation. It:

* Opens exactly one driver per instance (avoids per-query Bolt handshakes).
* Serialises ``Node``, ``Relationship``, and ``Path`` results into plain
  JSON-safe dicts so the records flow through personakit's Tool interface
  and LLM prompts without pickle-ing Neo4j-specific objects.
* Returns a structured ``QueryResult`` with ``status``, ``records``, and
  ``duration_ms`` — never raises on Cypher errors so callers can inspect
  and retry (mirrors personakit's tool-error contract).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .._logging import get_logger

_log = get_logger("graphrag.store")


@dataclass
class QueryResult:
    """The return value of ``GraphStore.query``.

    Attributes
    ----------
    status
        ``"success"`` when the query executed, ``"error"`` otherwise.
    records
        List of dict-shaped rows. Nodes / relationships / paths are already
        serialised into plain dicts (see ``_serialize_value``).
    query
        The Cypher string that was executed (for auditability / logging).
    duration_ms
        Wall-clock time the query took, measured client-side.
    error
        Present only when ``status == "error"``; the exception message.
    """

    status: str
    records: list[dict[str, Any]] = field(default_factory=list)
    query: str = ""
    duration_ms: float = 0.0
    error: str | None = None

    def __len__(self) -> int:
        return len(self.records)

    @property
    def ok(self) -> bool:
        return self.status == "success"


@runtime_checkable
class GraphStore(Protocol):
    """Contract every graph backend must satisfy.

    Implementations are expected to hold a persistent connection for the
    lifetime of the instance and release it in ``close``. Callers may use
    the store as a context manager.
    """

    def query(self, cypher: str, **parameters: Any) -> QueryResult:
        """Execute a read/write Cypher query and return structured records."""
        ...

    def close(self) -> None:
        """Release the underlying connection / driver."""
        ...


class Neo4jGraphStore:
    """Reference ``GraphStore`` implementation targeting Neo4j.

    Requires ``pip install personakit[graphrag]`` (which pulls in
    ``neo4j>=5.20``). Constructor accepts either explicit connection
    parameters or reads them from the standard Neo4j environment variables
    (``NEO4J_URI``, ``NEO4J_USERNAME``, ``NEO4J_PASSWORD``).
    """

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        *,
        database: str | None = None,
    ) -> None:
        import os

        try:
            from neo4j import GraphDatabase
        except ImportError as exc:
            raise ImportError(
                "Neo4jGraphStore requires the 'neo4j' package. "
                "Install with: pip install 'personakit[graphrag]'"
            ) from exc

        self._uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self._username = username or os.getenv("NEO4J_USERNAME", "neo4j")
        self._password = password or os.getenv("NEO4J_PASSWORD", "neo4j")
        self._database = database
        self._driver = GraphDatabase.driver(
            self._uri, auth=(self._username, self._password)
        )
        _log.info(
            "Neo4jGraphStore connected: uri=%s database=%s",
            self._uri,
            self._database or "(default)",
        )

    def query(self, cypher: str, **parameters: Any) -> QueryResult:
        started = time.perf_counter()
        try:
            with self._driver.session(database=self._database) as session:
                result = session.run(cypher, parameters)
                records = [
                    {key: _serialize_value(value) for key, value in record.items()}
                    for record in result
                ]
            duration_ms = (time.perf_counter() - started) * 1000
            _log.debug(
                "query ok: rows=%d duration_ms=%.1f",
                len(records),
                duration_ms,
            )
            return QueryResult(
                status="success",
                records=records,
                query=cypher,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            _log.warning("query failed: %s", exc)
            return QueryResult(
                status="error",
                records=[],
                query=cypher,
                duration_ms=duration_ms,
                error=str(exc),
            )

    def close(self) -> None:
        if self._driver is not None:
            self._driver.close()
            _log.info("Neo4jGraphStore closed")

    def __enter__(self) -> Neo4jGraphStore:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


def _serialize_value(value: Any) -> Any:
    """Convert Neo4j Node / Relationship / Path objects into plain dicts.

    This is intentionally lazy about imports — the ``neo4j`` package is an
    optional dep, so we only try to import its classes when we're actually
    handed a value we don't already know how to serialise.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}

    try:
        from neo4j.graph import Node, Path, Relationship
    except ImportError:
        return str(value)

    if isinstance(value, Node):
        return {
            "_type": "Node",
            "id": getattr(value, "element_id", None),
            "labels": list(value.labels),
            "properties": dict(value.items()),
        }
    if isinstance(value, Relationship):
        start = getattr(value.start_node, "element_id", None) if value.start_node else None
        end = getattr(value.end_node, "element_id", None) if value.end_node else None
        return {
            "_type": "Relationship",
            "id": getattr(value, "element_id", None),
            "type": value.type,
            "start_node_id": start,
            "end_node_id": end,
            "properties": dict(value.items()),
        }
    if isinstance(value, Path):
        return {
            "_type": "Path",
            "nodes": [_serialize_value(n) for n in value.nodes],
            "relationships": [_serialize_value(r) for r in value.relationships],
        }
    return str(value)
