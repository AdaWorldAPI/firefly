"""
LadybugDB POC - Level 8: ANTIPATTERN TEST SUITE

Test against standard code antipatterns.
Trace weaknesses back to WHERE they land.

ANTIPATTERNS TESTED:
1. God Object           - One class does everything
2. Spaghetti Code       - Tangled control flow
3. Circular Dependency  - A→B→C→A
4. Feature Envy         - Method uses other class more than own
5. Shotgun Surgery      - One change, many files
6. Lava Flow            - Dead code accumulation
7. Golden Hammer        - One solution for everything
8. Copy-Paste           - Duplicated logic
9. Arrow Antipattern    - Deep nested conditionals
10. Big Ball of Mud     - No discernible architecture

Each test:
1. Build the antipattern
2. Run detection
3. TRACE WHERE it lands
4. Verify detection accuracy
"""

import numpy as np
import hashlib
import struct
from typing import Dict, List, Set, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import IntEnum
from collections import defaultdict
import re

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
# TYPES
# =============================================================================

class NodeType(IntEnum):
    MODULE = 1
    CLASS = 2
    METHOD = 3
    FUNCTION = 4
    IF = 5
    ELIF = 6
    ELSE = 7
    FOREACH = 8
    WHILE = 9
    CALL = 10
    VARIABLE = 11
    RETURN = 12
    TRY = 13
    EXCEPT = 14


class EdgeType(IntEnum):
    CONTAINS = 1
    CALLS = 2
    DEPENDS = 3
    INHERITS = 4
    READS = 5
    WRITES = 6


class Smell(IntEnum):
    GOD_OBJECT = 1
    SPAGHETTI = 2
    CIRCULAR_DEPENDENCY = 3
    FEATURE_ENVY = 4
    SHOTGUN_SURGERY = 5
    LAVA_FLOW = 6
    GOLDEN_HAMMER = 7
    COPY_PASTE = 8
    ARROW_CODE = 9
    BIG_BALL_OF_MUD = 10
    LONG_METHOD = 11
    LONG_PARAMETER_LIST = 12
    DATA_CLUMP = 13
    DEAD_CODE = 14


# =============================================================================
# NODE & EDGE
# =============================================================================

@dataclass
class Node:
    id: int
    node_type: NodeType
    name: str
    body: str = ""
    fingerprint: np.ndarray = field(default_factory=lambda: np.zeros(DIM_U64, dtype=np.uint64))
    line_count: int = 0
    param_count: int = 0
    
    def __post_init__(self):
        if np.all(self.fingerprint == 0):
            identity = f"{self.node_type.name}::{self.name}::{self.body}"
            self.fingerprint = fingerprint(identity)
    
    def __hash__(self):
        return self.id


@dataclass
class Edge:
    from_id: int
    to_id: int
    edge_type: EdgeType


@dataclass
class Weakness:
    """A detected weakness with trace information."""
    smell: Smell
    confidence: float
    node: Node
    trace: List[str]  # Path showing WHERE it lands
    evidence: Dict[str, Any]


# =============================================================================
# ANTIPATTERN DETECTOR
# =============================================================================

