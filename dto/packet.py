"""
Firefly Packet: mRNA transport for distributed graph execution.

Total: ~1.5KB
- Routing header: 64 bytes
- Resonance payload: 1250 bytes
- Execution context: variable (MessagePack)

Packets flow through Redis streams, routed by Hamming similarity.
"""

import struct
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import hashlib
import json

from core import bind, PACKED


# Packet flags
FLAG_ASYNC = 0x01      # Don't wait for response
FLAG_SYNC = 0x02       # Wait for response
FLAG_BROADCAST = 0x04  # Send to all matching nodes
FLAG_TRACE = 0x08      # Record execution trace
FLAG_PRIORITY = 0x10   # High priority


@dataclass
class FireflyPacket:
    """
    mRNA packet for distributed graph execution.
    
    Like a ribosome carrying instructions through the cell,
    packets carry execution context through the graph.
    """
    
    # Routing (64 bytes total when packed)
    source_node: bytes = field(default_factory=lambda: b'\0' * 32)  # 32 bytes
    target_node: bytes = field(default_factory=lambda: b'\0' * 32)  # 32 bytes
    
    # Control
    ttl: int = 8              # Max hops before death
    priority: int = 5         # 0-10, higher = more urgent
    flags: int = FLAG_TRACE   # Bitfield
    sequence: int = 0         # For ordering/dedup
    
    # Payload (1250 bytes)
    resonance: bytes = field(default_factory=lambda: b'\0' * PACKED)
    
    # Execution context (variable, MessagePack encoded)
    dto_id: str = ""
    operation: str = ""       # CREATE | UPDATE | DESTROY | QUERY
    input_data: Dict[str, Any] = field(default_factory=dict)
    trace: List[str] = field(default_factory=list)  # Node IDs visited
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def pack_header(self) -> bytes:
        """
        Pack routing header to exactly 64 bytes.
        
        Format:
        - source_node: 32 bytes
        - target_node: 32 bytes
        - ttl: 1 byte
        - priority: 1 byte  
        - flags: 2 bytes
        - sequence: 4 bytes
        - checksum: 4 bytes
        - reserved: 20 bytes
        """
        # Ensure node addresses are exactly 32 bytes
        source = self.source_node[:32].ljust(32, b'\0')
        target = self.target_node[:32].ljust(32, b'\0')
        
        # Pack control fields
        header = struct.pack(
            "32s32sBBHI",
            source,
            target,
            self.ttl,
            self.priority,
            self.flags,
            self.sequence
        )
        
        # Add checksum (CRC32 of header so far)
        import zlib
        checksum = zlib.crc32(header) & 0xFFFFFFFF
        header += struct.pack("I", checksum)
        
        # Pad to 64 bytes
        header += b'\0' * (64 - len(header))
        
        return header
    
    @classmethod
    def unpack_header(cls, data: bytes) -> dict:
        """Unpack routing header from 64 bytes."""
        source, target, ttl, priority, flags, sequence = struct.unpack(
            "32s32sBBHI", data[:72]
        )
        checksum = struct.unpack("I", data[72:76])[0]
        
        return {
            "source_node": source.rstrip(b'\0'),
            "target_node": target.rstrip(b'\0'),
            "ttl": ttl,
            "priority": priority,
            "flags": flags,
            "sequence": sequence,
            "checksum": checksum,
        }
    
    def route_key(self) -> str:
        """Redis stream key for routing."""
        # Use first 16 chars of hex-encoded target for sharding
        target_hex = self.target_node.hex()[:16] if self.target_node else "broadcast"
        return f"firefly:route:{target_hex}"
    
    def node_key(self) -> str:
        """Redis stream key for specific node."""
        target_hex = self.target_node.hex()[:32] if self.target_node else "unknown"
        return f"firefly:node:{target_hex}"
    
    @classmethod
    def for_node(cls, node_id: str, **kwargs) -> "FireflyPacket":
        """Create packet targeting a specific node by ID."""
        # Hash node ID to get 32-byte address
        target = hashlib.sha256(node_id.encode()).digest()
        return cls(target_node=target, **kwargs)
    
    @classmethod
    def for_dto(cls, dto_id: str, operation: str, input_data: dict) -> "FireflyPacket":
        """Create packet for DTO operation."""
        # Target the entry point node
        entry_id = f"{dto_id}_{operation}_entry"
        target = hashlib.sha256(entry_id.encode()).digest()
        
        return cls(
            target_node=target,
            dto_id=dto_id,
            operation=operation,
            input_data=input_data,
            flags=FLAG_TRACE | FLAG_SYNC,
        )
    
    def hop(self, current_node_id: str, next_node_id: str) -> "FireflyPacket":
        """
        Create new packet for next hop.
        
        Decrements TTL, updates source, adds to trace.
        """
        if self.ttl <= 0:
            raise ValueError("Packet TTL expired")
        
        # Hash node IDs to addresses
        source = hashlib.sha256(current_node_id.encode()).digest()
        target = hashlib.sha256(next_node_id.encode()).digest()
        
        return FireflyPacket(
            source_node=source,
            target_node=target,
            ttl=self.ttl - 1,
            priority=self.priority,
            flags=self.flags,
            sequence=self.sequence + 1,
            resonance=self.resonance,
            dto_id=self.dto_id,
            operation=self.operation,
            input_data=self.input_data,
            trace=self.trace + [current_node_id],
            created_at=self.created_at,
        )
    
    def to_dict(self) -> dict:
        """Serialize for Redis/storage."""
        return {
            "source_node": self.source_node.hex(),
            "target_node": self.target_node.hex(),
            "ttl": self.ttl,
            "priority": self.priority,
            "flags": self.flags,
            "sequence": self.sequence,
            "resonance": self.resonance.hex(),
            "dto_id": self.dto_id,
            "operation": self.operation,
            "input_data": self.input_data,
            "trace": self.trace,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "FireflyPacket":
        """Deserialize from Redis/storage."""
        return cls(
            source_node=bytes.fromhex(data.get("source_node", "00" * 32)),
            target_node=bytes.fromhex(data.get("target_node", "00" * 32)),
            ttl=data.get("ttl", 8),
            priority=data.get("priority", 5),
            flags=data.get("flags", FLAG_TRACE),
            sequence=data.get("sequence", 0),
            resonance=bytes.fromhex(data.get("resonance", "00" * PACKED)),
            dto_id=data.get("dto_id", ""),
            operation=data.get("operation", ""),
            input_data=data.get("input_data", {}),
            trace=data.get("trace", []),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
        )
    
    def __sizeof__(self) -> int:
        """Base size without variable context."""
        return 64 + PACKED  # header + resonance
    
    def __repr__(self) -> str:
        target_short = self.target_node.hex()[:8] if self.target_node else "none"
        return f"FireflyPacket(→{target_short}, dto={self.dto_id}, op={self.operation}, ttl={self.ttl})"
