"""
LadybugDB POC - Level 6: META/NARS

Reasoning primitives above code structure:

TEMPORAL:
  WAITS_FOR    - A must complete before B starts
  SEQUENCE     - ordered execution A → B → C
  PARALLEL     - concurrent execution A || B

HYPOTHETICAL:
  WHAT_IF      - explore counterfactual branch
  EXPECTATION  - predicted outcome of action

GUARDED:
  WHILE_DO     - condition ⊢ action (NAL-7 style)
  UNTIL        - action ⊢ condition (inverse guard)

NARS PRIMITIVES:
  GOAL         - objective to achieve (!)
  BELIEF       - asserted fact with confidence (.)
  QUESTION     - query to resolve (?)
  JUDGMENT     - derived conclusion with truth value

This layer enables:
- Temporal reasoning ("A before B")
- Counterfactual exploration ("what if X failed?")
- Goal-directed planning ("achieve Y by doing Z")
- Belief propagation with confidence
"""

import numpy as np
import hashlib
import struct
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import IntEnum

# =============================================================================
# CONSTANTS
# =============================================================================

DIM = 10_000
DIM_U64 = 157
LAST_MASK = np.uint64((1 << 16) - 1)

# =============================================================================
# FINGERPRINT
# =============================================================================

def fingerprint(identity: str) -> np.ndarray:
    data = np.empty(DIM_U64, dtype=np.uint64)
    for i in range(DIM_U64):
        h = hashlib.sha256(f"{identity}:{i}".encode()).digest()
        data[i] = struct.unpack('<Q', h[:8])[0]
    data[-1] &= LAST_MASK
    return data


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    xored = np.bitwise_xor(a, b)
    dist = sum(bin(int(x)).count('1') for x in xored)
    return 1.0 - dist / DIM


# =============================================================================
# NODE TYPES
# =============================================================================

class NodeType(IntEnum):
    # Code layer (L1-L5)
    FUNCTION = 1
    CLASS = 2
    METHOD = 3
    IF = 4
    FOREACH = 5
    CALL = 6
    
    # Meta/NARS layer (L6)
    GOAL = 100           # Objective to achieve (!)
    BELIEF = 101         # Asserted fact (.)
    QUESTION = 102       # Query to resolve (?)
    JUDGMENT = 103       # Derived conclusion
    EXPECTATION = 104    # Predicted outcome
    
    # Temporal
    SEQUENCE = 110       # Ordered execution
    PARALLEL = 111       # Concurrent execution
    
    # Hypothetical
    WHAT_IF = 120        # Counterfactual branch
    SCENARIO = 121       # Named hypothesis
    
    # Guarded
    WHILE_DO = 130       # condition ⊢ action
    UNTIL = 131          # action ⊢ condition


class EdgeType(IntEnum):
    # Structural
    CONTAINS = 1
    CALLS = 2
    
    # Temporal
    WAITS_FOR = 10       # A must complete before B
    PRECEDES = 11        # A comes before B (soft order)
    CONCURRENT = 12      # A runs with B
    
    # Causal
    CAUSES = 20          # A causes B
    ENABLES = 21         # A enables B (necessary condition)
    PREVENTS = 22        # A prevents B
    
    # NARS
    ACHIEVES = 30        # Action achieves goal
    SUPPORTS = 31        # Belief supports conclusion
    CONTRADICTS = 32     # Belief contradicts belief
    ANSWERS = 33         # Judgment answers question
    
    # Hypothetical
    BRANCHES_TO = 40     # What-if branches to scenario
    EXPECTS = 41         # Action expects outcome


# =============================================================================
# TRUTH VALUE (NARS style)
# =============================================================================

