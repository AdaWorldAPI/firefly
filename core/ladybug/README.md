# LadybugDB

**Resonance = XOR + POPCOUNT** (deterministic CAM)

## Core Principle

```
query ⊗ atom = XOR(query, atom)
distance = POPCOUNT(query ⊗ atom)  
similarity = 1 - distance/10000

That's it. Pure content-addressable memory.
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      LADYBUGDB                              │
├─────────────────────────────────────────────────────────────┤
│  AVX512Engine    ← L1/L2 cache (hot SIMD: 50M/sec)         │
│  DragonQueue     ← CPU pipelines (parallel execution)       │
│  LanceStore      ← Working memory (vector storage)          │
│  DuckGraph       ← Deterministic paths (no hallucination)   │
└─────────────────────────────────────────────────────────────┘
```

## Usage

```python
from core.ladybug import LadybugDB

db = LadybugDB()

# Register functions → deterministic fingerprints
db.register(validate_email)
db.register(create_user, deps=["validate_email"])

# Execute
result = db.execute("validate_email", "test@example.com")

# Resonate (XOR + POPCOUNT)
similar = db.resonate("validate_email", threshold=0.6)
```

## Fingerprint

10K-bit deterministic hash via SHA256 chain:

```python
identity = f"{name}::{signature}::{body}"
for i in range(157):
    h = sha256(f"{identity}:{i}")
    fingerprint[i] = h[:8]  # 64 bits
```

**Same code = same fingerprint (ALWAYS)**

## Orthogonal Cleaning (Separate)

Only used after bundling many vectors:

```python
dirty = bind(a, b, c, d, e, ...)  # Accumulated noise
cleaned = project_onto_basis(dirty)  # Optional cleanup
```

This is NOT resonance. Resonance is pure XOR + POPCOUNT.

## Performance

| Operation | Time | Throughput |
|-----------|------|------------|
| Single Hamming | 267 ns | 3.75M/sec |
| Batch 10K | 20 ns/vec | 50M/sec |
| 20K atoms | 0.4 ms | 1250x faster than Ruby |
