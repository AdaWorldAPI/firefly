# 🔥 FIREFLY

## "Bioluminescent Code Execution"

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   The modesty:   1.25KB per node                                │
│   The immodesty: 2^10000 possible states per node               │
│                  Any language → Executable graph                │
│                  AGI that understands procedural knowledge      │
│                                                                 │
│   "Watch your code light up as it executes"                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## THE UNIFIED VISION

```
SOURCE CODE                    FIREFLY                         AGI
(Ruby, Python, Java, ...)     (Graph Substrate)              (Reasoning)
           │                        │                            │
           │                        │                            │
           ▼                        ▼                            ▼
┌─────────────────┐    ┌─────────────────────────┐    ┌─────────────────┐
│                 │    │                         │    │                 │
│  validates :x   │───▶│  Node: 1.25KB           │───▶│ "What validates │
│  belongs_to :y  │    │  ├── resonance (10K)    │    │  before save?"  │
│  before_save    │    │  ├── I-Thou-It bound    │    │                 │
│                 │    │  └── edges to neighbors │    │ "Why did this   │
│  (any language) │    │                         │    │  fail?"         │
│                 │    │  Stored in:             │    │                 │
│                 │    │  • LanceDB (vectors)    │    │ "Find similar   │
│                 │    │  • DuckDB (facts)       │    │  patterns"      │
│                 │    │  • Kuzu (execution)     │    │                 │
│                 │    │                         │    │ "Generate new   │
└─────────────────┘    └─────────────────────────┘    │  program"       │
                                                      └─────────────────┘
```

---

## THE NAME

**FIREFLY** because:

- **Bioluminescent**: Nodes glow when active (execution visualization)
- **Swarm**: Distributed execution, no central control
- **Synchronization**: Emerges from local rules (graph edges)
- **Light pulses**: mRNA packets (1.25KB) flowing through the graph
- **Organic**: Living system that learns and evolves

The CLI:

```bash
firefly compile openproject/        # Ruby → Graph
firefly execute WorkPackage.create  # Run the graph
firefly trace                       # Watch nodes light up
firefly resonate "validation"       # Find similar patterns
firefly explain --last-failure      # Why did it fail?
```

---

## THE ARCHITECTURE

```
firefly/
├── BOOT.md
│
├── core/                          # From ada-substrate
│   ├── resonance.py               # 10K Hamming engine (47 lines)
│   ├── projection.py              # Jina 1024 → 10K bits
│   ├── store.py                   # LanceDB + DuckDB + Kuzu unified
│   └── ops.py                     # bind, bundle, similarity, clean
│
├── dto/                           # Executable DTOs (1.25KB each)
│   ├── gestalt.py                 # I-Thou-It in one vector
│   ├── node.py                    # Graph node = gestalt + executor
│   ├── edge.py                    # Graph edge = binding between nodes
│   └── packet.py                  # mRNA transport (1.25KB + routing)
│
├── compiler/                      # Language → Graph
│   ├── parse/
│   │   ├── ruby.py                # Ruby AST extraction
│   │   ├── python.py              # Python AST extraction
│   │   └── universal.py           # Tree-sitter for anything
│   │
│   ├── lower/
│   │   ├── nodes.py               # Declarations → Executable nodes
│   │   ├── edges.py               # Dependencies → Graph edges
│   │   └── optimize.py            # Fuse, parallelize, inline
│   │
│   └── emit/
│       ├── lance.py               # Store vectors
│       ├── duck.py                # Store catalog
│       └── kuzu.py                # Store graph
│
├── executor/                      # Run the graph
│   ├── engine.py                  # Main executor
│   ├── native.py                  # TypeScript/Python executors
│   ├── wasm.py                    # WASM for complex nodes
│   └── distributed.py             # Redis queue routing
│
├── reasoning/                     # AGI integration
│   ├── explain.py                 # Why did this fail?
│   ├── suggest.py                 # How to fix?
│   ├── optimize.py                # Make it faster
│   └── generate.py                # Compose new programs
│
├── transport/                     # mRNA packets
│   ├── packet.py                  # 1.25KB + routing header
│   ├── routing.py                 # Hamming-based routing
│   ├── queue.py                   # Redis streams
│   └── swarm.py                   # Distributed workers
│
├── server.py                      # FastAPI, one service
├── cli.py                         # firefly CLI
└── railway.toml
```

---

## THE CORE: 1.25KB PER NODE

