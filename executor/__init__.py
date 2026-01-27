"""
Firefly Executor: Run compiled graphs, watch nodes glow.
"""

from executor.engine import (
    FireflyEngine, 
    ExecutionContext, 
    GlowState,
    BUILTIN_EXECUTORS,
    validate_presence,
    validate_length,
    transform_identity,
)

__all__ = [
    "FireflyEngine",
    "ExecutionContext",
    "GlowState",
    "BUILTIN_EXECUTORS",
    "validate_presence",
    "validate_length",
    "transform_identity",
]
