"""
LadybugDB Hamming Operations - Python with Numba JIT

Near-native performance via LLVM compilation. Falls back to NumPy if Numba unavailable.

Hot paths compiled to machine code:
- hamming_distance_jit: XOR + POPCOUNT (~10x faster than pure Python)
- xor_vectors_jit: XOR binding
- bundle_vectors_jit: Majority superposition
- resonate_jit: Batch similarity search
"""

import numpy as np
from typing import List, Tuple, Optional
import hashlib
import struct

# =============================================================================
# CONSTANTS
# =============================================================================

DIM = 10_000
DIM_U64 = 157
PACKED = 1250
LAST_MASK = np.uint64((1 << 16) - 1)

# =============================================================================
# NUMBA JIT KERNELS (compiled to LLVM IR -> machine code)
# =============================================================================

try:
    from numba import njit, prange, uint64, int64, float64, boolean
    from numba.typed import List as TypedList
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    # Fallback decorators that do nothing
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args or not callable(args[0]) else args[0]
    prange = range


# Popcount lookup table (computed once at module load)
_POPCOUNT_TABLE = np.array([bin(i).count('1') for i in range(256)], dtype=np.uint8)


@njit(cache=True, fastmath=True)
def _popcount_u64(x: uint64) -> int64:
    """Popcount for a single u64 using bit manipulation.

    This compiles to POPCNT instruction on supported CPUs.
    """
    # Kernighan's algorithm optimized for LLVM
    x = x - ((x >> 1) & np.uint64(0x5555555555555555))
    x = (x & np.uint64(0x3333333333333333)) + ((x >> 2) & np.uint64(0x3333333333333333))
    x = (x + (x >> 4)) & np.uint64(0x0F0F0F0F0F0F0F0F)
    return int64((x * np.uint64(0x0101010101010101)) >> 56)


@njit(cache=True, fastmath=True, parallel=False)
def hamming_distance_jit(a: np.ndarray, b: np.ndarray) -> int64:
    """
    Hamming distance between two 10K-bit vectors.

    JIT-compiled to native code. ~10x faster than pure Python.
    Properly masks the last u64 to exclude garbage bits.
    """
    total = int64(0)

    # Process all but the last u64
    for i in range(DIM_U64 - 1):
        xored = a[i] ^ b[i]
        total += _popcount_u64(xored)

    # Last u64: mask to only count valid 16 bits
    last_xor = (a[DIM_U64 - 1] ^ b[DIM_U64 - 1]) & LAST_MASK
    total += _popcount_u64(last_xor)

    return total


@njit(cache=True, fastmath=True)
def xor_vectors_jit(a: np.ndarray, b: np.ndarray, out: np.ndarray) -> None:
    """
    XOR two vectors in-place into `out`.

    JIT-compiled for zero-copy performance.
    """
    for i in range(DIM_U64 - 1):
        out[i] = a[i] ^ b[i]
    out[DIM_U64 - 1] = (a[DIM_U64 - 1] ^ b[DIM_U64 - 1]) & LAST_MASK


@njit(cache=True, fastmath=True)
def similarity_jit(a: np.ndarray, b: np.ndarray) -> float64:
    """Normalized similarity [0, 1]."""
    dist = hamming_distance_jit(a, b)
    return 1.0 - float64(dist) / float64(DIM)


