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
_R_lock = None

def _get_lock():
    """Lazy-init threading lock."""
    global _R_lock
    if _R_lock is None:
        import threading
        _R_lock = threading.Lock()
    return _R_lock

def projection_matrix() -> np.ndarray:
    """Lazy-load projection matrix: 1024 → 10K.

    Thread-safe initialization using double-checked locking.
    Uses isolated RandomState to avoid polluting global RNG.
    """
    global _R
    if _R is None:
        with _get_lock():
            if _R is None:
                # Use isolated RandomState instead of seeding global
                rng = np.random.RandomState(42)
                _R = rng.randn(DIM, 1024).astype(np.float32) / 32
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

    Uses iterated hashing to produce independent bits across all 10K positions.
    Each 64-bit chunk is derived from a unique hash, avoiding correlation.
    """
    import hashlib
    import struct

    DIM_U64 = 157  # 10000 / 64, rounded up
    data = bytearray(DIM_U64 * 8)

    for i in range(DIM_U64):
        # Each chunk gets a unique hash
        h = hashlib.sha256(f"{name}:{i}".encode()).digest()
        # Take first 8 bytes as uint64
        data[i*8:(i+1)*8] = h[:8]

    # Mask the last uint64 to only have valid bits (lower 16)
    LAST_MASK = (1 << 16) - 1
    last_val = struct.unpack('<Q', data[-8:])[0]
    last_val &= LAST_MASK
    data[-8:] = struct.pack('<Q', last_val)

    return bytes(data[:PACKED])


# Pre-computed role vectors for node components
ROLE_SCHEMA = role_vector("FIREFLY:NODE:SCHEMA:WHAT")
ROLE_LOGIC = role_vector("FIREFLY:NODE:LOGIC:HOW")
ROLE_CONTEXT = role_vector("FIREFLY:NODE:CONTEXT:WHERE")

# Pre-computed role vectors for gestalt components
ROLE_I = role_vector("FIREFLY:GESTALT:I:SELF")
ROLE_THOU = role_vector("FIREFLY:GESTALT:THOU:OTHER")
ROLE_IT = role_vector("FIREFLY:GESTALT:IT:WORLD")
