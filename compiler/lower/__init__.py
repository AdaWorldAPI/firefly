"""
Compiler Phase 3: LOWER — Graph IR Generation

Input:  Semantic dependency graph
Output: Executable FireflyNodes + FireflyEdges

Generates:
- Node for each validation → native validator fn
- Node for each callback → native or WASM
- Node for persistence → SQL executor
- Edges for data flow and control flow
"""

from compiler.lower.nodes import GraphLowering

__all__ = ["GraphLowering"]
