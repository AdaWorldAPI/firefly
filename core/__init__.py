"""
Firefly Core: 10K Hamming Resonance Engine

47 lines. Infinite capacity. 2^10000 state space.
"""

import numpy as np
from typing import List

DIM = 10000      # bits
PACKED = 1250    # bytes (DIM / 8)

# Deterministic projection matrix (seed=42 for reproducibility)
_R = None

def projection_matrix() -> np.ndarray:
    """Lazy-load projection matrix: 1024 → 10K."""
    global _R
    if _R is None:
        np.random.seed(42)
        _R = np.random.randn(DIM, 1024).astype(np.float32) / 32
    return _R


def project(jina_embedding: np.ndarray) -> bytes:
    """
    Project 1024D Jina embedding → 10K bits (1.25KB).
    
    This is the compression step that enables Hamming search.
    """
    projected = projection_matrix() @ jina_embedding
    bits = (projected > 0).astype(np.uint8)
    return np.packbits(bits).tobytes()


def hamming(a: bytes, b: bytes) -> int:
    """
    Hamming distance between two resonance vectors.
    
    XOR + popcount. O(1) with SIMD.
    """
    xa = np.frombuffer(a, dtype=np.uint8)
    xb = np.frombuffer(b, dtype=np.uint8)
    return int(np.unpackbits(np.bitwise_xor(xa, xb)).sum())


def similarity(a: bytes, b: bytes) -> float:
    """Similarity as 1 - normalized Hamming distance."""
    return 1.0 - hamming(a, b) / DIM


def bind(a: bytes, b: bytes) -> bytes:
    """
    XOR binding — self-inverse.
    
    bind(bind(a, b), b) == a (approximately, due to noise)
    """
    return bytes(x ^ y for x, y in zip(a, b))


def bundle(vecs: List[bytes]) -> bytes:
    """
    Majority vote superposition.
    
    Combines multiple vectors into one that resonates with all of them.
    """
    unpacked = [np.unpackbits(np.frombuffer(v, dtype=np.uint8)) for v in vecs]
    stacked = np.stack(unpacked)
    majority = (stacked.sum(axis=0) > len(vecs) / 2).astype(np.uint8)
    return np.packbits(majority[:DIM]).tobytes()


def random_vector() -> bytes:
    """Generate a random resonance vector."""
    return np.packbits(np.random.randint(0, 2, DIM, dtype=np.uint8)).tobytes()


def role_vector(name: str) -> bytes:
    """
    Deterministic role vector from name.
    
    Used for binding I-Thou-It components.
    """
    import hashlib
    h = hashlib.sha256(name.encode()).digest()
    # Tile hash to fill 1250 bytes
    repeated = (h * 40)[:PACKED]
    return repeated


# Pre-computed role vectors for node components
ROLE_SCHEMA = role_vector("FIREFLY:NODE:SCHEMA:WHAT")
ROLE_LOGIC = role_vector("FIREFLY:NODE:LOGIC:HOW")
ROLE_CONTEXT = role_vector("FIREFLY:NODE:CONTEXT:WHERE")

# Pre-computed role vectors for gestalt components
ROLE_I = role_vector("FIREFLY:GESTALT:I:SELF")
ROLE_THOU = role_vector("FIREFLY:GESTALT:THOU:OTHER")
ROLE_IT = role_vector("FIREFLY:GESTALT:IT:WORLD")
