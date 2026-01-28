"""
Consciousness State: Cross-session state persistence.

Encodes the full consciousness state as a single 10K-bit vector
that can be stored, compared, and recalled.

The state captures:
- Which layers are active (activation profile)
- Current τ/σ/q parameters
- Execution history fingerprint
- Graph topology fingerprint

This enables "resuming consciousness" across sessions
by finding the most similar prior state.
"""

import hashlib
import numpy as np
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from core import bind, bundle, similarity, PACKED
from consciousness.layers import ConsciousnessStack, Layer
from consciousness.membrane import Membrane, ConsciousnessParams


@dataclass
class ConsciousnessState:
    """
    Full consciousness state encoded as 10K-bit resonance.

    Can be stored in LanceDB for similarity-based recall.
    """
    resonance: bytes  # 1250 bytes = 10K bits
    params: ConsciousnessParams = field(default_factory=ConsciousnessParams)
    activation_profile: Dict[str, float] = field(default_factory=dict)
    session_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_stack(
        cls,
        stack: ConsciousnessStack,
        params: ConsciousnessParams,
        session_id: str = "",
        execution_trace: List[str] = None,
    ) -> "ConsciousnessState":
        """
        Capture current consciousness state from a running stack.
        """
        membrane = Membrane()

        # Encode τ/σ/q as base vector
        base_vec = membrane.encode(params)

        # Encode activation profile
        profile = stack.get_activation_profile()
        profile_str = "|".join(f"{k}:{v:.2f}" for k, v in profile.items())
        profile_vec = (hashlib.sha256(profile_str.encode()).digest() * 40)[:PACKED]

        # Encode execution trace fingerprint
        if execution_trace:
            trace_str = "→".join(execution_trace[:20])
            trace_vec = (hashlib.sha256(trace_str.encode()).digest() * 40)[:PACKED]
        else:
            trace_vec = b'\x00' * PACKED

        # Bundle all components
        resonance = bundle([base_vec, profile_vec, trace_vec])

        return cls(
            resonance=resonance,
            params=params,
            activation_profile=profile,
            session_id=session_id,
            metadata={
                "trace_length": len(execution_trace) if execution_trace else 0,
            },
        )

    def similarity_to(self, other: "ConsciousnessState") -> float:
        """How similar is this state to another?"""
        return similarity(self.resonance, other.resonance)

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "resonance": self.resonance.hex(),
            "tau": self.params.tau,
            "sigma": self.params.sigma,
            "qualia": self.params.qualia,
            "activation_profile": self.activation_profile,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConsciousnessState":
        """Deserialize from storage."""
        return cls(
            resonance=bytes.fromhex(data["resonance"]),
            params=ConsciousnessParams(
                tau=data.get("tau", 0.0),
                sigma=data.get("sigma", 0.5),
                qualia=data.get("qualia", ""),
            ),
            activation_profile=data.get("activation_profile", {}),
            session_id=data.get("session_id", ""),
            metadata=data.get("metadata", {}),
        )