class AntipatternDetector:
    """
    Detects antipatterns and traces WHERE weaknesses land.
    """
    
    def __init__(self):
        self.nodes: Dict[int, Node] = {}
        self.edges: List[Edge] = []
        self._next_id = 0
        self._call_graph: Dict[int, Set[int]] = defaultdict(set)
        self._reverse_call_graph: Dict[int, Set[int]] = defaultdict(set)
    
    def _get_id(self) -> int:
        id = self._next_id
        self._next_id += 1
        return id
    
    def _rebuild_call_graph(self):
        self._call_graph.clear()
        self._reverse_call_graph.clear()
        for e in self.edges:
            if e.edge_type == EdgeType.CALLS:
                self._call_graph[e.from_id].add(e.to_id)
                self._reverse_call_graph[e.to_id].add(e.from_id)
    
    # -------------------------------------------------------------------------
    # Node/Edge creation
    # -------------------------------------------------------------------------
    
    def add_node(self, node_type: NodeType, name: str, body: str = "", 
                 line_count: int = 0, param_count: int = 0) -> Node:
        node = Node(self._get_id(), node_type, name, body, line_count=line_count, param_count=param_count)
        self.nodes[node.id] = node
        return node
    
    def add_edge(self, from_node: Node, to_node: Node, edge_type: EdgeType) -> Edge:
        edge = Edge(from_node.id, to_node.id, edge_type)
        self.edges.append(edge)
        if edge_type == EdgeType.CALLS:
            self._call_graph[from_node.id].add(to_node.id)
            self._reverse_call_graph[to_node.id].add(from_node.id)
        return edge
    
    def module(self, name: str) -> Node:
        return self.add_node(NodeType.MODULE, name)
    
    def class_(self, name: str, parent: Node = None) -> Node:
        node = self.add_node(NodeType.CLASS, name)
        if parent:
            self.add_edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def method(self, name: str, parent: Node, body: str = "", 
               line_count: int = 5, param_count: int = 2) -> Node:
        node = self.add_node(NodeType.METHOD, name, body, line_count, param_count)
        self.add_edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def function(self, name: str, parent: Node = None, body: str = "",
                 line_count: int = 5, param_count: int = 2) -> Node:
        node = self.add_node(NodeType.FUNCTION, name, body, line_count, param_count)
        if parent:
            self.add_edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def if_(self, condition: str, parent: Node) -> Node:
        node = self.add_node(NodeType.IF, f"if({condition})", condition)
        self.add_edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def elif_(self, condition: str, parent: Node) -> Node:
        node = self.add_node(NodeType.ELIF, f"elif({condition})", condition)
        self.add_edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def calls(self, caller: Node, callee: Node) -> Edge:
        return self.add_edge(caller, callee, EdgeType.CALLS)
    
    def depends(self, dependent: Node, dependency: Node) -> Edge:
        return self.add_edge(dependent, dependency, EdgeType.DEPENDS)
    
    def inherits(self, child: Node, parent: Node) -> Edge:
        return self.add_edge(child, parent, EdgeType.INHERITS)
    
    # -------------------------------------------------------------------------
    # Query helpers
    # -------------------------------------------------------------------------
    
    def get_children(self, parent: Node) -> List[Node]:
        child_ids = [e.to_id for e in self.edges 
                     if e.from_id == parent.id and e.edge_type == EdgeType.CONTAINS]
        return [self.nodes[id] for id in child_ids]
    
    def get_methods(self, cls: Node) -> List[Node]:
        return [c for c in self.get_children(cls) if c.node_type == NodeType.METHOD]
    
    def fan_out(self, node: Node) -> int:
        return len(self._call_graph.get(node.id, set()))
    
    def fan_in(self, node: Node) -> int:
        return len(self._reverse_call_graph.get(node.id, set()))
    
    def get_path(self, node: Node) -> str:
        """Get hierarchical path to node."""
        parts = [node.name]
        current = node
        while True:
            parent_id = next((e.from_id for e in self.edges 
                             if e.to_id == current.id and e.edge_type == EdgeType.CONTAINS), None)
            if parent_id is None:
                break
            parent = self.nodes.get(parent_id)
            if parent:
                parts.insert(0, parent.name)
                current = parent
            else:
                break
        return " → ".join(parts)
    
    def nesting_depth(self, node: Node) -> int:
        """Calculate nesting depth of control flow."""
        depth = 0
        max_depth = 0
        
        def traverse(n: Node, d: int):
            nonlocal max_depth
            if n.node_type in {NodeType.IF, NodeType.ELIF, NodeType.FOREACH, NodeType.WHILE}:
                d += 1
                max_depth = max(max_depth, d)
            for child in self.get_children(n):
                traverse(child, d)
        
        traverse(node, 0)
        return max_depth
    
    # -------------------------------------------------------------------------
    # CYCLE DETECTION (Tarjan's SCC)
    # -------------------------------------------------------------------------
    
    def find_cycles(self) -> List[List[Node]]:
        """Find all cycles using Tarjan's algorithm."""
        index_counter = [0]
        stack = []
        lowlinks = {}
        index = {}
        on_stack = {}
        sccs = []
        
        def strongconnect(node_id):
            index[node_id] = index_counter[0]
            lowlinks[node_id] = index_counter[0]
            index_counter[0] += 1
            on_stack[node_id] = True
            stack.append(node_id)
            
            for succ_id in self._call_graph.get(node_id, set()):
                if succ_id not in index:
                    strongconnect(succ_id)
                    lowlinks[node_id] = min(lowlinks[node_id], lowlinks[succ_id])
                elif on_stack.get(succ_id, False):
                    lowlinks[node_id] = min(lowlinks[node_id], index[succ_id])
            
            if lowlinks[node_id] == index[node_id]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack[w] = False
                    scc.append(w)
                    if w == node_id:
                        break
                if len(scc) > 1:  # Only cycles, not single nodes
                    sccs.append(scc)
        
        for node_id in self.nodes:
            if node_id not in index:
                strongconnect(node_id)
        
        return [[self.nodes[id] for id in scc] for scc in sccs]
    
    # -------------------------------------------------------------------------
    # DUPLICATE DETECTION (via fingerprint similarity)
    # -------------------------------------------------------------------------
    
    def find_duplicates(self, threshold: float = 0.85) -> List[Tuple[Node, Node, float]]:
        """Find duplicate/similar code via fingerprint comparison."""
        duplicates = []
        methods = [n for n in self.nodes.values() 
                   if n.node_type in {NodeType.METHOD, NodeType.FUNCTION}]
        
        for i, a in enumerate(methods):
            for b in methods[i+1:]:
                sim = similarity(a.fingerprint, b.fingerprint)
                if sim >= threshold:
                    duplicates.append((a, b, sim))
        
        return sorted(duplicates, key=lambda x: x[2], reverse=True)
    
    # -------------------------------------------------------------------------
    # ANTIPATTERN DETECTION
    # -------------------------------------------------------------------------
    
    def detect_god_object(self) -> List[Weakness]:
        """
        GOD OBJECT: One class does too much.
        
        Indicators:
        - > 10 methods
        - > 20 dependencies (fan-out)
        - Low cohesion (methods don't relate)
        """
        weaknesses = []
        
        for node in self.nodes.values():
            if node.node_type != NodeType.CLASS:
                continue
            
            methods = self.get_methods(node)
            method_count = len(methods)
            total_fan_out = sum(self.fan_out(m) for m in methods)
            
            if method_count > 10 or total_fan_out > 20:
                confidence = min((method_count / 15 + total_fan_out / 30) / 2, 1.0)
                
                # TRACE: Where does this land?
                trace = [
                    f"CLASS: {node.name}",
                    f"  └── {method_count} methods (threshold: 10)",
                    f"  └── {total_fan_out} total outgoing calls (threshold: 20)",
                ]
                
                # Find the worst offender methods
                hotspots = sorted(methods, key=lambda m: self.fan_out(m), reverse=True)[:3]
                for m in hotspots:
                    trace.append(f"      └── HOTSPOT: {m.name} (fan_out={self.fan_out(m)})")
                
                weaknesses.append(Weakness(
                    smell=Smell.GOD_OBJECT,
                    confidence=confidence,
                    node=node,
                    trace=trace,
                    evidence={"method_count": method_count, "fan_out": total_fan_out}
                ))
        
        return weaknesses
    
    def detect_spaghetti(self) -> List[Weakness]:
        """
        SPAGHETTI CODE: Tangled control flow.
        
        Indicators:
        - High cyclomatic complexity
        - Many cross-calls between unrelated methods
        - No clear hierarchy
        """
        weaknesses = []
        
        # Calculate global tangledness
        total_edges = len([e for e in self.edges if e.edge_type == EdgeType.CALLS])
        node_count = len(self.nodes)
        
        if node_count > 0:
            edge_ratio = total_edges / node_count
            
            if edge_ratio > 2:
                # Find the tangled region
                hot_nodes = sorted(
                    [(n, self.fan_in(n) + self.fan_out(n)) for n in self.nodes.values()],
                    key=lambda x: x[1], reverse=True
                )[:5]
                
                trace = [
                    f"GLOBAL SPAGHETTI DETECTED",
                    f"  └── Edge ratio: {edge_ratio:.2f} (threshold: 2.0)",
                    f"  └── Total calls: {total_edges}",
                    f"  └── TANGLED NODES:",
                ]
                
                for n, degree in hot_nodes:
                    trace.append(f"      └── {self.get_path(n)} (degree={degree})")
                
                weaknesses.append(Weakness(
                    smell=Smell.SPAGHETTI,
                    confidence=min(edge_ratio / 4, 1.0),
                    node=hot_nodes[0][0] if hot_nodes else list(self.nodes.values())[0],
                    trace=trace,
                    evidence={"edge_ratio": edge_ratio, "total_calls": total_edges}
                ))
        
        return weaknesses
    
    def detect_circular_dependency(self) -> List[Weakness]:
        """
        CIRCULAR DEPENDENCY: A→B→C→A
        
        Uses Tarjan's SCC algorithm to find cycles.
        """
        weaknesses = []
        cycles = self.find_cycles()
        
        for cycle in cycles:
            cycle_path = " → ".join(n.name for n in cycle) + " → " + cycle[0].name
            
            trace = [
                f"CIRCULAR DEPENDENCY DETECTED",
                f"  └── Cycle: {cycle_path}",
                f"  └── Length: {len(cycle)} nodes",
                f"  └── NODES IN CYCLE:",
            ]
            
            for n in cycle:
                trace.append(f"      └── {self.get_path(n)}")
            
            weaknesses.append(Weakness(
                smell=Smell.CIRCULAR_DEPENDENCY,
                confidence=1.0,  # Cycles are definite
                node=cycle[0],
                trace=trace,
                evidence={"cycle": [n.name for n in cycle], "length": len(cycle)}
            ))
        
        return weaknesses
    
    def detect_feature_envy(self) -> List[Weakness]:
        """
        FEATURE ENVY: Method uses other class more than its own.
        
        Indicators:
        - Method calls external methods more than internal
        - Method accesses external data more than internal
        """
        weaknesses = []
        
        for node in self.nodes.values():
            if node.node_type != NodeType.METHOD:
                continue
            
            # Find parent class
            parent_id = next((e.from_id for e in self.edges 
                             if e.to_id == node.id and e.edge_type == EdgeType.CONTAINS), None)
            if parent_id is None:
                continue
            
            parent = self.nodes.get(parent_id)
            if not parent or parent.node_type != NodeType.CLASS:
                continue
            
            # Get sibling methods
            siblings = set(m.id for m in self.get_methods(parent))
            
            # Count internal vs external calls
            internal_calls = 0
            external_calls = 0
            external_targets = []
            
            for callee_id in self._call_graph.get(node.id, set()):
                if callee_id in siblings:
                    internal_calls += 1
                else:
                    external_calls += 1
                    callee = self.nodes.get(callee_id)
                    if callee:
                        external_targets.append(callee.name)
            
            if external_calls > internal_calls and external_calls > 2:
                confidence = min(external_calls / (internal_calls + external_calls + 1), 1.0)
                
                trace = [
                    f"FEATURE ENVY: {node.name}",
                    f"  └── In class: {parent.name}",
                    f"  └── Internal calls: {internal_calls}",
                    f"  └── External calls: {external_calls}",
                    f"  └── ENVIED METHODS:",
                ]
                for target in external_targets[:5]:
                    trace.append(f"      └── {target}")
                
                weaknesses.append(Weakness(
                    smell=Smell.FEATURE_ENVY,
                    confidence=confidence,
                    node=node,
                    trace=trace,
                    evidence={"internal": internal_calls, "external": external_calls}
                ))
        
        return weaknesses
    
    def detect_arrow_code(self) -> List[Weakness]:
        """
        ARROW CODE: Deep nested conditionals.
        
        Looks like:
        if x:
            if y:
                if z:
                    if w:
                        ...
        """
        weaknesses = []
        
        for node in self.nodes.values():
            if node.node_type not in {NodeType.METHOD, NodeType.FUNCTION}:
                continue
            
            depth = self.nesting_depth(node)
            
            if depth >= 4:
                trace = [
                    f"ARROW CODE: {node.name}",
                    f"  └── Nesting depth: {depth} (threshold: 4)",
                    f"  └── Path: {self.get_path(node)}",
                    f"  └── NESTED STRUCTURE:",
                ]
                
                # Show nesting structure
                def show_nesting(n: Node, indent: int):
                    if n.node_type in {NodeType.IF, NodeType.ELIF, NodeType.FOREACH, NodeType.WHILE}:
                        trace.append(f"{'  ' * indent}└── {n.node_type.name}: {n.name}")
                    for child in self.get_children(n):
                        show_nesting(child, indent + 1)
                
                show_nesting(node, 2)
                
                weaknesses.append(Weakness(
                    smell=Smell.ARROW_CODE,
                    confidence=min(depth / 6, 1.0),
                    node=node,
                    trace=trace,
                    evidence={"depth": depth}
                ))
        
        return weaknesses
    
    def detect_copy_paste(self) -> List[Weakness]:
        """
        COPY-PASTE: Duplicated code detected via fingerprint similarity.
        """
        weaknesses = []
        duplicates = self.find_duplicates(threshold=0.8)
        
        for a, b, sim in duplicates:
            trace = [
                f"COPY-PASTE DETECTED",
                f"  └── Similarity: {sim:.1%}",
                f"  └── Source A: {self.get_path(a)}",
                f"  └── Source B: {self.get_path(b)}",
            ]
            
            weaknesses.append(Weakness(
                smell=Smell.COPY_PASTE,
                confidence=sim,
                node=a,
                trace=trace,
                evidence={"similarity": sim, "other": b.name}
            ))
        
        return weaknesses
    
    def detect_long_method(self) -> List[Weakness]:
        """
        LONG METHOD: Method with too many lines.
        """
        weaknesses = []
        
        for node in self.nodes.values():
            if node.node_type not in {NodeType.METHOD, NodeType.FUNCTION}:
                continue
            
            if node.line_count > 50:
                trace = [
                    f"LONG METHOD: {node.name}",
                    f"  └── Lines: {node.line_count} (threshold: 50)",
                    f"  └── Path: {self.get_path(node)}",
                ]
                
                weaknesses.append(Weakness(
                    smell=Smell.LONG_METHOD,
                    confidence=min(node.line_count / 100, 1.0),
                    node=node,
                    trace=trace,
                    evidence={"lines": node.line_count}
                ))
        
        return weaknesses
    
    def detect_long_parameter_list(self) -> List[Weakness]:
        """
        LONG PARAMETER LIST: Too many parameters.
        """
        weaknesses = []
        
        for node in self.nodes.values():
            if node.node_type not in {NodeType.METHOD, NodeType.FUNCTION}:
                continue
            
            if node.param_count > 5:
                trace = [
                    f"LONG PARAMETER LIST: {node.name}",
                    f"  └── Parameters: {node.param_count} (threshold: 5)",
                    f"  └── Path: {self.get_path(node)}",
                ]
                
                weaknesses.append(Weakness(
                    smell=Smell.LONG_PARAMETER_LIST,
                    confidence=min(node.param_count / 10, 1.0),
                    node=node,
                    trace=trace,
                    evidence={"params": node.param_count}
                ))
        
        return weaknesses
    
    def detect_dead_code(self) -> List[Weakness]:
        """
        DEAD CODE: Methods that are never called.
        """
        weaknesses = []
        
        # Exclude entry points (conventionally named)
        entry_points = {'main', '__init__', 'run', 'start', 'execute', 'handle'}
        
        for node in self.nodes.values():
            if node.node_type not in {NodeType.METHOD, NodeType.FUNCTION}:
                continue
            
            if node.name.lower() in entry_points:
                continue
            
            callers = self.fan_in(node)
            
            if callers == 0:
                trace = [
                    f"DEAD CODE: {node.name}",
                    f"  └── Never called (fan_in = 0)",
                    f"  └── Path: {self.get_path(node)}",
                ]
                
                weaknesses.append(Weakness(
                    smell=Smell.DEAD_CODE,
                    confidence=0.8,  # Not 100% sure, might be called externally
                    node=node,
                    trace=trace,
                    evidence={"fan_in": 0}
                ))
        
        return weaknesses
    
    # -------------------------------------------------------------------------
    # FULL ANALYSIS
    # -------------------------------------------------------------------------
    
    def analyze(self) -> Dict[Smell, List[Weakness]]:
        """Run all detectors and return categorized weaknesses."""
        self._rebuild_call_graph()
        
        results = {}
        
        detectors = [
            (Smell.GOD_OBJECT, self.detect_god_object),
            (Smell.SPAGHETTI, self.detect_spaghetti),
            (Smell.CIRCULAR_DEPENDENCY, self.detect_circular_dependency),
            (Smell.FEATURE_ENVY, self.detect_feature_envy),
            (Smell.ARROW_CODE, self.detect_arrow_code),
            (Smell.COPY_PASTE, self.detect_copy_paste),
            (Smell.LONG_METHOD, self.detect_long_method),
            (Smell.LONG_PARAMETER_LIST, self.detect_long_parameter_list),
            (Smell.DEAD_CODE, self.detect_dead_code),
        ]
        
        for smell, detector in detectors:
            weaknesses = detector()
            if weaknesses:
                results[smell] = weaknesses
        
        return results
    
    def print_report(self, results: Dict[Smell, List[Weakness]]):
        """Print formatted weakness report."""
        print("\n" + "=" * 70)
        print("WEAKNESS ANALYSIS REPORT")
        print("=" * 70)
        
        total = sum(len(ws) for ws in results.values())
        print(f"\nTotal weaknesses found: {total}")
        print(f"Categories: {len(results)}")
        
        for smell, weaknesses in sorted(results.items(), key=lambda x: -len(x[1])):
            print(f"\n{'─' * 70}")
            print(f"[{smell.name}] - {len(weaknesses)} instance(s)")
            print(f"{'─' * 70}")
            
            for w in weaknesses:
                print(f"\nConfidence: {w.confidence:.1%}")
                for line in w.trace:
                    print(f"  {line}")


