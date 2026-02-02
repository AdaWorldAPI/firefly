"""
LadybugDB Declarative Layer - Code as Graph

Language constructs as Numba jitclass nodes/edges.
Sits ABOVE the Hamming substrate.

Node Types:
- CLASS, METHOD, FUNCTION, PROPERTY
- FOREACH, IF, WHILE, MATCH
- EXPRESSION, LITERAL, REFERENCE
- IMPORT, EXPORT, MODULE

Edge Types:
- CONTAINS, CALLS, RETURNS, DEPENDS
- INHERITS, IMPLEMENTS, USES
- BRANCHES_TO, LOOPS_TO
"""

import numpy as np
from numba import types, typed
from numba.experimental import jitclass
from enum import IntEnum
from typing import List, Dict, Optional, Tuple
import hashlib
import struct

# =============================================================================
# CONSTANTS
# =============================================================================

DIM = 10_000
DIM_U64 = 157
LAST_MASK = np.uint64((1 << 16) - 1)

# =============================================================================
# NODE TYPES (language constructs)
# =============================================================================

class NodeType(IntEnum):
    """Language construct types."""
    # Containers
    MODULE = 1
    CLASS = 2
    FUNCTION = 3
    METHOD = 4
    PROPERTY = 5
    
    # Control flow
    IF = 10
    ELSE = 11
    ELIF = 12
    MATCH = 13
    CASE = 14
    
    # Loops
    FOR = 20
    FOREACH = 21
    WHILE = 22
    LOOP = 23
    
    # Expressions
    EXPRESSION = 30
    LITERAL = 31
    REFERENCE = 32
    CALL = 33
    BINARY_OP = 34
    UNARY_OP = 35
    
    # Declarations
    VARIABLE = 40
    PARAMETER = 41
    RETURN = 42
    YIELD = 43
    
    # Imports
    IMPORT = 50
    EXPORT = 51
    
    # Special
    COMMENT = 60
    DECORATOR = 61
    ANNOTATION = 62


class EdgeType(IntEnum):
    """Relationship types between nodes."""
    # Structural
    CONTAINS = 1       # parent contains child
    NEXT = 2           # sequential flow
    
    # Dependencies  
    CALLS = 10         # function/method call
    RETURNS = 11       # return type/value
    DEPENDS = 12       # depends on
    USES = 13          # uses variable/import
    
    # OOP
    INHERITS = 20      # class inheritance
    IMPLEMENTS = 21    # interface implementation
    OVERRIDES = 22     # method override
    
    # Control flow
    BRANCHES_TO = 30   # if/match branch
    LOOPS_TO = 31      # loop back edge
    BREAKS_TO = 32     # break target
    CONTINUES_TO = 33  # continue target
    
    # Data flow
    ASSIGNS = 40       # assignment
    READS = 41         # read access
    WRITES = 42        # write access


# =============================================================================
# NUMBA JITCLASS SPECS
# =============================================================================

# Fingerprint spec (10K bits as uint64 array)
fingerprint_spec = [
    ('data', types.uint64[:]),
]

# Base node spec
node_spec = [
    ('id', types.int64),
    ('node_type', types.int32),
    ('name', types.unicode_type),
    ('fingerprint', types.uint64[:]),
    ('start_line', types.int32),
    ('end_line', types.int32),
    ('parent_id', types.int64),
]

# Edge spec
edge_spec = [
    ('from_id', types.int64),
    ('to_id', types.int64),
    ('edge_type', types.int32),
    ('weight', types.float32),
]


# =============================================================================
# FINGERPRINT (compiled to native)
# =============================================================================

@jitclass(fingerprint_spec)
class Fingerprint:
    """10K-bit fingerprint as Numba jitclass."""
    
    def __init__(self):
        self.data = np.zeros(DIM_U64, dtype=np.uint64)
    
    def xor(self, other):
        """XOR bind - returns new fingerprint."""
        result = Fingerprint()
        for i in range(DIM_U64):
            result.data[i] = self.data[i] ^ other.data[i]
        result.data[DIM_U64 - 1] &= LAST_MASK
        return result
    
    def hamming(self, other) -> int:
        """Hamming distance via XOR + POPCOUNT."""
        total = 0
        for i in range(DIM_U64):
            x = self.data[i] ^ other.data[i]
            # Popcount
            x = x - ((x >> 1) & np.uint64(0x5555555555555555))
            x = (x & np.uint64(0x3333333333333333)) + ((x >> 2) & np.uint64(0x3333333333333333))
            x = (x + (x >> 4)) & np.uint64(0x0F0F0F0F0F0F0F0F)
            total += int((x * np.uint64(0x0101010101010101)) >> 56)
        return total
    
    def similarity(self, other) -> float:
        """Normalized similarity [0, 1]."""
        return 1.0 - self.hamming(other) / DIM