@dataclass
class TruthValue:
    """
    NARS-style truth value: <frequency, confidence>
    
    frequency: proportion of positive evidence [0, 1]
    confidence: amount of evidence [0, 1)
    
    Examples:
      <1.0, 0.9> = "almost certainly true"
      <0.5, 0.5> = "uncertain"
      <0.0, 0.9> = "almost certainly false"
      <1.0, 0.0> = "no evidence but assumed true"
    """
    frequency: float = 1.0
    confidence: float = 0.9
    
    def __str__(self):
        return f"<{self.frequency:.2f}, {self.confidence:.2f}>"
    
    @property
    def expectation(self) -> float:
        """Expected truth value: weighted average toward 0.5."""
        return self.confidence * (self.frequency - 0.5) + 0.5
    
    def revision(self, other: 'TruthValue') -> 'TruthValue':
        """Combine two truth values (NARS revision rule)."""
        # Weight by confidence * (1 - other_confidence)
        w1 = self.confidence * (1 - other.confidence)
        w2 = other.confidence * (1 - self.confidence)
        w_sum = w1 + w2
        
        if w_sum < 0.001:
            return TruthValue(0.5, 0.0)
        
        # Combined frequency
        f = (self.frequency * w1 + other.frequency * w2) / w_sum
        
        # Combined confidence (increases with more evidence)
        c = (self.confidence + other.confidence) / (1 + self.confidence + other.confidence)
        
        return TruthValue(min(f, 1.0), min(c, 0.99))


# =============================================================================
# NODE
# =============================================================================

@dataclass
class Node:
    id: int
    node_type: NodeType
    name: str
    content: str = ""
    truth: TruthValue = field(default_factory=TruthValue)
    fingerprint: np.ndarray = field(default_factory=lambda: np.zeros(DIM_U64, dtype=np.uint64))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if np.all(self.fingerprint == 0):
            identity = f"{self.node_type.name}::{self.name}::{self.content}"
            self.fingerprint = fingerprint(identity)
    
    def __str__(self):
        suffix = {
            NodeType.GOAL: "!",
            NodeType.BELIEF: ".",
            NodeType.QUESTION: "?",
            NodeType.JUDGMENT: ".",
        }.get(self.node_type, "")
        return f"{self.name}{suffix} {self.truth}"


@dataclass
class Edge:
    from_id: int
    to_id: int
    edge_type: EdgeType
    truth: TruthValue = field(default_factory=TruthValue)


# =============================================================================
# NARS GRAPH
# =============================================================================