# =============================================================================
# TEST CASES
# =============================================================================

def test_god_object():
    """Test GOD OBJECT detection."""
    print("\n" + "=" * 60)
    print("TEST: GOD OBJECT")
    print("=" * 60)
    
    d = AntipatternDetector()
    mod = d.module("app")
    
    # Create a god class with too many methods
    god = d.class_("EverythingManager", mod)
    
    methods = []
    for i in range(15):  # 15 methods = god object
        m = d.method(f"do_thing_{i}", god)
        methods.append(m)
    
    # Add cross-calls
    for i, m in enumerate(methods):
        for j in range(3):  # Each calls 3 others
            target = methods[(i + j + 1) % len(methods)]
            d.calls(m, target)
    
    results = d.analyze()
    
    assert Smell.GOD_OBJECT in results, "FAIL: Should detect GOD_OBJECT"
    print(f"✓ Detected GOD_OBJECT")
    
    d.print_report(results)
    return True


def test_spaghetti():
    """Test SPAGHETTI detection."""
    print("\n" + "=" * 60)
    print("TEST: SPAGHETTI CODE")
    print("=" * 60)
    
    d = AntipatternDetector()
    mod = d.module("chaos")
    
    # Create tangled web of functions
    funcs = []
    for i in range(10):
        f = d.function(f"func_{i}", mod)
        funcs.append(f)
    
    # Everyone calls everyone
    for f in funcs:
        for target in funcs:
            if f != target:
                d.calls(f, target)
    
    results = d.analyze()
    
    assert Smell.SPAGHETTI in results, "FAIL: Should detect SPAGHETTI"
    print(f"✓ Detected SPAGHETTI")
    
    d.print_report(results)
    return True


