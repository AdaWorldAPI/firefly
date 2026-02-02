"""
Redis Stream Transport: Queue management for distributed graph execution.

Uses Redis Streams (via Upstash REST API or direct connection) for:
- Execution request queuing
- Per-node work distribution
- Result collection
- Dead letter handling

Stream topology:
  firefly:execute:{dto_id}     → Incoming execution requests
  firefly:node:{node_hash}     → Per-node work queue
  firefly:results:{exec_id}    → Execution results
  firefly:dead-letter          → Failed executions
"""

import json
import hashlib
import asyncio
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from dto.packet import FireflyPacket


# Maximum stream length before backpressure kicks in
MAX_STREAM_LENGTH = 10000


@dataclass
class StreamEntry:
    """An entry read from a Redis stream."""
    entry_id: str
    data: Dict[str, Any]


class RedisTransport:
    """
    Redis Streams transport layer.

    Supports two modes:
    1. Upstash REST API (serverless, for production)
    2. Direct Redis connection (for local development)
    """

    def __init__(self, url: str = "", token: str = "", redis_client=None):
        """
        Args:
            url: Upstash REST endpoint (e.g., https://xxx.upstash.io)
            token: Upstash REST token
            redis_client: Direct redis-py client (alternative to REST)
        """
        self.url = url.rstrip("/")
        self.token = token
        self.redis = redis_client
        self._http_client = None

    async def _get_http(self):
        """Lazy-init HTTP client for Upstash REST."""
        if self._http_client is None:
            try:
                import httpx
                self._http_client = httpx.AsyncClient(
                    base_url=self.url,
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=30.0,
                )
            except ImportError:
                raise RuntimeError("httpx required for Upstash transport: pip install httpx")
        return self._http_client

    async def xadd(self, stream: str, data: dict, max_len: int = MAX_STREAM_LENGTH) -> str:
        """Add entry to stream."""
        serialized = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
                      for k, v in data.items()}

        if self.redis:
            return self.redis.xadd(stream, serialized, maxlen=max_len)

        client = await self._get_http()
        # Upstash REST: POST /xadd/{stream}/MAXLEN~{max_len}/*
        fields = []
        for k, v in serialized.items():
            fields.extend([k, v])
        resp = await client.post("/", json=["XADD", stream, "MAXLEN", "~", str(max_len), "*"] + fields)
        return resp.json().get("result", "")

    async def xread(
        self,
        streams: List[str],
        count: int = 10,
        block: int = 5000,
        last_ids: Optional[Dict[str, str]] = None
    ) -> Dict[str, List[StreamEntry]]:
        """Read from streams."""
        if last_ids is None:
            last_ids = {s: "0" for s in streams}

        if self.redis:
            raw = self.redis.xread(
                {s: last_ids.get(s, "0") for s in streams},
                count=count,
                block=block
            )
            result = {}
            if raw:
                for stream_name, entries in raw:
                    stream_key = stream_name.decode() if isinstance(stream_name, bytes) else stream_name
                    result[stream_key] = [
                        StreamEntry(
                            entry_id=eid.decode() if isinstance(eid, bytes) else eid,
                            data={k.decode(): v.decode() for k, v in edata.items()}
                        )
                        for eid, edata in entries
                    ]
            return result

        client = await self._get_http()
        args = ["XREAD", "COUNT", str(count), "BLOCK", str(block), "STREAMS"]
        args.extend(streams)
        args.extend([last_ids.get(s, "0") for s in streams])
        resp = await client.post("/", json=args)
        raw = resp.json().get("result")
        result = {}
        if raw:
            for stream_data in raw:
                stream_name = stream_data[0]
                entries = stream_data[1]
                result[stream_name] = [
                    StreamEntry(entry_id=e[0], data=dict(zip(e[1][::2], e[1][1::2])))
                    for e in entries
                ]
        return result

    async def xlen(self, stream: str) -> int:
        """Get stream length."""
        if self.redis:
            return self.redis.xlen(stream)

        client = await self._get_http()
        resp = await client.post("/", json=["XLEN", stream])
        return resp.json().get("result", 0)

    async def send_packet(self, packet: FireflyPacket) -> str:
        """Send a packet to its target stream."""
        stream = packet.route_key()
        return await self.xadd(stream, packet.to_dict())

    async def send_to_node(self, packet: FireflyPacket) -> str:
        """Send a packet to a specific node's work queue."""
        stream = packet.node_key()
        return await self.xadd(stream, packet.to_dict())

    async def send_result(self, exec_id: str, result: dict) -> str:
        """Send execution result."""
        stream = f"firefly:results:{exec_id}"
        return await self.xadd(stream, result)

    async def send_dead_letter(self, packet: FireflyPacket, error: str) -> str:
        """Send failed packet to dead letter queue."""
        data = packet.to_dict()
        data["error"] = error
        return await self.xadd("firefly:dead-letter", data)

    async def xadd_with_backpressure(self, stream: str, data: dict) -> str:
        """Add to stream with backpressure handling."""
        length = await self.xlen(stream)

        if length > MAX_STREAM_LENGTH:
            # Wait for consumers to catch up
            await asyncio.sleep(0.1)
            length = await self.xlen(stream)
            if length > MAX_STREAM_LENGTH:
                raise BackpressureError(f"Stream {stream} at capacity ({length})")

        return await self.xadd(stream, data)

    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()


class BackpressureError(Exception):
    """Raised when stream is at capacity."""
    pass
