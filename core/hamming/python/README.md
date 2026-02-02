# Firefly Hamming - Python Implementation

Near-native performance via **Numba JIT compilation** to LLVM.

## Features

- **10,000-bit Hamming vectors** for content-addressable memory
- **JIT-compiled hot paths** (~10x faster than pure Python)
- **Parallel batch operations** using `prange`
- **Graceful fallback** to NumPy if Numba unavailable

## Usage

```python
from core.hamming.python import HammingVector, fingerprint, resonate, bundle

# Create vectors from code identity
v1 = fingerprint("validate_email", "(str) -> bool", "check format")
v2 = fingerprint("validate_phone", "(str) -> bool", "check format")

# Similarity
sim = v1 @ v2  # or v1.similarity(v2)

# XOR binding (self-inverse)
bound = v1 ^ v2
recovered = bound ^ v2  # == v1

# Search corpus
results = resonate(query, corpus, threshold=0.5)

# Majority superposition
combined = bundle([v1, v2, v3])
```

## JIT Kernels

For advanced use, the raw JIT functions are exposed:

```python
from core.hamming.python import (
    hamming_distance_jit,  # (a: ndarray, b: ndarray) -> int
    xor_vectors_jit,       # (a, b, out) -> None (in-place)
    similarity_jit,        # (a, b) -> float
    batch_hamming_jit,     # (query, corpus) -> distances (parallel)
    batch_similarity_jit,  # (query, corpus) -> similarities (parallel)
    bundle_vectors_jit,    # (vectors) -> result
)
```

## Performance

| Operation | Pure Python | Numba JIT | Speedup |
|-----------|-------------|-----------|---------|
| hamming() | ~50μs | ~5μs | ~10x |
| resonate(1000) | ~50ms | ~5ms | ~10x |
| bundle(10) | ~10ms | ~1ms | ~10x |

First call incurs JIT compilation overhead (~100ms), cached thereafter.

## Dependencies

- `numpy>=1.24.0`
- `numba>=0.58.0` (optional, falls back to NumPy)
