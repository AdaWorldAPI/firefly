"""LadybugDB Hamming Operations - Python"""

import numpy as np
from typing import List, Tuple
import hashlib
import struct

DIM = 10_000
DIM_U64 = 157
LAST_MASK = np.uint64((1 << 16) - 1)


class HammingVector:
    """10K-bit vector for content-addressable memory."""
    
    __slots__ = ['data']
    
    def __init__(self, data: np.ndarray = None):
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
    
    def xor(self, other: 'HammingVector') -> 'HammingVector':
        """XOR bind."""
        result = np.bitwise_xor(self.data, other.data)
        result[-1] &= LAST_MASK
        return HammingVector(result)
    
    def hamming(self, other: 'HammingVector') -> int:
        """Hamming distance via XOR + POPCOUNT."""
        xored = np.bitwise_xor(self.data, other.data)
        total = 0
        for x in xored:
            total += bin(x).count('1')
        return total
    
    def similarity(self, other: 'HammingVector') -> float:
        """Normalized similarity [0, 1]."""
        return 1.0 - self.hamming(other) / DIM
    
    def __xor__(self, other):
        return self.xor(other)
    
    def __matmul__(self, other):
        return self.similarity(other)
    
    def to_hex(self) -> str:
        return self.data.tobytes().hex()
    
    @classmethod
    def from_hex(cls, h: str) -> 'HammingVector':
        return cls(np.frombuffer(bytes.fromhex(h), dtype=np.uint64).copy())


def fingerprint(name: str, signature: str, body: str) -> HammingVector:
    """Deterministic fingerprint from code identity."""
    return HammingVector.from_seed(f"{name}::{signature}::{body}")


def resonate(query: HammingVector, corpus: List[HammingVector], threshold: float = 0.5) -> List[Tuple[int, float]]:
    """Find all vectors resonating above threshold."""
    results = []
    for i, vec in enumerate(corpus):
        sim = query @ vec
        if sim >= threshold:
            results.append((i, sim))
    results.sort(key=lambda x: x[1], reverse=True)
    return results