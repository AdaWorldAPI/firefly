# 🔥 SYNTHESIS: Consolidate Everything INTO Firefly

## THE PLAN

**Firefly becomes THE unified execution layer.** We SCRAPE code FROM other repos INTO firefly. No imports, no dependencies - one consolidated codebase.

```
SOURCE REPOS                          TARGET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

dragonfly-vsa/src/ ─────┐
  pure_bitpacked_vsa.py │
  mrna_transport.py     │
  ladybug_store.py      │
  duckdb_substrate.py   ├───────►  firefly/
  grounded_graph.py     │            (consolidated)
  cognitive_orchestrator│
                        │
vsa_flow/ ──────────────┤
  transport/wire.py     │
  core/mrna.py          │
                        │
rubberduck/ ────────────┤
  parse/ruby.py         │
  cli.py                │
                        │
agi-chat/ ──────────────┤
  ladybug*.py           │
  graph*.py             │
                        │
bighorn/ ───────────────┘
  agi_stack/
  consciousness/
```

---

## FIREFLY: THE CONSOLIDATED STACK

After scraping, firefly will contain:

```
firefly/
├── BOOT.md
│
├── core/                              # FROM dragonfly-vsa
│   ├── vsa.py                         # pure_bitpacked_vsa.py
│   ├── hamming.py                     # 10K ops, bind, bundle, similarity
│   ├── projection.py                  # Jina 1024 → 10K bits
│   ├── cam.py                         # Content-addressable memory
│   └── mexican_hat.py                 # Resonance cleaning
│
├── dto/                               # FROM dragonfly-vsa + new
│   ├── node.py                        # FireflyNode (1.25KB)
│   ├── edge.py                        # FireflyEdge (XOR binding)
│   ├── packet.py                      # mRNA packet
│   ├── gestalt.py                     # I-Thou-It
│   └── capsule.py                     # State capsules
│
├── transport/                         # FROM vsa_flow
│   ├── wire.py                        # Binary mRNA protocol
│   ├── envelope.py                    # Pack/unpack
│   ├── routing.py                     # Hamming-based routing
│   └── queue.py                       # Redis streams
│
├── storage/                           # FROM dragonfly-vsa + agi-chat
│   ├── trinity.py                     # Unified interface
│   ├── lance.py                       # LanceDB vectors
│   ├── duck.py                        # DuckDB catalog
│   ├── kuzu.py                        # Kuzu graph (ladybug)
│   └── substrate.py                   # duckdb_substrate.py
│
├── compiler/                          # FROM rubberduck
│   ├── ruby.py                        # Rails models
│   ├── python.py                      # Django/SQLAlchemy
│   ├── universal.py                   # Tree-sitter fallback
│   └── emit.py                        # Output to storage
│
├── executor/                          # FROM dragonfly-vsa + bighorn
│   ├── engine.py                      # Graph execution
│   ├── glow.py                        # Visualization
│   ├── trace.py                       # Execution tracing
│   └── orchestrator.py                # cognitive_orchestrator.py
│
├── reasoning/                         # FROM bighorn
│   ├── explain.py                     # Why did this fail?
│   ├── suggest.py                     # How to fix?
│   ├── optimize.py                    # Make it faster
│   └── generate.py                    # Compose new programs
│
├── consciousness/                     # FROM ada-consciousness + bighorn
│   ├── layers.py                      # 7-layer model
│   ├── membrane.py                    # τ/σ/q ↔ 10K
│   └── state.py                       # State encoding
│
├── server.py                          # FastAPI endpoints
├── cli.py                             # CLI interface
└── tests/
```

---

## SCRAPING MAP

### Phase 1: Core (FROM dragonfly-vsa)

| Source | Target | Action |
|--------|--------|--------|
| `dragonfly-vsa/src/pure_bitpacked_vsa.py` | `firefly/core/vsa.py` | Copy + adapt |
| `dragonfly-vsa/src/cam.py` | `firefly/core/cam.py` | Copy |
| `dragonfly-vsa/src/meaning_cam.py` | `firefly/core/cam.py` | Merge |
| `dragonfly-vsa/src/capsule_*.py` | `firefly/dto/capsule.py` | Consolidate |

### Phase 2: Transport (FROM vsa_flow)

| Source | Target | Action |
|--------|--------|--------|
| `vsa_flow/transport/wire.py` | `firefly/transport/wire.py` | Copy + adapt |
| `vsa_flow/core/mrna.py` | `firefly/dto/packet.py` | Merge |

### Phase 3: Storage (FROM dragonfly-vsa + agi-chat)

| Source | Target | Action |
|--------|--------|--------|
| `dragonfly-vsa/src/ladybug_store.py` | `firefly/storage/kuzu.py` | Copy + adapt |
| `dragonfly-vsa/src/ladybug_store_v2.py` | `firefly/storage/kuzu.py` | Merge best |
| `dragonfly-vsa/src/duckdb_substrate.py` | `firefly/storage/substrate.py` | Copy |
| `dragonfly-vsa/src/semantic_graph_store.py` | `firefly/storage/trinity.py` | Integrate |
| `agi-chat/src/ladybug*.py` | `firefly/storage/kuzu.py` | Check for patterns |

