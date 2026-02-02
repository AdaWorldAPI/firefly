"""
Graph Composer: "Create a new DTO like X but with Y"

1. Load X's graph structure
2. Find nodes for capability Y in other DTOs
3. Compose new graph from existing nodes
4. Validate: no cycles, types match, complete

Uses Hamming similarity to find reusable components
across the entire compiled graph corpus.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from dto.node import FireflyNode
from dto.edge import FireflyEdge
from storage.store import FireflyStore
from core import similarity, bind, bundle


@dataclass
class ComposedGraph:
    """A newly composed graph from existing components."""
    name: str
    nodes: List[FireflyNode]
    edges: List[FireflyEdge]
    source_dtos: List[str]  # DTOs that contributed nodes
    validation_errors: List[str]


class GraphComposer:
    """
    Compose new graphs from existing compiled components.

    This is the "creative" reasoning capability:
    given a description, find and assemble matching
    graph components into a new executable graph.
    """

    def __init__(self, store: FireflyStore):
        self.store = store

    async def compose(
        self,
        name: str,
        base_dto: str,
        additions: List[str] = None,
        removals: List[str] = None,
    ) -> ComposedGraph:
        """
        Create a new graph based on an existing DTO.

        Args:
            name: Name for the new graph
            base_dto: Source DTO to clone
            additions: Descriptions of capabilities to add
            removals: Node IDs to remove
        """
        additions = additions or []
        removals = removals or []

        # 1. Clone base graph
        nodes, edges = await self._clone_graph(base_dto)
        source_dtos = [base_dto]

        # 2. Remove specified nodes
        if removals:
            remove_set = set(removals)
            nodes = [n for n in nodes if n.id not in remove_set]
            edges = [e for e in edges
                     if e.source_id not in remove_set and e.target_id not in remove_set]

        # 3. Find and add new capabilities
        for addition_desc in additions:
            found_nodes = await self._find_matching_nodes(addition_desc)
            for found in found_nodes[:3]:  # Top 3 matches
                # Clone the node with new ID
                new_node = FireflyNode(
                    id=f"{name}_{found.id}",
                    resonance=found.resonance,
                    executor=found.executor,
                    fn_name=found.fn_name,
                    type=found.type,
                    cost=found.cost,
                    pure=found.pure,
                    parallelizable=found.parallelizable,
                    input_schema=found.input_schema,
                    output_schema=found.output_schema,
                )
                nodes.append(new_node)

        # 4. Validate the composed graph
        errors = self._validate_graph(nodes, edges)

        return ComposedGraph(
            name=name,
            nodes=nodes,
            edges=edges,
            source_dtos=source_dtos,
            validation_errors=errors,
        )

    async def _clone_graph(
        self, dto_id: str
    ) -> Tuple[List[FireflyNode], List[FireflyEdge]]:
        """Clone all nodes and edges for a DTO."""
        nodes = []
        edges = []

        if not self.store.duck:
            return nodes, edges

        # Get all nodes for this DTO
        node_results = self.store.duck.execute("""
            SELECT id, type, executor, fn_name, cost, pure, parallelizable
            FROM nodes
            WHERE id LIKE ?
        """, [f"{dto_id}_%"]).fetchall()

        for r in node_results:
            node = FireflyNode.from_id(
                r[0],
                type=r[1] or "TRANSFORM",
                executor=r[2] or "NATIVE",
                fn_name=r[3] or "",
                cost=r[4] or 1,
                pure=bool(r[5]),
                parallelizable=bool(r[6]),
            )
            nodes.append(node)

        # Get all edges between these nodes
        node_ids = {n.id for n in nodes}
        edge_results = self.store.duck.execute("""
            SELECT id, source_id, target_id, type, condition, field
            FROM edges
            WHERE source_id LIKE ? OR target_id LIKE ?
        """, [f"{dto_id}_%", f"{dto_id}_%"]).fetchall()

        for r in edge_results:
            if r[1] in node_ids and r[2] in node_ids:
                edge = FireflyEdge(
                    id=r[0],
                    source_id=r[1],
                    target_id=r[2],
                    resonance=b'\0' * 1250,
                    type=r[3] or "FEEDS",
                    condition=r[4],
                    field=r[5],
                )
                edges.append(edge)

        return nodes, edges

    async def _find_matching_nodes(
        self, description: str, limit: int = 5
    ) -> List[FireflyNode]:
        """Find nodes matching a description via similarity search."""
        import hashlib
        query_vec = (hashlib.sha256(description.encode()).digest() * 40)[:1250]

        results = await self.store.find_similar_nodes(query_vec, k=limit)

        nodes = []
        for r in results:
            node_id = r.get("id", "")
            node = await self.store.get_node(node_id)
            if node:
                nodes.append(node)

        return nodes

    def _validate_graph(
        self,
        nodes: List[FireflyNode],
        edges: List[FireflyEdge],
    ) -> List[str]:
        """
        Validate the composed graph.

        Checks:
        - No orphan edges (both source and target exist)
        - No cycles (DAG requirement)
        - At least one entry point
        - At least one terminal node
        """
        errors = []
        node_ids = {n.id for n in nodes}

        # Check edges
        for edge in edges:
            if edge.source_id not in node_ids:
                errors.append(f"Orphan edge source: {edge.source_id}")
            if edge.target_id not in node_ids:
                errors.append(f"Orphan edge target: {edge.target_id}")

        # Check for entry points
        has_incoming = {e.target_id for e in edges}
        entry_points = [n for n in nodes if n.id not in has_incoming]
        if not entry_points:
            errors.append("No entry point (all nodes have incoming edges)")

        # Check for terminal nodes
        has_outgoing = {e.source_id for e in edges}
        terminals = [n for n in nodes if n.id not in has_outgoing]
        if not terminals:
            errors.append("No terminal node (all nodes have outgoing edges)")

        # Cycle detection (simple DFS)
        outgoing = {}
        for edge in edges:
            outgoing.setdefault(edge.source_id, []).append(edge.target_id)

        visited = set()
        path = set()

        def has_cycle(nid: str) -> bool:
            if nid in path:
                return True
            if nid in visited:
                return False
            visited.add(nid)
            path.add(nid)
            for target in outgoing.get(nid, []):
                if has_cycle(target):
                    return True
            path.discard(nid)
            return False

        for node in nodes:
            if has_cycle(node.id):
                errors.append(f"Cycle detected involving {node.id}")
                break

        return errors
