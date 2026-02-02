"""
Firefly Node: Executable graph node in 1.25KB.

Each node encodes:
- WHAT: input/output schema (bound with ROLE_SCHEMA)
- HOW:  execution logic (bound with ROLE_LOGIC)
- WHERE: position in graph (bound with ROLE_CONTEXT)

All three recoverable via XOR unbinding.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional, Any, Dict
from datetime import datetime
import hashlib

from core import (
    bind, bundle, similarity, 
    ROLE_SCHEMA, ROLE_LOGIC, ROLE_CONTEXT,
    PACKED
)


@dataclass
class FireflyNode:
    """
    Executable graph node in 1.25KB.
    
    The resonance vector is the identity — everything else is metadata.
    """
    id: str
    resonance: bytes  # 1250 bytes = 10K bits
    
    # Executor configuration
    executor: str = "NATIVE"  # NATIVE | WASM | SQL
    fn_name: str = ""         # Function reference
    
    # Node metadata
    type: str = "TRANSFORM"   # VALIDATE | TRANSFORM | PERSIST | TRIGGER | QUERY
    cost: int = 1             # Relative execution cost (for optimizer)
    pure: bool = True         # No side effects = cacheable
    parallelizable: bool = True
    
    # Schema (stored separately, not in resonance)
    input_schema: Dict[str, str] = field(default_factory=dict)
    output_schema: Dict[str, str] = field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_components(
        cls,
        id: str,
        schema_vec: bytes,    # Embedded input/output schema
        logic_vec: bytes,     # Embedded logic description
        context_vec: bytes,   # Embedded graph context
        **kwargs
    ) -> "FireflyNode":
        """
        Create node from semantic components.
        
        The resonance vector is the bundle of role-bound components:
        resonance = bundle([
            bind(schema, ROLE_SCHEMA),
            bind(logic, ROLE_LOGIC),
            bind(context, ROLE_CONTEXT)
        ])
        """
        bound_schema = bind(schema_vec, ROLE_SCHEMA)
        bound_logic = bind(logic_vec, ROLE_LOGIC)
        bound_context = bind(context_vec, ROLE_CONTEXT)
        
        resonance = bundle([bound_schema, bound_logic, bound_context])
        return cls(id=id, resonance=resonance, **kwargs)
    
    @classmethod
    def from_id(cls, id: str, **kwargs) -> "FireflyNode":
        """Create node with deterministic resonance from ID."""
        # Simple hash-based resonance for bootstrapping
        h = hashlib.sha256(id.encode()).digest()
        resonance = (h * 40)[:PACKED]
        return cls(id=id, resonance=resonance, **kwargs)
    
    def extract_schema(self) -> bytes:
        """Approximate recovery of schema component."""
        return bind(self.resonance, ROLE_SCHEMA)
    
    def extract_logic(self) -> bytes:
        """Approximate recovery of logic component."""
        return bind(self.resonance, ROLE_LOGIC)
    
    def extract_context(self) -> bytes:
        """Approximate recovery of context component."""
        return bind(self.resonance, ROLE_CONTEXT)
    
    def similarity_to(self, other: "FireflyNode") -> float:
        """How similar is this node to another?"""
        return similarity(self.resonance, other.resonance)
    
    def bind_with(self, other: "FireflyNode") -> bytes:
        """Create edge resonance by binding with another node."""
        return bind(self.resonance, other.resonance)
    
    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "id": self.id,
            "resonance": self.resonance.hex(),
            "executor": self.executor,
            "fn_name": self.fn_name,
            "type": self.type,
            "cost": self.cost,
            "pure": self.pure,
            "parallelizable": self.parallelizable,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "FireflyNode":
        """Deserialize from storage."""
        return cls(
            id=data["id"],
            resonance=bytes.fromhex(data["resonance"]),
            executor=data.get("executor", "NATIVE"),
            fn_name=data.get("fn_name", ""),
            type=data.get("type", "TRANSFORM"),
            cost=data.get("cost", 1),
            pure=data.get("pure", True),
            parallelizable=data.get("parallelizable", True),
            input_schema=data.get("input_schema", {}),
            output_schema=data.get("output_schema", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
        )
    
    def __sizeof__(self) -> int:
        """Always 1.25KB for resonance."""
        return PACKED
    
    def __repr__(self) -> str:
        return f"FireflyNode(id={self.id!r}, type={self.type!r}, cost={self.cost})"
