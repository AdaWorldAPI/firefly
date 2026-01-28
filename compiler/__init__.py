"""
Firefly Compiler: Source code → Executable graph substrate.

Pipeline: PARSE → ANALYZE → LOWER → OPTIMIZE → EMBED → EMIT

Each phase transforms the representation:
- PARSE:    Source text → Structured declarations (RubyParser)
- ANALYZE:  Declarations → Semantic dependency graph (SemanticAnalyzer)
- LOWER:    Semantic graph → Executable nodes + edges (GraphLowering)
- OPTIMIZE: Raw graph → Optimized graph (GraphOptimizer)
- EMBED:    Graph → Vectors (VectorEmbedder)
- EMIT:     Vectors + graph → Trinity storage (GraphEmitter)

Currently supports:
- Ruby (Rails models)

Coming soon:
- Python (Django/SQLAlchemy)
- TypeScript
- Java
"""

from compiler.ruby import RubyParser, RubyCompiler, RubyModel, RubyValidation, RubyAssociation, RubyCallback
from compiler.analyze.semantic import SemanticAnalyzer, SemanticGraph
from compiler.lower.nodes import GraphLowering
from compiler.optimize.pipeline import GraphOptimizer
from compiler.embed.vectors import VectorEmbedder
from compiler.emit.store import GraphEmitter

__all__ = [
    # Parse
    "RubyParser",
    "RubyCompiler",
    "RubyModel",
    "RubyValidation",
    "RubyAssociation",
    "RubyCallback",
    # Analyze
    "SemanticAnalyzer",
    "SemanticGraph",
    # Lower
    "GraphLowering",
    # Optimize
    "GraphOptimizer",
    # Embed
    "VectorEmbedder",
    # Emit
    "GraphEmitter",
]