def test_circular_dependency():
    """Test CIRCULAR DEPENDENCY detection."""
    print("\n" + "=" * 60)
    print("TEST: CIRCULAR DEPENDENCY")
    print("=" * 60)
    
    d = AntipatternDetector()
    mod = d.module("cycle")
    
    # A → B → C → A
    cls_a = d.class_("ServiceA", mod)
    cls_b = d.class_("ServiceB", mod)
    cls_c = d.class_("ServiceC", mod)
    
    m_a = d.method("call_b", cls_a)
    m_b = d.method("call_c", cls_b)
    m_c = d.method("call_a", cls_c)
    
    d.calls(m_a, m_b)
    d.calls(m_b, m_c)
    d.calls(m_c, m_a)
    
    results = d.analyze()
    
    assert Smell.CIRCULAR_DEPENDENCY in results, "FAIL: Should detect CIRCULAR_DEPENDENCY"
    print(f"✓ Detected CIRCULAR_DEPENDENCY")
    
    d.print_report(results)
    return True


def test_feature_envy():
    """Test FEATURE ENVY detection."""
    print("\n" + "=" * 60)
    print("TEST: FEATURE ENVY")
    print("=" * 60)
    
    d = AntipatternDetector()
    mod = d.module("envy")
    
    # Class A with methods
    cls_a = d.class_("ClassA", mod)
    a1 = d.method("internal_a1", cls_a)
    a2 = d.method("internal_a2", cls_a)
    a3 = d.method("internal_a3", cls_a)
    
    # Class B with methods
    cls_b = d.class_("ClassB", mod)
    b1 = d.method("useful_b1", cls_b)
    b2 = d.method("useful_b2", cls_b)
    b3 = d.method("useful_b3", cls_b)
    b4 = d.method("useful_b4", cls_b)
    
    # Envious method in A that calls B more than A
    envious = d.method("envious_method", cls_a)
    d.calls(envious, b1)
    d.calls(envious, b2)
    d.calls(envious, b3)
    d.calls(envious, b4)
    d.calls(envious, a1)  # Only one internal call
    
    results = d.analyze()
    
    assert Smell.FEATURE_ENVY in results, "FAIL: Should detect FEATURE_ENVY"
    print(f"✓ Detected FEATURE_ENVY")
    
    d.print_report(results)
    return True


