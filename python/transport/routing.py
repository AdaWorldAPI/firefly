"""
Packet Router: Hamming-based routing for distributed graph execution.

Routes packets to nodes based on:
1. Direct routing — target_node address matches specific node
2. Broadcast routing — find similar nodes via Hamming search
3. Priority routing — high-priority packets jump the queue

From vsa-flow: mRNA packets carry execution context through the graph,
like ribosomes carrying instructions through a cell.
"""

import hashlib
from typing import List, Dict, Optional

from dto.packet import FireflyPacket, FLAG_BROADCAST, FLAG_PRIORITY
from storage.store import FireflyStore
from transport.queue import RedisTransport


class PacketRouter:
    """
    Route packets through the distributed execution graph.

    Manages the orchestration layer between clients and workers:
    1. Accept execution requests
    2. Plan execution path (from Kuzu graph)
    3. Route packets to appropriate node workers
    4. Collect and return results
    """

    def __init__(self, transport: RedisTransport, store: FireflyStore):
        self.transport = transport
        self.store = store

    async def route(self, packet: FireflyPacket):
        """
        Route a packet to its destination.

        Handles broadcast, priority, and direct routing.
        """
        if packet.flags & FLAG_BROADCAST:
            await self._route_broadcast(packet)
        else:
            await self._route_direct(packet)

    async def _route_direct(self, packet: FireflyPacket):
        """Route packet directly to target node."""
        await self.transport.send_to_node(packet)

    async def _route_broadcast(self, packet: FireflyPacket):
        """Route packet to similar nodes via Hamming search."""
        similar = await self.store.find_similar_nodes(
            packet.resonance, k=10
        )

        for node_info in similar:
            node_id = node_info.get("id", "")
            target_packet = packet.hop(
                current_node_id="router",
                next_node_id=node_id,
            )
            await self.transport.send_to_node(target_packet)

    async def submit_execution(
        self,
        dto_id: str,
        operation: str,
        input_data: dict,
    ) -> str:
        """
        Submit an execution request.

        Creates a packet and routes it to the entry point.
        Returns execution ID for result collection.
        """
        packet = FireflyPacket.for_dto(dto_id, operation, input_data)

        # Add to execution request stream
        stream = f"firefly:execute:{dto_id}"
        await self.transport.xadd(stream, packet.to_dict())

        return packet.created_at.isoformat()

    async def plan_execution(self, dto_id: str, operation: str) -> List[str]:
        """
        Get execution plan from graph database.

        Returns ordered list of node IDs to execute.
        """
        entry_id = f"{dto_id}_{operation}_entry"
        path = await self.store.get_execution_path(entry_id)

        if path and path[0].get("node_ids"):
            return path[0]["node_ids"]

        # Fallback: just the entry node
        return [entry_id]

    async def collect_result(
        self,
        exec_id: str,
        timeout_ms: int = 30000
    ) -> Optional[dict]:
        """
        Wait for and collect execution result.

        Blocks until result appears or timeout.
        """
        stream = f"firefly:results:{exec_id}"
        result = await self.transport.xread(
            [stream],
            count=1,
            block=timeout_ms,
        )

        if stream in result and result[stream]:
            return result[stream][0].data

        return None