# =============================================================================
# NODE (compiled to native)
# =============================================================================

@jitclass(node_spec)
class Node:
    """Language construct as Numba jitclass."""
    
    def __init__(self, id: int, node_type: int, name: str):
        self.id = id
        self.node_type = node_type
        self.name = name
        self.fingerprint = np.zeros(DIM_U64, dtype=np.uint64)
        self.start_line = 0
        self.end_line = 0
        self.parent_id = -1
    
    def set_fingerprint(self, fp: np.ndarray):
        """Set fingerprint from external computation."""
        for i in range(DIM_U64):
            self.fingerprint[i] = fp[i]
    
    def hamming(self, other) -> int:
        """Hamming distance to another node."""
        total = 0
        for i in range(DIM_U64):
            x = self.fingerprint[i] ^ other.fingerprint[i]
            x = x - ((x >> 1) & np.uint64(0x5555555555555555))
            x = (x & np.uint64(0x3333333333333333)) + ((x >> 2) & np.uint64(0x3333333333333333))
            x = (x + (x >> 4)) & np.uint64(0x0F0F0F0F0F0F0F0F)
            total += int((x * np.uint64(0x0101010101010101)) >> 56)
        return total
    
    def similarity(self, other) -> float:
        """Similarity to another node."""
        return 1.0 - self.hamming(other) / DIM


# =============================================================================
# EDGE (compiled to native)
# =============================================================================

@jitclass(edge_spec)
class Edge:
    """Relationship between nodes as Numba jitclass."""
    
    def __init__(self, from_id: int, to_id: int, edge_type: int):
        self.from_id = from_id
        self.to_id = to_id
        self.edge_type = edge_type
        self.weight = 1.0


# =============================================================================
# PYTHON WRAPPERS (for fingerprint generation)
# =============================================================================

def compute_fingerprint(identity: str) -> np.ndarray:
    """Compute 10K fingerprint from identity string (Python, not JIT)."""
    data = np.empty(DIM_U64, dtype=np.uint64)
    for i in range(DIM_U64):
        h = hashlib.sha256(f"{identity}:{i}".encode()).digest()
        data[i] = struct.unpack('<Q', h[:8])[0]
    data[-1] &= LAST_MASK
    return data


def make_node(
    id: int,
    node_type: NodeType,
    name: str,
    body: str = "",
    signature: str = "",
    parent_id: int = -1,
    start_line: int = 0,
    end_line: int = 0,
) -> Node:
    """Create a node with computed fingerprint."""
    node = Node(id, int(node_type), name)
    node.parent_id = parent_id
    node.start_line = start_line
    node.end_line = end_line
    
    # Compute fingerprint from identity
    identity = f"{NodeType(node_type).name}::{name}::{signature}::{body}"
    fp = compute_fingerprint(identity)
    node.set_fingerprint(fp)
    
    return node


def make_edge(
    from_id: int,
    to_id: int,
    edge_type: EdgeType,
    weight: float = 1.0,
) -> Edge:
    """Create an edge between nodes."""
    edge = Edge(from_id, to_id, int(edge_type))
    edge.weight = weight
    return edge


# =============================================================================
# GRAPH (nodes + edges stored for DuckDB)
# =============================================================================

