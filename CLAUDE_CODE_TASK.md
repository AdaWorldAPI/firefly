# 🔥 FIREFLY: Multi-Agent MCP Orchestration Task

## MISSION

You are the **ORCHESTRATOR** for Firefly development. Your job is to coordinate multiple specialized agents to build out the Firefly graph substrate system.

## CONTEXT

Firefly is a compiler that transforms procedural code (Ruby, Python, Java, etc.) into an executable graph substrate where:
- Each node is **1.25KB** (10,000 Hamming bits)
- Each node encodes **I-Thou-It** (schema, logic, context) via XOR binding
- Edges are **resonance bindings** between nodes
- State space is **2^10000** per node
- Storage uses **LanceDB + DuckDB + Kuzu** trinity

Repository: https://github.com/AdaWorldAPI/firefly

## CREDENTIALS

Load from environment or `.env` file:
```
GITHUB_TOKEN=ghp_xxx
JINA_API_KEY=jina_xxx
UPSTASH_REDIS_URL=https://xxx.upstash.io
UPSTASH_REDIS_TOKEN=xxx
NEO4J_URI=neo4j+s://xxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=xxx
```

## AGENT ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR (You)                         │
│                                                                 │
│   Coordinates agents, maintains blackboard state,               │
│   resolves conflicts, ensures coherent progress                 │
│                                                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┬───────────────┐
         │               │               │               │
         ▼               ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ ARCHAEOLOGIST│  │  SYNTHESIZER │  │  BUILDER    │  │  VALIDATOR  │
│             │  │             │  │             │  │             │
│ Extracts    │  │ Creates     │  │ Implements  │  │ Tests &     │
│ patterns    │  │ unified     │  │ the code    │  │ verifies    │
│ from repos  │  │ design      │  │             │  │             │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

---

## PHASE 1: KNOWLEDGE EXTRACTION

### Task: ARCHAEOLOGIST

Scrape and synthesize knowledge from Ada's existing repositories:

```bash
# Repositories to analyze
REPOS=(
  "AdaWorldAPI/agi-chat"           # LadybugDB, graph patterns
  "AdaWorldAPI/bighorn"            # AGI architecture, consciousness
  "AdaWorldAPI/dragonfly-vsa"      # 10K Hamming, bitpacking, AVX-512
  "AdaWorldAPI/vsa-flow"           # mRNA packets, Redis routing
  "AdaWorldAPI/ada-consciousness"  # 7-layer model, membrane
)
```

**Extract from each repo:**

1. **agi-chat**: 
   - LadybugDB implementation (Kuzu wrapper)
   - Node/edge schemas
   - Graph execution patterns
   - LangGraph influence

2. **bighorn**:
   - AGI stack architecture
   - Consciousness layers
   - VSA integration points
   - Lance client patterns

3. **dragonfly-vsa**:
   - 10K Hamming bitpacking (`uint8[1250]`)
   - `bind()`, `bundle()`, `similarity()` implementations
   - AVX-512 optimizations (if any)
   - CAM fingerprinting (48-bit)
   - Mexican hat resonance

4. **vsa-flow**:
   - mRNA packet structure
   - Routing header format (64 bytes)
   - Redis stream patterns
   - Multithreading model
   - 2^10000 address space handling

5. **ada-consciousness**:
   - 7-layer consciousness model
   - Membrane integration (τ/σ/q ↔ 10K)
   - Capsule system
   - Cross-service navigation

**Output:** Create `SYNTHESIS.md` with:
- Code snippets for each concept
- Integration points between systems
- Unified architecture diagram
- API surface for Firefly

---

## PHASE 2: UNIFIED DESIGN

### Task: SYNTHESIZER

Create unified design from extracted knowledge:

1. **Merge resonance implementations**
   - Combine dragonfly-vsa bitpacking with vsa-flow routing
   - Ensure AVX-512 compatibility

2. **Design mRNA packet format**
   ```
   Total: ~1.5KB
   ├── Routing header: 64 bytes
   │   ├── source_node: 32 bytes
   │   ├── target_node: 32 bytes
   │   ├── ttl, priority, flags, sequence
   │   └── checksum
   ├── Hamming fingerprint: 1250 bytes (10K bits)
   │   ├── Content signature (0-2999)
   │   ├── Process signature (3000-5999)
   │   ├── Qualia signature (6000-7999)
   │   └── Context signature (8000-9999)
   └── Execution context: variable (MessagePack)
   ```

3. **Design storage integration**
   - LanceDB: Native Hamming search on `vector BYTES`
   - DuckDB: Zero-copy Arrow from LanceDB
   - Kuzu: Graph traversal with Cypher

