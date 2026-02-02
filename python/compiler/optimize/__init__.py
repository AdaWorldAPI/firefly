"""
Compiler Phase 4: OPTIMIZE — Graph Transformations

Input:  Raw graph (nodes + edges)
Output: Optimized graph

Transformations:
- Fuse sequential pure nodes
- Parallelize independent branches
- Inline small nodes
- Eliminate dead nodes
- Cache pure node results
"""

from compiler.optimize.pipeline import GraphOptimizer

__all__ = ["GraphOptimizer"]