class CodeGraph:
    """
    Declarative code graph.
    Nodes are language constructs, edges are relationships.
    Backed by DuckDB for deterministic traversal.
    """
    
    def __init__(self):
        self.nodes: Dict[int, Node] = {}
        self.edges: List[Edge] = []
        self._next_id = 0
        self._db = None  # DuckDB connection
    
    def _get_id(self) -> int:
        """Get next node ID."""
        id = self._next_id
        self._next_id += 1
        return id
    
    # -------------------------------------------------------------------------
    # Node creation methods
    # -------------------------------------------------------------------------
    
    def module(self, name: str) -> Node:
        """Create MODULE node."""
        return self._add_node(NodeType.MODULE, name)
    
    def class_(self, name: str, parent: Optional[Node] = None) -> Node:
        """Create CLASS node."""
        return self._add_node(NodeType.CLASS, name, parent)
    
    def method(self, name: str, signature: str, body: str, parent: Node) -> Node:
        """Create METHOD node inside a class."""
        node = self._add_node(NodeType.METHOD, name, parent, signature=signature, body=body)
        self.edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def function(self, name: str, signature: str, body: str, parent: Optional[Node] = None) -> Node:
        """Create FUNCTION node."""
        node = self._add_node(NodeType.FUNCTION, name, parent, signature=signature, body=body)
        if parent:
            self.edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def property_(self, name: str, type_hint: str, parent: Node) -> Node:
        """Create PROPERTY node inside a class."""
        node = self._add_node(NodeType.PROPERTY, name, parent, signature=type_hint)
        self.edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def if_(self, condition: str, parent: Node) -> Node:
        """Create IF node."""
        node = self._add_node(NodeType.IF, f"if({condition})", parent, body=condition)
        self.edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def foreach(self, var: str, iterable: str, parent: Node) -> Node:
        """Create FOREACH node."""
        node = self._add_node(NodeType.FOREACH, f"for {var} in {iterable}", parent, 
                             signature=var, body=iterable)
        self.edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def while_(self, condition: str, parent: Node) -> Node:
        """Create WHILE node."""
        node = self._add_node(NodeType.WHILE, f"while({condition})", parent, body=condition)
        self.edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def match(self, expr: str, parent: Node) -> Node:
        """Create MATCH node."""
        node = self._add_node(NodeType.MATCH, f"match({expr})", parent, body=expr)
        self.edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def case(self, pattern: str, parent: Node) -> Node:
        """Create CASE node inside a match."""
        node = self._add_node(NodeType.CASE, f"case {pattern}", parent, body=pattern)
        self.edge(parent, node, EdgeType.BRANCHES_TO)
        return node
    
    def variable(self, name: str, type_hint: str, parent: Node) -> Node:
        """Create VARIABLE node."""
        node = self._add_node(NodeType.VARIABLE, name, parent, signature=type_hint)
        self.edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def call(self, target: str, args: str, parent: Node) -> Node:
        """Create CALL node."""
        node = self._add_node(NodeType.CALL, f"{target}({args})", parent, 
                             signature=target, body=args)
        self.edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def import_(self, module: str, parent: Optional[Node] = None) -> Node:
        """Create IMPORT node."""
        return self._add_node(NodeType.IMPORT, module, parent)
    
    def literal(self, value: str, parent: Node) -> Node:
        """Create LITERAL node."""
        node = self._add_node(NodeType.LITERAL, value, parent, body=value)
        self.edge(parent, node, EdgeType.CONTAINS)
        return node
    
    def reference(self, name: str, parent: Node) -> Node:
        """Create REFERENCE node."""
        node = self._add_node(NodeType.REFERENCE, name, parent)
        self.edge(parent, node, EdgeType.USES)
        return node
    
    # -------------------------------------------------------------------------
    # Edge creation
    # -------------------------------------------------------------------------
    
    def edge(self, from_node: Node, to_node: Node, edge_type: EdgeType, weight: float = 1.0) -> Edge:
        """Create edge between nodes."""
        e = make_edge(from_node.id, to_node.id, edge_type, weight)
        self.edges.append(e)
        return e
    
    def calls(self, caller: Node, callee: Node) -> Edge:
        """Create CALLS edge."""
        return self.edge(caller, callee, EdgeType.CALLS)
    
    def inherits(self, child: Node, parent: Node) -> Edge:
        """Create INHERITS edge."""
        return self.edge(child, parent, EdgeType.INHERITS)
    
    def implements(self, class_: Node, interface: Node) -> Edge:
        """Create IMPLEMENTS edge."""
        return self.edge(class_, interface, EdgeType.IMPLEMENTS)
    
    def depends(self, dependent: Node, dependency: Node) -> Edge:
        """Create DEPENDS edge."""
        return self.edge(dependent, dependency, EdgeType.DEPENDS)
    
    # -------------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------------
    
    def _add_node(
        self, 
        node_type: NodeType, 
        name: str, 
        parent: Optional[Node] = None,
        signature: str = "",
        body: str = "",
    ) -> Node:
        """Internal: add node to graph."""
        id = self._get_id()
        parent_id = parent.id if parent else -1
        node = make_node(id, node_type, name, body, signature, parent_id)
        self.nodes[id] = node
        return node
    
    # -------------------------------------------------------------------------
    # Query
    # -------------------------------------------------------------------------
    
    def get_children(self, parent: Node) -> List[Node]:
        """Get all children of a node."""
        child_ids = [e.to_id for e in self.edges 
                     if e.from_id == parent.id and e.edge_type == int(EdgeType.CONTAINS)]
        return [self.nodes[id] for id in child_ids]
    
    def get_calls(self, node: Node) -> List[Node]:
        """Get all nodes called by this node."""
        callee_ids = [e.to_id for e in self.edges 
                      if e.from_id == node.id and e.edge_type == int(EdgeType.CALLS)]
        return [self.nodes[id] for id in callee_ids if id in self.nodes]
    
    def find_by_type(self, node_type: NodeType) -> List[Node]:
        """Find all nodes of a given type."""
        return [n for n in self.nodes.values() if n.node_type == int(node_type)]
    
    def find_similar(self, query: Node, threshold: float = 0.5) -> List[Tuple[Node, float]]:
        """Find nodes similar to query (above threshold)."""
        results = []
        for node in self.nodes.values():
            if node.id != query.id:
                sim = query.similarity(node)
                if sim >= threshold:
                    results.append((node, sim))
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    # -------------------------------------------------------------------------
    # Export
    # -------------------------------------------------------------------------
    
    def to_duckdb(self):
        """Export to DuckDB for deterministic queries."""
        try:
            import duckdb
        except ImportError:
            raise ImportError("pip install duckdb")
        
        conn = duckdb.connect()
        
        # Create nodes table
        conn.execute("""
            CREATE TABLE nodes (
                id BIGINT PRIMARY KEY,
                node_type INTEGER,
                name VARCHAR,
                fingerprint_hex VARCHAR,
                parent_id BIGINT,
                start_line INTEGER,
                end_line INTEGER
            )
        """)
        
        # Create edges table
        conn.execute("""
            CREATE TABLE edges (
                from_id BIGINT,
                to_id BIGINT,
                edge_type INTEGER,
                weight FLOAT
            )
        """)
        
        # Insert nodes
        for node in self.nodes.values():
            fp_hex = node.fingerprint.tobytes().hex()
            conn.execute(
                "INSERT INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?)",
                [node.id, node.node_type, node.name, fp_hex, 
                 node.parent_id, node.start_line, node.end_line]
            )
        
        # Insert edges
        for edge in self.edges:
            conn.execute(
                "INSERT INTO edges VALUES (?, ?, ?, ?)",
                [edge.from_id, edge.to_id, edge.edge_type, edge.weight]
            )
        
        self._db = conn
        return conn
    
    def to_graphviz(self) -> str:
        """Export to Graphviz DOT format."""
        lines = ["digraph CodeGraph {"]
        lines.append("  rankdir=TB;")
        lines.append("  node [shape=box];")
        
        # Node shapes by type
        shapes = {
            NodeType.MODULE: "folder",
            NodeType.CLASS: "box3d",
            NodeType.FUNCTION: "ellipse",
            NodeType.METHOD: "ellipse",
            NodeType.IF: "diamond",
            NodeType.FOREACH: "hexagon",
            NodeType.WHILE: "hexagon",
            NodeType.MATCH: "diamond",
        }
        
        for node in self.nodes.values():
            shape = shapes.get(NodeType(node.node_type), "box")
            label = f"{NodeType(node.node_type).name}\\n{node.name}"
            lines.append(f'  n{node.id} [label="{label}" shape={shape}];')
        
        edge_styles = {
            EdgeType.CONTAINS: "solid",
            EdgeType.CALLS: "dashed",
            EdgeType.INHERITS: "bold",
            EdgeType.BRANCHES_TO: "dotted",
        }
        
        for edge in self.edges:
            style = edge_styles.get(EdgeType(edge.edge_type), "solid")
            label = EdgeType(edge.edge_type).name
            lines.append(f'  n{edge.from_id} -> n{edge.to_id} [style={style} label="{label}"];')
        
        lines.append("}")
        return "\n".join(lines)


