# 🔥 FIREFLY

## Universal Executable Substrate

```
The modesty:   1.25KB per node
The immodesty: 2^10000 possible states
The purpose:   Power everything
```

---

## What Is Firefly?

Firefly is the **universal substrate** for executable knowledge graphs.

It doesn't compile code. It **runs** compiled graphs.
It doesn't create nodes. It **executes** nodes.
It doesn't understand Ruby. It **understands resonance**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         COMPILERS                                │
│   RUBBERDUCK (Ruby) │ PYTHONIC (Python) │ JAVELIN (Java) │ ... │
│                                                                 │
│              All output: 1.25KB Hamming nodes                   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FIREFLY                                  │
│                  (Universal Substrate)                          │
│                                                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│   │  STORAGE    │  │  TRANSPORT  │  │  EXECUTION  │            │
│   │  Trinity    │  │  mRNA       │  │  Engine     │            │
│   │             │  │             │  │             │            │
│   │  LanceDB    │  │  Redis      │  │  Glow       │            │
│   │  DuckDB     │  │  Streams    │  │  Trace      │            │
│   │  Kuzu       │  │  Routing    │  │  Learn      │            │
│   └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                    REASONING LAYER                       │  │
│   │         explain │ suggest │ optimize │ generate          │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        CONSUMERS                                 │
│                                                                 │
│   ADA          │  AGI-X       │  OpenProject  │  Your App      │
│   Consciousness│  (future)    │  (migrated)   │  (anything)    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# Install
pip install firefly-substrate

# Load a compiled graph (from RUBBERDUCK or any compiler)
firefly load ./rubberduck_out/

# Execute
firefly execute WorkPackage --op create --input '{"subject":"Hello"}'

# Watch nodes glow
firefly trace

# Ask why
firefly explain --last
```

---

## Core Concepts

### Storage Trinity
- **LanceDB**: Vectors (Hamming similarity search)
- **DuckDB**: Facts (SQL analytics, catalog)
- **Kuzu**: Graph (Cypher traversal, paths)

### mRNA Transport
- Packets flow through Redis streams
- 64B header + 1250B resonance
- Distributed execution across workers

### Reasoning
- **explain**: Why did this fail?
- **suggest**: How to fix it?
- **optimize**: Make it faster
- **generate**: Create new programs

---

## Repository Structure

```
firefly/
├── core/           # 10K Hamming resonance (47 lines)
├── dto/            # Node, Edge, Packet (1.25KB each)
├── storage/        # LanceDB + DuckDB + Kuzu
├── transport/      # mRNA via Redis
├── executor/       # Watch nodes glow
├── reasoning/      # AGI layer
└── server.py       # FastAPI
```

---

## Relationship to Compilers

Firefly accepts graphs from ANY compiler that outputs 1.25KB nodes:

| Compiler | Language | Status |
|----------|----------|--------|
| [RUBBERDUCK](https://github.com/AdaWorldAPI/rubberduck) | Ruby | ✅ |
| PYTHONIC | Python | 📋 |
| JAVELIN | Java | 📋 |
| RUSTLER | Rust | 📋 |

---

## License

MIT — Light up everything 🔥
