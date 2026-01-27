# mRNA Transport: Distributed Graph Execution

## Overview

Firefly packets flow through the graph like mRNA through a cell:
- **Ribosomes** = Worker nodes
- **mRNA** = Packets carrying execution context
- **Proteins** = Results of execution

---

## Packet Format

```
┌─────────────────────────────────────────────────────────────────┐
│                     FIREFLY PACKET (~1.5KB)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ROUTING HEADER (64 bytes)                                     │
│   ════════════════════════                                      │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │ source_node:    32 bytes (256-bit node address)         │  │
│   │ target_node:    32 bytes (256-bit node address)         │  │
│   │ ttl:            1 byte  (max hops)                      │  │
│   │ priority:       1 byte  (0-10)                          │  │
│   │ flags:          2 bytes (ASYNC|SYNC|BROADCAST|TRACE)    │  │
│   │ sequence:       4 bytes (ordering/dedup)                │  │
│   │ checksum:       4 bytes (CRC32)                         │  │
│   │ reserved:       20 bytes                                │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   HAMMING FINGERPRINT (1250 bytes = 10,000 bits)               │
│   ══════════════════════════════════════════════               │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │ Bits 0-2999:     Content signature (WHAT)               │  │
│   │ Bits 3000-5999:  Process signature (HOW)                │  │
│   │ Bits 6000-7999:  Qualia signature (FEEL)                │  │
│   │ Bits 8000-9999:  Context signature (WHERE)              │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   EXECUTION CONTEXT (variable, MessagePack)                    │
│   ═════════════════════════════════════════                    │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │ dto_id:         string                                   │  │
│   │ operation:      CREATE|UPDATE|DESTROY|QUERY              │  │
│   │ input:          MessagePack encoded payload              │  │
│   │ trace:          execution path so far                    │  │
│   │ checkpoints:    transaction markers                      │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Flags

```python
FLAG_ASYNC     = 0x01  # Don't wait for response
FLAG_SYNC      = 0x02  # Wait for response
FLAG_BROADCAST = 0x04  # Send to all matching nodes
FLAG_TRACE     = 0x08  # Record execution trace
FLAG_PRIORITY  = 0x10  # High priority routing
```

---

## Redis Queue Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   REDIS STREAM TOPOLOGY                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Entry Points                                                  │
│   ════════════                                                  │
│   firefly:execute:{dto_id}     → Incoming execution requests    │
│                                                                 │
│   Node Queues                                                   │
│   ═══════════                                                   │
│   firefly:node:{node_hash}     → Per-node work queue            │
│                                                                 │
│   Results                                                       │
│   ═══════                                                       │
│   firefly:results:{exec_id}    → Execution results              │
│                                                                 │
│   Dead Letter                                                   │
│   ═══════════                                                   │
│   firefly:dead-letter          → Failed executions              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Flow

```
1. Client
   │
   │ XADD firefly:execute:WorkPackage
   │ {dto: "WorkPackage", op: "create", input: {...}}
   ▼
2. Orchestrator
   │
   │ Read from execute stream
   │ Plan execution path
   │ XADD firefly:node:{validate_subject_hash}
   ▼
3. Worker (validate_subject)
   │
   │ Read from node stream
   │ Execute validation
   │ XADD firefly:node:{next_node_hash}
   ▼
4. Worker (validate_length)
   │
   │ ...continues through graph...
   ▼
5. Worker (persist)
   │
   │ Execute final node
   │ XADD firefly:results:{exec_id}
   ▼
6. Client
   │
   │ Read from results stream
   │ Get final result
   ▼
   Done
