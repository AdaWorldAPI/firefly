"""
Graph Lowering: Convert semantic graph → executable FireflyNodes + FireflyEdges.

Each semantic DependencyNode becomes a FireflyNode with:
- Resonance vector (from semantic content)
- Executor type (NATIVE, WASM, SQL)
- Function reference
- Input/output schemas
"""

import hashlib
from typing import List, Tuple, Dict, Optional, Callable
from dataclasses import dataclass

from dto.node import FireflyNode
from dto.edge import FireflyEdge
from core import bind, bundle, PACKED, ROLE_SCHEMA, ROLE_LOGIC, ROLE_CONTEXT
from compiler.analyze.semantic import SemanticGraph, DependencyNode, Phase


# Validation type → executor function mapping
VALIDATION_EXECUTORS = {
    "presence": "validate_presence",
    "length": "validate_length",
    "format": "validate_format",
    "uniqueness": "validate_uniqueness",
    "numericality": "validate_numericality",
    "inclusion": "validate_inclusion",
    "exclusion": "validate_exclusion",
    "custom": "validate_custom",
}

# Phase → default executor mapping
PHASE_EXECUTORS = {
    Phase.ENTRY: "transform_identity",
    Phase.VALIDATE: "validate_presence",
    Phase.BEFORE_CALLBACK: "callback_exec",
    Phase.TRANSFORM: "transform_identity",
    Phase.PERSIST: "persist_record",
    Phase.AFTER_CALLBACK: "callback_exec",
    Phase.QUERY: "query_exec",
}


def _hash_to_vec(text: str) -> bytes:
    """Deterministic vector from text (used when no embedding model available)."""
    h = hashlib.sha256(text.encode()).digest()
    return (h * 40)[:PACKED]


class GraphLowering:
    """
    Lower a SemanticGraph into executable FireflyNodes and FireflyEdges.
    """

    def __init__(self, embed_fn: Optional[Callable] = None):
        """
        Args:
            embed_fn: Optional async function (str) -> bytes[1250]
                      for semantic embedding. If None, uses hash-based vectors.
        """
        self.embed_fn = embed_fn

    async def lower(self, graph: SemanticGraph) -> Tuple[List[FireflyNode], List[FireflyEdge]]:
        """
        Lower an entire semantic graph to executable nodes and edges.

        Returns (nodes, edges).
        """
        nodes = []
        edges = []
        node_map: Dict[str, FireflyNode] = {}

        # Lower each semantic node to a FireflyNode
        for dep_node in graph.nodes.values():
            ff_node = await self._lower_node(graph.model_name, dep_node)
            nodes.append(ff_node)
            node_map[dep_node.id] = ff_node

        # Lower each semantic edge to a FireflyEdge
        for dep_edge in graph.edges:
            if dep_edge.source_id in node_map and dep_edge.target_id in node_map:
                src = node_map[dep_edge.source_id]
                tgt = node_map[dep_edge.target_id]

                edge_type = {
                    "data_flow": "FEEDS",
                    "control_flow": "TRIGGERS",
                    "guard": "GUARDS",
                    "trigger": "TRIGGERS",
                }.get(dep_edge.kind, "FEEDS")

                ff_edge = FireflyEdge.from_nodes(
                    src, tgt,
                    type=edge_type,
                    condition=dep_edge.condition,
                    field=dep_edge.field,
                )
                edges.append(ff_edge)

        return nodes, edges

    async def _lower_node(self, model_name: str, dep_node: DependencyNode) -> FireflyNode:
        """Lower a single semantic node to a FireflyNode."""

        # Determine executor and function
        executor, fn_name = self._resolve_executor(dep_node)

        # Build semantic descriptions
        schema_desc = self._describe_schema(model_name, dep_node)
        logic_desc = self._describe_logic(dep_node)
        context_desc = self._describe_context(model_name, dep_node)

        # Generate vectors
        schema_vec = await self._embed(schema_desc)
        logic_vec = await self._embed(logic_desc)
        context_vec = await self._embed(context_desc)

        # Determine node type
        node_type = {
            "validation": "VALIDATE",
            "callback": "TRIGGER",
            "persist": "PERSIST",
            "entry": "TRIGGER",
            "scope": "QUERY",
        }.get(dep_node.kind, "TRANSFORM")

        # Build input/output schemas
        input_schema = {}
        for f in dep_node.fields_read:
            input_schema[f] = "any"
        if not input_schema:
            input_schema = {"_input": "any"}

        output_schema = {"valid": "bool", "errors": "string[]"} if dep_node.kind == "validation" else {"result": "any"}

        return FireflyNode.from_components(
            id=dep_node.id,
            schema_vec=schema_vec,
            logic_vec=logic_vec,
            context_vec=context_vec,
            executor=executor,
            fn_name=fn_name,
            type=node_type,
            cost=self._estimate_cost(dep_node),
            pure=dep_node.is_pure,
            parallelizable=dep_node.is_parallelizable,
            input_schema=input_schema,
            output_schema=output_schema,
        )

    def _resolve_executor(self, dep_node: DependencyNode) -> Tuple[str, str]:
        """Determine executor type and function name for a node."""
        if dep_node.kind == "validation":
            v_type = dep_node.metadata.get("type", dep_node.name.split("(")[-1].rstrip(")") if "(" in dep_node.name else "presence")
            # Extract validation type from the node name
            for vtype, fn in VALIDATION_EXECUTORS.items():
                if vtype in dep_node.id:
                    return "NATIVE", fn
            return "NATIVE", "validate_presence"

        elif dep_node.kind == "persist":
            return "SQL", f"persist_{dep_node.operation}"

        elif dep_node.kind == "callback":
            return "NATIVE", dep_node.source_ref or "callback_exec"

        elif dep_node.kind == "scope":
            return "SQL", f"scope_{dep_node.metadata.get('name', 'unknown')}"

        else:
            fn = PHASE_EXECUTORS.get(dep_node.phase, "transform_identity")
            return "NATIVE", fn

    def _describe_schema(self, model_name: str, dep_node: DependencyNode) -> str:
        """Generate schema description for embedding."""
        fields = ", ".join(dep_node.fields_read) if dep_node.fields_read else "record"
        return f"{model_name} {dep_node.kind}: input({fields}) output({dep_node.kind}_result)"

    def _describe_logic(self, dep_node: DependencyNode) -> str:
        """Generate logic description for embedding."""
        return f"{dep_node.name} — {dep_node.kind} during {dep_node.operation}"

    def _describe_context(self, model_name: str, dep_node: DependencyNode) -> str:
        """Generate context description for embedding."""
        return f"{dep_node.phase.value} phase of {model_name}.{dep_node.operation}"

    def _estimate_cost(self, dep_node: DependencyNode) -> int:
        """Estimate relative execution cost."""
        costs = {
            "entry": 1,
            "validation": 2,
            "callback": 5,
            "persist": 10,
            "scope": 8,
        }
        return costs.get(dep_node.kind, 3)

    async def _embed(self, text: str) -> bytes:
        """Embed text to vector. Uses real embeddings if available, else hash."""
        if self.embed_fn:
            return await self.embed_fn(text)
        return _hash_to_vec(text)