@njit(cache=True, parallel=True)
def batch_hamming_jit(query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """
    Compute Hamming distance from query to all corpus vectors.

    Parallelized across corpus using prange.

    Args:
        query: (DIM_U64,) uint64 array
        corpus: (N, DIM_U64) uint64 array

    Returns:
        (N,) int64 array of distances
    """
    n = corpus.shape[0]
    distances = np.empty(n, dtype=np.int64)

    for i in prange(n):
        distances[i] = hamming_distance_jit(query, corpus[i])

    return distances


@njit(cache=True, parallel=True)
def batch_similarity_jit(query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """
    Compute similarity from query to all corpus vectors.

    Parallelized across corpus.
    """
    n = corpus.shape[0]
    similarities = np.empty(n, dtype=np.float64)

    for i in prange(n):
        similarities[i] = similarity_jit(query, corpus[i])

    return similarities


@njit(cache=True)
def bundle_vectors_jit(vectors: np.ndarray) -> np.ndarray:
    """
    Majority vote superposition of multiple vectors.

    Args:
        vectors: (N, DIM_U64) uint64 array

    Returns:
        (DIM_U64,) uint64 array
    """
    n = vectors.shape[0]
    threshold = n // 2
    result = np.zeros(DIM_U64, dtype=np.uint64)

    # For each bit position
    for bit_pos in range(DIM):
        u64_idx = bit_pos // 64
        bit_idx = bit_pos % 64

        # Count how many vectors have this bit set
        count = int64(0)
        for v in range(n):
            if (vectors[v, u64_idx] >> bit_idx) & 1:
                count += 1

        # Set bit if majority
        if count > threshold:
            result[u64_idx] |= np.uint64(1) << bit_idx

    # Mask last element
    result[DIM_U64 - 1] &= LAST_MASK
    return result


# =============================================================================
# PYTHON CLASS WRAPPER
# =============================================================================

class HammingVector:
    """
    10K-bit vector for content-addressable memory.

    Delegates hot operations to JIT-compiled kernels for near-native performance.
    """

    __slots__ = ['data']

    def __init__(self, data: Optional[np.ndarray] = None):
        if data is None:
            self.data = np.zeros(DIM_U64, dtype=np.uint64)
        else:
            self.data = np.ascontiguousarray(data, dtype=np.uint64)

    @classmethod
    def from_seed(cls, seed: str) -> 'HammingVector':
        """Deterministic fingerprint from string seed."""
        data = np.empty(DIM_U64, dtype=np.uint64)
        for i in range(DIM_U64):
            h = hashlib.sha256(f"{seed}:{i}".encode()).digest()
            data[i] = struct.unpack('<Q', h[:8])[0]
        data[-1] &= LAST_MASK
        return cls(data)

    @classmethod
    def random(cls, seed: int = None) -> 'HammingVector':
        """Random vector (for testing)."""
        rng = np.random.RandomState(seed)
        data = rng.randint(0, 2**63, DIM_U64, dtype=np.uint64)
        data[-1] &= LAST_MASK
        return cls(data)

    def xor(self, other: 'HammingVector') -> 'HammingVector':
        """XOR binding (JIT-accelerated)."""
        result = np.empty(DIM_U64, dtype=np.uint64)
        xor_vectors_jit(self.data, other.data, result)
        return HammingVector(result)

    def hamming(self, other: 'HammingVector') -> int:
        """Hamming distance (JIT-accelerated)."""
        return int(hamming_distance_jit(self.data, other.data))

    def similarity(self, other: 'HammingVector') -> float:
        """Normalized similarity [0, 1] (JIT-accelerated)."""
        return float(similarity_jit(self.data, other.data))

    def popcount(self) -> int:
        """Number of set bits."""
        zero = np.zeros(DIM_U64, dtype=np.uint64)
        return int(hamming_distance_jit(self.data, zero))

    def __xor__(self, other: 'HammingVector') -> 'HammingVector':
        return self.xor(other)

    def __matmul__(self, other: 'HammingVector') -> float:
        """v1 @ v2 = similarity(v1, v2)"""
        return self.similarity(other)

    def __eq__(self, other: 'HammingVector') -> bool:
        return np.array_equal(self.data, other.data)

    def __hash__(self) -> int:
        return hash(self.data.tobytes())

    def __repr__(self) -> str:
        return f"HammingVector({self.to_hex()[:16]}...)"

    def to_hex(self) -> str:
        """Convert to hex string (2500 chars)."""
        return self.data.tobytes()[:PACKED].hex()

    @classmethod
    def from_hex(cls, h: str) -> 'HammingVector':
        """Parse from hex string."""
        if len(h) != PACKED * 2:
            raise ValueError(f"Expected {PACKED * 2} hex chars, got {len(h)}")
        data = np.frombuffer(bytes.fromhex(h), dtype=np.uint64).copy()
        if len(data) < DIM_U64:
            # Pad if needed
            padded = np.zeros(DIM_U64, dtype=np.uint64)
            padded[:len(data)] = data
            data = padded
        data[-1] &= LAST_MASK
        return cls(data)

    def to_bytes(self) -> bytes:
        """Convert to raw bytes."""
        return self.data.tobytes()[:PACKED]

    @classmethod
    def from_bytes(cls, b: bytes) -> 'HammingVector':
        """Parse from raw bytes."""
        if len(b) != PACKED:
            raise ValueError(f"Expected {PACKED} bytes, got {len(b)}")
        # Pad to full u64 array size
        padded = b + b'\x00' * (DIM_U64 * 8 - len(b))
        data = np.frombuffer(padded, dtype=np.uint64).copy()
        data[-1] &= LAST_MASK
        return cls(data)


# =============================================================================
# HIGH-LEVEL FUNCTIONS
# =============================================================================

def fingerprint(name: str, signature: str, body: str) -> HammingVector:
    """Deterministic fingerprint from code identity."""
    return HammingVector.from_seed(f"{name}::{signature}::{body}")


def resonate(
    query: HammingVector,
    corpus: List[HammingVector],
    threshold: float = 0.5
) -> List[Tuple[int, float]]:
    """
    Find all vectors resonating above threshold (JIT-accelerated).

    Uses batch similarity computation for large corpora.
    """
    if not corpus:
        return []

    # Stack corpus into 2D array for batch processing
    corpus_data = np.stack([v.data for v in corpus])

    # Batch compute similarities (parallelized)
    similarities = batch_similarity_jit(query.data, corpus_data)

    # Filter and sort
    results = [
        (i, float(sim))
        for i, sim in enumerate(similarities)
        if sim >= threshold
    ]
    results.sort(key=lambda x: x[1], reverse=True)

    return results


def bundle(vectors: List[HammingVector]) -> HammingVector:
    """
    Majority vote superposition (JIT-accelerated).

    Creates a vector that resonates with all inputs.
    """
    if not vectors:
        raise ValueError("Cannot bundle empty list")

    if len(vectors) == 1:
        return HammingVector(vectors[0].data.copy())

    # Stack into 2D array
    stacked = np.stack([v.data for v in vectors])

    # JIT-compiled majority vote
    result = bundle_vectors_jit(stacked)

    return HammingVector(result)


# =============================================================================
# MODULE INFO
# =============================================================================

def info() -> dict:
    """Return module configuration info."""
    return {
        "dim": DIM,
        "dim_u64": DIM_U64,
        "packed_bytes": PACKED,
        "numba_available": HAS_NUMBA,
        "numba_version": None,
    }


# Warm up JIT on first import (compiles lazily)
if HAS_NUMBA:
    try:
        # Force compilation by calling with dummy data
        _dummy_a = np.zeros(DIM_U64, dtype=np.uint64)
        _dummy_b = np.zeros(DIM_U64, dtype=np.uint64)
        _ = hamming_distance_jit(_dummy_a, _dummy_b)
        xor_vectors_jit(_dummy_a, _dummy_b, _dummy_a.copy())
        del _dummy_a, _dummy_b
    except Exception:
        pass  # JIT warmup is optional
