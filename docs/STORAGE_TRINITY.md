# Storage Trinity: LanceDB + DuckDB + Kuzu

## The Three Questions

Each database answers a different question:

| Database | Question | Use Case |
|----------|----------|----------|
| **LanceDB** | "What is similar?" | Vector search, resonance |
| **DuckDB** | "What are the facts?" | SQL analytics, catalog |
| **Kuzu** | "How does it connect?" | Graph traversal |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    STORAGE TRINITY                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────┐                                           │
│   │    LanceDB      │  "What is similar?"                       │
│   │                 │                                           │
│   │  • Node vectors │  → Find nodes with similar resonance      │
│   │  • Edge vectors │  → Find similar relationships             │
│   │  • Trace vectors│  → Find similar execution patterns        │
│   │                 │                                           │
│   │  Hamming native │  → O(1) 10K bit comparison                │
│   │  Versioned      │  → Time travel through history            │
│   │  S3-backed      │  → Infinite scale, low cost               │
│   └────────┬────────┘                                           │
│            │                                                    │
│            │ Arrow (zero-copy)                                  │
│            │                                                    │
│   ┌────────▼────────┐                                           │
│   │     DuckDB      │  "What are the facts?"                    │
│   │                 │                                           │
│   │  • Node catalog │  → SELECT * FROM nodes WHERE type='...'   │
│   │  • Edge catalog │  → JOIN nodes ON edges                    │
│   │  • Exec logs    │  → Analytics on execution times           │
│   │                 │                                           │
│   │  SQL interface  │  → Familiar querying                      │
│   │  Columnar       │  → Fast aggregations                      │
│   │  In-process     │  → No network overhead                    │
│   └────────┬────────┘                                           │
│            │                                                    │
│            │ Shared IDs                                         │
│            │                                                    │
│   ┌────────▼────────┐                                           │
│   │      Kuzu       │  "How does it connect?"                   │
│   │                 │                                           │
│   │  • Node table   │  → (:Node {id, type, executor})           │
│   │  • Edge table   │  → -[:FLOWS {type, condition}]->          │
│   │                 │                                           │
│   │  Cypher queries │  → MATCH path = (a)-[*]->(b)              │
│   │  Path finding   │  → Execution order                        │
│   │  Embedded       │  → No external service                    │
│   └─────────────────┘                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## LanceDB: Vector Storage

### Why LanceDB?

- **Native Hamming distance** for binary vectors
- **Versioned** - every write creates immutable version
- **S3-native** - runs directly on object storage
- **Zero-copy Arrow** - integrates with DuckDB/Pandas

### Schema

```python
# nodes table
{
    "id": "validate_subject",
    "vector": bytes[1250],        # 10K bits, Hamming-searchable
    "type": "VALIDATE",
    "dto_id": "WorkPackage",
    "created_at": "2024-01-27T..."
}

# edges table
{
    "id": "validate_subject→validate_length",
    "vector": bytes[1250],        # Relationship resonance
    "type": "FEEDS",
    "source_id": "validate_subject",
    "target_id": "validate_length"
}

# traces table
{
    "id": "exec_abc123",
    "vector": bytes[1250],        # Execution fingerprint
    "dto_id": "WorkPackage",
    "operation": "create",
    "success": true,
    "duration_ms": 45.2
}
```

### Queries

```python
# Find similar nodes
results = table.search(query_vector) \
    .metric("hamming") \
    .limit(10) \
    .to_list()

# Time travel
old_table = table.checkout(version=42)
old_results = old_table.search(query).to_list()
```

---

## DuckDB: Relational Analytics

### Why DuckDB?

- **SQL interface** - familiar, powerful
- **Columnar** - fast aggregations
- **In-process** - no network latency
- **Arrow integration** - zero-copy from LanceDB

### Schema

```sql
CREATE TABLE nodes (
    id VARCHAR PRIMARY KEY,
    type VARCHAR,           -- VALIDATE, TRANSFORM, PERSIST, TRIGGER
    executor VARCHAR,       -- NATIVE, WASM, SQL
    fn_name VARCHAR,
    cost INTEGER,
    pure BOOLEAN,
    parallelizable BOOLEAN,
    input_schema JSON,
    output_schema JSON,
    created_at TIMESTAMP
);

CREATE TABLE edges (
    id VARCHAR PRIMARY KEY,
    source_id VARCHAR REFERENCES nodes(id),
    target_id VARCHAR REFERENCES nodes(id),
    type VARCHAR,           -- FEEDS, TRIGGERS, GUARDS
    condition VARCHAR,
    field VARCHAR,
    created_at TIMESTAMP
);

CREATE TABLE execution_log (
    id VARCHAR PRIMARY KEY,
    execution_id VARCHAR,
    node_id VARCHAR,
    duration_ms DOUBLE,
    success BOOLEAN,
    error VARCHAR,
    timestamp TIMESTAMP
);
```

### Queries

```sql
-- Slowest nodes
SELECT 
    node_id,
    COUNT(*) as executions,
    AVG(duration_ms) as avg_ms,
    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures
FROM execution_log
GROUP BY node_id
ORDER BY avg_ms DESC
LIMIT 10;

-- Node dependencies
SELECT 
    n.id,
    n.type,
    COUNT(e.id) as outgoing_edges
FROM nodes n
LEFT JOIN edges e ON n.id = e.source_id
GROUP BY n.id, n.type;

-- Execution path stats
SELECT 
    dto_id,
    operation,
    AVG(duration_ms) as avg_duration,
    COUNT(*) as total_executions
FROM (
    SELECT DISTINCT execution_id, dto_id, operation
    FROM execution_log
) 
GROUP BY dto_id, operation;
```

---

## Kuzu: Graph Traversal

### Why Kuzu?

