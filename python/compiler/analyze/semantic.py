"""
Semantic Analyzer: Build dependency graph from parsed declarations.

Takes parsed model declarations and produces:
1. Dependency graph (topological ordering)
2. Data flow analysis (what feeds into what)
3. Side effect analysis (callbacks, triggers)
4. Execution phases (validate → transform → persist)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum


class Phase(Enum):
    """Execution phases in order."""
    ENTRY = "entry"
    VALIDATE = "validate"
    BEFORE_CALLBACK = "before_callback"
    TRANSFORM = "transform"
    PERSIST = "persist"
    AFTER_CALLBACK = "after_callback"
    QUERY = "query"


@dataclass
class DependencyNode:
    """A node in the semantic dependency graph."""
    id: str
    name: str
    phase: Phase
    operation: str  # create, update, destroy, query
    kind: str  # validation, callback, persist, association, scope, entry
    source_ref: str = ""  # Reference to source declaration
    fields_read: Set[str] = field(default_factory=set)
    fields_written: Set[str] = field(default_factory=set)
    is_pure: bool = True  # No side effects
    is_parallelizable: bool = True
    metadata: Dict = field(default_factory=dict)

    def __hash__(self):
        return hash(self.id)


@dataclass
class DependencyEdge:
    """An edge in the semantic dependency graph."""
    source_id: str
    target_id: str
    kind: str  # data_flow, control_flow, guard, trigger
    field: Optional[str] = None  # For data flow: which field
    condition: Optional[str] = None  # For guards: predicate


@dataclass
class SemanticGraph:
    """The complete semantic dependency graph for a model."""
    model_name: str
    nodes: Dict[str, DependencyNode] = field(default_factory=dict)
    edges: List[DependencyEdge] = field(default_factory=list)

    def add_node(self, node: DependencyNode):
        self.nodes[node.id] = node

    def add_edge(self, edge: DependencyEdge):
        self.edges.append(edge)

    def get_outgoing(self, node_id: str) -> List[DependencyEdge]:
        return [e for e in self.edges if e.source_id == node_id]

    def get_incoming(self, node_id: str) -> List[DependencyEdge]:
        return [e for e in self.edges if e.target_id == node_id]

    def topological_sort(self) -> List[List[str]]:
        """
        Topological sort with parallelization.

        Returns list of stages. Nodes in the same stage
        can execute in parallel.
        """
        in_degree = {nid: 0 for nid in self.nodes}
        for edge in self.edges:
            if edge.target_id in in_degree:
                in_degree[edge.target_id] += 1

        stages = []
        remaining = set(self.nodes.keys())

        while remaining:
            # Find all nodes with no incoming edges from remaining
            ready = {
                nid for nid in remaining
                if in_degree.get(nid, 0) == 0
            }
            if not ready:
                # Cycle detected — break by choosing nodes with lowest in-degree
                min_deg = min(in_degree[nid] for nid in remaining)
                ready = {nid for nid in remaining if in_degree[nid] == min_deg}

            # Group ready nodes by phase for ordering
            phase_groups: Dict[Phase, List[str]] = {}
            for nid in ready:
                node = self.nodes[nid]
                phase_groups.setdefault(node.phase, []).append(nid)

            # Emit each phase group as a stage
            for phase in Phase:
                if phase in phase_groups:
                    stage_nodes = phase_groups[phase]
                    # Within a stage, parallelizable nodes can run together
                    parallel = [nid for nid in stage_nodes
                                if self.nodes[nid].is_parallelizable]
                    sequential = [nid for nid in stage_nodes
                                  if not self.nodes[nid].is_parallelizable]

                    if parallel:
                        stages.append(parallel)
                    for nid in sequential:
                        stages.append([nid])

            # Remove ready nodes and update in-degrees
            for nid in ready:
                remaining.discard(nid)
                for edge in self.get_outgoing(nid):
                    if edge.target_id in in_degree:
                        in_degree[edge.target_id] -= 1

        return stages

    def data_flow_fields(self) -> Dict[str, Set[str]]:
        """Map each node to the fields that flow into it."""
        result = {}
        for edge in self.edges:
            if edge.kind == "data_flow" and edge.field:
                result.setdefault(edge.target_id, set()).add(edge.field)
        return result


class SemanticAnalyzer:
    """
    Analyze parsed model declarations into a semantic graph.

    Produces dependency information, execution ordering,
    and data flow analysis.
    """

    def analyze_model(self, model) -> Dict[str, SemanticGraph]:
        """
        Analyze a parsed model (RubyModel) and produce semantic graphs.

        Returns one graph per operation (create, update, destroy).
        """
        graphs = {}
        for operation in ["create", "update", "destroy"]:
            graph = self._build_graph(model, operation)
            graphs[operation] = graph
        return graphs

    def _build_graph(self, model, operation: str) -> SemanticGraph:
        """Build a semantic graph for a specific operation."""
        graph = SemanticGraph(model_name=model.name)

        # 1. Entry point
        entry_id = f"{model.name}_{operation}_entry"
        entry = DependencyNode(
            id=entry_id,
            name=f"{operation} entry",
            phase=Phase.ENTRY,
            operation=operation,
            kind="entry",
            is_pure=True,
        )
        graph.add_node(entry)

        prev_ids = [entry_id]

        # 2. Before callbacks
        before_callbacks = [
            cb for cb in model.callbacks
            if cb.timing == "before" and (
                cb.event == operation or cb.event == "save"
            )
        ]
        for cb in before_callbacks:
            cb_id = f"{model.name}_before_{cb.event}_{cb.method}"
            cb_node = DependencyNode(
                id=cb_id,
                name=f"before_{cb.event}: {cb.method}",
                phase=Phase.BEFORE_CALLBACK,
                operation=operation,
                kind="callback",
                is_pure=False,
                is_parallelizable=False,
                source_ref=cb.method,
            )
            graph.add_node(cb_node)
            for pid in prev_ids:
                graph.add_edge(DependencyEdge(pid, cb_id, "control_flow"))
            prev_ids = [cb_id]

        # 3. Validations (can run in parallel)
        validation_ids = []
        for i, v in enumerate(model.validations):
            v_id = f"{model.name}_validate_{v.field}_{v.type}_{i}"
            v_node = DependencyNode(
                id=v_id,
                name=f"validate {v.field} ({v.type})",
                phase=Phase.VALIDATE,
                operation=operation,
                kind="validation",
                fields_read={v.field},
                is_pure=True,
                is_parallelizable=True,
                metadata=v.options,
            )
            graph.add_node(v_node)
            for pid in prev_ids:
                graph.add_edge(DependencyEdge(
                    pid, v_id, "data_flow", field=v.field
                ))
            validation_ids.append(v_id)

        if validation_ids:
            prev_ids = validation_ids

        # 4. Persist node
        if operation != "destroy":
            persist_id = f"{model.name}_persist"
            persist = DependencyNode(
                id=persist_id,
                name=f"persist {model.name}",
                phase=Phase.PERSIST,
                operation=operation,
                kind="persist",
                is_pure=False,
                is_parallelizable=False,
            )
            graph.add_node(persist)
            for pid in prev_ids:
                graph.add_edge(DependencyEdge(pid, persist_id, "control_flow"))
            prev_ids = [persist_id]
        else:
            destroy_id = f"{model.name}_destroy"
            destroy = DependencyNode(
                id=destroy_id,
                name=f"destroy {model.name}",
                phase=Phase.PERSIST,
                operation=operation,
                kind="persist",
                is_pure=False,
                is_parallelizable=False,
            )
            graph.add_node(destroy)
            for pid in prev_ids:
                graph.add_edge(DependencyEdge(pid, destroy_id, "control_flow"))
            prev_ids = [destroy_id]

        # 5. After callbacks
        after_callbacks = [
            cb for cb in model.callbacks
            if cb.timing == "after" and (
                cb.event == operation or cb.event == "save"
            )
        ]
        for cb in after_callbacks:
            cb_id = f"{model.name}_after_{cb.event}_{cb.method}"
            cb_node = DependencyNode(
                id=cb_id,
                name=f"after_{cb.event}: {cb.method}",
                phase=Phase.AFTER_CALLBACK,
                operation=operation,
                kind="callback",
                is_pure=False,
                is_parallelizable=False,
                source_ref=cb.method,
            )
            graph.add_node(cb_node)
            for pid in prev_ids:
                graph.add_edge(DependencyEdge(pid, cb_id, "control_flow"))
            prev_ids = [cb_id]

        return graph

    def analyze_associations(self, model, graph: SemanticGraph):
        """
        Add association-derived nodes to the graph.

        belongs_to → adds foreign key validation
        has_many   → adds cascade behavior on destroy
        """
        for assoc in model.associations:
            if assoc.type == "belongs_to":
                # Foreign key must exist
                fk_field = f"{assoc.name}_id"
                v_id = f"{model.name}_validate_fk_{assoc.name}"
                v_node = DependencyNode(
                    id=v_id,
                    name=f"validate FK: {fk_field}",
                    phase=Phase.VALIDATE,
                    operation="create",
                    kind="validation",
                    fields_read={fk_field},
                    is_pure=True,
                    metadata={"association": assoc.name, "type": "belongs_to"},
                )
                graph.add_node(v_node)

            elif assoc.type in ("has_many", "has_one"):
                # On destroy, may need cascade
                dependent = assoc.options.get("dependent")
                if dependent:
                    d_id = f"{model.name}_cascade_{assoc.name}"
                    d_node = DependencyNode(
                        id=d_id,
                        name=f"cascade {dependent}: {assoc.name}",
                        phase=Phase.BEFORE_CALLBACK,
                        operation="destroy",
                        kind="callback",
                        is_pure=False,
                        is_parallelizable=False,
                        metadata={"dependent": dependent, "association": assoc.name},
                    )
                    graph.add_node(d_node)

    def analyze_scopes(self, model, graph: SemanticGraph):
        """Add scope-derived query nodes."""
        for scope in model.scopes:
            s_id = f"{model.name}_scope_{scope['name']}"
            s_node = DependencyNode(
                id=s_id,
                name=f"scope: {scope['name']}",
                phase=Phase.QUERY,
                operation="query",
                kind="scope",
                is_pure=True,
                metadata=scope,
            )
            graph.add_node(s_node)
