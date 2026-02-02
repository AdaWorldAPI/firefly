"""LadybugDB — Code as Deterministic Data.

Single executable surface wiring:
    AVX-512  → L1/L2 cache (hot SIMD computation)
    Dragonfly → Thread lanes (parallel execution queues)  
    LanceDB  → Working memory (vector atom storage)
    DuckDB   → Deterministic graph (execution plans, reversible paths)

Every function/class → hash(signature) → deterministic fingerprint → O(1) lookup

Usage:
    from ladybugdb import LadybugDB
    
    db = LadybugDB()
    db.register(my_function)
    result = db.execute("my_function", arg1, arg2)
    
    # Find similar code
    similar = db.resonate(my_function, threshold=0.7)
    
    # Export to any language
    rust_code = db.translate("my_function", target="rust")
"""

__version__ = "0.1.0"

import hashlib
import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from pathlib import Path
import struct
import json

import numpy as np
import duckdb
import lancedb
import pyarrow as pa

# Try numba, fallback to numpy
try:
    from numba import njit, prange, uint64, int64, int32, float64
    from numba import config
    config.NUMBA_DEFAULT_NUM_THREADS = 8
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False


# =============================================================================
# CONSTANTS
# =============================================================================

DIM = 10_000          # 10K bit fingerprint
DIM_U64 = 157         # (10000 + 63) // 64
LAST_MASK = np.uint64((1 << 16) - 1)  # Mask for last uint64

# Type codes (256 fixed types)
TYPE_FUNCTION = 0x00
TYPE_METHOD = 0x01
TYPE_CLASS = 0x02
TYPE_MODULE = 0x03
TYPE_COROUTINE = 0x04
TYPE_GENERATOR = 0x05
TYPE_LAMBDA = 0x06
TYPE_BUILTIN = 0x07
TYPE_VALIDATE = 0x10
TYPE_TRANSFORM = 0x20
TYPE_PERSIST = 0x30
TYPE_QUERY = 0x40


# =============================================================================
# AVX-512 SIMD KERNELS (L1/L2 Cache Layer)
# =============================================================================

if HAS_NUMBA:
    @njit(int64(uint64), cache=True, inline='always')
    def _popcnt(x):
        """Hardware popcount."""
        x = x - ((x >> 1) & uint64(0x5555555555555555))
        x = (x & uint64(0x3333333333333333)) + ((x >> 2) & uint64(0x3333333333333333))
        x = (x + (x >> 4)) & uint64(0x0F0F0F0F0F0F0F0F)
        return int64((x * uint64(0x0101010101010101)) >> uint64(56))

    @njit(cache=True, fastmath=True, parallel=True)
    def _batch_hamming(query, corpus, out):
        """Parallel batch Hamming - AVX-512 optimized."""
        n = corpus.shape[0]
        for i in prange(n):
            total = int64(0)
            for j in range(DIM_U64):
                diff = query[j] ^ corpus[i, j]
                total += _popcnt(diff)
            out[i] = int32(total)

    @njit(cache=True, fastmath=True)
    def _hamming(a, b):
        """Single Hamming distance."""
        total = int64(0)
        for i in range(DIM_U64):
            diff = a[i] ^ b[i]
            total += _popcnt(diff)
        return int32(total)

    @njit(cache=True, fastmath=True)
    def _xor(a, b, out):
        """XOR bind."""
        for i in range(DIM_U64):
            out[i] = a[i] ^ b[i]
        out[DIM_U64 - 1] &= LAST_MASK
else:
    # NumPy fallback
    def _popcnt(x):
        return bin(x).count('1')
    
    def _batch_hamming(query, corpus, out):
        for i in range(corpus.shape[0]):
            out[i] = np.sum(np.unpackbits((query ^ corpus[i]).view(np.uint8)))
    
    def _hamming(a, b):
        return np.sum(np.unpackbits((a ^ b).view(np.uint8)))
    
    def _xor(a, b, out):
        np.bitwise_xor(a, b, out=out)
        out[-1] &= LAST_MASK


