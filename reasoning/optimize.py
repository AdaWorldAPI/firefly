"""
Performance Optimizer: "Make this faster"

1. Query execution_log for slowest nodes
2. Find similar nodes that are faster
3. Suggest fusion/parallelization
4. Auto-apply safe optimizations
"""

from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass

from dto.node import FireflyNode
from dto.edge import FireflyEdge
from storage.store import FireflyStore


@dataclass
class OptimizationSuggestion:
    """A suggested performance optimization."""
    description: str
    impact: str  # high, medium, low
    node_ids: List[str]
    action: str  # parallelize, fuse, cache, inline
    estimated_speedup: float  # multiplier (e.g., 2.0 = 2x faster)
    auto_applicable: bool = False


class PerformanceOptimizer:
    """
    Analyze graph execution performance and suggest optimizations.
    """

    def __init__(self, store: FireflyStore):
        self.store = store

    async def analyze(self, limit: int = 10) -> List[OptimizationSuggestion]:
        """
        Analyze execution performance and generate suggestions.
        """
        suggestions = []

        # 1. Find slowest nodes
        slowest = await self.store.get_slowest_nodes(limit)
        for node_info in slowest:
            node_suggestions = await self._analyze_slow_node(node_info)
            suggestions.extend(node_suggestions)

        # 2. Find parallelization opportunities
        parallel_suggestions = await self._find_parallel_opportunities()
        suggestions.extend(parallel_suggestions)

        # 3. Find caching opportunities
        cache_suggestions = await self._find_cache_opportunities()
        suggestions.extend(cache_suggestions)

        # Sort by estimated impact
        suggestions.sort(key=lambda s: s.estimated_speedup, reverse=True)
        return suggestions[:limit]

    async def _analyze_slow_node(
        self, node_info: Dict[str, Any]
    ) -> List[OptimizationSuggestion]:
        """Analyze a slow node and suggest improvements."""
        suggestions = []
        node_id = node_info["node_id"]
        avg_ms = node_info.get("avg_duration", 0)
        failures = node_info.get("failures", 0)
        executions = node_info.get("executions", 1)

        node = await self.store.get_node(node_id)
        if not node:
            return suggestions

        # High failure rate
        if executions > 0 and failures / executions > 0.1:
            suggestions.append(OptimizationSuggestion(
                description=f"{node_id} fails {failures}/{executions} times — fix errors to avoid retry overhead",
                impact="high",
                node_ids=[node_id],
                action="fix_errors",
                estimated_speedup=1.0 + (failures / executions),
            ))

        # Slow pure node — candidate for caching
        if node.pure and avg_ms > 10:
            suggestions.append(OptimizationSuggestion(
                description=f"Cache results of pure node {node_id} (avg {avg_ms:.1f}ms)",
                impact="medium",
                node_ids=[node_id],
                action="cache",
                estimated_speedup=min(avg_ms / 0.1, 100),
                auto_applicable=True,
            ))

        # Slow SQL node — suggest indexing
        if node.executor == "SQL" and avg_ms > 50:
            suggestions.append(OptimizationSuggestion(
                description=f"SQL node {node_id} is slow ({avg_ms:.1f}ms) — add database indexes",
                impact="high",
                node_ids=[node_id],
                action="add_index",
                estimated_speedup=5.0,
            ))

        return suggestions

    async def _find_parallel_opportunities(self) -> List[OptimizationSuggestion]:
        """Find nodes that could be parallelized."""
        suggestions = []

        if not self.store.duck:
            return suggestions

        # Find sequential pure nodes that share the same predecessor
        results = self.store.duck.execute("""
            SELECT e1.target_id, e2.target_id, e1.source_id
            FROM edges e1
            JOIN edges e2 ON e1.source_id = e2.source_id
            JOIN nodes n1 ON e1.target_id = n1.id
            JOIN nodes n2 ON e2.target_id = n2.id
            WHERE e1.target_id < e2.target_id
              AND n1.pure AND n2.pure
              AND NOT n1.parallelizable
        """).fetchall()

        if results:
            for r in results[:5]:
                suggestions.append(OptimizationSuggestion(
                    description=f"Parallelize {r[0]} and {r[1]} (both pure, same predecessor {r[2]})",
                    impact="medium",
                    node_ids=[r[0], r[1]],
                    action="parallelize",
                    estimated_speedup=1.5,
                    auto_applicable=True,
                ))

        return suggestions

    async def _find_cache_opportunities(self) -> List[OptimizationSuggestion]:
        """Find frequently-called pure nodes that could benefit from caching."""
        suggestions = []

        if not self.store.duck:
            return suggestions

        results = self.store.duck.execute("""
            SELECT el.node_id, COUNT(*) as calls, AVG(el.duration_ms) as avg_ms
            FROM execution_log el
            JOIN nodes n ON el.node_id = n.id
            WHERE n.pure AND el.success
            GROUP BY el.node_id
            HAVING calls > 10 AND avg_ms > 5
            ORDER BY calls * avg_ms DESC
            LIMIT 5
        """).fetchall()

        for r in results:
            suggestions.append(OptimizationSuggestion(
                description=f"Node {r[0]} called {r[1]} times at {r[2]:.1f}ms avg — add result cache",
                impact="high" if r[1] * r[2] > 1000 else "medium",
                node_ids=[r[0]],
                action="cache",
                estimated_speedup=min(r[2] / 0.1, 50),
                auto_applicable=True,
            ))

        return suggestions
