"""
Firefly DTOs: Data Transfer Objects for the graph substrate.

All DTOs are 1.25KB (resonance) + metadata.
"""

from dto.node import FireflyNode
from dto.edge import FireflyEdge
from dto.packet import FireflyPacket, FLAG_ASYNC, FLAG_SYNC, FLAG_BROADCAST, FLAG_TRACE, FLAG_PRIORITY

__all__ = [
    "FireflyNode",
    "FireflyEdge", 
    "FireflyPacket",
    "FLAG_ASYNC",
    "FLAG_SYNC",
    "FLAG_BROADCAST",
    "FLAG_TRACE",
    "FLAG_PRIORITY",
]
