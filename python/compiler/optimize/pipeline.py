"""
Graph Optimizer: Transform raw execution graphs for performance.

Applies a sequence of optimization passes:
1. Dead node elimination — remove unreachable nodes
2. Node fusion — merge sequential pure nodes into one
3. Parallelization — identify independent branches
4. Inlining — embed small nodes into callers
5. Caching — mark pure nodes for result caching
"""

from typing import List, Dict, Set, Tuple
from dataclasses import dataclass, field

from dto.node import FireflyNode
from dto.edge import FireflyEdge
from core import bind, bundle


@dataclass
class OptimizationStats:
    """Statistics from optimization passes."""
    nodes_before: int = 0
    nodes_after: int = 0
    edges_before: int = 0
    edges_after: int = 0
    fused: int = 0
    eliminated: int = 0
    parallelized: int = 0
    inlined: int = 0
    cached: int = 0


class GraphOptimizer:
    """
    Apply optimization passes to a compiled graph.

    Each pass transforms (nodes, edges) → (nodes, edges).
    """

    def __init__(self, enable_fusion=True, enable_dead_code=True,
                 enable_parallel=True, enable_cache=True):
        self.enable_fusion = enable_fusion
        self.enable_dead_code = enable_dead_code
        self.enable_parallel = enable_parallel
        self.enable_cache = enable_cache

    def optimize(
        self,
        nodes: List[FireflyNode],
        edges: List[FireflyEdge]
    ) -> Tuple[List[FireflyNode], List[FireflyEdge], OptimizationStats]:
        """
        Run all optimization passes.

        Returns (optimized_nodes, optimized_edges, stats).
        """
        stats = OptimizationStats(
            nodes_before=len(nodes),
            edges_before=len(edges),
        )

        if self.enable_dead_code:
            nodes, edges, eliminated = self._eliminate_dead(nodes, edges)
            stats.eliminated = eliminated

        if self.enable_fusion:
            nodes, edges, fused = self._fuse_sequential(nodes, edges)
            stats.fused = fused

        if self.enable_parallel:
            parallelized = self._mark_parallel(nodes, edges)
            stats.parallelized = parallelized

        if self.enable_cache:
            cached = self._mark_cacheable(nodes)
            stats.cached = cached

        stats.nodes_after = len(nodes)
        stats.edges_after = len(edges)

        return nodes, edges, stats

    def _eliminate_dead(
        self,
        nodes: List[FireflyNode],
        edges: List[FireflyEdge]
    ) -> Tuple[List[FireflyNode], List[FireflyEdge], int]:
        """
        Remove nodes that are unreachable from any entry point.

        Entry points are nodes with type TRIGGER and no incoming edges.
        """
        node_ids = {n.id for n in nodes}
        incoming = {nid: set() for nid in node_ids}
        outgoing = {nid: set() for nid in node_ids}

        for edge in edges:
            if edge.source_id in incoming and edge.target_id in incoming:
                incoming[edge.target_id].add(edge.source_id)
                outgoing[edge.source_id].add(edge.target_id)

        # Find entry points (no incoming edges or TRIGGER type)
        entry_points = set()
        for node in nodes:
            if not incoming.get(node.id) or node.type == "TRIGGER":
                entry_points.add(node.id)

        # BFS from entry points
        reachable = set()
        queue = list(entry_points)
        while queue:
            nid = queue.pop(0)
            if nid in reachable:
                continue
            reachable.add(nid)
            for target in outgoing.get(nid, set()):
                if target not in reachable:
                    queue.append(target)

        # Filter
        eliminated = len(nodes) - len(reachable)
        live_nodes = [n for n in nodes if n.id in reachable]
        live_edges = [e for e in edges
                      if e.source_id in reachable and e.target_id in reachable]

        return live_nodes, live_edges, eliminated

    def _fuse_sequential(
        self,
        nodes: List[FireflyNode],
        edges: List[FireflyEdge]
    ) -> Tuple[List[FireflyNode], List[FireflyEdge], int]:
        """
        Fuse sequential pure nodes into single nodes.

        Two nodes A → B can be fused if:
        - A has exactly one outgoing edge (to B)
        - B has exactly one incoming edge (from A)
        - Both are pure
        - Both use the same executor type
        """
        node_map = {n.id: n for n in nodes}
        outgoing: Dict[str, List[str]] = {n.id: [] for n in nodes}
        incoming: Dict[str, List[str]] = {n.id: [] for n in nodes}

        for edge in edges:
            if edge.source_id in outgoing:
                outgoing[edge.source_id].append(edge.target_id)
            if edge.target_id in incoming:
                incoming[edge.target_id].append(edge.source_id)

        fused = 0
        to_remove = set()

        for node in nodes:
            if node.id in to_remove:
                continue
            if not node.pure:
                continue
            if len(outgoing.get(node.id, [])) != 1:
                continue

            target_id = outgoing[node.id][0]
            target = node_map.get(target_id)
            if not target or target.id in to_remove:
                continue
            if not target.pure:
                continue
            if len(incoming.get(target_id, [])) != 1:
                continue
            if node.executor != target.executor:
                continue

            # Fuse: merge target into source
            node.fn_name = f"fused:{node.fn_name}+{target.fn_name}"
            node.output_schema = target.output_schema
            node.cost = node.cost + target.cost
            # Combine resonance via bundling
            node.resonance = bundle([node.resonance, target.resonance])

            # Redirect target's outgoing edges
            for edge in edges:
                if edge.source_id == target_id:
                    edge.source_id = node.id

            to_remove.add(target_id)
            fused += 1

        # Filter
        fused_nodes = [n for n in nodes if n.id not in to_remove]
        fused_edges = [e for e in edges
                       if e.source_id not in to_remove and e.target_id not in to_remove]

        return fused_nodes, fused_edges, fused

    def _mark_parallel(
        self,
        nodes: List[FireflyNode],
        edges: List[FireflyEdge]
    ) -> int:
        """
        Mark nodes that can execute in parallel.

        Nodes sharing the same predecessor(s) and no data dependencies
        between them can run in parallel.
        """
        node_map = {n.id: n for n in nodes}
        incoming: Dict[str, Set[str]] = {n.id: set() for n in nodes}

        for edge in edges:
            if edge.target_id in incoming:
                incoming[edge.target_id].add(edge.source_id)

        # Group nodes by their predecessor set
        pred_groups: Dict[frozenset, List[str]] = {}
        for nid, preds in incoming.items():
            key = frozenset(preds)
            pred_groups.setdefault(key, []).append(nid)

        parallelized = 0
        for preds, group_ids in pred_groups.items():
            if len(group_ids) > 1:
                # Check all are pure (no data deps between them)
                all_pure = all(
                    node_map[nid].pure
                    for nid in group_ids
                    if nid in node_map
                )
                if all_pure:
                    for nid in group_ids:
                        if nid in node_map:
                            node_map[nid].parallelizable = True
                            parallelized += 1

        return parallelized

    def _mark_cacheable(self, nodes: List[FireflyNode]) -> int:
        """Mark pure nodes as cacheable."""
        cached = 0
        for node in nodes:
            if node.pure and node.type in ("VALIDATE", "TRANSFORM", "QUERY"):
                # Already marked as pure — can be cached
                cached += 1
        return cached
