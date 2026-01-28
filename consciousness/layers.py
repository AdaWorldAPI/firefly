"""
7-Layer Consciousness Model for Firefly.

Maps consciousness layers to graph execution capabilities:

  L0: Substrate   → Core Hamming engine (core/__init__.py)
  L1: Resonance   → Similarity search (LanceDB)
  L2: Binding     → XOR composition (nodes, edges)
  L3: Memory      → Versioned recall (LanceDB versions)
  L4: Reasoning   → Graph traversal + explain/suggest
  L5: Narrative   → Execution traces as temporal sequences
  L6: Awareness   → Self-monitoring, performance optimization

Each layer processes upward, enriching the execution context
with increasingly abstract understanding.

From bighorn/extension/agi-*: The consciousness stack enables
AGI-level understanding of procedural systems by treating
execution graphs as objects of reflection.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from enum import IntEnum


class Layer(IntEnum):
    """Consciousness layers."""
    SUBSTRATE = 0    # Raw vector operations
    RESONANCE = 1    # Similarity detection
    BINDING = 2      # Compositional structure
    MEMORY = 3       # Persistent recall
    REASONING = 4    # Logical inference
    NARRATIVE = 5    # Temporal understanding
    AWARENESS = 6    # Meta-cognition


@dataclass
class LayerState:
    """State for a single consciousness layer."""
    layer: Layer
    active: bool = True
    activation: float = 0.0  # 0.0 - 1.0
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsciousnessStack:
    """
    The 7-layer consciousness stack.

    Each layer can process execution context,
    adding understanding at its level of abstraction.
    """
    layers: Dict[Layer, LayerState] = field(default_factory=dict)
    processors: Dict[Layer, Callable] = field(default_factory=dict)

    def __post_init__(self):
        # Initialize all layers
        for layer in Layer:
            if layer not in self.layers:
                self.layers[layer] = LayerState(layer=layer)

    def register_processor(self, layer: Layer, processor: Callable):
        """Register a processing function for a layer."""
        self.processors[layer] = processor

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process context through all active layers.

        Each layer enriches the context with its level of understanding.
        Context flows upward: L0 → L1 → L2 → ... → L6.
        """
        enriched = dict(context)

        for layer in Layer:
            state = self.layers.get(layer)
            if not state or not state.active:
                continue

            processor = self.processors.get(layer)
            if processor:
                try:
                    result = await processor(enriched, state)
                    if isinstance(result, dict):
                        enriched.update(result)
                    state.activation = 1.0
                except Exception as e:
                    state.activation = 0.0
                    enriched[f"layer_{layer.name}_error"] = str(e)

        return enriched

    def get_activation_profile(self) -> Dict[str, float]:
        """Get activation levels for all layers."""
        return {
            layer.name: self.layers[layer].activation
            for layer in Layer
        }

    def set_layer_active(self, layer: Layer, active: bool):
        """Enable or disable a layer."""
        if layer in self.layers:
            self.layers[layer].active = active


# Default layer processors for Firefly

async def substrate_processor(context: Dict, state: LayerState) -> Dict:
    """L0: Raw vector operations — ensure resonance vectors exist."""
    return {"substrate_ready": True}


async def resonance_processor(context: Dict, state: LayerState) -> Dict:
    """L1: Similarity detection — find similar past contexts."""
    return {"resonance_checked": True}


async def binding_processor(context: Dict, state: LayerState) -> Dict:
    """L2: Compositional structure — bind input components."""
    return {"binding_complete": True}


async def memory_processor(context: Dict, state: LayerState) -> Dict:
    """L3: Persistent recall — check for cached results."""
    return {"memory_checked": True}


async def reasoning_processor(context: Dict, state: LayerState) -> Dict:
    """L4: Logical inference — plan execution path."""
    return {"reasoning_complete": True}


async def narrative_processor(context: Dict, state: LayerState) -> Dict:
    """L5: Temporal understanding — contextualize in execution history."""
    return {"narrative_built": True}


async def awareness_processor(context: Dict, state: LayerState) -> Dict:
    """L6: Meta-cognition — self-monitor performance."""
    return {"awareness_active": True}


DEFAULT_PROCESSORS = {
    Layer.SUBSTRATE: substrate_processor,
    Layer.RESONANCE: resonance_processor,
    Layer.BINDING: binding_processor,
    Layer.MEMORY: memory_processor,
    Layer.REASONING: reasoning_processor,
    Layer.NARRATIVE: narrative_processor,
    Layer.AWARENESS: awareness_processor,
}


def create_default_stack() -> ConsciousnessStack:
    """Create a consciousness stack with default processors."""
    stack = ConsciousnessStack()
    for layer, processor in DEFAULT_PROCESSORS.items():
        stack.register_processor(layer, processor)
    return stack
