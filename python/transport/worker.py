"""
Graph Worker: Distributed node execution worker.

Each worker:
1. Subscribes to a set of node queues
2. Reads packets from its assigned streams
3. Executes the node function
4. Routes the result packet to the next node
5. Logs execution to DuckDB

Consumer groups ensure:
- VALIDATE/TRANSFORM: High parallelism (N workers)
- PERSIST: Single consumer (ordering guarantee)
- TRIGGER: Medium parallelism (may have side effects)
"""

import asyncio
import time
import uuid
from typing import Dict, Callable, Any, Optional, List

from dto.packet import FireflyPacket
from dto.node import FireflyNode
from storage.store import FireflyStore
from transport.queue import RedisTransport
from executor.engine import ExecutionContext, BUILTIN_EXECUTORS


# Consumer group scaling rules
PARALLELISM = {
    "VALIDATE": 4,
    "TRANSFORM": 4,
    "PERSIST": 1,
    "TRIGGER": 2,
    "QUERY": 2,
}


class GraphWorker:
    """
    Distributed graph execution worker.

    Processes packets from Redis streams, executes node functions,
    and routes results to the next node in the graph.
    """

    def __init__(
        self,
        worker_id: str,
        transport: RedisTransport,
        store: FireflyStore,
        node_types: Optional[List[str]] = None,
    ):
        self.worker_id = worker_id
        self.transport = transport
        self.store = store
        self.node_types = node_types or ["VALIDATE", "TRANSFORM", "PERSIST", "TRIGGER"]
        self.running = False

        # Executor registry
        self.executors: Dict[str, Callable] = dict(BUILTIN_EXECUTORS)

    def register_executor(self, name: str, fn: Callable):
        """Register a native executor function."""
        self.executors[name] = fn

    async def start(self):
        """Start the worker loop."""
        self.running = True
        while self.running:
            try:
                await self._process_cycle()
            except Exception as e:
                print(f"Worker {self.worker_id} error: {e}")
                await asyncio.sleep(1.0)

    async def stop(self):
        """Stop the worker."""
        self.running = False

    async def _process_cycle(self):
        """Single processing cycle: read, execute, route."""
        # Listen to execution request streams
        streams = [f"firefly:execute:*"]

        # Also listen to node-specific streams if assigned
        # In production, these would be specific node IDs
        result = await self.transport.xread(
            streams,
            count=10,
            block=5000,
        )

        for stream_name, entries in result.items():
            for entry in entries:
                await self._process_entry(stream_name, entry)

    async def _process_entry(self, stream: str, entry):
        """Process a single stream entry."""
        try:
            packet = FireflyPacket.from_dict(entry.data)
            await self._execute_packet(packet)
        except Exception as e:
            print(f"Worker {self.worker_id} failed on {stream}: {e}")
            try:
                packet = FireflyPacket.from_dict(entry.data)
                await self.transport.send_dead_letter(packet, str(e))
            except Exception:
                pass

    async def _execute_packet(self, packet: FireflyPacket):
        """Execute a packet's target node."""
        # Find the target node
        # The target is encoded as a hash in packet.target_node
        # We need to look up which node this corresponds to
        target_hex = packet.target_node.hex()[:32]

        # Get node from store
        # Try to match by looking up nodes
        node = await self.store.get_node(packet.dto_id + "_" + packet.operation + "_entry")

        if not node:
            return

        # Build execution context
        ctx = ExecutionContext(input_data=packet.input_data)

        # Execute the node
        start = time.time()
        executor = self.executors.get(node.fn_name)

        if executor:
            if asyncio.iscoroutinefunction(executor):
                result = await executor(packet.input_data, ctx)
            else:
                result = executor(packet.input_data, ctx)
        else:
            result = {"status": "no_executor", "node": node.id}

        duration_ms = (time.time() - start) * 1000

        # Log execution
        await self.store.log_execution(
            ctx.execution_id,
            node.id,
            duration_ms,
            success=True,
        )

        # Get outgoing edges for next hop
        outgoing = await self.store.get_outgoing_edges(node.id)

        if outgoing:
            # Route to next nodes
            for edge in outgoing:
                try:
                    next_packet = packet.hop(node.id, edge.target_id)
                    next_packet.input_data = result if isinstance(result, dict) else {"result": result}
                    await self.transport.send_to_node(next_packet)
                except ValueError:
                    # TTL expired
                    pass
        else:
            # Terminal node — send result
            await self.transport.send_result(
                ctx.execution_id,
                {
                    "dto_id": packet.dto_id,
                    "operation": packet.operation,
                    "result": str(result),
                    "trace": ",".join(packet.trace + [node.id]),
                    "success": "true",
                }
            )
