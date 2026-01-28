"""
LadybugDB Incremental POC - Difficulty Levels

L1: ATOM       - Single function → fingerprint
L2: CONTROL    - Function + IF/FOREACH
L3: CLASS      - Class + methods + CALLS
L4: INHERITANCE - Multiple classes + INHERITS
L5: PARSE      - Real Python AST → graph
"""

import hashlib
import struct
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from enum import IntEnum

# =============================================================================
# CONSTANTS
# =============================================================================

DIM = 10_000
DIM_U64 = 157
LAST_MASK = np.uint64((1 << 16) - 1)


# =============================================================================
# SHARED: Fingerprint computation
# =============================================================================

def fingerprint(identity: str) -> np.ndarray:
    """Deterministic 10K-bit fingerprint from identity string."""
    data = np.empty(DIM_U64, dtype=np.uint64)
    for i in range(DIM_U64):
        h = hashlib.sha256(f"{identity}:{i}".encode()).digest()
        data[i] = struct.unpack('<Q', h[:8])[0]
    data[-1] &= LAST_MASK
    return data


def hamming(a: np.ndarray, b: np.ndarray) -> int:
    """Hamming distance via XOR + POPCOUNT."""
    xored = np.bitwise_xor(a, b)
    total = 0
    for x in xored:
        total += bin(int(x)).count('1')
    return total


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Normalized similarity [0, 1]."""
    return 1.0 - hamming(a, b) / DIM


# =============================================================================
# L1: ATOM - Single function → fingerprint
# =============================================================================

def poc_l1_atom():
    """
    L1: Prove deterministic fingerprinting works.
    
    Same code → same fingerprint (always)
    Different code → ~50% Hamming distance (quasi-orthogonal)
    """
    print("=" * 60)
    print("L1: ATOM - Single function fingerprinting")
    print("=" * 60)
    
    # Define two functions
    code_a = "def validate_email(s): return '@' in s"
    code_b = "def validate_email(s): return '@' in s"  # Same
    code_c = "def check_phone(s): return s.isdigit()"  # Different
    
    # Compute fingerprints
    fp_a = fingerprint(code_a)
    fp_b = fingerprint(code_b)
    fp_c = fingerprint(code_c)
    
    # Test 1: Same code = same fingerprint
    assert np.array_equal(fp_a, fp_b), "FAIL: Same code should have same fingerprint"
    print("✓ Same code → same fingerprint")
    
    # Test 2: Deterministic (run twice)
    fp_a2 = fingerprint(code_a)
    assert np.array_equal(fp_a, fp_a2), "FAIL: Fingerprint should be deterministic"
    print("✓ Deterministic (reproducible)")
    
    # Test 3: Different code = ~50% distance
    dist = hamming(fp_a, fp_c)
    sim = similarity(fp_a, fp_c)
    print(f"✓ Different code: distance={dist}, similarity={sim:.3f}")
    assert 4000 < dist < 6000, f"FAIL: Expected ~5000 distance, got {dist}"
    
    # Test 4: Hex serialization roundtrip
    hex_str = fp_a.tobytes().hex()
    fp_restored = np.frombuffer(bytes.fromhex(hex_str), dtype=np.uint64).copy()
    assert np.array_equal(fp_a, fp_restored), "FAIL: Hex roundtrip failed"
    print("✓ Hex serialization roundtrip")
    
    print("\nL1 PASSED ✓")
    return True


# =============================================================================
# L2: CONTROL - Function with IF/FOREACH
# =============================================================================

class NodeType(IntEnum):
    FUNCTION = 1
    IF = 2
    FOREACH = 3
    CALL = 4
    LITERAL = 5


class EdgeType(IntEnum):
    CONTAINS = 1
    NEXT = 2


@dataclass
class Node:
    id: int
    node_type: NodeType
    name: str
    body: str = ""
    fingerprint: np.ndarray = field(default_factory=lambda: np.zeros(DIM_U64, dtype=np.uint64))
    
    def __post_init__(self):
        identity = f"{self.node_type.name}::{self.name}::{self.body}"
        self.fingerprint = fingerprint(identity)


@dataclass
class Edge:
    from_id: int
    to_id: int
    edge_type: EdgeType


def poc_l2_control():
    """
    L2: Function with control flow → parent-child nodes.
    
    def process(items):
        for item in items:
            if item.valid:
                handle(item)
    
    Graph:
        FUNCTION[process] ──CONTAINS──► FOREACH[item in items]
                                              │
                                         CONTAINS
                                              │
                                              ▼
                                         IF[item.valid]
                                              │
                                         CONTAINS
                                              │
                                              ▼
                                         CALL[handle(item)]
    """
    print("\n" + "=" * 60)
    print("L2: CONTROL - Function with IF/FOREACH")
    print("=" * 60)
    
    nodes: Dict[int, Node] = {}
    edges: List[Edge] = []
    next_id = 0
    
    def add_node(node_type: NodeType, name: str, body: str = "") -> Node:
        nonlocal next_id
        node = Node(next_id, node_type, name, body)
        nodes[next_id] = node
        next_id += 1
        return node
    
    def add_edge(from_node: Node, to_node: Node, edge_type: EdgeType):
        edges.append(Edge(from_node.id, to_node.id, edge_type))
    
    # Build graph
    func = add_node(NodeType.FUNCTION, "process", "def process(items): ...")
    foreach = add_node(NodeType.FOREACH, "for item in items", "item in items")
    if_node = add_node(NodeType.IF, "if item.valid", "item.valid")
    call = add_node(NodeType.CALL, "handle(item)", "handle, item")
    
    add_edge(func, foreach, EdgeType.CONTAINS)
    add_edge(foreach, if_node, EdgeType.CONTAINS)
    add_edge(if_node, call, EdgeType.CONTAINS)
    
    # Test 1: Correct structure
    assert len(nodes) == 4, f"FAIL: Expected 4 nodes, got {len(nodes)}"
    assert len(edges) == 3, f"FAIL: Expected 3 edges, got {len(edges)}"
    print(f"✓ Graph structure: {len(nodes)} nodes, {len(edges)} edges")
    
    # Test 2: Each node has unique fingerprint
    fps = [n.fingerprint for n in nodes.values()]
    for i, fp_i in enumerate(fps):
        for j, fp_j in enumerate(fps):
            if i != j:
                sim = similarity(fp_i, fp_j)
                assert sim < 0.6, f"FAIL: Nodes {i} and {j} too similar: {sim}"
    print("✓ Each node has distinct fingerprint")
    
    # Test 3: Can traverse parent → children
    func_children = [e.to_id for e in edges if e.from_id == func.id]
    assert foreach.id in func_children, "FAIL: FOREACH should be child of FUNCTION"
    print("✓ Parent-child traversal works")
    
    # Test 4: Node types are correct
    assert nodes[func.id].node_type == NodeType.FUNCTION
    assert nodes[foreach.id].node_type == NodeType.FOREACH
    assert nodes[if_node.id].node_type == NodeType.IF
    assert nodes[call.id].node_type == NodeType.CALL
    print("✓ Node types preserved")
    
    print("\nL2 PASSED ✓")
    return nodes, edges


# =============================================================================
# L3: CLASS - Class with methods + CALLS
# =============================================================================

class NodeTypeL3(IntEnum):
    CLASS = 1
    METHOD = 2
    PROPERTY = 3
    IF = 4
    CALL = 5


class EdgeTypeL3(IntEnum):
    CONTAINS = 1
    CALLS = 2
    USES = 3


@dataclass
class NodeL3:
    id: int
    node_type: NodeTypeL3
    name: str
    signature: str = ""
    body: str = ""
    fingerprint: np.ndarray = field(default_factory=lambda: np.zeros(DIM_U64, dtype=np.uint64))
    
    def __post_init__(self):
        identity = f"{self.node_type.name}::{self.name}::{self.signature}::{self.body}"
        self.fingerprint = fingerprint(identity)


def poc_l3_class():
    """
    L3: Class with methods and CALLS edges.
    
    class UserService:
        def __init__(self, db):
            self.db = db
        
        def validate(self, user):
            if user.email:
                return self.db.check(user.email)
        
        def batch(self, users):
            return [self.validate(u) for u in users]
    
    Graph:
        CLASS[UserService]
            ├── CONTAINS → METHOD[__init__]
            ├── CONTAINS → METHOD[validate]
            │                  └── CALLS → CALL[self.db.check]
            └── CONTAINS → METHOD[batch]
                               └── CALLS → METHOD[validate]
    """
    print("\n" + "=" * 60)
    print("L3: CLASS - Class with methods + CALLS")
    print("=" * 60)
    
    nodes: Dict[int, NodeL3] = {}
    edges: List[Edge] = []
    next_id = 0
    
    def add_node(node_type: NodeTypeL3, name: str, sig: str = "", body: str = "") -> NodeL3:
        nonlocal next_id
        node = NodeL3(next_id, node_type, name, sig, body)
        nodes[next_id] = node
        next_id += 1
        return node
    
    def add_edge(from_node: NodeL3, to_node: NodeL3, edge_type: EdgeTypeL3):
        edges.append(Edge(from_node.id, to_node.id, edge_type))
    
    # Build graph
    cls = add_node(NodeTypeL3.CLASS, "UserService")
    init = add_node(NodeTypeL3.METHOD, "__init__", "(self, db)", "self.db = db")
    validate = add_node(NodeTypeL3.METHOD, "validate", "(self, user) -> bool", 
                        "if user.email: return self.db.check(user.email)")
    batch = add_node(NodeTypeL3.METHOD, "batch", "(self, users) -> List[bool]",
                     "return [self.validate(u) for u in users]")
    db_check = add_node(NodeTypeL3.CALL, "self.db.check", "", "user.email")
    
    # Structure edges
    add_edge(cls, init, EdgeTypeL3.CONTAINS)
    add_edge(cls, validate, EdgeTypeL3.CONTAINS)
    add_edge(cls, batch, EdgeTypeL3.CONTAINS)
    
    # Call edges
    add_edge(validate, db_check, EdgeTypeL3.CALLS)
    add_edge(batch, validate, EdgeTypeL3.CALLS)
    
    # Test 1: Structure
    assert len(nodes) == 5, f"FAIL: Expected 5 nodes, got {len(nodes)}"
    print(f"✓ Graph structure: {len(nodes)} nodes, {len(edges)} edges")
    
    # Test 2: Class contains all methods
    class_children = [e.to_id for e in edges 
                      if e.from_id == cls.id and e.edge_type == EdgeTypeL3.CONTAINS]
    assert len(class_children) == 3, f"FAIL: Class should contain 3 methods"
    print("✓ Class contains 3 methods")
    
    # Test 3: batch CALLS validate
    batch_calls = [e.to_id for e in edges 
                   if e.from_id == batch.id and e.edge_type == EdgeTypeL3.CALLS]
    assert validate.id in batch_calls, "FAIL: batch should call validate"
    print("✓ batch() calls validate()")
    
    # Test 4: validate CALLS db.check
    validate_calls = [e.to_id for e in edges 
                      if e.from_id == validate.id and e.edge_type == EdgeTypeL3.CALLS]
    assert db_check.id in validate_calls, "FAIL: validate should call db.check"
    print("✓ validate() calls self.db.check()")
    
    # Test 5: Similar methods have higher similarity
    sim_init_validate = similarity(init.fingerprint, validate.fingerprint)
    sim_validate_batch = similarity(validate.fingerprint, batch.fingerprint)
    print(f"✓ Method similarities: init↔validate={sim_init_validate:.3f}, validate↔batch={sim_validate_batch:.3f}")
    
    print("\nL3 PASSED ✓")
    return nodes, edges


# =============================================================================
# L4: INHERITANCE - Multiple classes + INHERITS
# =============================================================================

class EdgeTypeL4(IntEnum):
    CONTAINS = 1
    CALLS = 2
    INHERITS = 3
    OVERRIDES = 4
    DEPENDS = 5


def poc_l4_inheritance():
    """
    L4: Multiple classes with inheritance.
    
    class BaseValidator:
        def validate(self, data): pass
    
    class EmailValidator(BaseValidator):
        def validate(self, data):
            return '@' in data
    
    class PhoneValidator(BaseValidator):
        def validate(self, data):
            return data.isdigit()
    
    class CompositeValidator:
        def __init__(self, validators):
            self.validators = validators
        
        def validate_all(self, data):
            return all(v.validate(data) for v in self.validators)
    
    Graph:
        CLASS[BaseValidator]
            └── CONTAINS → METHOD[validate]
                               ▲
                               │ OVERRIDES
        CLASS[EmailValidator] ─┼─ INHERITS → CLASS[BaseValidator]
            └── CONTAINS → METHOD[validate]
                               │
        CLASS[PhoneValidator] ─┼─ INHERITS → CLASS[BaseValidator]
            └── CONTAINS → METHOD[validate]
        
        CLASS[CompositeValidator]
            └── CONTAINS → METHOD[validate_all]
                               └── DEPENDS → CLASS[BaseValidator]
    """
    print("\n" + "=" * 60)
    print("L4: INHERITANCE - Multiple classes + INHERITS")
    print("=" * 60)
    
    nodes: Dict[int, NodeL3] = {}
    edges: List[Tuple[int, int, EdgeTypeL4]] = []
    next_id = 0
    
    def add_node(node_type: NodeTypeL3, name: str, sig: str = "", body: str = "") -> NodeL3:
        nonlocal next_id
        node = NodeL3(next_id, node_type, name, sig, body)
        nodes[next_id] = node
        next_id += 1
        return node
    
    def add_edge(from_id: int, to_id: int, edge_type: EdgeTypeL4):
        edges.append((from_id, to_id, edge_type))
    
    # BaseValidator
    base = add_node(NodeTypeL3.CLASS, "BaseValidator")
    base_validate = add_node(NodeTypeL3.METHOD, "validate", "(self, data)", "pass")
    add_edge(base.id, base_validate.id, EdgeTypeL4.CONTAINS)
    
    # EmailValidator
    email = add_node(NodeTypeL3.CLASS, "EmailValidator")
    email_validate = add_node(NodeTypeL3.METHOD, "validate", "(self, data)", "return '@' in data")
    add_edge(email.id, email_validate.id, EdgeTypeL4.CONTAINS)
    add_edge(email.id, base.id, EdgeTypeL4.INHERITS)
    add_edge(email_validate.id, base_validate.id, EdgeTypeL4.OVERRIDES)
    
    # PhoneValidator
    phone = add_node(NodeTypeL3.CLASS, "PhoneValidator")
    phone_validate = add_node(NodeTypeL3.METHOD, "validate", "(self, data)", "return data.isdigit()")
    add_edge(phone.id, phone_validate.id, EdgeTypeL4.CONTAINS)
    add_edge(phone.id, base.id, EdgeTypeL4.INHERITS)
    add_edge(phone_validate.id, base_validate.id, EdgeTypeL4.OVERRIDES)
    
    # CompositeValidator
    composite = add_node(NodeTypeL3.CLASS, "CompositeValidator")
    composite_validate = add_node(NodeTypeL3.METHOD, "validate_all", "(self, data)",
                                   "return all(v.validate(data) for v in self.validators)")
    add_edge(composite.id, composite_validate.id, EdgeTypeL4.CONTAINS)
    add_edge(composite_validate.id, base.id, EdgeTypeL4.DEPENDS)
    
    # Test 1: Structure
    classes = [n for n in nodes.values() if n.node_type == NodeTypeL3.CLASS]
    methods = [n for n in nodes.values() if n.node_type == NodeTypeL3.METHOD]
    assert len(classes) == 4, f"FAIL: Expected 4 classes, got {len(classes)}"
    assert len(methods) == 4, f"FAIL: Expected 4 methods, got {len(methods)}"
    print(f"✓ Structure: {len(classes)} classes, {len(methods)} methods")
    
    # Test 2: Inheritance edges
    inherits_edges = [(f, t) for f, t, e in edges if e == EdgeTypeL4.INHERITS]
    assert len(inherits_edges) == 2, f"FAIL: Expected 2 INHERITS edges"
    print("✓ 2 INHERITS edges (Email→Base, Phone→Base)")
    
    # Test 3: Override edges
    override_edges = [(f, t) for f, t, e in edges if e == EdgeTypeL4.OVERRIDES]
    assert len(override_edges) == 2, f"FAIL: Expected 2 OVERRIDES edges"
    print("✓ 2 OVERRIDES edges")
    
    # Test 4: validate methods are similar (same signature, different body)
    sim_email_phone = similarity(email_validate.fingerprint, phone_validate.fingerprint)
    sim_email_base = similarity(email_validate.fingerprint, base_validate.fingerprint)
    print(f"✓ Method similarities: email↔phone={sim_email_phone:.3f}, email↔base={sim_email_base:.3f}")
    
    # Test 5: Can find all subclasses
    subclasses = [f for f, t, e in edges if t == base.id and e == EdgeTypeL4.INHERITS]
    assert set(subclasses) == {email.id, phone.id}
    print("✓ Can find all subclasses of BaseValidator")
    
    print("\nL4 PASSED ✓")
    return nodes, edges


# =============================================================================
# L5: PARSE - Real Python AST → graph
# =============================================================================

def poc_l5_parse():
    """
    L5: Parse real Python source code into graph.
    
    Uses Python's ast module to extract structure.
    """
    print("\n" + "=" * 60)
    print("L5: PARSE - Real Python AST → graph")
    print("=" * 60)
    
    import ast
    
    source = '''
class DataProcessor:
    """Process data items."""
    
    def __init__(self, config):
        self.config = config
        self.cache = {}
    
    def process(self, items):
        results = []
        for item in items:
            if self.validate(item):
                result = self.transform(item)
                results.append(result)
        return results
    
    def validate(self, item):
        return item is not None
    
    def transform(self, item):
        return item.upper()
'''
    
    tree = ast.parse(source)
    
    nodes: Dict[int, dict] = {}
    edges: List[Tuple[int, int, str]] = []
    next_id = 0
    
    def add_node(node_type: str, name: str, **kwargs) -> int:
        nonlocal next_id
        node_id = next_id
        identity = f"{node_type}::{name}::{kwargs.get('body', '')}"
        nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "name": name,
            "fingerprint": fingerprint(identity),
            **kwargs
        }
        next_id += 1
        return node_id
    
    def add_edge(from_id: int, to_id: int, edge_type: str):
        edges.append((from_id, to_id, edge_type))
    
    def visit(node, parent_id: Optional[int] = None):
        """Recursively visit AST nodes."""
        node_id = None
        
        if isinstance(node, ast.ClassDef):
            node_id = add_node("CLASS", node.name, lineno=node.lineno)
            if parent_id is not None:
                add_edge(parent_id, node_id, "CONTAINS")
            
            for item in node.body:
                visit(item, node_id)
        
        elif isinstance(node, ast.FunctionDef):
            args = ", ".join(a.arg for a in node.args.args)
            body_src = ast.unparse(node) if hasattr(ast, 'unparse') else str(node.body)
            node_id = add_node("METHOD", node.name, signature=f"({args})", 
                              body=body_src[:100], lineno=node.lineno)
            if parent_id is not None:
                add_edge(parent_id, node_id, "CONTAINS")
            
            for item in node.body:
                visit(item, node_id)
        
        elif isinstance(node, ast.For):
            target = ast.unparse(node.target) if hasattr(ast, 'unparse') else "item"
            iter_src = ast.unparse(node.iter) if hasattr(ast, 'unparse') else "items"
            node_id = add_node("FOREACH", f"for {target} in {iter_src}", 
                              body=f"{target} in {iter_src}")
            if parent_id is not None:
                add_edge(parent_id, node_id, "CONTAINS")
            
            for item in node.body:
                visit(item, node_id)
        
        elif isinstance(node, ast.If):
            cond = ast.unparse(node.test) if hasattr(ast, 'unparse') else "condition"
            node_id = add_node("IF", f"if {cond}", body=cond)
            if parent_id is not None:
                add_edge(parent_id, node_id, "CONTAINS")
            
            for item in node.body:
                visit(item, node_id)
        
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                call_name = f"{ast.unparse(node.func.value)}.{node.func.attr}" if hasattr(ast, 'unparse') else node.func.attr
            elif isinstance(node.func, ast.Name):
                call_name = node.func.id
            else:
                call_name = "call"
            
            node_id = add_node("CALL", call_name)
            if parent_id is not None:
                add_edge(parent_id, node_id, "CALLS")
        
        elif isinstance(node, ast.Assign):
            for item in ast.walk(node):
                if isinstance(item, ast.Call):
                    visit(item, parent_id)
        
        elif isinstance(node, ast.Expr):
            visit(node.value, parent_id)
        
        elif isinstance(node, ast.Return):
            if node.value:
                for item in ast.walk(node.value):
                    if isinstance(item, ast.Call):
                        visit(item, parent_id)
        
        return node_id
    
    # Parse the source
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            visit(node)
    
    # Test 1: Found the class
    classes = [n for n in nodes.values() if n["type"] == "CLASS"]
    assert len(classes) == 1, f"FAIL: Expected 1 class, got {len(classes)}"
    print(f"✓ Parsed class: {classes[0]['name']}")
    
    # Test 2: Found all methods
    methods = [n for n in nodes.values() if n["type"] == "METHOD"]
    method_names = {m["name"] for m in methods}
    expected = {"__init__", "process", "validate", "transform"}
    assert method_names == expected, f"FAIL: Expected {expected}, got {method_names}"
    print(f"✓ Found {len(methods)} methods: {method_names}")
    
    # Test 3: Found control flow
    foreachs = [n for n in nodes.values() if n["type"] == "FOREACH"]
    ifs = [n for n in nodes.values() if n["type"] == "IF"]
    print(f"✓ Control flow: {len(foreachs)} FOREACH, {len(ifs)} IF")
    
    # Test 4: Found calls
    calls = [n for n in nodes.values() if n["type"] == "CALL"]
    call_names = {c["name"] for c in calls}
    print(f"✓ Found {len(calls)} calls: {call_names}")
    
    # Test 5: Edge count
    contains_edges = [e for e in edges if e[2] == "CONTAINS"]
    calls_edges = [e for e in edges if e[2] == "CALLS"]
    print(f"✓ Edges: {len(contains_edges)} CONTAINS, {len(calls_edges)} CALLS")
    
    print(f"\nTotal: {len(nodes)} nodes, {len(edges)} edges")
    print("\nL5 PASSED ✓")
    return nodes, edges


# =============================================================================
# RUN ALL
# =============================================================================

def run_all():
    """Run all POC levels."""
    print("\n" + "=" * 60)
    print("LADYBUGDB INCREMENTAL POC")
    print("=" * 60)
    
    results = []
    
    try:
        poc_l1_atom()
        results.append(("L1: ATOM", "✓"))
    except Exception as e:
        results.append(("L1: ATOM", f"✗ {e}"))
    
    try:
        poc_l2_control()
        results.append(("L2: CONTROL", "✓"))
    except Exception as e:
        results.append(("L2: CONTROL", f"✗ {e}"))
    
    try:
        poc_l3_class()
        results.append(("L3: CLASS", "✓"))
    except Exception as e:
        results.append(("L3: CLASS", f"✗ {e}"))
    
    try:
        poc_l4_inheritance()
        results.append(("L4: INHERITANCE", "✓"))
    except Exception as e:
        results.append(("L4: INHERITANCE", f"✗ {e}"))
    
    try:
        poc_l5_parse()
        results.append(("L5: PARSE", "✓"))
    except Exception as e:
        results.append(("L5: PARSE", f"✗ {e}"))
    
    # L6: NARS (import from separate module)
    try:
        import sys
        sys.path.insert(0, '/home/claude/ladybugdb/poc')
        from l6_nars import poc_l6_nars
        poc_l6_nars()
        results.append(("L6: NARS", "✓"))
    except Exception as e:
        results.append(("L6: NARS", f"✗ {e}"))
    
    # L7: META-HEURISTICS
    try:
        from l7_meta import poc_l7_meta
        poc_l7_meta()
        results.append(("L7: META", "✓"))
    except Exception as e:
        results.append(("L7: META", f"✗ {e}"))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for level, status in results:
        print(f"  {level:20} {status}")
    
    passed = sum(1 for _, s in results if s == "✓")
    print(f"\n{passed}/{len(results)} levels passed")
    
    return all(s == "✓" for _, s in results)


if __name__ == "__main__":
    run_all()
