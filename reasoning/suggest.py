"""
Fix Suggester: "How to fix this?"

Given a failure:
1. Find similar successful executions (Hamming search)
2. Diff the execution paths
3. Identify divergence point
4. Suggest specific fixes
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from storage.store import FireflyStore


@dataclass
class FixSuggestion:
    """A suggested fix for a failure."""
    description: str
    confidence: float  # 0.0 - 1.0
    similar_success_id: Optional[str] = None
    divergence_node: Optional[str] = None
    action: str = ""  # add_validation, modify_input, reorder_nodes, etc.


class FixSuggester:
    """
    Suggest fixes based on comparison with successful executions.
    """

    def __init__(self, store: FireflyStore):
        self.store = store

    async def suggest_fixes(
        self,
        failed_node_id: str,
        execution_id: str = "",
        limit: int = 3
    ) -> List[FixSuggestion]:
        """
        Generate fix suggestions for a failed execution.

        Strategy:
        1. Find successful executions of the same DTO/operation
        2. Compare traces to find divergence points
        3. Generate actionable suggestions
        """
        suggestions = []

        if not self.store.duck:
            return [FixSuggestion(
                description="Database not available for analysis",
                confidence=0.0,
            )]

        # Get the failed execution's DTO context
        failed_info = await self._get_execution_context(execution_id)

        # Find successful executions
        successes = await self._find_successful_executions(
            failed_node_id, limit=10
        )

        if successes:
            # Compare traces
            for success in successes[:limit]:
                suggestion = await self._compare_and_suggest(
                    failed_node_id, execution_id, success
                )
                if suggestion:
                    suggestions.append(suggestion)

        # Add general suggestions based on node type
        node = await self.store.get_node(failed_node_id)
        if node:
            suggestions.extend(self._type_based_suggestions(node))

        return suggestions[:limit]

    async def _get_execution_context(self, execution_id: str) -> Dict[str, Any]:
        """Get context about a failed execution."""
        if not execution_id or not self.store.duck:
            return {}

        results = self.store.duck.execute("""
            SELECT node_id, success, error, duration_ms
            FROM execution_log
            WHERE execution_id = ?
            ORDER BY timestamp
        """, [execution_id]).fetchall()

        return {
            "nodes": [r[0] for r in results],
            "errors": {r[0]: r[2] for r in results if not r[1]},
            "durations": {r[0]: r[3] for r in results},
        }

    async def _find_successful_executions(
        self,
        node_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """Find recent successful executions that passed through this node."""
        if not self.store.duck:
            return []

        results = self.store.duck.execute("""
            SELECT DISTINCT execution_id
            FROM execution_log
            WHERE node_id = ? AND success
            ORDER BY timestamp DESC
            LIMIT ?
        """, [node_id, limit]).fetchall()

        return [{"execution_id": r[0]} for r in results]

    async def _compare_and_suggest(
        self,
        failed_node_id: str,
        failed_exec_id: str,
        success: Dict,
    ) -> Optional[FixSuggestion]:
        """Compare failed and successful executions."""
        success_exec_id = success.get("execution_id", "")
        if not success_exec_id:
            return None

        success_ctx = await self._get_execution_context(success_exec_id)
        failed_ctx = await self._get_execution_context(failed_exec_id)

        if not success_ctx.get("nodes") or not failed_ctx.get("nodes"):
            return None

        # Find divergence: first node where paths differ
        s_nodes = success_ctx["nodes"]
        f_nodes = failed_ctx["nodes"]

        divergence = None
        for i, (s, f) in enumerate(zip(s_nodes, f_nodes)):
            if s != f:
                divergence = f"Step {i}: success took '{s}', failure took '{f}'"
                break

        if not divergence:
            # Same path but different outcomes
            return FixSuggestion(
                description=f"Same execution path succeeded previously — check input data",
                confidence=0.7,
                similar_success_id=success_exec_id,
                action="check_input",
            )

        return FixSuggestion(
            description=f"Execution diverged: {divergence}",
            confidence=0.5,
            similar_success_id=success_exec_id,
            divergence_node=failed_node_id,
            action="investigate_divergence",
        )

    def _type_based_suggestions(self, node) -> List[FixSuggestion]:
        """Generate suggestions based on node type."""
        suggestions = []

        if node.type == "VALIDATE":
            suggestions.append(FixSuggestion(
                description=f"Add input sanitization before validation node {node.id}",
                confidence=0.4,
                action="add_sanitizer",
            ))

        elif node.type == "PERSIST":
            suggestions.append(FixSuggestion(
                description=f"Check database constraints for {node.id}",
                confidence=0.4,
                action="check_constraints",
            ))

        return suggestions
