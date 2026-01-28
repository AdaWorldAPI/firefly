# LadybugDB

**Code as deterministic graph. Every construct is a node.**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              DECLARATIVE LAYER (graph.py)                   │
│              ════════════════════════════                   │
│                                                             │
│   CLASS ──CONTAINS──► METHOD ──CALLS──► METHOD             │
│     │                    │                  │               │
│     └──CONTAINS──► PROPERTY            FOREACH             │
│                                           │                 │
│                                      IF ──┴──► CALL        │
│                                                             │
│   Numba jitclass: Node, Edge                               │
│   DuckDB for deterministic traversal                        │
├─────────────────────────────────────────────────────────────┤
│              HAMMING LAYER (substrate)                      │
│              ════════════════════════                       │
│                                                             │
│   XOR │ POPCOUNT │ fingerprint │ similarity                │
│                                                             │
│   Each node gets 10K-bit fingerprint                       │
│   Similarity = 1 - hamming/10000                           │
└─────────────────────────────────────────────────────────────┘
```

## Node Types

| Type | Description | Example |
|------|-------------|---------|
| MODULE | File/package | `user_service.py` |
| CLASS | Class declaration | `class UserService` |
| METHOD | Method inside class | `def validate()` |
| FUNCTION | Standalone function | `def helper()` |
| PROPERTY | Class property | `self.db: Database` |
| IF | Conditional | `if user.email:` |
| FOREACH | For loop | `for user in users:` |
| WHILE | While loop | `while active:` |
| MATCH | Pattern match | `match status:` |
| CALL | Function call | `db.query()` |

## Edge Types

| Type | Description |
|------|-------------|
| CONTAINS | Parent contains child |
| CALLS | Function/method call |
| DEPENDS | Dependency relationship |
| INHERITS | Class inheritance |
| IMPLEMENTS | Interface implementation |
| BRANCHES_TO | Control flow branch |
| LOOPS_TO | Loop back edge |

## Usage

```python
from core.ladybug.graph import CodeGraph, NodeType, EdgeType

g = CodeGraph()

# Build graph declaratively
mod = g.module("user_service")
cls = g.class_("UserService", mod)

# Method with signature and body
validate = g.method(
    "validate_user",
    "(user: User) -> bool",
    "return self.db.check(user.email)",
    cls
)

# Control flow
if_block = g.if_("user.email", validate)
call = g.call("self.db.check", "user.email", if_block)

# Loops
batch = g.method("batch_validate", "(users: List[User]) -> List[bool]", "...", cls)
loop = g.foreach("user", "users", batch)
inner_call = g.call("self.validate_user", "user", loop)

# Connect calls
g.calls(inner_call, validate)

# Query
similar = g.find_similar(validate, threshold=0.5)
children = g.get_children(cls)
methods = g.find_by_type(NodeType.METHOD)

# Export
dot = g.to_graphviz()
db = g.to_duckdb()
```

## Numba JIT Classes

All nodes and edges are Numba jitclass - compiled to native machine code:

```python
@jitclass(node_spec)
class Node:
    id: int64
    node_type: int32
    name: unicode
    fingerprint: uint64[157]  # 10K bits
    parent_id: int64
    
    def hamming(self, other) -> int:
        # Native POPCNT instruction
        ...
    
    def similarity(self, other) -> float:
        return 1.0 - self.hamming(other) / 10000
```

## Fingerprint

Each node gets deterministic 10K-bit fingerprint:

```
identity = f"{NODE_TYPE}::{name}::{signature}::{body}"

for i in 0..157:
    hash = SHA256(f"{identity}:{i}")
    fingerprint[i] = little_endian_u64(hash[0:8])
```

Same code = same fingerprint = same node identity.

## Files

```
core/ladybug/
├── __init__.py    # LadybugDB core (execution, storage)
├── graph.py       # Declarative layer (Node, Edge, CodeGraph)
├── simd.py        # AVX-512 kernels (batch Hamming)
└── README.md
```
