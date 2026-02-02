"""
Graph Emitter: Store compiled graph in the Trinity databases.

Writes to all three databases:
- LanceDB: Node/edge resonance vectors for similarity search
- DuckDB: Catalog metadata for SQL analytics
- Kuzu: Graph topology for Cypher traversal
"""

from typing import List

from dto.node import FireflyNode
from dto.edge import FireflyEdge
from storage.store import FireflyStore


class GraphEmitter:
    """
    Emit a compiled graph to the Trinity storage layer.
    """

    def __init__(self, store: FireflyStore):
        self.store = store

    async def emit(
        self,
        nodes: List[FireflyNode],
        edges: List[FireflyEdge],
        dto_id: str = "",
    ) -> dict:
        """
        Store all nodes and edges in the Trinity databases.

        Returns summary statistics.
        """
        stored_nodes = 0
        stored_edges = 0
        errors = []

        # Store nodes
        for node in nodes:
            try:
                await self.store.store_node(node)
                stored_nodes += 1
            except Exception as e:
                errors.append(f"Node {node.id}: {e}")

        # Store edges
        for edge in edges:
            try:
                await self.store.store_edge(edge)
                stored_edges += 1
            except Exception as e:
                errors.append(f"Edge {edge.id}: {e}")

        return {
            "dto_id": dto_id,
            "nodes_stored": stored_nodes,
            "edges_stored": stored_edges,
            "total_size_kb": stored_nodes * 1.25,
            "errors": errors,
        }

    async def emit_dto_catalog(
        self,
        dto_id: str,
        table_name: str,
        fields: dict,
        source_file: str,
        entry_nodes: dict,
    ):
        """
        Store DTO catalog entry in DuckDB.

        This maps a DTO (e.g., WorkPackage) to its entry point nodes.
        """
        if not self.store.duck:
            return

        import json
        self.store.duck.execute("""
            CREATE TABLE IF NOT EXISTS dto_catalog (
                id VARCHAR PRIMARY KEY,
                table_name VARCHAR,
                fields JSON,
                source_file VARCHAR,
                entry_create VARCHAR,
                entry_update VARCHAR,
                entry_destroy VARCHAR
            )
        """)

        self.store.duck.execute("""
            INSERT OR REPLACE INTO dto_catalog
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            dto_id,
            table_name,
            json.dumps(fields),
            source_file,
            entry_nodes.get("create", ""),
            entry_nodes.get("update", ""),
            entry_nodes.get("destroy", ""),
        ])