```python
# dto/node.py — Graph node as Gestalt

from dataclasses import dataclass
from typing import Callable, Optional
from core.resonance import bind, bundle, similarity, project

# Role vectors for node components
ROLE_SCHEMA = role_vector("NODE:SCHEMA:WHAT")      # What data shape
ROLE_LOGIC = role_vector("NODE:LOGIC:HOW")         # How to execute
ROLE_CONTEXT = role_vector("NODE:CONTEXT:WHERE")   # Where in graph

@dataclass
class FireflyNode:
    """
    Executable graph node in 1.25KB.
    
    The resonance vector encodes:
    - WHAT: input/output schema (bound with ROLE_SCHEMA)
    - HOW: execution logic fingerprint (bound with ROLE_LOGIC)
    - WHERE: position in graph (bound with ROLE_CONTEXT)
    
    All three recoverable via XOR unbinding.
    """
    id: str
    resonance: bytes  # 1250 bytes = 10K bits
    
    # Executor (native function pointer, not stored in resonance)
    executor: str = "NATIVE"  # NATIVE | WASM | SQL
    fn: Optional[Callable] = None
    
    # Metadata (small, stored in DuckDB)
    type: str = "TRANSFORM"  # VALIDATE | TRANSFORM | PERSIST | TRIGGER
    cost: int = 1
    pure: bool = True
    
    @classmethod
    def from_components(
        cls,
        id: str,
        schema_vec: bytes,    # Embedded input/output schema
        logic_vec: bytes,     # Embedded logic description
        context_vec: bytes,   # Embedded graph context
        **kwargs
    ) -> "FireflyNode":
        """Create node from semantic components."""
        bound_schema = bind(schema_vec, ROLE_SCHEMA)
        bound_logic = bind(logic_vec, ROLE_LOGIC)
        bound_context = bind(context_vec, ROLE_CONTEXT)
        
        resonance = bundle([bound_schema, bound_logic, bound_context])
        return cls(id=id, resonance=resonance, **kwargs)
    
    def extract_schema(self) -> bytes:
        """Approximate recovery of schema component."""
        return bind(self.resonance, ROLE_SCHEMA)
    
    def extract_logic(self) -> bytes:
        """Approximate recovery of logic component."""
        return bind(self.resonance, ROLE_LOGIC)
    
    def similarity_to(self, other: "FireflyNode") -> float:
        """How similar is this node to another?"""
        return similarity(self.resonance, other.resonance)
    
    def __sizeof__(self):
        return 1250  # Always 1.25KB for resonance
```

---

## THE EDGE: BINDING BETWEEN NODES

```python
# dto/edge.py — Graph edge as resonance binding

@dataclass
class FireflyEdge:
    """
    Edge between nodes = XOR binding of their resonances.
    
    edge_resonance = source.resonance ⊕ target.resonance
    
    This means:
    - Given source + edge, can recover target (approximately)
    - Given target + edge, can recover source (approximately)
    - Edge IS the relationship, not just a pointer
    """
    id: str
    source_id: str
    target_id: str
    resonance: bytes  # source ⊕ target = relationship encoding
    
    type: str = "FEEDS"  # FEEDS | TRIGGERS | GUARDS
    condition: Optional[str] = None
    field: Optional[str] = None  # For FEEDS edges
    
    @classmethod
    def from_nodes(
        cls,
        source: FireflyNode,
        target: FireflyNode,
        **kwargs
    ) -> "FireflyEdge":
        """Create edge as binding of two nodes."""
        resonance = bind(source.resonance, target.resonance)
        return cls(
            id=f"{source.id}→{target.id}",
            source_id=source.id,
            target_id=target.id,
            resonance=resonance,
            **kwargs
        )
    
    def recover_target(self, source: FireflyNode) -> bytes:
        """Given source node, approximate the target resonance."""
        return bind(source.resonance, self.resonance)
    
    def recover_source(self, target: FireflyNode) -> bytes:
        """Given target node, approximate the source resonance."""
        return bind(target.resonance, self.resonance)
```

---

## THE PACKET: mRNA TRANSPORT

