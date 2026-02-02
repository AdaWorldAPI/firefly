"""
Vector Embedder: Generate semantic and structural vectors for graph nodes.

Two vector types:
1. Semantic vectors — from Jina embeddings of node descriptions
   - 1024D float32 → 10K Hamming bits via random projection
   - Captures MEANING: "what does this node do?"

2. Structural fingerprints — from graph topology
   - Hash of (node_type, neighbors, depth, phase)
   - Captures STRUCTURE: "where does this node sit in the graph?"

Both are stored as 1250 bytes (10K bits) for unified Hamming search.
"""

import hashlib
import numpy as np
from typing import List, Dict, Optional, Callable, Awaitable

from dto.node import FireflyNode
from dto.edge import FireflyEdge
from core import project, bind, bundle, PACKED, DIM


class VectorEmbedder:
    """
    Generate and attach vectors to compiled graph nodes.
    """

    def __init__(self, embed_fn: Optional[Callable[[str], Awaitable[np.ndarray]]] = None):
        """
        Args:
            embed_fn: Async function that takes text and returns float32[1024]
                      Jina embedding. If None, uses hash-based approximation.
        """
        self.embed_fn = embed_fn

    async def embed_graph(
        self,
        nodes: List[FireflyNode],
        edges: List[FireflyEdge]
    ) -> List[FireflyNode]:
        """
        Generate vectors for all nodes in the graph.

        Updates node resonance vectors in-place and returns them.
        """
        # Build adjacency info for structural fingerprints
        outgoing = {}
        incoming = {}
        for edge in edges:
            outgoing.setdefault(edge.source_id, []).append(edge.target_id)
            incoming.setdefault(edge.target_id, []).append(edge.source_id)

        for node in nodes:
            # Generate structural fingerprint
            structural = self._structural_fingerprint(
                node, outgoing, incoming
            )

            # If we have a real embedding function, enhance the semantic vector
            if self.embed_fn:
                semantic_desc = self._describe_node(node)
                embedding = await self.embed_fn(semantic_desc)
                semantic = project(embedding)
                # Combine semantic + structural into final resonance
                node.resonance = bundle([node.resonance, semantic, structural])
            else:
                # Blend existing resonance with structural fingerprint
                node.resonance = bundle([node.resonance, structural])

        return nodes

    def _structural_fingerprint(
        self,
        node: FireflyNode,
        outgoing: Dict[str, List[str]],
        incoming: Dict[str, List[str]]
    ) -> bytes:
        """
        Generate structural fingerprint from graph topology.

        Encodes:
        - Node type (VALIDATE, TRANSFORM, PERSIST, etc.)
        - Number and types of incoming/outgoing edges
        - Position (depth from entry)
        - Executor type
        """
        components = [
            f"type:{node.type}",
            f"executor:{node.executor}",
            f"pure:{node.pure}",
            f"parallel:{node.parallelizable}",
            f"cost:{node.cost}",
            f"out:{len(outgoing.get(node.id, []))}",
            f"in:{len(incoming.get(node.id, []))}",
        ]

        # Hash neighbors for locality-sensitive fingerprint
        out_ids = sorted(outgoing.get(node.id, []))
        in_ids = sorted(incoming.get(node.id, []))
        components.append(f"out_ids:{','.join(out_ids[:5])}")
        components.append(f"in_ids:{','.join(in_ids[:5])}")

        fingerprint = "|".join(components)
        h = hashlib.sha256(fingerprint.encode()).digest()
        return (h * 40)[:PACKED]

    def _describe_node(self, node: FireflyNode) -> str:
        """Generate text description for semantic embedding."""
        parts = [
            f"{node.type} node",
            f"executor: {node.executor}",
            f"function: {node.fn_name}",
        ]
        if node.input_schema:
            parts.append(f"input: {node.input_schema}")
        if node.output_schema:
            parts.append(f"output: {node.output_schema}")
        return " | ".join(parts)

    @staticmethod
    def cam_fingerprint(resonance: bytes, bits: int = 48) -> int:
        """
        Content-Addressable Memory fingerprint.

        Compress 10K-bit resonance to a 48-bit CAM address.
        Used for O(1) exact-match lookup.

        From dragonfly-vsa: 48-bit fingerprints enable
        hash-table lookup of resonance vectors.
        """
        # Use first 48 bits of SHA-256 of resonance
        h = hashlib.sha256(resonance).digest()
        # Pack first 6 bytes as 48-bit integer
        cam = int.from_bytes(h[:6], 'big')
        return cam & ((1 << bits) - 1)