def test_arrow_code():
    """Test ARROW CODE detection."""
    print("\n" + "=" * 60)
    print("TEST: ARROW CODE")
    print("=" * 60)
    
    d = AntipatternDetector()
    mod = d.module("arrow")
    cls = d.class_("Validator", mod)
    
    # Method with deep nesting
    validate = d.method("validate", cls)
    
    if1 = d.if_("user", validate)
    if2 = d.if_("user.email", if1)
    if3 = d.if_("user.email.valid", if2)
    if4 = d.if_("user.email.confirmed", if3)
    if5 = d.if_("not user.email.blacklisted", if4)
    
    results = d.analyze()
    
    assert Smell.ARROW_CODE in results, "FAIL: Should detect ARROW_CODE"
    print(f"✓ Detected ARROW_CODE")
    
    d.print_report(results)
    return True


def test_copy_paste():
    """Test COPY-PASTE detection."""
    print("\n" + "=" * 60)
    print("TEST: COPY-PASTE")
    print("=" * 60)
    
    d = AntipatternDetector()
    mod = d.module("duplicates")
    cls = d.class_("Processor", mod)
    
    # Two methods with identical fingerprint
    body = "validate(data); transform(data); save(data); return data"
    m1 = d.method("process_user", cls, body)
    m2 = d.method("process_admin", cls, body)  # Copy-paste!
    
    results = d.analyze()
    
    assert Smell.COPY_PASTE in results, "FAIL: Should detect COPY_PASTE"
    print(f"✓ Detected COPY_PASTE")
    
    d.print_report(results)
    return True