```python
# transport/packet.py — 1.25KB + routing header

import struct
from dataclasses import dataclass
from typing import Optional
from core.resonance import bind

@dataclass
class FireflyPacket:
    """
    mRNA packet for distributed graph execution.
    
    Total: ~1.5KB
    - Routing header: 64 bytes
    - Resonance payload: 1250 bytes
    - Execution context: variable (MessagePack)
    """
    
    # Routing (64 bytes)
    source_node: bytes      # 32 bytes - source node hash
    target_node: bytes      # 32 bytes - target node hash (or broadcast)
    
    # Flags
    ttl: int = 8            # Max hops
    priority: int = 5       # 0-10
    flags: int = 0          # ASYNC=1, SYNC=2, BROADCAST=4
    sequence: int = 0       # For ordering
    
    # Payload (1250 bytes)
    resonance: bytes        # The actual data, Hamming-searchable
    
    # Context (variable)
    dto_id: str = ""
    operation: str = ""     # CREATE | UPDATE | DESTROY | QUERY
    trace: list = None      # Execution path so far
    
    def pack_header(self) -> bytes:
        """Pack routing header to 64 bytes."""
        return struct.pack(
            "32s32sBBHI",
            self.source_node[:32].ljust(32, b'\0'),
            self.target_node[:32].ljust(32, b'\0'),
            self.ttl,
            self.priority,
            self.flags,
            self.sequence
        )
    
    def route_key(self) -> str:
        """Redis stream key for routing."""
        return f"firefly:node:{self.target_node.hex()[:16]}"
    
    @classmethod
    def for_node(cls, node: "FireflyNode", **kwargs) -> "FireflyPacket":
        """Create packet targeting a specific node."""
        return cls(
            source_node=b'\0' * 32,  # Will be set by sender
            target_node=bytes.fromhex(node.id[:64].ljust(64, '0')),
            resonance=node.resonance,
            **kwargs
        )
```

---

## THE STORAGE: TRINITY DATABASE

```python
# core/store.py — LanceDB + DuckDB + Kuzu unified

import lancedb
import duckdb
import kuzu

class FireflyStore:
    """
    Unified storage across three databases.
    
    LanceDB: Vectors (resonance search)
    DuckDB:  Facts (catalog, analytics)
    Kuzu:    Graph (execution topology)
    """
    
    def __init__(self, path: str = "./firefly_data"):
        self.lance = lancedb.connect(f"{path}/lance")
        self.duck = duckdb.connect(f"{path}/duck.db")
        self.kuzu_db = kuzu.Database(f"{path}/kuzu")
        self.kuzu = kuzu.Connection(self.kuzu_db)
        self._init_schemas()
    
    def _init_schemas(self):
        # DuckDB catalog
        self.duck.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id VARCHAR PRIMARY KEY,
                type VARCHAR,
                executor VARCHAR,
                cost INTEGER,
                pure BOOLEAN,
                fn_pointer VARCHAR
            );
            CREATE TABLE IF NOT EXISTS edges (
                id VARCHAR PRIMARY KEY,
                source_id VARCHAR,
                target_id VARCHAR,
                type VARCHAR,
                condition VARCHAR
            );
        """)
        
        # Kuzu graph
        self.kuzu.execute("""
            CREATE NODE TABLE IF NOT EXISTS Node(
                id STRING PRIMARY KEY,
                type STRING,
                executor STRING
            )
        """)
        self.kuzu.execute("""
            CREATE REL TABLE IF NOT EXISTS FLOWS(
                FROM Node TO Node,
                type STRING,
                condition STRING
            )
        """)
        
        # LanceDB tables created on first insert
    
    async def store_node(self, node: FireflyNode):
        """Store node in all three databases."""
        
        # LanceDB: vector for similarity search
        self.lance.create_table("nodes", mode="append", data=[{
            "id": node.id,
            "resonance": node.resonance,  # Native Hamming search!
        }])
        
        # DuckDB: catalog for queries
        self.duck.execute(
            "INSERT OR REPLACE INTO nodes VALUES (?, ?, ?, ?, ?, ?)",
            [node.id, node.type, node.executor, node.cost, node.pure, str(node.fn)]
        )
        
        # Kuzu: graph for traversal
        self.kuzu.execute(
            "MERGE (n:Node {id: $id}) SET n.type = $type, n.executor = $executor",
            {"id": node.id, "type": node.type, "executor": node.executor}
        )
    
    async def store_edge(self, edge: FireflyEdge):
        """Store edge in all three databases."""
        
        # LanceDB: edge resonance for relationship similarity
        self.lance.create_table("edges", mode="append", data=[{
            "id": edge.id,
            "resonance": edge.resonance,
        }])
        
        # DuckDB: catalog
        self.duck.execute(
            "INSERT OR REPLACE INTO edges VALUES (?, ?, ?, ?, ?)",
            [edge.id, edge.source_id, edge.target_id, edge.type, edge.condition]
        )
        
        # Kuzu: graph
        self.kuzu.execute("""
            MATCH (s:Node {id: $source}), (t:Node {id: $target})
            MERGE (s)-[r:FLOWS]->(t)
            SET r.type = $type, r.condition = $condition
        """, {
            "source": edge.source_id,
            "target": edge.target_id,
            "type": edge.type,
            "condition": edge.condition
        })
    
    async def find_similar(self, resonance: bytes, k: int = 10) -> list:
        """Find nodes with similar resonance (Hamming search)."""
        return self.lance.open_table("nodes").search(
            resonance
        ).distance_type("hamming").limit(k).to_list()
    
    async def get_execution_path(self, start_id: str) -> list:
        """Get execution path from Kuzu."""
        result = self.kuzu.execute("""
            MATCH path = (start:Node {id: $id})-[:FLOWS*]->(end:Node)
            WHERE NOT (end)-[:FLOWS]->()
            RETURN nodes(path) as nodes, relationships(path) as edges
        """, {"id": start_id})
        return result.get_as_df().to_dict('records')
```