- **Cypher queries** - expressive graph patterns
- **Embedded** - no external service
- **Path finding** - execution order
- **Property graph** - nodes and edges have attributes

### Schema

```cypher
-- Node table
CREATE NODE TABLE Node(
    id STRING PRIMARY KEY,
    type STRING,
    executor STRING
)

-- Edge table
CREATE REL TABLE FLOWS(
    FROM Node TO Node,
    type STRING,
    condition STRING
)
```

### Queries

```cypher
-- Execution path from entry to terminal
MATCH path = (start:Node {id: 'WorkPackage_create_entry'})-[:FLOWS*]->(end:Node)
WHERE NOT EXISTS { MATCH (end)-[:FLOWS]->() }
RETURN [n IN nodes(path) | n.id] as execution_order

-- Upstream dependencies
MATCH (upstream:Node)-[:FLOWS*1..3]->(target:Node {id: 'Task_persist'})
RETURN DISTINCT upstream.id, upstream.type

-- Parallel stages (nodes at same depth)
MATCH path = (entry:Node {id: 'Task_create_entry'})-[:FLOWS*]->(n:Node)
RETURN n.id, length(path) as depth
ORDER BY depth

-- All paths between two nodes
MATCH paths = allShortestPaths(
    (a:Node {id: 'validate_subject'})-[:FLOWS*]-(b:Node {id: 'persist'})
)
RETURN paths
```

---

## Integration Pattern

```python
class FireflyStore:
    """Unified storage across three databases."""
    
    def __init__(self, path: str):
        self.lance = lancedb.connect(f"{path}/lance")
        self.duck = duckdb.connect(f"{path}/duck.db")
        self.kuzu_db = kuzu.Database(f"{path}/kuzu")
        self.kuzu = kuzu.Connection(self.kuzu_db)
    
    async def store_node(self, node: FireflyNode):
        """Store node in ALL THREE databases."""
        
        # LanceDB: vector for similarity
        self.lance.open_table("nodes").add([{
            "id": node.id,
            "vector": node.resonance,
            "type": node.type,
        }])
        
        # DuckDB: catalog for SQL
        self.duck.execute(
            "INSERT INTO nodes VALUES (?, ?, ?, ...)",
            [node.id, node.type, node.executor, ...]
        )
        
        # Kuzu: graph for traversal
        self.kuzu.execute("""
            MERGE (n:Node {id: $id})
            SET n.type = $type, n.executor = $executor
        """, {"id": node.id, ...})
    
    async def find_similar(self, resonance: bytes, k: int = 10):
        """Find similar nodes (LanceDB)."""
        return self.lance.open_table("nodes") \
            .search(resonance) \
            .metric("hamming") \
            .limit(k) \
            .to_list()
    
    async def get_execution_path(self, entry_id: str):
        """Get execution path (Kuzu)."""
        return self.kuzu.execute("""
            MATCH path = (start:Node {id: $id})-[:FLOWS*]->(end:Node)
            WHERE NOT EXISTS { MATCH (end)-[:FLOWS]->() }
            RETURN [n IN nodes(path) | n.id]
        """, {"id": entry_id}).get_as_df()
    
    async def get_slowest_nodes(self, limit: int = 10):
        """Get slowest nodes (DuckDB)."""
        return self.duck.execute("""
            SELECT node_id, AVG(duration_ms) as avg_ms
            FROM execution_log
            GROUP BY node_id
            ORDER BY avg_ms DESC
            LIMIT ?
        """, [limit]).fetchall()
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA FLOW                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   WRITE PATH                                                    │
│   ══════════                                                    │
│                                                                 │
│   Compiler                                                      │
│      │                                                          │
│      ├──► LanceDB: Store resonance vector                       │
│      ├──► DuckDB: Store metadata/catalog                        │
│      └──► Kuzu: Store graph structure                           │
│                                                                 │
│   ─────────────────────────────────────────────────────────────  │
│                                                                 │
│   READ PATH (Execution)                                         │
│   ═════════════════════                                         │
│                                                                 │
│   1. Kuzu: Get execution path                                   │
│      │                                                          │
│      │ MATCH (entry)-[:FLOWS*]->(end)                           │
│      ▼                                                          │
│   2. DuckDB: Get node metadata                                  │
│      │                                                          │
│      │ SELECT executor, fn_name FROM nodes                      │
│      ▼                                                          │
│   3. Execute nodes                                              │
│      │                                                          │
│      │ Call native/WASM/SQL                                     │
│      ▼                                                          │
│   4. DuckDB: Log execution                                      │
│      │                                                          │
│      │ INSERT INTO execution_log                                │
│      ▼                                                          │
│   Done                                                          │
│                                                                 │
│   ─────────────────────────────────────────────────────────────  │
│                                                                 │
│   READ PATH (Similarity)                                        │
│   ══════════════════════                                        │
│                                                                 │
│   1. LanceDB: Find similar                                      │
│      │                                                          │
│      │ search(query).metric("hamming")                          │
│      ▼                                                          │
│   2. DuckDB: Enrich with metadata                               │
│      │                                                          │
│      │ SELECT * FROM nodes WHERE id IN (...)                    │
│      ▼                                                          │
│   Return enriched results                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## The Point

Three databases, three questions, one unified interface.

| Query Type | Database | Time Complexity |
|------------|----------|-----------------|
| Similarity search | LanceDB | O(log n) |
| SQL analytics | DuckDB | O(n) with indexes |
| Graph traversal | Kuzu | O(V + E) |

All connected via:
- **Shared IDs** (node.id is primary key everywhere)
- **Arrow interchange** (zero-copy between Lance and Duck)
- **Unified API** (FireflyStore wraps all three)

The trinity is the foundation. Everything builds on top.