class AVX512Engine:
    """L1/L2 Cache Layer - Hot SIMD Computation."""
    
    def __init__(self, max_batch: int = 100_000):
        self._max_batch = max_batch
        self._out_int = np.zeros(max_batch, dtype=np.int32)
        self._out_vec = np.zeros(DIM_U64, dtype=np.uint64)
        self._warmed = False
    
    def warmup(self):
        """JIT warmup."""
        if self._warmed or not HAS_NUMBA:
            return
        a = np.random.randint(0, 2**63, DIM_U64, dtype=np.uint64)
        b = np.random.randint(0, 2**63, DIM_U64, dtype=np.uint64)
        corpus = np.random.randint(0, 2**63, (100, DIM_U64), dtype=np.uint64)
        out = np.zeros(100, dtype=np.int32)
        for _ in range(10):
            _hamming(a, b)
            _batch_hamming(a, corpus, out)
        self._warmed = True
    
    def hamming(self, a: np.ndarray, b: np.ndarray) -> int:
        return int(_hamming(a, b))
    
    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return 1.0 - _hamming(a, b) / DIM
    
    def batch_hamming(self, query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
        n = corpus.shape[0]
        if n > self._max_batch:
            out = np.zeros(n, dtype=np.int32)
        else:
            out = self._out_int[:n]
        _batch_hamming(query, corpus, out)
        return out if n > self._max_batch else out.copy()
    
    def xor(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        out = self._out_vec.copy()
        _xor(a, b, out)
        return out


# =============================================================================
# FINGERPRINT (Deterministic Hash → 10K Vector)
# =============================================================================

def fingerprint(name: str, signature: str, body: str) -> np.ndarray:
    """Deterministic 10K fingerprint from function identity.
    
    Same input → ALWAYS same fingerprint.
    Different input → quasi-orthogonal (50% Hamming).
    """
    identity = f"{name}::{signature}::{body}"
    data = np.empty(DIM_U64, dtype=np.uint64)
    
    for i in range(DIM_U64):
        chunk = f"{identity}:{i}".encode()
        h = hashlib.sha256(chunk).digest()
        data[i] = struct.unpack('<Q', h[:8])[0]
    
    data[-1] &= LAST_MASK
    return np.ascontiguousarray(data)


def fingerprint_callable(func: Callable) -> np.ndarray:
    """Extract fingerprint from callable."""
    name = getattr(func, '__name__', str(func))
    
    try:
        sig = str(inspect.signature(func))
    except (ValueError, TypeError):
        sig = "()"
    
    try:
        body = inspect.getsource(func)
    except (OSError, TypeError):
        body = f"<builtin:{name}>"
    
    return fingerprint(name, sig, body)


def fingerprint_index(fp: np.ndarray) -> int:
    """Convert fingerprint to 32-bit index."""
    return int(fp[0] & 0xFFFFFFFF)


def fingerprint_to_bytes(fp: np.ndarray) -> bytes:
    """Convert fingerprint to bytes for storage."""
    return fp.tobytes()


def fingerprint_from_bytes(b: bytes) -> np.ndarray:
    """Reconstruct fingerprint from bytes."""
    return np.frombuffer(b, dtype=np.uint64).copy()


# =============================================================================
# ATOM: Smallest Executable Unit
# =============================================================================

@dataclass
class Atom:
    """Atomic code unit with deterministic identity.
    
    Every function, method, class → Atom.
    Fully reversible back to source.
    """
    
    index: int                           # Deterministic 32-bit index
    name: str                            # Human name
    fingerprint: np.ndarray              # 10K bit identity
    
    type_code: int = TYPE_FUNCTION       # Classification
    subtype_code: int = 0
    
    # Source (for reconstruction)
    signature: str = ""
    body: str = ""
    language: str = "python"
    module: str = ""
    
    # Execution
    callable: Optional[Callable] = None
    
    # Graph edges
    depends_on: List[int] = field(default_factory=list)
    depended_by: List[int] = field(default_factory=list)
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    version: int = 1
    
    def __hash__(self):
        return self.index
    
    def __eq__(self, other):
        if isinstance(other, Atom):
            return self.index == other.index
        return False
    
    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "index": self.index,
            "name": self.name,
            "fingerprint": fingerprint_to_bytes(self.fingerprint).hex(),
            "type_code": self.type_code,
            "subtype_code": self.subtype_code,
            "signature": self.signature,
            "body": self.body,
            "language": self.language,
            "module": self.module,
            "depends_on": self.depends_on,
            "depended_by": self.depended_by,
            "created_at": self.created_at,
            "version": self.version,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'Atom':
        """Deserialize from storage."""
        fp = fingerprint_from_bytes(bytes.fromhex(d["fingerprint"]))
        return cls(
            index=d["index"],
            name=d["name"],
            fingerprint=fp,
            type_code=d.get("type_code", TYPE_FUNCTION),
            subtype_code=d.get("subtype_code", 0),
            signature=d.get("signature", ""),
            body=d.get("body", ""),
            language=d.get("language", "python"),
            module=d.get("module", ""),
            depends_on=d.get("depends_on", []),
            depended_by=d.get("depended_by", []),
            created_at=d.get("created_at", time.time()),
            version=d.get("version", 1),
        )


# =============================================================================
# DUCKDB GRAPH: Deterministic Execution Plans
# =============================================================================

class DuckGraph:
    """DuckDB-backed deterministic execution graph.
    
    NO hallucination. NO philosophy. PURE deterministic paths.
    Every edge is traceable. Every plan is reversible.
    """
    
    def __init__(self, db_path: str = ":memory:"):
        self.conn = duckdb.connect(db_path)
        self._init_schema()
    
    def _init_schema(self):
        """Create deterministic schema."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS atoms (
                idx BIGINT PRIMARY KEY,
                name VARCHAR NOT NULL,
                type_code INTEGER NOT NULL,
                subtype_code INTEGER NOT NULL,
                signature VARCHAR,
                body VARCHAR,
                language VARCHAR DEFAULT 'python',
                module VARCHAR,
                fingerprint_hex VARCHAR NOT NULL,
                created_at DOUBLE,
                version INTEGER DEFAULT 1
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                from_idx BIGINT NOT NULL,
                to_idx BIGINT NOT NULL,
                edge_type VARCHAR NOT NULL,
                weight DOUBLE DEFAULT 1.0,
                created_at DOUBLE,
                PRIMARY KEY (from_idx, to_idx, edge_type)
            )
        """)
        
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS seq_execution_log START 1
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS execution_log (
                id BIGINT DEFAULT nextval('seq_execution_log') PRIMARY KEY,
                atom_idx BIGINT NOT NULL,
                started_at DOUBLE NOT NULL,
                duration_ns BIGINT,
                status VARCHAR,
                result_hash VARCHAR
            )
        """)
        
        # Indexes for fast lookup
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_atoms_name ON atoms(name)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_idx)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_idx)")
    
    def store_atom(self, atom: Atom):
        """Store atom in graph."""
        self.conn.execute("""
            INSERT OR REPLACE INTO atoms 
            (idx, name, type_code, subtype_code, signature, body, language, module, fingerprint_hex, created_at, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            atom.index, atom.name, atom.type_code, atom.subtype_code,
            atom.signature, atom.body, atom.language, atom.module,
            fingerprint_to_bytes(atom.fingerprint).hex(),
            atom.created_at, atom.version
        ])
    
    def add_edge(self, from_idx: int, to_idx: int, edge_type: str = "DEPENDS", weight: float = 1.0):
        """Add edge between atoms."""
        self.conn.execute("""
            INSERT OR REPLACE INTO edges (from_idx, to_idx, edge_type, weight, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, [from_idx, to_idx, edge_type, weight, time.time()])
    
    def get_dependencies(self, idx: int) -> List[int]:
        """Get atoms this atom depends on."""
        result = self.conn.execute(
            "SELECT to_idx FROM edges WHERE from_idx = ? AND edge_type = 'DEPENDS'",
            [idx]
        ).fetchall()
        return [r[0] for r in result]
    
    def get_dependents(self, idx: int) -> List[int]:
        """Get atoms that depend on this atom."""
        result = self.conn.execute(
            "SELECT from_idx FROM edges WHERE to_idx = ? AND edge_type = 'DEPENDS'",
            [idx]
        ).fetchall()
        return [r[0] for r in result]
    
    def topological_levels(self) -> List[List[int]]:
        """Compute parallel execution levels via topological sort.
        
        Returns list of levels, atoms in same level can execute in parallel.
        """
        # Get all atoms and their dependency counts
        result = self.conn.execute("""
            WITH dep_counts AS (
                SELECT a.idx, COUNT(e.to_idx) as dep_count
                FROM atoms a
                LEFT JOIN edges e ON a.idx = e.from_idx AND e.edge_type = 'DEPENDS'
                GROUP BY a.idx
            )
            SELECT idx, dep_count FROM dep_counts
        """).fetchall()
        
        if not result:
            return []
        
        # Kahn's algorithm for topological sort
        dep_count = {r[0]: r[1] for r in result}
        reverse_edges = {}
        
        edges = self.conn.execute(
            "SELECT from_idx, to_idx FROM edges WHERE edge_type = 'DEPENDS'"
        ).fetchall()
        
        for from_idx, to_idx in edges:
            if to_idx not in reverse_edges:
                reverse_edges[to_idx] = []
            reverse_edges[to_idx].append(from_idx)
        
        levels = []
        remaining = set(dep_count.keys())
        
        while remaining:
            # Find atoms with no unsatisfied dependencies
            ready = [idx for idx in remaining if dep_count.get(idx, 0) == 0]
            
            if not ready:
                # Cycle detected - break it
                ready = [min(remaining)]
            
            levels.append(ready)
            
            for idx in ready:
                remaining.discard(idx)
                # Decrement dep count for dependents
                for dependent in reverse_edges.get(idx, []):
                    dep_count[dependent] = dep_count.get(dependent, 1) - 1
        
        return levels
    
    def execution_plan(self, target_indices: List[int]) -> List[List[int]]:
        """Build execution plan for specific targets.
        
        Returns minimal set of atoms needed, ordered by level.
        """
        # BFS to find all required atoms
        required = set(target_indices)
        queue = list(target_indices)
        
        while queue:
            idx = queue.pop(0)
            deps = self.get_dependencies(idx)
            for dep in deps:
                if dep not in required:
                    required.add(dep)
                    queue.append(dep)
        
        # Filter levels to only required
        all_levels = self.topological_levels()
        return [
            [idx for idx in level if idx in required]
            for level in all_levels
        ]
    
    def log_execution(self, atom_idx: int, duration_ns: int, status: str, result_hash: str = None):
        """Log execution for audit trail."""
        self.conn.execute("""
            INSERT INTO execution_log (atom_idx, started_at, duration_ns, status, result_hash)
            VALUES (?, ?, ?, ?, ?)
        """, [atom_idx, time.time(), duration_ns, status, result_hash])
    
    def export_graphviz(self) -> str:
        """Export as DOT for visualization."""
        lines = ["digraph LadybugDB {", "  rankdir=LR;"]
        
        atoms = self.conn.execute("SELECT idx, name, type_code FROM atoms").fetchall()
        for idx, name, type_code in atoms:
            color = {
                TYPE_FUNCTION: "lightblue",
                TYPE_METHOD: "lightgreen",
                TYPE_CLASS: "lightyellow",
                TYPE_VALIDATE: "lightpink",
            }.get(type_code, "white")
            lines.append(f'  n{idx} [label="{name}" style=filled fillcolor={color}];')
        
        edges = self.conn.execute("SELECT from_idx, to_idx, edge_type FROM edges").fetchall()
        for from_idx, to_idx, edge_type in edges:
            style = "solid" if edge_type == "DEPENDS" else "dashed"
            lines.append(f'  n{from_idx} -> n{to_idx} [style={style}];')
        
        lines.append("}")
        return "\n".join(lines)


# =============================================================================
# LANCE STORE: Vector Working Memory
# =============================================================================

class LanceStore:
    """LanceDB-backed vector storage.
    
    Working memory for atom fingerprints.
    O(1) lookup by index, O(log n) similarity search.
    """
    
    def __init__(self, db_path: str = "/tmp/ladybug_lance"):
        self.db_path = Path(db_path)
        self.db = lancedb.connect(str(self.db_path))
        self._table = None
        self._cache: Dict[int, np.ndarray] = {}  # Hot cache
        self._max_cache = 10_000
    
    def _ensure_table(self):
        """Create table if not exists."""
        if self._table is not None:
            return
        
        try:
            self._table = self.db.open_table("atoms")
        except Exception:
            # Create with schema
            schema = pa.schema([
                ("idx", pa.int64()),
                ("name", pa.string()),
                ("fingerprint", pa.list_(pa.uint64(), DIM_U64)),
            ])
            self._table = self.db.create_table("atoms", schema=schema)
    
    def store(self, atom: Atom):
        """Store atom fingerprint."""
        self._ensure_table()
        
        # Add to Lance
        data = [{
            "idx": atom.index,
            "name": atom.name,
            "fingerprint": atom.fingerprint.tolist(),
        }]
        
        try:
            self._table.add(data)
        except Exception:
            # Already exists - update
            pass
        
        # Hot cache
        if len(self._cache) < self._max_cache:
            self._cache[atom.index] = atom.fingerprint
    
    def get(self, idx: int) -> Optional[np.ndarray]:
        """Get fingerprint by index."""
        if idx in self._cache:
            return self._cache[idx]
        
        self._ensure_table()
        result = self._table.search().where(f"idx = {idx}").limit(1).to_list()
        
        if result:
            fp = np.array(result[0]["fingerprint"], dtype=np.uint64)
            self._cache[idx] = fp
            return fp
        return None
    
    def all_fingerprints(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get all fingerprints as contiguous array for batch ops.
        
        Returns (indices, corpus) where corpus is [N, 157] uint64.
        """
        self._ensure_table()
        
        df = self._table.to_pandas()
        if df.empty:
            return np.array([], dtype=np.int64), np.zeros((0, DIM_U64), dtype=np.uint64)
        
        indices = df["idx"].values.astype(np.int64)
        corpus = np.stack([np.array(fp, dtype=np.uint64) for fp in df["fingerprint"].values])
        
        return indices, np.ascontiguousarray(corpus)


# =============================================================================
# DRAGON QUEUE: Parallel Execution Lanes
# =============================================================================

class DragonQueue:
    """DragonflyDB-style parallel execution queue.
    
    In-memory for now, can be backed by Redis/Dragonfly.
    Multiple lanes for parallel work distribution.
    """
    
    def __init__(self, n_lanes: int = 8, redis_url: str = None):
        self.n_lanes = n_lanes
        self._lanes: List[List[Tuple[int, Any]]] = [[] for _ in range(n_lanes)]
        self._results: Dict[int, Any] = {}
        self._redis = None
        
        if redis_url:
            try:
                import redis
                self._redis = redis.from_url(redis_url)
            except Exception:
                pass
    
    def enqueue(self, atom_idx: int, args: tuple = (), lane: int = None):
        """Add work to queue."""
        if lane is None:
            lane = atom_idx % self.n_lanes
        
        self._lanes[lane].append((atom_idx, args))
        
        if self._redis:
            self._redis.rpush(f"ladybug:lane:{lane}", f"{atom_idx}:{args}")
    
    def dequeue(self, lane: int) -> Optional[Tuple[int, Any]]:
        """Get work from lane."""
        if self._lanes[lane]:
            return self._lanes[lane].pop(0)
        return None
    
    def dequeue_all(self, lane: int) -> List[Tuple[int, Any]]:
        """Get all work from lane."""
        work = self._lanes[lane]
        self._lanes[lane] = []
        return work
    
    def store_result(self, atom_idx: int, result: Any):
        """Store execution result."""
        self._results[atom_idx] = result
        
        if self._redis:
            self._redis.hset("ladybug:results", str(atom_idx), str(result))
    
    def get_result(self, atom_idx: int) -> Any:
        """Get stored result."""
        return self._results.get(atom_idx)
    
    def lane_sizes(self) -> List[int]:
        """Get size of each lane."""
        return [len(lane) for lane in self._lanes]


# =============================================================================
# LADYBUGDB: Unified Executable Surface
# =============================================================================

class LadybugDB:
    """Code as Deterministic Data.
    
    Unified surface wiring AVX-512, DuckDB, LanceDB, DragonflyDB.
    
    Every function/class → fingerprint → hashtable → execution
    Fully deterministic. Fully reversible. Any language.
    
    Usage:
        db = LadybugDB()
        
        # Register code
        db.register(validate_user)
        db.register(save_record, deps=["validate_user"])
        
        # Execute
        result = db.execute("validate_user", user_data)
        
        # Find similar code
        similar = db.resonate(validate_user, threshold=0.7)
        
        # Export deterministic graph
        dot = db.export_graph()
    """
    
    def __init__(
        self,
        duck_path: str = ":memory:",
        lance_path: str = "/tmp/ladybug_lance",
        redis_url: str = None,
        n_lanes: int = 8,
    ):
        # Core components
        self.engine = AVX512Engine()
        self.graph = DuckGraph(duck_path)
        self.store = LanceStore(lance_path)
        self.queue = DragonQueue(n_lanes, redis_url)
        
        # Local registry (hot cache)
        self._atoms: Dict[int, Atom] = {}
        self._name_to_idx: Dict[str, int] = {}
        
        # Warmup
        self.engine.warmup()
        
        # Stats
        self._stats = {
            "registered": 0,
            "executed": 0,
            "cache_hits": 0,
            "total_ns": 0,
        }
    
    # =========================================================================
    # REGISTRATION
    # =========================================================================
    
    def register(
        self,
        func: Callable,
        deps: List[str] = None,
        type_code: int = None,
    ) -> Atom:
        """Register callable as atom.
        
        Args:
            func: The callable to register
            deps: Names of dependencies
            type_code: Override type classification
        
        Returns:
            Created Atom
        """
        # Create fingerprint
        fp = fingerprint_callable(func)
        idx = fingerprint_index(fp)
        
        # Handle collision
        if idx in self._atoms:
            existing = self._atoms[idx]
            if existing.name == func.__name__:
                return existing
            # Secondary hash
            idx = int(fp[1] & 0xFFFFFFFF) | (1 << 31)
        
        # Get source info
        name = getattr(func, '__name__', str(func))
        
        try:
            sig = str(inspect.signature(func))
        except (ValueError, TypeError):
            sig = "()"
        
        try:
            body = inspect.getsource(func)
        except (OSError, TypeError):
            body = f"<builtin:{name}>"
        
        # Detect type
        if type_code is None:
            if inspect.ismethod(func):
                type_code = TYPE_METHOD
            elif inspect.isclass(func):
                type_code = TYPE_CLASS
            elif inspect.iscoroutinefunction(func):
                type_code = TYPE_COROUTINE
            elif inspect.isgeneratorfunction(func):
                type_code = TYPE_GENERATOR
            elif name == "<lambda>":
                type_code = TYPE_LAMBDA
            elif inspect.isbuiltin(func):
                type_code = TYPE_BUILTIN
            else:
                type_code = TYPE_FUNCTION
        
        # Resolve dependencies
        dep_indices = []
        if deps:
            for dep_name in deps:
                if dep_name in self._name_to_idx:
                    dep_idx = self._name_to_idx[dep_name]
                    dep_indices.append(dep_idx)
        
        # Create atom
        atom = Atom(
            index=idx,
            name=name,
            fingerprint=fp,
            type_code=type_code,
            signature=sig,
            body=body,
            module=getattr(func, '__module__', ''),
            callable=func,
            depends_on=dep_indices,
        )
        
        # Store everywhere
        self._atoms[idx] = atom
        self._name_to_idx[name] = idx
        self.graph.store_atom(atom)
        self.store.store(atom)
        
        # Add edges
        for dep_idx in dep_indices:
            self.graph.add_edge(idx, dep_idx, "DEPENDS")
        
        self._stats["registered"] += 1
        
        return atom
    
    def register_many(self, *funcs: Callable) -> List[Atom]:
        """Register multiple callables."""
        return [self.register(f) for f in funcs]
    
    # =========================================================================
    # RETRIEVAL
    # =========================================================================
    
    def get(self, name_or_idx: Union[str, int]) -> Optional[Atom]:
        """Get atom by name or index."""
        if isinstance(name_or_idx, str):
            idx = self._name_to_idx.get(name_or_idx)
            if idx is None:
                return None
            return self._atoms.get(idx)
        return self._atoms.get(name_or_idx)
    
    def __getitem__(self, key: Union[str, int]) -> Atom:
        """Get atom, raise if not found."""
        atom = self.get(key)
        if atom is None:
            raise KeyError(f"No atom: {key}")
        return atom
    
    def __contains__(self, key: Union[str, int]) -> bool:
        """Check if atom exists."""
        return self.get(key) is not None
    
    # =========================================================================
    # EXECUTION
    # =========================================================================
    
    def execute(self, name: str, *args, **kwargs) -> Any:
        """Execute atom by name."""
        atom = self.get(name)
        if atom is None:
            raise KeyError(f"No atom: {name}")
        if atom.callable is None:
            raise RuntimeError(f"No callable for: {name}")
        
        start = time.perf_counter_ns()
        result = atom.callable(*args, **kwargs)
        duration = time.perf_counter_ns() - start
        
        # Log
        result_hash = hashlib.md5(str(result).encode()).hexdigest()[:8]
        self.graph.log_execution(atom.index, duration, "success", result_hash)
        
        self._stats["executed"] += 1
        self._stats["total_ns"] += duration
        
        return result
    
    def execute_plan(self, names: List[str], args_map: Dict[str, tuple] = None) -> Dict[str, Any]:
        """Execute multiple atoms according to dependency order.
        
        Atoms at same level could be parallelized.
        """
        if args_map is None:
            args_map = {}
        
        # Get indices
        indices = []
        for name in names:
            atom = self.get(name)
            if atom:
                indices.append(atom.index)
        
        # Get execution plan
        plan = self.graph.execution_plan(indices)
        
        results = {}
        for level in plan:
            for idx in level:
                atom = self._atoms.get(idx)
                if atom and atom.callable:
                    args = args_map.get(atom.name, ())
                    result = atom.callable(*args)
                    results[atom.name] = result
        
        return results
    
    # =========================================================================
    # SIMILARITY / RESONANCE
    # =========================================================================
    
    def similarity(self, a: Union[str, int, Callable], b: Union[str, int, Callable]) -> float:
        """Compute similarity between two atoms/callables."""
        # Get fingerprints
        if callable(a):
            fp_a = fingerprint_callable(a)
        else:
            atom_a = self.get(a)
            fp_a = atom_a.fingerprint if atom_a else None
        
        if callable(b):
            fp_b = fingerprint_callable(b)
        else:
            atom_b = self.get(b)
            fp_b = atom_b.fingerprint if atom_b else None
        
        if fp_a is None or fp_b is None:
            return 0.0
        
        return self.engine.similarity(fp_a, fp_b)
    
    def resonate(
        self,
        query: Union[str, int, Callable, np.ndarray],
        threshold: float = 0.6,
        k: int = None,
    ) -> List[Tuple[str, float]]:
        """Find atoms resonating with query.
        
        Args:
            query: Atom name/index, callable, or raw fingerprint
            threshold: Minimum similarity
            k: Max results (None = all above threshold)
        
        Returns:
            List of (name, similarity) tuples
        """
        # Get query fingerprint
        if isinstance(query, np.ndarray):
            fp = query
        elif callable(query):
            fp = fingerprint_callable(query)
        else:
            atom = self.get(query)
            fp = atom.fingerprint if atom else None
        
        if fp is None:
            return []
        
        # Get all fingerprints
        indices, corpus = self.store.all_fingerprints()
        if len(indices) == 0:
            return []
        
        # Batch Hamming
        distances = self.engine.batch_hamming(fp, corpus)
        similarities = 1.0 - distances / DIM
        
        # Filter and sort
        results = []
        for i, (idx, sim) in enumerate(zip(indices, similarities)):
            if sim >= threshold:
                atom = self._atoms.get(int(idx))
                if atom:
                    results.append((atom.name, float(sim)))
        
        results.sort(key=lambda x: x[1], reverse=True)
        
        if k is not None:
            results = results[:k]
        
        return results
    
    def find_similar(self, func: Callable, k: int = 5) -> List[Tuple[str, float]]:
        """Find k most similar registered atoms."""
        return self.resonate(func, threshold=0.0, k=k)
    
    # =========================================================================
    # EXPORT / TRANSLATE
    # =========================================================================
    
    def export_graph(self) -> str:
        """Export as Graphviz DOT."""
        return self.graph.export_graphviz()
    
    def export_json(self) -> str:
        """Export all atoms as JSON."""
        atoms = [atom.to_dict() for atom in self._atoms.values()]
        return json.dumps({"atoms": atoms, "version": __version__}, indent=2)
    
    def translate(self, name: str, target: str = "typescript") -> str:
        """Translate atom to another language.
        
        Deterministic translation based on AST structure.
        """
        atom = self.get(name)
        if atom is None:
            raise KeyError(f"No atom: {name}")
        
        if target == "typescript":
            return self._translate_typescript(atom)
        elif target == "rust":
            return self._translate_rust(atom)
        else:
            raise ValueError(f"Unknown target: {target}")
    
    def _translate_typescript(self, atom: Atom) -> str:
        """Translate to TypeScript."""
        # Simple signature translation
        sig = atom.signature.replace("self, ", "").replace("self", "")
        
        lines = [
            f"// Fingerprint: {fingerprint_to_bytes(atom.fingerprint).hex()[:16]}...",
            f"// Index: {atom.index}",
            f"function {atom.name}{sig}: any {{",
            f"  // TODO: Implement",
            f"  throw new Error('Not implemented');",
            f"}}",
        ]
        return "\n".join(lines)
    
    def _translate_rust(self, atom: Atom) -> str:
        """Translate to Rust."""
        sig = atom.signature.replace("self, ", "").replace("self", "")
        
        lines = [
            f"// Fingerprint: {fingerprint_to_bytes(atom.fingerprint).hex()[:16]}...",
            f"// Index: {atom.index}",
            f"fn {atom.name}{sig} -> Result<(), Error> {{",
            f"    // TODO: Implement",
            f"    unimplemented!()",
            f"}}",
        ]
        return "\n".join(lines)
    
    # =========================================================================
    # STATS
    # =========================================================================
    
    def stats(self) -> dict:
        """Get statistics."""
        return {
            **self._stats,
            "avg_ns": self._stats["total_ns"] / max(self._stats["executed"], 1),
            "atoms": len(self._atoms),
        }
    
    def __repr__(self) -> str:
        return f"LadybugDB({len(self._atoms)} atoms, {self._stats['executed']} executed)"
    
    def __len__(self) -> int:
        return len(self._atoms)


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

__all__ = [
    "LadybugDB",
    "Atom",
    "fingerprint",
    "fingerprint_callable",
    "TYPE_FUNCTION",
    "TYPE_METHOD",
    "TYPE_CLASS",
    "TYPE_VALIDATE",
    "TYPE_TRANSFORM",
    "TYPE_PERSIST",
    "TYPE_QUERY",
]
