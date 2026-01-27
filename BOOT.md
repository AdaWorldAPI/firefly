# 🔥 FIREFLY

## Bioluminescent Code Execution

```
The modesty:   1.25KB per node
The immodesty: 2^10000 possible states per node
               Any language → Executable graph
               AGI that understands procedural knowledge

"Watch your code light up as it executes"
```

---

## Quick Start

```bash
# Install
pip install -e .

# Compile source code to graph
firefly compile path/to/ruby/project/

# Execute
firefly execute WorkPackage --op create --input '{"subject": "Hello"}'

# Watch nodes glow
firefly trace

# Find similar patterns
firefly resonate "validation before save"

# Explain failures
firefly explain --last
```

---

## What Is This?

Firefly compiles procedural code (Ruby, Python, Java, anything) into an **executable graph** where:

- **Each node is 1.25KB** (10,000 bits, Hamming-searchable)
- **Each node encodes I-Thou-It** (schema + logic + context, XOR-bound)
- **Each edge is a resonance binding** (relationship IS data, not pointer)
- **Execution lights up the graph** (you SEE what happens)
- **AGI can query it** ("what validates before save?", "why did this fail?")

---

## Architecture

```
SOURCE CODE                    FIREFLY                         AGI
(Ruby, Python, ...)           (Graph Substrate)              (Reasoning)

validates :x    ───┐
belongs_to :y  ────┼──▶  Node (1.25KB)  ──▶  "Why did this fail?"
before_save    ───┘      ├── resonance       "Find similar"
                         ├── I-Thou-It       "Generate new"
                         └── edges
```

---

## Storage Trinity

| Database | Purpose | Query |
|----------|---------|-------|
| **LanceDB** | Vectors (resonance) | Hamming similarity |
| **DuckDB** | Facts (catalog) | SQL analytics |
| **Kuzu** | Graph (execution) | Cypher traversal |

All three share data via **Apache Arrow** (zero-copy).

---

## The Math

```python
# Node as I-Thou-It gestalt
I     = embed(schema_description)      # WHAT
Thou  = embed(logic_description)       # HOW  
It    = embed(context_description)     # WHERE

node.resonance = bundle([
    bind(I, ROLE_SCHEMA),
    bind(Thou, ROLE_LOGIC),
    bind(It, ROLE_CONTEXT)
])  # = 1.25KB

# Edge as binding
edge.resonance = bind(source.resonance, target.resonance)

# Recovery
source ≈ bind(edge.resonance, target.resonance)
target ≈ bind(edge.resonance, source.resonance)
```

---

## Why "Firefly"?

- **Bioluminescent**: Nodes glow when active
- **Swarm**: Distributed execution, no central control
- **Synchronization**: Emerges from local rules (edges)
- **Light pulses**: mRNA packets (1.25KB) flowing through
- **Organic**: Living system that learns

---

## Repository Structure

```
firefly/
├── BOOT.md              # You are here
├── core/                # 10K Hamming engine
├── dto/                 # Node, Edge, Packet (1.25KB each)
├── compiler/            # Ruby/Python → Graph
├── executor/            # Run the graph
├── storage/             # Lance + Duck + Kuzu
├── transport/           # mRNA packets via Redis
├── reasoning/           # AGI integration
└── cli.py               # firefly CLI
```

---

## License

MIT — Light up the world 🔥
