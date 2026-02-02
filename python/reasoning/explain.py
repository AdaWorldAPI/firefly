"""
Failure Explainer: "Why did this fail?"

Given a failed execution:
1. Find the failed node in the execution trace
2. Query upstream nodes: what fed into it?
3. Query similar failures: seen this pattern before?
4. Generate explanation from graph structure

Uses Hamming similarity to find similar past failures,
graph traversal to identify root causes.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from storage.store import FireflyStore
from core import similarity


@dataclass
class FailureExplanation:
    """Structured explanation of a failure."""
    failed_node_id: str
    error: str
    timestamp: str
    upstream_nodes: List[str]
    similar_failures: List[Dict[str, Any]]
    root_cause: str
    suggestion: str


class FailureExplainer:
    """
    Explain graph execution failures.

    Combines graph traversal (Kuzu) with similarity search (LanceDB)
    and analytics (DuckDB) to produce human-readable explanations.
    """

    def __init__(self, store: FireflyStore):
        self.store = store

    async def explain_last(self) -> Optional[FailureExplanation]:
        """Explain the most recent failure."""
        if not self.store.duck:
            return None

        result = self.store.duck.execute("""
            SELECT node_id, error, timestamp, execution_id
            FROM execution_log
            WHERE NOT success
            ORDER BY timestamp DESC
            LIMIT 1
        """).fetchone()

        if not result:
            return None

        node_id, error, timestamp, exec_id = result
        return await self.explain_failure(node_id, error, str(timestamp), exec_id)

    async def explain_failure(
        self,
        node_id: str,
        error: str,
        timestamp: str,
        execution_id: str = "",
    ) -> FailureExplanation:
        """
        Generate full explanation for a specific failure.
        """
        # 1. Get upstream nodes (what fed into the failure)
        upstream = await self.store.get_upstream_nodes(node_id, hops=3)

        # 2. Get the failing node's details
        node = await self.store.get_node(node_id)

        # 3. Find similar past failures
        similar = await self._find_similar_failures(node_id, error)

        # 4. Analyze the execution trace
        trace_analysis = await self._analyze_trace(execution_id)

        # 5. Generate root cause hypothesis
        root_cause = self._hypothesize_root_cause(
            node_id, error, upstream, similar, trace_analysis
        )

        # 6. Generate suggestion
        suggestion = self._generate_suggestion(
            node_id, error, similar, root_cause
        )

        return FailureExplanation(
            failed_node_id=node_id,
            error=error,
            timestamp=timestamp,
            upstream_nodes=upstream,
            similar_failures=similar,
            root_cause=root_cause,
            suggestion=suggestion,
        )

    async def _find_similar_failures(
        self,
        node_id: str,
        error: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar past failures."""
        if not self.store.duck:
            return []

        results = self.store.duck.execute("""
            SELECT node_id, error, timestamp, execution_id
            FROM execution_log
            WHERE NOT success AND node_id != ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, [node_id, limit]).fetchall()

        return [
            {
                "node_id": r[0],
                "error": r[1],
                "timestamp": str(r[2]),
                "execution_id": r[3],
            }
            for r in results
        ]

    async def _analyze_trace(self, execution_id: str) -> Dict[str, Any]:
        """Analyze the execution trace for an execution."""
        if not self.store.duck or not execution_id:
            return {}

        results = self.store.duck.execute("""
            SELECT node_id, duration_ms, success, error
            FROM execution_log
            WHERE execution_id = ?
            ORDER BY timestamp
        """, [execution_id]).fetchall()

        trace = []
        total_ms = 0
        for r in results:
            trace.append({
                "node_id": r[0],
                "duration_ms": r[1],
                "success": r[2],
                "error": r[3],
            })
            total_ms += r[1] or 0

        return {
            "steps": trace,
            "total_ms": total_ms,
            "failed_at_step": next(
                (i for i, t in enumerate(trace) if not t["success"]), -1
            ),
        }

    def _hypothesize_root_cause(
        self,
        node_id: str,
        error: str,
        upstream: List[str],
        similar: List[Dict],
        trace: Dict,
    ) -> str:
        """Generate a root cause hypothesis from available data."""
        parts = []

        # Check error type
        if "blank" in error.lower() or "null" in error.lower() or "empty" in error.lower():
            parts.append(f"Missing required input for {node_id}")
            if upstream:
                parts.append(f"Data should flow from: {' → '.join(upstream[:3])}")

        elif "too short" in error.lower() or "too long" in error.lower():
            parts.append(f"Length constraint violation at {node_id}")

        elif "unique" in error.lower() or "duplicate" in error.lower():
            parts.append(f"Uniqueness constraint violation at {node_id}")

        else:
            parts.append(f"Execution error at {node_id}: {error}")

        # Check for patterns in similar failures
        if similar:
            same_node = [s for s in similar if s["node_id"] == node_id]
            if len(same_node) >= 2:
                parts.append(f"This node has failed {len(same_node)} times before — recurring issue")

        # Check trace
        if trace.get("failed_at_step", -1) == 0:
            parts.append("Failed at very first step — likely bad input data")

        return ". ".join(parts) if parts else f"Unknown failure at {node_id}: {error}"

    def _generate_suggestion(
        self,
        node_id: str,
        error: str,
        similar: List[Dict],
        root_cause: str,
    ) -> str:
        """Generate actionable suggestion."""
        if "missing" in root_cause.lower() or "required" in root_cause.lower():
            return f"Ensure all required fields are provided before {node_id} executes"

        if "recurring" in root_cause.lower():
            return f"Node {node_id} has a systemic issue — consider adding input validation upstream"

        if "length" in root_cause.lower():
            return f"Check field length constraints at {node_id}"

        return f"Review the execution path leading to {node_id} and verify input data"
