"""
Firefly Hamming Operations - Python Implementation

Near-native performance via Numba JIT compilation to LLVM.
Falls back gracefully to NumPy if Numba is unavailable.

Usage:
    from core.hamming.python import HammingVector, fingerprint, resonate, bundle

    # Create vectors
    v1 = HammingVector.from_seed("function_a")
    v2 = HammingVector.from_seed("function_b")

    # Operations
    distance = v1.hamming(v2)
    similarity = v1.similarity(v2)  # or v1 @ v2
    bound = v1 ^ v2  # XOR binding

    # Search
    results = resonate(query, corpus, threshold=0.5)
"""

from .hamming import (
    # Constants
    DIM,
    DIM_U64,
    PACKED,
    LAST_MASK,
    HAS_NUMBA,

    # Core class
    HammingVector,

    # High-level functions
    fingerprint,
    resonate,
    bundle,
    info,

    # JIT kernels (for advanced use)
    hamming_distance_jit,
    xor_vectors_jit,
    similarity_jit,
    batch_hamming_jit,
    batch_similarity_jit,
    bundle_vectors_jit,
)

__all__ = [
    # Constants
    "DIM",
    "DIM_U64",
    "PACKED",
    "LAST_MASK",
    "HAS_NUMBA",

    # Core class
    "HammingVector",

    # High-level functions
    "fingerprint",
    "resonate",
    "bundle",
    "info",

    # JIT kernels
    "hamming_distance_jit",
    "xor_vectors_jit",
    "similarity_jit",
    "batch_hamming_jit",
    "batch_similarity_jit",
    "bundle_vectors_jit",
]
