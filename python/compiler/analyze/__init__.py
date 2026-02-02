"""
Compiler Phase 2: ANALYZE — Semantic Extraction

Input:  Parsed declarations (from parse phase)
Output: Semantic dependency graph

Builds:
- Dependency graph (what needs what)
- Execution order (topological sort)
- Data flow (what produces what)
- Side effects (what triggers what)
"""

from compiler.analyze.semantic import SemanticAnalyzer, SemanticGraph, DependencyNode, DependencyEdge

__all__ = ["SemanticAnalyzer", "SemanticGraph", "DependencyNode", "DependencyEdge"]
