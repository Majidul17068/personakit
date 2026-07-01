"""personakit GraphRAG — graph-aware retrieval for specialist agents.

This subpackage is optional. Install with ``pip install personakit[graphrag]``
to pull in the Neo4j driver used by the default backend.

Phase 1 exposes the ``GraphStore`` protocol and the ``Neo4jGraphStore`` backend
so a specialist can execute Cypher queries and receive structured records.
Later phases will add safe LLM-driven Cypher generation (Phase 2), hybrid
vector + graph retrieval (Phase 3), and ingestion helpers (Phase 4).
"""

from __future__ import annotations

from .store import GraphStore, Neo4jGraphStore, QueryResult

__all__ = [
    "GraphStore",
    "Neo4jGraphStore",
    "QueryResult",
]