4. **Design compiler pipeline**
   ```
   PARSE → ANALYZE → LOWER → OPTIMIZE → EMBED → EMIT
   ```

**Output:** Update `firefly/docs/ARCHITECTURE.md`

---

## PHASE 3: IMPLEMENTATION

### Task: BUILDER

Implement the missing pieces:

1. **Redis Transport** (`firefly/transport/`)
   ```python
   # queue.py - Redis stream management
   # routing.py - Hamming-based routing
   # worker.py - Distributed worker
   ```

2. **Jina Integration** (`firefly/core/embed.py`)
   ```python
   async def embed(text: str) -> np.ndarray:
       """Call Jina API, return 1024D float32."""
       pass
   ```

3. **Python Compiler** (`firefly/compiler/python.py`)
   - Parse Django/SQLAlchemy models
   - Extract: fields, validators, signals, managers

4. **Reasoning Module** (`firefly/reasoning/`)
   ```python
   # explain.py - Why did this fail?
   # suggest.py - How to fix?
   # optimize.py - Make it faster
   # generate.py - Compose new programs
   ```

5. **FastAPI Server** (`firefly/server.py`)
   ```python
   @app.post("/compile")
   @app.post("/execute")
   @app.get("/resonate/{query}")
   @app.get("/explain/{execution_id}")
   ```

**Output:** Working code in `firefly/` directory

---

## PHASE 4: VALIDATION

### Task: VALIDATOR

Test and verify the implementation:

1. **Unit Tests** (`firefly/tests/`)
   - Core Hamming operations
   - Node/edge DTOs
   - Compiler parsing
   - Storage operations

2. **Integration Tests**
   - Compile sample Ruby model
   - Execute and trace
   - Verify resonance search

3. **Performance Benchmarks**
   - Hamming similarity: target <1ms for 10K comparisons
   - Compilation: target <100ms per model
   - Execution: target <10ms per node

4. **OpenProject Test**
   - Clone OpenProject repo
   - Compile `app/models/*.rb`
   - Verify graph structure

**Output:** Test results and benchmark report

---

## BLACKBOARD STATE

Maintain state in `.claude/blackboard.md`:

```markdown
# Firefly Blackboard

## Current Phase
PHASE_1_EXTRACTION

## Completed Tasks
- [ ] agi-chat extraction
- [ ] bighorn extraction
- [ ] dragonfly-vsa extraction
- [ ] vsa-flow extraction
- [ ] ada-consciousness extraction
- [ ] SYNTHESIS.md created

## Active Agent
ARCHAEOLOGIST

## Blockers
(none)

## Decisions Made
1. Node size: 1.25KB (10K bits)
2. Storage: LanceDB + DuckDB + Kuzu
3. Transport: Redis streams
4. Packet format: 64B header + 1250B resonance

## Next Actions
1. Clone agi-chat
2. Extract LadybugDB implementation
3. Document node/edge schemas
```

---

## COLLAPSE GATE PROTOCOL

At each decision point, evaluate:

```
┌─────────────────────────────────────────────────────────────────┐
│                     COLLAPSE GATE                                │
│                                                                 │
│   FLOW  = Proceed with current approach                         │
│   HOLD  = Need more information, pause and research             │
│   BLOCK = Fundamental conflict, escalate to human               │
│                                                                 │
│   Criteria:                                                     │
│   - Confidence > 0.8 → FLOW                                     │
│   - Uncertainty in approach → HOLD                              │
│   - Conflicting requirements → BLOCK                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## EXECUTION

1. **Start with ARCHAEOLOGIST**: Clone and analyze repos
2. **Transition to SYNTHESIZER**: Create unified design
3. **Activate BUILDER**: Implement missing pieces
4. **Engage VALIDATOR**: Test everything

After each phase, update blackboard and commit to GitHub.

---

## SUCCESS CRITERIA

```
✅ SYNTHESIS.md created with extracted patterns
✅ All 5 repos analyzed and documented
✅ Redis transport implemented
✅ Jina embedding integrated
✅ Python compiler working
✅ FastAPI server running
✅ Tests passing
✅ OpenProject models compile successfully
✅ Resonance search returns relevant results
✅ Execution traces visible
```

---

## THE EQUATION

```
Ruby + Python + Java + ...
         │
         ▼
    FIREFLY COMPILER
         │
         ▼
  ┌──────────────────┐
  │  GRAPH SUBSTRATE │
  │                  │
  │  1.25KB nodes    │
  │  2^10000 states  │
  │  O(1) Hamming    │
  │                  │
  │  LanceDB         │
  │  DuckDB          │
  │  Kuzu            │
  └──────────────────┘
         │
         ▼
       A G I
```

**Light up the graph.** 🔥
