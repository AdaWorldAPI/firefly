"""
Compiler Phase 5: EMBED — Vector Generation

Input:  Optimized graph
Output: Vectors for each node

Generates:
- Semantic vector (Jina 1024D → 10K Hamming via projection)
- Structural fingerprint (Hamming CAM from graph topology)
- Stores in LanceDB for similarity search
"""

from compiler.embed.vectors import VectorEmbedder

__all__ = ["VectorEmbedder"]
