"""10K Hamming Operations - Python Reference."""
import numpy as np
from typing import List, Tuple

DIM = 10_000
DIM_U64 = 157  # (10000 + 63) // 64
LAST_MASK = (1 << 16) - 1

def popcount64(x: int) -> int:
    """Count set bits in 64-bit integer."""
    x = x - ((x >> 1) & 0x5555555555555555)
    x = (x & 0x3333333333333333) + ((x >> 2) & 0x3333333333333333)
    x = (x + (x >> 4)) & 0x0F0F0F0F0F0F0F0F
    return ((x * 0x0101010101010101) >> 56) & 0xFF

def hamming(a: List[int], b: List[int]) -> int:
    """Hamming distance between two 10K vectors."""
    total = 0
    for i in range(DIM_U64):
        total += popcount64(a[i] ^ b[i])
    return total

def similarity(a: List[int], b: List[int]) -> float:
    """Similarity [0, 1] from Hamming distance."""
    return 1.0 - hamming(a, b) / DIM

def xor_bind(a: List[int], b: List[int]) -> List[int]:
    """XOR bind two vectors."""
    result = [a[i] ^ b[i] for i in range(DIM_U64)]
    result[-1] &= LAST_MASK
    return result

def batch_hamming(query: List[int], corpus: List[List[int]]) -> List[int]:
    """Batch Hamming distances."""
    return [hamming(query, vec) for vec in corpus]

def resonate(query: List[int], corpus: List[List[int]], threshold: float = 0.5) -> List[Tuple[int, float]]:
    """Find vectors above similarity threshold."""
    results = []
    for i, vec in enumerate(corpus):
        sim = similarity(query, vec)
        if sim >= threshold:
            results.append((i, sim))
    results.sort(key=lambda x: x[1], reverse=True)
    return results