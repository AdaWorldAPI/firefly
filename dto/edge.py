"""
Firefly Edge: Graph edge as resonance binding.

edge.resonance = source.resonance ⊕ target.resonance

This means:
- Given source + edge → recover target (approximately)
- Given target + edge → recover source (approximately)
- Edge IS the relationship, not just a pointer
"""

from dataclasses import dataclass, field as dataclass_field
from typing import Optional
from datetime import datetime

from core import bind, similarity, PACKED
from dto.node import FireflyNode


@dataclass
class FireflyEdge:
    """
    Edge between nodes = XOR binding of their resonances.
    
    The edge resonance encodes the RELATIONSHIP between nodes,
    not just connectivity. Similar edges = similar relationships.
    """
    id: str
    source_id: str
    target_id: str
    resonance: bytes  # source ⊕ target = relationship encoding
    
    # Edge metadata
    type: str = "FEEDS"       # FEEDS | TRIGGERS | GUARDS | CHECKPOINTS
    condition: Optional[str] = None  # For GUARDS: predicate expression
    field: Optional[str] = None      # For FEEDS: which field flows
    
    # Timestamps
    created_at: datetime = dataclass_field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_nodes(
        cls,
        source: FireflyNode,
        target: FireflyNode,
        **kwargs
    ) -> "FireflyEdge":
        """Create edge as binding of two nodes."""
        resonance = bind(source.resonance, target.resonance)
        return cls(
            id=f"{source.id}→{target.id}",
            source_id=source.id,
            target_id=target.id,
            resonance=resonance,
            **kwargs
        )
    
    @classmethod
    def from_resonances(
        cls,
        source_id: str,
        target_id: str,
        source_resonance: bytes,
        target_resonance: bytes,
        **kwargs
    ) -> "FireflyEdge":
        """Create edge from raw resonances."""
        resonance = bind(source_resonance, target_resonance)
        return cls(
            id=f"{source_id}→{target_id}",
            source_id=source_id,
            target_id=target_id,
            resonance=resonance,
            **kwargs
        )
    
    def recover_target(self, source: FireflyNode) -> bytes:
        """
        Given source node, approximate the target resonance.
        
        target ≈ bind(source.resonance, edge.resonance)
        """
        return bind(source.resonance, self.resonance)
    
    def recover_source(self, target: FireflyNode) -> bytes:
        """
        Given target node, approximate the source resonance.
        
        source ≈ bind(target.resonance, edge.resonance)
        """
        return bind(target.resonance, self.resonance)
    
    def similarity_to(self, other: "FireflyEdge") -> float:
        """How similar is this relationship to another?"""
        return similarity(self.resonance, other.resonance)
    
    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "resonance": self.resonance.hex(),
            "type": self.type,
            "condition": self.condition,
            "field": self.field,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "FireflyEdge":
        """Deserialize from storage."""
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            resonance=bytes.fromhex(data["resonance"]),
            type=data.get("type", "FEEDS"),
            condition=data.get("condition"),
            field=data.get("field"),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
        )
    
    def __sizeof__(self) -> int:
        return PACKED
    
    def __repr__(self) -> str:
        return f"FireflyEdge({self.source_id} --[{self.type}]--> {self.target_id})"