```

---

## Consumer Groups

```python
# One consumer group per node type
CONSUMER_GROUPS = {
    "validate": "firefly:cg:validate",  # Stateless, parallelizable
    "transform": "firefly:cg:transform",
    "persist": "firefly:cg:persist",    # Single consumer (ordering)
    "trigger": "firefly:cg:trigger",
}
```

### Scaling Rules

| Node Type | Parallelism | Reason |
|-----------|-------------|--------|
| VALIDATE | High (N workers) | Pure, no side effects |
| TRANSFORM | High (N workers) | Pure, no side effects |
| PERSIST | Single | Must maintain ordering |
| TRIGGER | Medium | May have side effects |

---

## Routing by Hamming

For **broadcast** packets, route to nodes with similar resonance:

```python
async def route_broadcast(packet: FireflyPacket, store: FireflyStore):
    """Route packet to similar nodes."""
    # Find nodes with similar resonance
    similar = await store.find_similar_nodes(
        packet.resonance, 
        k=10
    )
    
    # Send to each
    for node in similar:
        target_packet = packet.hop(
            current_node_id="router",
            next_node_id=node['id']
        )
        await redis.xadd(
            target_packet.node_key(),
            target_packet.to_dict()
        )
```

---

## Backpressure

```python
# Stream length limits
MAX_STREAM_LENGTH = 10000

async def xadd_with_backpressure(stream: str, data: dict):
    """Add to stream with backpressure."""
    length = await redis.xlen(stream)
    
    if length > MAX_STREAM_LENGTH:
        # Wait for consumers to catch up
        await asyncio.sleep(0.1)
        
        # Check again
        length = await redis.xlen(stream)
        if length > MAX_STREAM_LENGTH:
            raise BackpressureError(f"Stream {stream} full")
    
    return await redis.xadd(stream, data)
```

---

## Packet Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                     PACKET LIFECYCLE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   CREATED                                                       │
│      │                                                          │
│      │ Client creates packet                                    │
│      ▼                                                          │
│   QUEUED                                                        │
│      │                                                          │
│      │ Added to execute stream                                  │
│      ▼                                                          │
│   ROUTING                                                       │
│      │                                                          │
│      │ Orchestrator plans path                                  │
│      ▼                                                          │
│   EXECUTING                                                     │
│      │                                                          │
│      │ Workers process node by node                             │
│      │ TTL decrements at each hop                               │
│      ▼                                                          │
│   COMPLETED ──or──► FAILED                                      │
│      │                    │                                     │
│      │                    │ Move to dead-letter                 │
│      ▼                    ▼                                     │
│   RESULT              DEAD-LETTER                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation

```python
# transport/queue.py

import httpx
from typing import Optional
from dto.packet import FireflyPacket

class RedisTransport:
    def __init__(self, url: str, token: str):
        self.url = url
        self.headers = {"Authorization": f"Bearer {token}"}
    
    async def xadd(self, stream: str, data: dict) -> str:
        """Add entry to stream."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.url}/xadd/{stream}/*",
                headers=self.headers,
                json=data
            )
            return resp.json()["result"]
    
    async def xread(
        self, 
        streams: list[str], 
        count: int = 10,
        block: int = 5000
    ) -> list:
        """Read from streams."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.url}/xread",
                headers=self.headers,
                json={
                    "streams": streams,
                    "count": count,
                    "block": block
                }
            )
            return resp.json()["result"]
    
    async def send_packet(self, packet: FireflyPacket):
        """Send packet to appropriate stream."""
        stream = packet.route_key()
        return await self.xadd(stream, packet.to_dict())
    
    async def receive_packets(
        self, 
        node_id: str, 
        count: int = 10
    ) -> list[FireflyPacket]:
        """Receive packets for a node."""
        import hashlib
        node_hash = hashlib.sha256(node_id.encode()).hexdigest()[:16]
        stream = f"firefly:node:{node_hash}"
        
        entries = await self.xread([stream], count=count)
        return [
            FireflyPacket.from_dict(entry["data"])
            for entry in entries
        ]
```

---

## The Point

mRNA transport enables:
1. **Distributed execution** across multiple workers
2. **Fault tolerance** via dead-letter queues
3. **Backpressure** to prevent overload
4. **Tracing** of execution paths
5. **Hamming routing** for broadcast/similarity

The packet IS the execution context. It flows through the graph like life through a cell.