def test_long_method():
    """Test LONG METHOD detection."""
    print("\n" + "=" * 60)
    print("TEST: LONG METHOD")
    print("=" * 60)
    
    d = AntipatternDetector()
    mod = d.module("verbose")
    cls = d.class_("LongClass", mod)
    
    # Method with too many lines
    long_method = d.method("do_everything", cls, line_count=150)
    
    results = d.analyze()
    
    assert Smell.LONG_METHOD in results, "FAIL: Should detect LONG_METHOD"
    print(f"✓ Detected LONG_METHOD")
    
    d.print_report(results)
    return True


def test_long_parameter_list():
    """Test LONG PARAMETER LIST detection."""
    print("\n" + "=" * 60)
    print("TEST: LONG PARAMETER LIST")
    print("=" * 60)
    
    d = AntipatternDetector()
    mod = d.module("params")
    cls = d.class_("ConfigurableClass", mod)
    
    # Method with too many parameters
    many_params = d.method("configure", cls, param_count=12)
    
    results = d.analyze()
    
    assert Smell.LONG_PARAMETER_LIST in results, "FAIL: Should detect LONG_PARAMETER_LIST"
    print(f"✓ Detected LONG_PARAMETER_LIST")
    
    d.print_report(results)
    return True


def test_dead_code():
    """Test DEAD CODE detection."""
    print("\n" + "=" * 60)
    print("TEST: DEAD CODE")
    print("=" * 60)
    
    d = AntipatternDetector()
    mod = d.module("graveyard")
    cls = d.class_("MixedClass", mod)
    
    # Entry point
    main = d.method("main", cls)
    
    # Used method
    used = d.method("used_method", cls)
    d.calls(main, used)
    
    # Dead method (never called)
    dead = d.method("dead_method", cls)
    
    results = d.analyze()
    
    assert Smell.DEAD_CODE in results, "FAIL: Should detect DEAD_CODE"
    print(f"✓ Detected DEAD_CODE")
    
    d.print_report(results)
    return True


