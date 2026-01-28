# LadybugDB Architecture

## 8-Layer Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ L8: ANTIPATTERN BATTERY   - Test, trace, report WHERE weaknesses land      │
├─────────────────────────────────────────────────────────────────────────────┤
│ L7: META-HEURISTICS       - Quantifiers, topology, smell/intent detection  │
├─────────────────────────────────────────────────────────────────────────────┤
│ L6: NARS REASONING        - GOAL! BELIEF. QUESTION? temporal/hypothetical  │
├─────────────────────────────────────────────────────────────────────────────┤
│ L5: PARSE                 - AST → graph transformation                     │
│ L4: INHERITANCE           - INHERITS, OVERRIDES, DEPENDS edges             │
│ L3: CLASS                 - CLASS contains METHOD, CALLS edges             │
│ L2: CONTROL               - IF, FOREACH, WHILE, BRANCHES_TO                │
│ L1: ATOM                  - function → 10K-bit fingerprint                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ HAMMING SUBSTRATE         - XOR bind │ POPCOUNT │ 50M/sec AVX-512          │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Principle

**Fingerprint = Identity**

Every code element gets a deterministic 10,000-bit fingerprint:
- Same code → same fingerprint (always)
- Different code → ~50% Hamming distance (quasi-orthogonal)

## Key Files

| File | Purpose |
|------|---------|
| `simd.py` | AVX-512 SIMD kernels (50M comparisons/sec) |
| `graph.py` | Declarative layer (Numba jitclass nodes/edges) |
| `nars.py` | NARS reasoning primitives |
| `meta.py` | Meta-heuristics (quantifiers, topology) |
| `antipatterns.py` | Test battery with trace-to-root |
| `poc.py` | Incremental proof-of-concept (L1-L8) |

## Antipattern Detection

Each smell traced to WHERE it lands:

```python
SmellReport {
  smell_type: GOD_CLASS
  node: OrderManager           # WHERE
  confidence: 0.60             # HOW SURE
  evidence: ["15 methods"]     # WHY
  suggested_fix: "Extract..."  # WHAT TO DO
  root_cause: OrderManager     # ROOT
}
```

## Usage

```python
from ladybug import AntipatternDetector

d = AntipatternDetector()
# ... build graph ...
results = d.detect_all()

for smell_type, reports in results.items():
    for r in reports:
        print(f"{smell_type.name}: {r.node.name}")
        print(f"  Evidence: {r.evidence}")
        print(f"  Fix: {r.suggested_fix}")
```