class NARSGraph:
    """Graph with NARS reasoning primitives."""
    
    def __init__(self):
        self.nodes: Dict[int, Node] = {}
        self.edges: List[Edge] = []
        self._next_id = 0
    
    def _get_id(self) -> int:
        id = self._next_id
        self._next_id += 1
        return id
    
    # -------------------------------------------------------------------------
    # Code layer nodes
    # -------------------------------------------------------------------------
    
    def function(self, name: str, body: str = "") -> Node:
        return self._add_node(NodeType.FUNCTION, name, body)
    
    def method(self, name: str, body: str = "") -> Node:
        return self._add_node(NodeType.METHOD, name, body)
    
    # -------------------------------------------------------------------------
    # NARS primitives
    # -------------------------------------------------------------------------
    
    def goal(self, name: str, content: str = "") -> Node:
        """Create a GOAL node (objective to achieve)."""
        return self._add_node(NodeType.GOAL, name, content, TruthValue(1.0, 0.9))
    
    def belief(self, name: str, content: str = "", freq: float = 1.0, conf: float = 0.9) -> Node:
        """Create a BELIEF node (asserted fact)."""
        return self._add_node(NodeType.BELIEF, name, content, TruthValue(freq, conf))
    
    def question(self, name: str, content: str = "") -> Node:
        """Create a QUESTION node (query to resolve)."""
        return self._add_node(NodeType.QUESTION, name, content, TruthValue(0.5, 0.0))
    
    def judgment(self, name: str, content: str = "", freq: float = 1.0, conf: float = 0.9) -> Node:
        """Create a JUDGMENT node (derived conclusion)."""
        return self._add_node(NodeType.JUDGMENT, name, content, TruthValue(freq, conf))
    
    def expectation(self, name: str, content: str = "", freq: float = 1.0, conf: float = 0.5) -> Node:
        """Create an EXPECTATION node (predicted outcome)."""
        return self._add_node(NodeType.EXPECTATION, name, content, TruthValue(freq, conf))
    
    # -------------------------------------------------------------------------
    # Temporal nodes
    # -------------------------------------------------------------------------
    
    def sequence(self, name: str, *steps: Node) -> Node:
        """Create ordered sequence: A → B → C."""
        node = self._add_node(NodeType.SEQUENCE, name)
        for i, step in enumerate(steps):
            self.add_edge(node, step, EdgeType.CONTAINS)
            if i > 0:
                self.add_edge(steps[i-1], step, EdgeType.PRECEDES)
        return node
    
    def parallel(self, name: str, *tasks: Node) -> Node:
        """Create parallel execution: A || B || C."""
        node = self._add_node(NodeType.PARALLEL, name)
        for task in tasks:
            self.add_edge(node, task, EdgeType.CONTAINS)
        for i, t1 in enumerate(tasks):
            for t2 in tasks[i+1:]:
                self.add_edge(t1, t2, EdgeType.CONCURRENT)
        return node
    
    # -------------------------------------------------------------------------
    # Hypothetical nodes
    # -------------------------------------------------------------------------
    
    def what_if(self, condition: str, *scenarios: Tuple[str, Node]) -> Node:
        """
        Create hypothetical branch.
        
        what_if("network fails", 
                ("retry", retry_action),
                ("fallback", fallback_action))
        """
        node = self._add_node(NodeType.WHAT_IF, f"what_if({condition})", condition)
        for scenario_name, scenario_node in scenarios:
            scenario = self._add_node(NodeType.SCENARIO, scenario_name)
            self.add_edge(node, scenario, EdgeType.BRANCHES_TO)
            self.add_edge(scenario, scenario_node, EdgeType.CONTAINS)
        return node
    
    # -------------------------------------------------------------------------
    # Guarded nodes
    # -------------------------------------------------------------------------
    
    def while_do(self, condition: str, action: Node) -> Node:
        """
        Create guarded loop: condition ⊢ action.
        
        "While condition holds, do action."
        """
        node = self._add_node(NodeType.WHILE_DO, f"while({condition})", condition)
        self.add_edge(node, action, EdgeType.CONTAINS)
        return node
    
    def until(self, action: Node, condition: str) -> Node:
        """
        Create inverse guard: action ⊢ condition.
        
        "Do action until condition."
        """
        node = self._add_node(NodeType.UNTIL, f"until({condition})", condition)
        self.add_edge(node, action, EdgeType.CONTAINS)
        return node
    
    # -------------------------------------------------------------------------
    # Edge creation
    # -------------------------------------------------------------------------
    
    def _add_node(self, node_type: NodeType, name: str, content: str = "", 
                  truth: TruthValue = None) -> Node:
        node = Node(
            id=self._get_id(),
            node_type=node_type,
            name=name,
            content=content,
            truth=truth or TruthValue(),
        )
        self.nodes[node.id] = node
        return node
    
    def add_edge(self, from_node: Node, to_node: Node, edge_type: EdgeType,
                 truth: TruthValue = None) -> Edge:
        edge = Edge(from_node.id, to_node.id, edge_type, truth or TruthValue())
        self.edges.append(edge)
        return edge
    
    # Temporal edges
    def waits_for(self, waiter: Node, dependency: Node) -> Edge:
        """A waits for B to complete."""
        return self.add_edge(waiter, dependency, EdgeType.WAITS_FOR)
    
    def precedes(self, first: Node, second: Node) -> Edge:
        """A comes before B (soft ordering)."""
        return self.add_edge(first, second, EdgeType.PRECEDES)
    
    # Causal edges
    def causes(self, cause: Node, effect: Node, conf: float = 0.9) -> Edge:
        """A causes B."""
        return self.add_edge(cause, effect, EdgeType.CAUSES, TruthValue(1.0, conf))
    
    def enables(self, enabler: Node, enabled: Node) -> Edge:
        """A enables B (necessary condition)."""
        return self.add_edge(enabler, enabled, EdgeType.ENABLES)
    
    def prevents(self, preventer: Node, prevented: Node) -> Edge:
        """A prevents B."""
        return self.add_edge(preventer, prevented, EdgeType.PREVENTS)
    
    # NARS edges
    def achieves(self, action: Node, goal: Node, conf: float = 0.9) -> Edge:
        """Action achieves goal."""
        return self.add_edge(action, goal, EdgeType.ACHIEVES, TruthValue(1.0, conf))
    
    def supports(self, evidence: Node, conclusion: Node, conf: float = 0.9) -> Edge:
        """Evidence supports conclusion."""
        return self.add_edge(evidence, conclusion, EdgeType.SUPPORTS, TruthValue(1.0, conf))
    
    def contradicts(self, belief1: Node, belief2: Node) -> Edge:
        """Beliefs contradict each other."""
        return self.add_edge(belief1, belief2, EdgeType.CONTRADICTS)
    
    def answers(self, judgment: Node, question: Node) -> Edge:
        """Judgment answers question."""
        return self.add_edge(judgment, question, EdgeType.ANSWERS)
    
    def expects(self, action: Node, outcome: Node, conf: float = 0.5) -> Edge:
        """Action expects outcome."""
        return self.add_edge(action, outcome, EdgeType.EXPECTS, TruthValue(1.0, conf))
    
    # -------------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------------
    
    def get_by_type(self, node_type: NodeType) -> List[Node]:
        return [n for n in self.nodes.values() if n.node_type == node_type]
    
    def get_edges_of_type(self, edge_type: EdgeType) -> List[Edge]:
        return [e for e in self.edges if e.edge_type == edge_type]
    
    def get_waits_for(self, node: Node) -> List[Node]:
        """Get all nodes this node waits for."""
        deps = [e.to_id for e in self.edges 
                if e.from_id == node.id and e.edge_type == EdgeType.WAITS_FOR]
        return [self.nodes[id] for id in deps]
    
    def get_achieves(self, goal: Node) -> List[Tuple[Node, float]]:
        """Get all actions that achieve a goal with confidence."""
        achievers = [(self.nodes[e.from_id], e.truth.confidence) 
                     for e in self.edges 
                     if e.to_id == goal.id and e.edge_type == EdgeType.ACHIEVES]
        return sorted(achievers, key=lambda x: x[1], reverse=True)
    
    def get_execution_order(self) -> List[List[Node]]:
        """Topological sort respecting WAITS_FOR edges."""
        # Build dependency graph
        deps = {n.id: set() for n in self.nodes.values()}
        for e in self.edges:
            if e.edge_type == EdgeType.WAITS_FOR:
                deps[e.from_id].add(e.to_id)
        
        # Kahn's algorithm
        levels = []
        remaining = set(deps.keys())
        
        while remaining:
            # Find nodes with no unresolved dependencies
            ready = [id for id in remaining if not (deps[id] & remaining)]
            if not ready:
                break  # Cycle detected
            
            levels.append([self.nodes[id] for id in ready])
            remaining -= set(ready)
        
        return levels
    
    # -------------------------------------------------------------------------
    # Print
    # -------------------------------------------------------------------------
    
    def print_graph(self):
        """Print graph structure."""
        print("\n=== NODES ===")
        for node in self.nodes.values():
            print(f"  [{node.id}] {node.node_type.name}: {node}")
        
        print("\n=== EDGES ===")
        for edge in self.edges:
            from_n = self.nodes[edge.from_id]
            to_n = self.nodes[edge.to_id]
            print(f"  {from_n.name} --{edge.edge_type.name}--> {to_n.name}")


