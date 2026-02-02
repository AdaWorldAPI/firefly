"""
Firefly Reasoning: AGI layer for graph understanding.

Capabilities:
- EXPLAIN: "Why did this fail?" — trace failure through graph
- SUGGEST: "How to fix?" — compare with successful executions
- OPTIMIZE: "Make faster" — find bottlenecks, suggest improvements
- GENERATE: "Create new DTO like X but with Y" — compose from existing
"""

from reasoning.explain import FailureExplainer
from reasoning.suggest import FixSuggester
from reasoning.optimize import PerformanceOptimizer
from reasoning.generate import GraphComposer

__all__ = ["FailureExplainer", "FixSuggester", "PerformanceOptimizer", "GraphComposer"]