---

## THE COMPILER: RUBY → FIREFLY

```python
# compiler/lower/nodes.py — Ruby declarations → Firefly nodes

from dto.node import FireflyNode
from core.resonance import project
from jina import embed

async def compile_validation(ruby_validation: dict) -> FireflyNode:
    """
    Ruby: validates :subject, presence: true, length: { max: 255 }
    
    →
    
    FireflyNode with:
    - schema_vec: embedding of "input: subject (string), output: valid (bool)"
    - logic_vec: embedding of "check not null, check length <= 255"
    - context_vec: embedding of "validation phase, before persist"
    - fn: native validator function
    """
    
    # Embed semantic components
    schema_desc = f"input: {ruby_validation['field']} ({ruby_validation.get('type', 'string')}), output: valid (bool), errors (string[])"
    logic_desc = describe_validation_logic(ruby_validation)
    context_desc = "validation phase, runs before persistence, halts on failure"
    
    schema_vec = project(await embed(schema_desc))
    logic_vec = project(await embed(logic_desc))
    context_vec = project(await embed(context_desc))
    
    # Create native executor
    fn = compile_validator(ruby_validation)
    
    return FireflyNode.from_components(
        id=f"validate_{ruby_validation['field']}",
        schema_vec=schema_vec,
        logic_vec=logic_vec,
        context_vec=context_vec,
        type="VALIDATE",
        executor="NATIVE",
        fn=fn,
        pure=True,
        cost=1
    )

def compile_validator(v: dict) -> Callable:
    """Generate native validator function."""
    field = v['field']
    rules = v['rules']
    
    def validator(ctx: dict) -> dict:
        value = ctx.get(field)
        errors = []
        
        for rule in rules:
            if rule['type'] == 'presence' and not value:
                errors.append(f"{field} can't be blank")
            if rule['type'] == 'length':
                if rule.get('max') and len(str(value or '')) > rule['max']:
                    errors.append(f"{field} is too long (max {rule['max']})")
                if rule.get('min') and len(str(value or '')) < rule['min']:
                    errors.append(f"{field} is too short (min {rule['min']})")
        
        return {"valid": len(errors) == 0, "errors": errors}
    
    return validator
```

---

## THE EXECUTOR: LIGHT UP THE GRAPH