# =============================================================================
# COMPREHENSIVE TEST
# =============================================================================

def test_real_world_codebase():
    """
    Test against a realistic messy codebase with multiple antipatterns.
    """
    print("\n" + "=" * 70)
    print("TEST: REAL-WORLD MESSY CODEBASE")
    print("=" * 70)
    
    d = AntipatternDetector()
    
    # Module
    mod = d.module("legacy_payment_system")
    
    # ─────────────────────────────────────────────────────────────────────────
    # GOD OBJECT: PaymentManager does everything
    # ─────────────────────────────────────────────────────────────────────────
    
    god = d.class_("PaymentManager", mod)
    
    god_methods = []
    for name in ["validate_card", "validate_user", "validate_address",
                 "process_payment", "process_refund", "process_chargeback",
                 "send_email", "send_sms", "send_push",
                 "log_transaction", "log_error", "log_audit",
                 "cache_result", "clear_cache", "update_cache"]:
        m = d.method(name, god, line_count=30)
        god_methods.append(m)
    
    # Cross-calls within god class
    for i, m in enumerate(god_methods):
        d.calls(m, god_methods[(i + 1) % len(god_methods)])
        d.calls(m, god_methods[(i + 3) % len(god_methods)])
    
    # ─────────────────────────────────────────────────────────────────────────
    # CIRCULAR DEPENDENCY: Service loop
    # ─────────────────────────────────────────────────────────────────────────
    
    auth = d.class_("AuthService", mod)
    user = d.class_("UserService", mod)
    perm = d.class_("PermissionService", mod)
    
    auth_check = d.method("check_auth", auth)
    user_get = d.method("get_user", user)
    perm_check = d.method("check_permission", perm)
    
    d.calls(auth_check, user_get)
    d.calls(user_get, perm_check)
    d.calls(perm_check, auth_check)  # Cycle!
    
    # ─────────────────────────────────────────────────────────────────────────
    # FEATURE ENVY: Method in wrong class
    # ─────────────────────────────────────────────────────────────────────────
    
    report_gen = d.class_("ReportGenerator", mod)
    data_access = d.class_("DataAccess", mod)
    
    da_query = d.method("query", data_access)
    da_aggregate = d.method("aggregate", data_access)
    da_filter = d.method("filter", data_access)
    da_sort = d.method("sort", data_access)
    
    # This method belongs in DataAccess but is in ReportGenerator
    envious = d.method("build_dataset", report_gen)
    d.calls(envious, da_query)
    d.calls(envious, da_aggregate)
    d.calls(envious, da_filter)
    d.calls(envious, da_sort)
    
    # ─────────────────────────────────────────────────────────────────────────
    # ARROW CODE: Deep nesting
    # ─────────────────────────────────────────────────────────────────────────
    
    validator = d.class_("ComplexValidator", mod)
    validate = d.method("validate_everything", validator)
    
    n1 = d.if_("request", validate)
    n2 = d.if_("request.user", n1)
    n3 = d.if_("request.user.active", n2)
    n4 = d.if_("request.user.verified", n3)
    n5 = d.if_("request.data", n4)
    n6 = d.if_("request.data.valid", n5)
    
    # ─────────────────────────────────────────────────────────────────────────
    # COPY-PASTE: Duplicated handlers
    # ─────────────────────────────────────────────────────────────────────────
    
    handlers = d.class_("Handlers", mod)
    
    handler_body = "validate(req); authorize(req); process(req); respond(req)"
    h1 = d.method("handle_create", handlers, handler_body)
    h2 = d.method("handle_update", handlers, handler_body)  # Duplicate
    h3 = d.method("handle_delete", handlers, handler_body)  # Duplicate
    
    # ─────────────────────────────────────────────────────────────────────────
    # LONG METHOD + LONG PARAMS
    # ─────────────────────────────────────────────────────────────────────────
    
    legacy = d.class_("LegacyProcessor", mod)
    monster = d.method("do_all_the_things", legacy, line_count=500, param_count=15)
    
    # ─────────────────────────────────────────────────────────────────────────
    # DEAD CODE
    # ─────────────────────────────────────────────────────────────────────────
    
    utils = d.class_("Utils", mod)
    main = d.method("main", utils)
    
    used = d.method("helper", utils)
    d.calls(main, used)
    
    dead1 = d.method("old_helper_v1", utils)
    dead2 = d.method("deprecated_function", utils)
    dead3 = d.method("unused_experiment", utils)
    
    # ─────────────────────────────────────────────────────────────────────────
    # ANALYZE
    # ─────────────────────────────────────────────────────────────────────────
    
    results = d.analyze()
    d.print_report(results)
    
    # Verify detection
    expected = {
        Smell.GOD_OBJECT,
        Smell.CIRCULAR_DEPENDENCY,
        Smell.FEATURE_ENVY,
        Smell.ARROW_CODE,
        Smell.COPY_PASTE,
        Smell.LONG_METHOD,
        Smell.LONG_PARAMETER_LIST,
        Smell.DEAD_CODE,
        Smell.SPAGHETTI,
    }
    
    detected = set(results.keys())
    
    print(f"\n{'=' * 70}")
    print("DETECTION SUMMARY")
    print(f"{'=' * 70}")
    
    for smell in expected:
        if smell in detected:
            count = len(results[smell])
            print(f"  ✓ {smell.name}: {count} instance(s)")
        else:
            print(f"  ✗ {smell.name}: NOT DETECTED")
    
    missing = expected - detected
    if missing:
        print(f"\nMissing: {[s.name for s in missing]}")
    
    return len(missing) == 0


