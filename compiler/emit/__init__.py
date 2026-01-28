"""
Compiler Phase 6: EMIT — Database Storage

Input:  Optimized graph + vectors
Output: Stored in Trinity databases (LanceDB + DuckDB + Kuzu)
"""

from compiler.emit.store import GraphEmitter

__all__ = ["GraphEmitter"]