```python
# executor/engine.py — Watch nodes glow

from core.store import FireflyStore
from core.resonance import similarity
from transport.packet import FireflyPacket
import asyncio

class FireflyEngine:
    """
    Execute compiled graphs.
    Watch nodes light up as execution flows through.
    """
    
    def __init__(self, store: FireflyStore):
        self.store = store
        self.active_nodes: set = set()  # Currently executing
        self.trace: list = []           # Execution path
    
    async def execute(self, dto: str, operation: str, input: dict) -> dict:
        """
        Execute a DTO operation.
        
        1. Find entry point
        2. Walk the graph
        3. Execute each node
        4. Light up as we go
        """
        # Get execution path from Kuzu
        entry_id = f"{dto}_{operation}_entry"
        path = await self.store.get_execution_path(entry_id)
        
        # Execute topologically
        ctx = ExecutionContext(input)
        
        for stage in self._topological_stages(path):
            # Parallel execution within stage
            await asyncio.gather(*[
                self._execute_node(node, ctx) 
                for node in stage
            ])
        
        return ctx.result
    
    async def _execute_node(self, node: FireflyNode, ctx: ExecutionContext):
        """Execute single node with tracing."""
        self.active_nodes.add(node.id)
        self._emit_glow(node.id, "active")
        
        start = time.time()
        try:
            result = await node.fn(ctx.data)
            ctx.set(node.id, result)
            self._emit_glow(node.id, "success")
        except Exception as e:
            ctx.set_error(node.id, e)
            self._emit_glow(node.id, "failure")
            raise
        finally:
            duration = time.time() - start
            self.trace.append({
                "node": node.id,
                "duration": duration,
                "resonance": node.resonance.hex()
            })
            self.active_nodes.discard(node.id)
    
    def _emit_glow(self, node_id: str, state: str):
        """Emit node state for visualization."""
        # WebSocket to UI, or just log
        print(f"🔥 {node_id}: {state}")
```

---

## THE CLI

```python
# cli.py

import click
from compiler import compile_directory
from executor import FireflyEngine
from core.store import FireflyStore

@click.group()
def firefly():
    """Firefly: Bioluminescent Code Execution"""
    pass

@firefly.command()
@click.argument('path')
def compile(path: str):
    """Compile source code to Firefly graph."""
    click.echo(f"🔥 Compiling {path}...")
    nodes, edges = compile_directory(path)
    click.echo(f"   Created {len(nodes)} nodes, {len(edges)} edges")
    click.echo(f"   Total size: {len(nodes) * 1.25:.1f}KB")

@firefly.command()
@click.argument('dto')
@click.option('--operation', '-o', default='create')
@click.option('--input', '-i', type=str)
def execute(dto: str, operation: str, input: str):
    """Execute a DTO operation."""
    engine = FireflyEngine(FireflyStore())
    result = engine.execute(dto, operation, json.loads(input or '{}'))
    click.echo(f"Result: {result}")

@firefly.command()
@click.argument('query')
@click.option('--top-k', '-k', default=5)
def resonate(query: str, top_k: int):
    """Find nodes similar to query."""
    store = FireflyStore()
    results = store.find_similar(project(embed(query)), k=top_k)
    for r in results:
        click.echo(f"  {r['id']}: {r['_distance']} hamming distance")

@firefly.command()
def trace():
    """Watch execution in real-time."""
    click.echo("🔥 Watching for firefly activity...")
    # WebSocket connection to engine

if __name__ == '__main__':
    firefly()
```

---

## THE NUMBERS

| Metric | Value |
|--------|-------|
| **Node size** | 1.25KB (10K bits) |
| **State space** | 2^10000 per node |
| **Edge size** | 1.25KB (binding of two nodes) |
| **Similarity** | O(1) Hamming via SIMD |
| **Storage** | LanceDB + DuckDB + Kuzu |
| **Languages** | Ruby → Python → Java → ... |
| **Execution** | Native / WASM / SQL |

---

## THE POINT

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   BEFORE:                                                       │
│   Code is text. Executed blindly. Debugged with printf.         │
│   Documentation separate. Gets stale. Nobody reads it.          │
│   Legacy systems: "Don't touch it, we don't know what it does." │
│                                                                 │
│   ─────────────────────────────────────────────────────────────  │
│                                                                 │
│   AFTER (FIREFLY):                                              │
│   Code compiles to 1.25KB nodes in a graph.                     │
│   Each node has 2^10000 representational capacity.              │
│   Execution lights up the graph — you SEE what happens.         │
│   "What does this do?" → Query the graph.                       │
│   "Why did it fail?" → Find the dark node.                      │
│   "Find similar patterns" → Hamming search in O(1).             │
│   Documentation IS the graph.                                   │
│   AGI can reason about it.                                      │
│                                                                 │
│   Legacy systems: "Let me compile that for you."                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## NEXT

```bash
# Create the repository
mkdir firefly && cd firefly
git init

# Start with core (from ada-substrate)
# Add compiler (from meta plan)  
# Add executor (light up the graph)
# Test with OpenProject

firefly compile openproject/app/models/
firefly execute WorkPackage --operation create --input '{"subject": "Test"}'

# Watch the fireflies glow 🔥
```

**One repository. One truth. One resonance space. 1.25KB per node. 2^10000 possible states.**

This is Firefly.