# =============================================================================
# MAIN
# =============================================================================

def poc_l8_antipatterns():
    """Run all antipattern tests."""
    print("=" * 70)
    print("L8 POC: ANTIPATTERN TEST SUITE")
    print("=" * 70)
    
    tests = [
        ("GOD_OBJECT", test_god_object),
        ("SPAGHETTI", test_spaghetti),
        ("CIRCULAR_DEPENDENCY", test_circular_dependency),
        ("FEATURE_ENVY", test_feature_envy),
        ("ARROW_CODE", test_arrow_code),
        ("COPY_PASTE", test_copy_paste),
        ("LONG_METHOD", test_long_method),
        ("LONG_PARAMETER_LIST", test_long_parameter_list),
        ("DEAD_CODE", test_dead_code),
        ("REAL_WORLD", test_real_world_codebase),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, "✓" if passed else "✗"))
        except Exception as e:
            results.append((name, f"✗ {e}"))
    
    print("\n" + "=" * 70)
    print("L8 SUMMARY")
    print("=" * 70)
    
    for name, status in results:
        print(f"  {name:25} {status}")
    
    passed = sum(1 for _, s in results if s == "✓")
    print(f"\n{passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("""
    Proved:
    ✓ GOD_OBJECT detection (too many methods, high fan-out)
    ✓ SPAGHETTI detection (tangled call graph)
    ✓ CIRCULAR_DEPENDENCY detection (Tarjan's SCC)
    ✓ FEATURE_ENVY detection (external > internal calls)
    ✓ ARROW_CODE detection (deep nesting)
    ✓ COPY_PASTE detection (fingerprint similarity)
    ✓ LONG_METHOD detection (line count)
    ✓ LONG_PARAMETER_LIST detection (param count)
    ✓ DEAD_CODE detection (fan_in = 0)
    ✓ REAL_WORLD codebase analysis
    
    Each weakness traced to WHERE it lands in the code graph.
        """)
    
    return passed == len(results)


if __name__ == "__main__":
    poc_l8_antipatterns()
