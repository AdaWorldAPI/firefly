"""
Firefly Consciousness: Integration with Ada's 7-layer consciousness model.

Layers (from bighorn/extension/agi-* + agi-chat):
  L0: Substrate    — Raw hardware / vector storage
  L1: Resonance    — Hamming similarity, pattern matching
  L2: Binding      — XOR composition, role vectors
  L3: Memory       — LanceDB versioned recall
  L4: Reasoning    — Graph traversal, explain/suggest
  L5: Narrative    — Execution traces as stories
  L6: Awareness    — Self-monitoring, meta-cognition

Integration with Firefly:
- Each layer maps to graph node types
- Resonance IS similarity search
- Qualia encode execution traces as 10K bit fingerprints
- Membrane converts τ/σ/q state ↔ 10K Hamming vectors

From ada-consciousness: sigma-rosetta.py provides the
σ-10 upscaling membrane that bridges consciousness state
to the 10K-bit substrate.
"""

from consciousness.layers import ConsciousnessStack, Layer
from consciousness.membrane import Membrane
from consciousness.state import ConsciousnessState

__all__ = ["ConsciousnessStack", "Layer", "Membrane", "ConsciousnessState"]