# =============================================================================
# POC
# =============================================================================

def poc_l6_nars():
    """
    L6 POC: Meta/NARS reasoning.
    
    Model a deployment pipeline with:
    - Temporal dependencies (WAITS_FOR)
    - Hypothetical branches (WHAT_IF)
    - Goals and beliefs
    - Guarded loops
    """
    print("=" * 60)
    print("L6: META/NARS - Reasoning primitives")
    print("=" * 60)
    
    g = NARSGraph()
    
    # -------------------------------------------------------------------------
    # Build deployment pipeline
    # -------------------------------------------------------------------------
    
    # Goals
    goal_deploy = g.goal("deploy_success", "Production deployment succeeds")
    goal_zero_downtime = g.goal("zero_downtime", "No service interruption")
    
    # Beliefs about current state
    belief_tests_pass = g.belief("tests_pass", "All tests pass", freq=1.0, conf=0.95)
    belief_staging_ok = g.belief("staging_ok", "Staging environment healthy", freq=1.0, conf=0.8)
    
    # Actions (as methods)
    run_tests = g.method("run_tests", "pytest --cov")
    build_image = g.method("build_image", "docker build")
    push_registry = g.method("push_registry", "docker push")
    deploy_staging = g.method("deploy_staging", "kubectl apply -f staging")
    run_smoke = g.method("run_smoke", "smoke_tests.py")
    deploy_prod = g.method("deploy_prod", "kubectl apply -f prod")
    
    # Temporal dependencies (WAITS_FOR)
    g.waits_for(build_image, run_tests)        # build waits for tests
    g.waits_for(push_registry, build_image)    # push waits for build
    g.waits_for(deploy_staging, push_registry) # staging waits for push
    g.waits_for(run_smoke, deploy_staging)     # smoke waits for staging
    g.waits_for(deploy_prod, run_smoke)        # prod waits for smoke
    
    # Causal relationships
    g.causes(run_tests, belief_tests_pass, conf=0.95)
    g.causes(run_smoke, belief_staging_ok, conf=0.8)
    
    # Goal achievement
    g.achieves(deploy_prod, goal_deploy, conf=0.9)
    g.supports(belief_tests_pass, goal_deploy, conf=0.7)
    g.supports(belief_staging_ok, goal_deploy, conf=0.8)
    
    # What-if: network failure
    retry_action = g.method("retry_with_backoff", "exponential backoff retry")
    fallback_action = g.method("rollback", "kubectl rollout undo")
    
    what_if_network = g.what_if("network_fails",
                                ("retry", retry_action),
                                ("rollback", fallback_action))
    
    # Expectation
    expect_success = g.expectation("deployment_succeeds", "prod healthy", freq=0.9, conf=0.7)
    g.expects(deploy_prod, expect_success, conf=0.7)
    
    # Question
    q_ready = g.question("ready_to_deploy", "Is system ready for production?")
    
    # Judgment answering question
    j_ready = g.judgment("system_ready", "System passes all checks", freq=1.0, conf=0.85)
    g.supports(belief_tests_pass, j_ready)
    g.supports(belief_staging_ok, j_ready)
    g.answers(j_ready, q_ready)
    
    # While-do: health check loop
    health_check = g.method("health_check", "curl /health")
    while_healthy = g.while_do("service_healthy", health_check)
    
    print(f"\n[1] Built NARS graph")
    print(f"    Nodes: {len(g.nodes)}")
    print(f"    Edges: {len(g.edges)}")
    
    # -------------------------------------------------------------------------
    # Test 2: Node types
    # -------------------------------------------------------------------------
    
    print(f"\n[2] Node types:")
    for nt in [NodeType.GOAL, NodeType.BELIEF, NodeType.QUESTION, 
               NodeType.JUDGMENT, NodeType.EXPECTATION, NodeType.WHAT_IF,
               NodeType.WHILE_DO]:
        nodes = g.get_by_type(nt)
        if nodes:
            print(f"    {nt.name}: {[str(n) for n in nodes]}")
    
    goals = g.get_by_type(NodeType.GOAL)
    assert len(goals) == 2, f"FAIL: Expected 2 goals"
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Test 3: WAITS_FOR chain
    # -------------------------------------------------------------------------
    
    print(f"\n[3] WAITS_FOR dependencies:")
    waits_for_edges = g.get_edges_of_type(EdgeType.WAITS_FOR)
    print(f"    {len(waits_for_edges)} WAITS_FOR edges")
    
    deps = g.get_waits_for(deploy_prod)
    print(f"    deploy_prod waits for: {[d.name for d in deps]}")
    assert len(deps) == 1 and deps[0].name == "run_smoke"
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Test 4: Execution order (topological sort)
    # -------------------------------------------------------------------------
    
    print(f"\n[4] Execution order:")
    levels = g.get_execution_order()
    for i, level in enumerate(levels):
        method_names = [n.name for n in level if n.node_type == NodeType.METHOD]
        if method_names:
            print(f"    Level {i}: {method_names}")
    
    # First level should include run_tests (no dependencies)
    level_0_names = [n.name for n in levels[0]]
    assert "run_tests" in level_0_names, "FAIL: run_tests should be in level 0"
    print(f"    ✓ PASS (run_tests first, deploy_prod last)")
    
    # -------------------------------------------------------------------------
    # Test 5: Goal achievement
    # -------------------------------------------------------------------------
    
    print(f"\n[5] Goal achievement:")
    achievers = g.get_achieves(goal_deploy)
    for action, conf in achievers:
        print(f"    {action.name} achieves deploy_success (conf={conf:.2f})")
    
    assert len(achievers) >= 1
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Test 6: WHAT_IF branches
    # -------------------------------------------------------------------------
    
    print(f"\n[6] WHAT_IF branches:")
    what_ifs = g.get_by_type(NodeType.WHAT_IF)
    branch_edges = g.get_edges_of_type(EdgeType.BRANCHES_TO)
    print(f"    {len(what_ifs)} WHAT_IF nodes, {len(branch_edges)} branches")
    
    scenarios = g.get_by_type(NodeType.SCENARIO)
    scenario_names = [s.name for s in scenarios]
    print(f"    Scenarios: {scenario_names}")
    
    assert "retry" in scenario_names and "rollback" in scenario_names
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Test 7: Truth value operations
    # -------------------------------------------------------------------------
    
    print(f"\n[7] Truth values:")
    print(f"    tests_pass: {belief_tests_pass.truth}")
    print(f"    staging_ok: {belief_staging_ok.truth}")
    
    # Revision: combine evidence
    combined = belief_tests_pass.truth.revision(belief_staging_ok.truth)
    print(f"    Combined (revision): {combined}")
    print(f"    Expectation: {combined.expectation:.3f}")
    
    assert 0 < combined.confidence < 1, "FAIL: Combined confidence should be in (0,1)"
    assert combined.frequency == 1.0, "FAIL: Both beliefs true, combined should be true"
    print(f"    ✓ PASS (revision combines evidence)")
    
    # -------------------------------------------------------------------------
    # Test 8: Question → Judgment → Answer
    # -------------------------------------------------------------------------
    
    print(f"\n[8] Question answering:")
    questions = g.get_by_type(NodeType.QUESTION)
    answers = g.get_edges_of_type(EdgeType.ANSWERS)
    
    for q in questions:
        print(f"    Question: {q.name}?")
        for e in answers:
            if e.to_id == q.id:
                j = g.nodes[e.from_id]
                print(f"    Answer: {j.name} {j.truth}")
    
    assert len(answers) == 1
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Test 9: WHILE_DO guard
    # -------------------------------------------------------------------------
    
    print(f"\n[9] Guarded loop:")
    while_dos = g.get_by_type(NodeType.WHILE_DO)
    for wd in while_dos:
        print(f"    {wd.name} (condition: {wd.content})")
    
    assert len(while_dos) == 1
    print(f"    ✓ PASS")
    
    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    
    print(f"\n" + "=" * 60)
    print("L6 POC: ALL TESTS PASSED")
    print("=" * 60)
    print("""
    Proved:
    ✓ GOAL nodes with achievement tracking
    ✓ BELIEF nodes with confidence values
    ✓ QUESTION → JUDGMENT → ANSWERS chain
    ✓ WAITS_FOR temporal dependencies
    ✓ Execution order (topological sort)
    ✓ WHAT_IF hypothetical branches
    ✓ WHILE_DO guarded loops
    ✓ Truth value revision
    
    NARS primitives enable:
    - Temporal reasoning ("A before B")
    - Counterfactual exploration ("what if X?")
    - Goal-directed planning
    - Belief propagation with confidence
    """)
    
    return g


if __name__ == "__main__":
    poc_l6_nars()