# =============================================================================
# EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Build a code graph
    g = CodeGraph()
    
    # Module
    mod = g.module("user_service")
    
    # Import
    imp = g.import_("typing", mod)
    
    # Class
    cls = g.class_("UserService", mod)
    
    # Properties
    db = g.property_("db", "Database", cls)
    cache = g.property_("cache", "Cache", cls)
    
    # Method with control flow
    validate = g.method(
        "validate_user",
        "(user: User) -> bool",
        "if user.email: return self.db.check(user.email)",
        cls
    )
    
    # Control flow inside method
    if_email = g.if_("user.email", validate)
    check_call = g.call("self.db.check", "user.email", if_email)
    
    # Another method with loop
    batch = g.method(
        "batch_validate",
        "(users: List[User]) -> List[bool]",
        "for user in users: results.append(self.validate_user(user))",
        cls
    )
    
    # Loop inside method
    loop = g.foreach("user", "users", batch)
    inner_call = g.call("self.validate_user", "user", loop)
    
    # Connect calls
    g.calls(inner_call, validate)
    g.depends(batch, validate)
    
    print("=== CODE GRAPH ===")
    print(f"Nodes: {len(g.nodes)}")
    print(f"Edges: {len(g.edges)}")
    
    print("\n=== NODES BY TYPE ===")
    for t in [NodeType.CLASS, NodeType.METHOD, NodeType.FOREACH, NodeType.IF]:
        nodes = g.find_by_type(t)
        print(f"  {t.name}: {len(nodes)}")
    
    print("\n=== SIMILAR TO validate_user ===")
    similar = g.find_similar(validate, threshold=0.4)
    for node, sim in similar[:5]:
        print(f"  {NodeType(node.node_type).name} {node.name}: {sim:.3f}")
    
    print("\n=== GRAPHVIZ ===")
    dot = g.to_graphviz()
    print(dot[:500] + "...")
