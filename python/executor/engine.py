"""
Firefly Executor: Watch nodes glow as execution flows through the graph.

The executor:
1. Loads the execution graph from storage
2. Plans execution (topological sort, parallelization)
3. Executes nodes (native/WASM/SQL)
4. Emits "glow" events for visualization
5. Captures traces for learning
"""

import asyncio
import time
import uuid
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum

from dto.node import FireflyNode
from dto.edge import FireflyEdge
from dto.packet import FireflyPacket
from storage.store import FireflyStore
from core import similarity


class GlowState(Enum):
    """Node execution state for visualization."""
    PENDING = "pending"
    ACTIVE = "active"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


@dataclass
class ExecutionContext:
    """
    Context passed through execution.
    
    Accumulates results from each node.
    """
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input_data: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)  # node_id → result
    errors: Dict[str, Exception] = field(default_factory=dict)
    trace: List[str] = field(default_factory=list)  # node IDs in execution order
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from input or previous results."""
        if key in self.input_data:
            return self.input_data[key]
        return self.results.get(key, default)
    
    def set(self, node_id: str, result: Any):
        """Set result from node execution."""
        self.results[node_id] = result
        self.trace.append(node_id)
    
    def set_error(self, node_id: str, error: Exception):
        """Record error from node execution."""
        self.errors[node_id] = error
        self.trace.append(f"{node_id}:ERROR")
    
    @property
    def success(self) -> bool:
        return len(self.errors) == 0
    
    @property
    def result(self) -> Any:
        """Final result (last node's output)."""
        if self.trace:
            last = self.trace[-1].replace(":ERROR", "")
            return self.results.get(last)
        return None


class FireflyEngine:
    """
    Execute compiled graphs.
    Watch nodes light up as execution flows through.
    """
    
    def __init__(self, store: FireflyStore):
        self.store = store
        self.active_nodes: set = set()
        self.glow_handlers: List[Callable] = []
        
        # Registry of native executors
        self.executors: Dict[str, Callable] = {}
    
    def register_executor(self, name: str, fn: Callable):
        """Register a native executor function."""
        self.executors[name] = fn
    
    def on_glow(self, handler: Callable[[str, GlowState], None]):
        """Register handler for node glow events."""
        self.glow_handlers.append(handler)
    
    def _emit_glow(self, node_id: str, state: GlowState):
        """Emit glow event to all handlers."""
        for handler in self.glow_handlers:
            try:
                handler(node_id, state)
            except Exception as e:
                print(f"Glow handler error: {e}")
        
        # Default console output
        emoji = {
            GlowState.PENDING: "⏳",
            GlowState.ACTIVE: "🔥",
            GlowState.SUCCESS: "✅",
            GlowState.FAILURE: "❌",
            GlowState.SKIPPED: "⏭️",
        }
        print(f"{emoji.get(state, '?')} {node_id}: {state.value}")
    
    async def execute(
        self, 
        dto: str, 
        operation: str, 
        input_data: Dict[str, Any]
    ) -> ExecutionContext:
        """
        Execute a DTO operation.
        
        1. Find entry point node
        2. Walk the graph
        3. Execute each node
        4. Return context with results
        """
        ctx = ExecutionContext(input_data=input_data)
        
        # Find entry point
        entry_id = f"{dto}_{operation}_entry"
        
        # Get execution path from graph
        path = await self.store.get_execution_path(entry_id)
        
        if not path:
            # Fallback: just execute the entry node
            await self._execute_single(entry_id, ctx)
            return ctx
        
        # Build execution stages (topological order with parallelization)
        stages = self._build_stages(path)
        
        # Execute each stage
        for stage in stages:
            # Parallel execution within stage
            await asyncio.gather(*[
                self._execute_node(node_id, ctx)
                for node_id in stage
            ])
            
            # Stop if any node failed
            if not ctx.success:
                break
        
        return ctx
    
    def _build_stages(self, path: List[dict]) -> List[List[str]]:
        """
        Build execution stages from path.
        
        Nodes in the same stage can run in parallel.
        """
        if not path:
            return []
        
        # Simple: one node per stage for now
        # TODO: Proper topological sort with parallelization
        node_ids = path[0].get("node_ids", [])
        return [[nid] for nid in node_ids]
    
    async def _execute_single(self, node_id: str, ctx: ExecutionContext):
        """Execute a single node by ID."""
        node = await self.store.get_node(node_id)
        if node:
            await self._execute_node_impl(node, ctx)
        else:
            ctx.set_error(node_id, Exception(f"Node not found: {node_id}"))
    
    async def _execute_node(self, node_id: str, ctx: ExecutionContext):
        """Execute a node by ID."""
        node = await self.store.get_node(node_id)
        if not node:
            self._emit_glow(node_id, GlowState.SKIPPED)
            return
        
        await self._execute_node_impl(node, ctx)
    
    async def _execute_node_impl(self, node: FireflyNode, ctx: ExecutionContext):
        """Execute a node with tracing and glow."""
        self.active_nodes.add(node.id)
        self._emit_glow(node.id, GlowState.ACTIVE)
        
        start = time.time()
        
        try:
            # Get executor
            executor = self.executors.get(node.fn_name)
            
            if executor:
                # Execute native function
                result = await self._run_executor(executor, node, ctx)
            elif node.executor == "SQL":
                # Execute SQL
                result = await self._run_sql(node, ctx)
            else:
                # No executor - pass through
                result = {"status": "no_executor", "node": node.id}
            
            ctx.set(node.id, result)
            self._emit_glow(node.id, GlowState.SUCCESS)
            
            # Log execution
            duration_ms = (time.time() - start) * 1000
            await self.store.log_execution(
                ctx.execution_id, 
                node.id, 
                duration_ms, 
                success=True
            )
            
        except Exception as e:
            ctx.set_error(node.id, e)
            self._emit_glow(node.id, GlowState.FAILURE)
            
            duration_ms = (time.time() - start) * 1000
            await self.store.log_execution(
                ctx.execution_id,
                node.id,
                duration_ms,
                success=False,
                error=str(e)
            )
            
        finally:
            self.active_nodes.discard(node.id)
    
    async def _run_executor(
        self, 
        executor: Callable, 
        node: FireflyNode, 
        ctx: ExecutionContext
    ) -> Any:
        """Run a native executor function."""
        # Build input from context
        input_data = {}
        for field in node.input_schema:
            input_data[field] = ctx.get(field)
        
        # Call executor (sync or async)
        if asyncio.iscoroutinefunction(executor):
            return await executor(input_data, ctx)
        else:
            return executor(input_data, ctx)
    
    async def _run_sql(self, node: FireflyNode, ctx: ExecutionContext) -> Any:
        """Execute a SQL node."""
        # SQL is stored in fn_name
        if not self.store.duck:
            raise Exception("DuckDB not available for SQL execution")
        
        # Simple parameter substitution
        sql = node.fn_name
        params = []
        
        for field in node.input_schema:
            value = ctx.get(field)
            params.append(value)
        
        result = self.store.duck.execute(sql, params).fetchall()
        return result


# =============================================================================
# BUILT-IN EXECUTORS
# =============================================================================

def validate_presence(input_data: dict, ctx: ExecutionContext) -> dict:
    """Validate that required fields are present."""
    errors = []
    field = input_data.get("_field", "value")
    value = input_data.get(field)
    
    if value is None or value == "":
        errors.append(f"{field} can't be blank")
    
    return {"valid": len(errors) == 0, "errors": errors}


def validate_length(input_data: dict, ctx: ExecutionContext) -> dict:
    """Validate field length."""
    errors = []
    field = input_data.get("_field", "value")
    value = input_data.get(field, "")
    min_len = input_data.get("_min")
    max_len = input_data.get("_max")
    
    if min_len and len(str(value)) < min_len:
        errors.append(f"{field} is too short (min {min_len})")
    if max_len and len(str(value)) > max_len:
        errors.append(f"{field} is too long (max {max_len})")
    
    return {"valid": len(errors) == 0, "errors": errors}


def transform_identity(input_data: dict, ctx: ExecutionContext) -> dict:
    """Pass through unchanged."""
    return input_data


# Register built-in executors
BUILTIN_EXECUTORS = {
    "validate_presence": validate_presence,
    "validate_length": validate_length,
    "transform_identity": transform_identity,
}
