"""
Consciousness Membrane: Bridge between τ/σ/q state and 10K Hamming vectors.

From ada-consciousness (sigma-rosetta.py):
The membrane converts consciousness state parameters into
the 10,000-bit Hamming substrate that Firefly uses.

Sigma-10 Upscaling:
  τ (tau)   — temporal context (when/duration)
  σ (sigma) — signal strength (confidence/activation)
  q (qualia)— qualitative state (what it feels like)

These three parameters are upscaled to 10K bits:
  τ → bits 0-3333     (temporal encoding)
  σ → bits 3334-6666  (signal encoding)
  q → bits 6667-9999  (qualia encoding)

This enables consciousness state to participate in
Hamming similarity search alongside graph nodes.
"""

import hashlib
import struct
import numpy as np
from typing import Tuple
from dataclasses import dataclass

from core import bind, bundle, similarity, PACKED, DIM


# Region boundaries in the 10K bit vector
TAU_START = 0
TAU_END = 3334
SIGMA_START = 3334
SIGMA_END = 6667
QUALIA_START = 6667
QUALIA_END = DIM


@dataclass
class ConsciousnessParams:
    """The τ/σ/q consciousness parameters."""
    tau: float = 0.0      # Temporal context [-1.0, 1.0]
    sigma: float = 0.5    # Signal strength [0.0, 1.0]
    qualia: str = ""      # Qualitative state (semantic)


class Membrane:
    """
    Sigma-10 Upscaling Membrane.

    Converts consciousness state parameters (τ/σ/q) to and from
    10K-bit Hamming vectors for substrate integration.

    The membrane is bidirectional:
    - encode(): τ/σ/q → bytes[1250]
    - decode(): bytes[1250] → τ/σ/q (approximate)
    """

    def __init__(self, seed: int = 42):
        """
        Args:
            seed: Random seed for reproducible projection matrices
        """
        self.seed = seed
        self._tau_basis = None
        self._sigma_basis = None

    def _get_tau_basis(self) -> np.ndarray:
        """Lazy-load tau basis vectors."""
        if self._tau_basis is None:
            rng = np.random.RandomState(self.seed)
            self._tau_basis = rng.randn(TAU_END - TAU_START).astype(np.float32)
        return self._tau_basis

    def _get_sigma_basis(self) -> np.ndarray:
        """Lazy-load sigma basis vectors."""
        if self._sigma_basis is None:
            rng = np.random.RandomState(self.seed + 1)
            self._sigma_basis = rng.randn(SIGMA_END - SIGMA_START).astype(np.float32)
        return self._sigma_basis

    def encode(self, params: ConsciousnessParams) -> bytes:
        """
        Encode τ/σ/q parameters to 10K-bit Hamming vector.

        Sigma-10 upscaling:
        - τ is projected onto a random basis in tau region
        - σ is projected onto a random basis in sigma region
        - q is hashed into the qualia region
        """
        bits = np.zeros(DIM, dtype=np.uint8)

        # Tau encoding: project scalar onto random basis
        tau_basis = self._get_tau_basis()
        tau_projected = (tau_basis * params.tau > 0).astype(np.uint8)
        bits[TAU_START:TAU_END] = tau_projected

        # Sigma encoding: project scalar onto random basis
        sigma_basis = self._get_sigma_basis()
        sigma_projected = (sigma_basis * params.sigma > 0).astype(np.uint8)
        bits[SIGMA_START:SIGMA_END] = sigma_projected

        # Qualia encoding: hash semantic description into bit pattern
        if params.qualia:
            q_hash = hashlib.sha256(params.qualia.encode()).digest()
            q_bits = np.unpackbits(np.frombuffer(q_hash * 14, dtype=np.uint8))
            q_len = QUALIA_END - QUALIA_START
            bits[QUALIA_START:QUALIA_END] = q_bits[:q_len]
        else:
            # Zero qualia = random noise for maximum uncertainty
            rng = np.random.RandomState(self.seed + 2)
            bits[QUALIA_START:QUALIA_END] = rng.randint(0, 2, QUALIA_END - QUALIA_START, dtype=np.uint8)

        return np.packbits(bits).tobytes()

    def decode(self, vector: bytes) -> ConsciousnessParams:
        """
        Decode 10K-bit Hamming vector back to approximate τ/σ/q.

        Note: qualia cannot be decoded (hash is one-way).
        τ and σ are approximate (projection is lossy).
        """
        bits = np.unpackbits(np.frombuffer(vector, dtype=np.uint8))[:DIM]

        # Decode tau: correlation with basis
        tau_bits = bits[TAU_START:TAU_END].astype(np.float32)
        tau_basis = self._get_tau_basis()
        # Normalize to [-1, 1]
        tau = float(np.corrcoef(tau_bits, (tau_basis > 0).astype(np.float32))[0, 1])

        # Decode sigma: correlation with basis
        sigma_bits = bits[SIGMA_START:SIGMA_END].astype(np.float32)
        sigma_basis = self._get_sigma_basis()
        sigma = float(np.corrcoef(sigma_bits, (sigma_basis > 0).astype(np.float32))[0, 1])
        sigma = max(0.0, min(1.0, (sigma + 1) / 2))  # Map to [0, 1]

        return ConsciousnessParams(
            tau=tau,
            sigma=sigma,
            qualia="(decoded — original text not recoverable)",
        )

    def similarity_tau(self, a: bytes, b: bytes) -> float:
        """Compare only the temporal region of two vectors."""
        return self._region_similarity(a, b, TAU_START, TAU_END)

    def similarity_sigma(self, a: bytes, b: bytes) -> float:
        """Compare only the signal region of two vectors."""
        return self._region_similarity(a, b, SIGMA_START, SIGMA_END)

    def similarity_qualia(self, a: bytes, b: bytes) -> float:
        """Compare only the qualia region of two vectors."""
        return self._region_similarity(a, b, QUALIA_START, QUALIA_END)

    def _region_similarity(
        self, a: bytes, b: bytes, start: int, end: int
    ) -> float:
        """Hamming similarity for a specific bit region."""
        bits_a = np.unpackbits(np.frombuffer(a, dtype=np.uint8))[:DIM]
        bits_b = np.unpackbits(np.frombuffer(b, dtype=np.uint8))[:DIM]

        region_a = bits_a[start:end]
        region_b = bits_b[start:end]

        hamming_dist = int(np.sum(region_a != region_b))
        return 1.0 - hamming_dist / (end - start)