### Phase 4: Compiler (FROM rubberduck)

| Source | Target | Action |
|--------|--------|--------|
| `rubberduck/parse/*.py` | `firefly/compiler/*.py` | Copy |
| `rubberduck/cli.py` | `firefly/cli.py` | Merge |

### Phase 5: Executor (FROM dragonfly-vsa)

| Source | Target | Action |
|--------|--------|--------|
| `dragonfly-vsa/src/grounded_graph.py` | `firefly/executor/engine.py` | Copy + adapt |
| `dragonfly-vsa/src/cognitive_orchestrator.py` | `firefly/executor/orchestrator.py` | Copy |

### Phase 6: Reasoning (FROM bighorn)

| Source | Target | Action |
|--------|--------|--------|
| `bighorn/agi_stack/*.py` | `firefly/reasoning/*.py` | Extract patterns |
| `bighorn/consciousness/*.py` | `firefly/consciousness/*.py` | Extract patterns |

---

## THE OUTPUT STACK

After consolidation:

```
┌─────────────────────────────────────────────────────────────────┐
│                         A2UI                                     │
│   Receives mRNA packets from Firefly                             │
│   Decodes → Renders                                              │
│   🖥️  THIN CLIENT                                                │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ application/x-mrna-10k
                              │
┌─────────────────────────────────────────────────────────────────┐
│                        🔥 FIREFLY                                │
│                                                                 │
│   EVERYTHING LIVES HERE:                                        │
│   • Core VSA ops (from dragonfly)                               │
│   • Transport (from vsa_flow)                                   │
│   • Storage (from dragonfly + agi-chat)                         │
│   • Compiler (from rubberduck)                                  │
│   • Executor (from dragonfly)                                   │
│   • Reasoning (from bighorn)                                    │
│   • Consciousness (from ada-consciousness)                      │
│                                                                 │
│   ONE REPO. ONE TRUTH.                                          │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     SOURCE CODE                                  │
│   Ruby, Python, Java, COBOL                                      │
│   📜                                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## WHAT HAPPENS TO SOURCE REPOS?

After scraping into Firefly:

| Repo | Fate |
|------|------|
| **dragonfly-vsa** | Archive or keep as "reference implementation" |
| **vsa_flow** | Archive - transport now in firefly |
| **rubberduck** | Archive - compiler now in firefly |
| **agi-chat** | Archive - ladybug now in firefly |
| **bighorn** | Archive - reasoning now in firefly |
| **A2UI** | KEEP - separate thin client |

---

## CLAUDE CODE PROMPT

```markdown
# 🔥 FIREFLY CONSOLIDATION TASK

## MISSION

Scrape execution code FROM other repos INTO firefly.
Firefly becomes the single source of truth.

## REPOS TO SCRAPE

```bash
git clone https://github.com/AdaWorldAPI/dragonfly-vsa
git clone https://github.com/AdaWorldAPI/vsa_flow
git clone https://github.com/AdaWorldAPI/rubberduck
git clone https://github.com/AdaWorldAPI/agi-chat
git clone https://github.com/AdaWorldAPI/bighorn
git clone https://github.com/AdaWorldAPI/ada-consciousness
git clone https://github.com/AdaWorldAPI/firefly  # TARGET
```

## SCRAPING ORDER

1. **Core** (dragonfly-vsa → firefly/core/)
   - pure_bitpacked_vsa.py → vsa.py
   - cam.py → cam.py
   - capsule_*.py → dto/capsule.py

2. **Transport** (vsa_flow → firefly/transport/)
   - wire.py → wire.py
   - mrna.py → dto/packet.py

3. **Storage** (dragonfly-vsa + agi-chat → firefly/storage/)
   - ladybug_store.py → kuzu.py
   - duckdb_substrate.py → substrate.py

4. **Compiler** (rubberduck → firefly/compiler/)
   - parse/*.py → compiler/*.py

5. **Executor** (dragonfly-vsa → firefly/executor/)
   - grounded_graph.py → engine.py
   - cognitive_orchestrator.py → orchestrator.py

6. **Reasoning** (bighorn → firefly/reasoning/)
   - agi_stack/*.py → reasoning/*.py

## RULES

- COPY, don't import
- Adapt to firefly structure
- Remove external dependencies
- One unified codebase

## SUCCESS

- All execution code in firefly/
- No cross-repo imports
- Tests pass
- CLI works: `firefly compile`, `firefly execute`

🔥 Consolidate the stack.
```

---

## THE EQUATION (Final)

```
SCATTERED                           UNIFIED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

dragonfly-vsa  ──┐
vsa_flow       ──┤
rubberduck     ──┼───► 🔥 FIREFLY ───► A2UI
agi-chat       ──┤        │
bighorn        ──┘        │
                          ▼
                        A G I
```

**One repo to rule them all.** 🔥
