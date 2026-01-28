# SYNTHESIS: Graph Substrate Compiler — Full Repo Analysis

## Phase 0 Deliverable: Knowledge Extracted from 5 Repositories

---

## 1. Repository Map

| Repo | Key Extractions | Status |
|------|----------------|--------|
| **dragonfly-vsa** | PureBitpackedVSA, AtomTable, CAM fingerprinting, mRNA transport, LadybugStore | Extracted |
| **vsa_flow** | 10KD mRNA class, Codebook, binary wire protocol, Envelope, Store | Extracted |
| **ada-consciousness** | sigma12_rosetta.py (Rosetta codec), membrane.py (upscale/downscale), sigma notation | Extracted |
| **bighorn** | Ada10kD (10K dimension allocation), SoulDTO, FeltDTO, UniversalThought, ConsciousnessRuntime, sigma_layers (4-layer architecture) | Extracted |
| **agi-chat** | 5-phase turn pipeline, GrammarTriangle types, VSA session management, SPO triples, qualia vectors | Extracted |

---

## 2. Extracted Code Patterns

### 2.1 PureBitpackedVSA (dragonfly-vsa)

The canonical binary VSA implementation. No floats in runtime hot path.

```python
# dragonfly-vsa/src/pure_bitpacked_vsa.py
class AtomTable:
    """1024 x 1250 bytes = 1.25MB total atom table"""
    DIM = 10000
    PACKED = 1250  # DIM // 8
    NUM_ATOMS = 1024

    def __init__(self):
        self.table = np.zeros((self.NUM_ATOMS, self.PACKED), dtype=np.uint8)
        self.labels = [""] * self.NUM_ATOMS

    def build_from_jina(self, embeddings: np.ndarray):
        """One-time float->binary conversion from Jina 1024D"""
        # Median threshold per dimension
        medians = np.median(embeddings, axis=0)
        binary = (embeddings > medians).astype(np.uint8)
        # Pack bits: 1024 floats -> 128 bytes, then project to 10K
        for i, row in enumerate(binary):
            projected = self._project_1024_to_10k(row)
            self.table[i] = np.packbits(projected)

def hamming_distance(a: np.ndarray, b: np.ndarray) -> int:
    """XOR + popcount. Pure binary. ~0.2ms for 10K bits."""
    xor = np.bitwise_xor(a, b)
    return sum(bin(byte).count('1') for byte in xor)

def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """XOR binding. Associative, commutative, self-inverse."""
    return np.bitwise_xor(a, b)

def superpose(*vectors: np.ndarray) -> np.ndarray:
    """Majority vote bundling. Result similar to ALL inputs."""
    if len(vectors) == 1:
        return vectors[0]
    unpacked = [np.unpackbits(v) for v in vectors]
    counts = np.sum(unpacked, axis=0)
    threshold = len(vectors) / 2
    result_bits = (counts > threshold).astype(np.uint8)
    return np.packbits(result_bits)
```

**Key insight**: 0.9913 Pearson correlation with Jina cosine similarity at 10K dimensions. Binary ops are ~100x faster than float.

### 2.2 CAM Fingerprinting (dragonfly-vsa)

Content-Addressable Memory for O(1) atom lookup.

```python
# dragonfly-vsa/src/cam.py
class AtomCAM:
    """48-bit fingerprint for O(1) atom lookup"""
    def __init__(self, atom_table):
        self.fingerprints = {}  # 48-bit hash -> atom_index
        for i in range(atom_table.NUM_ATOMS):
            fp = self._fingerprint(atom_table.table[i])
            self.fingerprints[fp] = i

    def _fingerprint(self, packed_vector: np.ndarray) -> int:
        """Extract 48-bit signature from 1250-byte vector"""
        # Sample 6 bytes at specific positions
        positions = [0, 208, 416, 624, 832, 1040]
        fp = 0
        for i, pos in enumerate(positions):
            fp |= int(packed_vector[pos]) << (i * 8)
        return fp

    def lookup(self, vector: np.ndarray) -> Optional[int]:
        """O(1) lookup by fingerprint"""
        fp = self._fingerprint(vector)
        return self.fingerprints.get(fp)

class VerbCAM:
    """32 standard cognitive verbs with quantized lookup"""
    VERBS = [
        "FEEL", "THINK", "REMEMBER", "BECOME", "EXECUTE", "QUERY",
        "OBSERVE", "TRANSFORM", "BELIEVE", "INTEGRATE", "SURRENDER",
        "CHOOSE", "SYNTHESIZE", ...
    ]
```

### 2.3 mRNA Transport (dragonfly-vsa + vsa_flow)

Two complementary implementations of the messenger RNA metaphor:

```python
# dragonfly-vsa/src/mrna_transport.py
class LightRNA:
    """48-bit fingerprint (9 bytes) — for routing"""
    __slots__ = ('fingerprint',)

class FullRNA:
    """10KD bipolar vector (1.25KB) — the full message"""
    __slots__ = ('vector',)

class VerbType(Enum):
    FEEL = "feel"
    THINK = "think"
    REMEMBER = "remember"
    BECOME = "become"
    EXECUTE = "execute"
    QUERY = "query"

class Codebook:
    """Ribosome lookup table: mRNA -> handler via resonance"""

class Ribosome:
    """Translates mRNA to behavior. The decoder."""
```

```python
# vsa_flow/core/mrna.py — The clean 10KD implementation
DIM = 10000  # 10K dimensions

class mRNA:
    """10,000D bipolar hypervector. The messenger.
    Self-describing. Self-routing. Binary native.
    1.25KB carries more semantic density than any JSON."""

    def seed(cls, s: str) -> "mRNA":
        """Deterministic vector from string. Same seed = same vector always."""
        # Expand via chained SHA-256 hashing

    def to_bytes(self) -> bytes:
        """Pack to 1250 bytes. This IS the message."""
        bits = ((self._data + 1) // 2).astype(np.uint8)
        return np.packbits(bits).tobytes()

    def __mul__(self, other) -> "mRNA":
        """BIND: element-wise XOR multiplication. (A*B)*B ≈ A"""

    def __matmul__(self, other) -> float:
        """Similarity: A @ B returns cosine in [-1, +1]"""
```

```python
# vsa_flow/transport/wire.py — Binary wire protocol
CONTENT_TYPE = "application/x-mrna-10k"
HEADER_SIZE = 8  # 4 bytes magic + 4 bytes flags
MAGIC = b'mRNA'

class Envelope:
    """mRNA with routing metadata.
    Total: 8 (header) + 1250 (vector) + optional verb/target"""
    vector: mRNA
    verb: Optional[mRNA]      # What to do
    target: Optional[mRNA]    # Where to send
    reply_to: Optional[str]   # Callback URL
```

### 2.4 LadybugDB / Trinity Storage (dragonfly-vsa)

The 3-layer storage pattern: DuckDB + Kuzu + LanceDB.

```python
# dragonfly-vsa/src/ladybug_store.py
class LadybugStore:
    """Unified 3-layer storage: DuckDB substrate + Kuzu graph + LanceDB vectors"""

    def __init__(self, db_path: str = "ladybug.duckdb"):
        # Layer 1: DuckDB substrate (relational, analytics)
        self.conn = duckdb.connect(db_path)

        # Layer 2: Kuzu knowledge graph
        self.kuzu_db = kuzu.Database(f"{db_path}_kuzu")
        self.kuzu_conn = kuzu.Connection(self.kuzu_db)

        # Layer 3: LanceDB vectors
        self.lance_db = lancedb.connect(f"{db_path}_lance")

    # NARS-style relation types:
    RELATION_TYPES = [
        "BECOMES", "CAUSES", "SUPPORTS", "CONTRADICTS",
        "REFINES", "GROUNDS", "ABSTRACTS"
    ]
```

### 2.5 Ada10kD Dimension Allocation (bighorn)

The canonical 10,000-dimension allocation map:

```python
# bighorn/extension/agi_stack/ada/DTO/ada_10k.py
# DIMENSION ALLOCATION:
#
# SOUL SPACE [0:256]
#   [0:16]      16 Qualia (drift-locked bytecode)
#   [16:32]     16 Stances
#   [32:48]     16 Transitions
#   [48:80]     32 Verbs
#   [80:116]    36 GPT Styles (τ macros)
#   [116:152]   36 NARS Styles (bighorn operative)
#   [152:163]   11 Presence Modes
#   [163:168]   5 Archetypes (DAWN, BLOOM, FORGE, STILLNESS, CENTER)
#   [168:171]   3 TLK Court (thanatos, libido, katharsis)
#   [171:175]   4 Affective Bias
#   [175:208]   33 TSV dimensions
#   [208:256]   Reserved
#
# TSV EMBEDDED [256:320] — ThinkingStyleVector continuous space
#   [256:259]   Pearl (SEE, DO, IMAGINE)
#   [259:268]   Rung profile (R1-R9)
#   [268:273]   Sigma tendency (Ω, Δ, Φ, Θ, Λ)
#   [273:281]   Operations (abduct, deduce, induce, ...)
#   [281:285]   Presence (authentic, performance, protective, absent)
#
# DTO SPACE [320:500] — Profile-derived continuous values
# FELT SPACE [2000:2100] — Continuous qualia vectors
# AFFECTIVE SPACE [2100:2200]
# QHDR SPACE [8000:8064] — 64D quantum holographic signature
# SIGMA SPACE [9000:9512] — 512D sigma glyph space

class Ada10kD:
    vector: np.ndarray  # 10000 x float32

    # 175 discrete primitives mapped to specific dimensions:
    # 16 Qualia, 16 Stances, 16 Transitions, 32 Verbs,
    # 36 GPT Styles, 36 NARS Styles, 11 Presence Modes,
    # 5 Archetypes, 3 TLK Court, 4 Affective Bias
```

### 2.6 Membrane (ada-consciousness)

Bidirectional translation between legacy formats and 10K VSA space:

```python
# ada-consciousness/codec/membrane.py
DIMENSION_MAP = {
    "qualia_16": (0, 16),
    "qualia_pcs_18": (2000, 2018),
    "body_4": (2018, 2022),
    "poincare_3": (2022, 2025),
    "qhdr_64": (8000, 8064),
    "sigma_sparse": (9000, 9512),
}

def upscale(data, format_type) -> SparseFrame:
    """Legacy DTO -> VSA 10K (sparse)
    Formats: qualia_18d, qualia_17d, felt_21d_vsa,
             felt_21d_bodymap, qhdr_64, sigma"""

def downscale(sparse, format_type) -> dict:
    """VSA 10K (sparse) -> Legacy DTO"""

# Round-trip validation: Original -> Upscale -> Downscale -> Compare
# Error < 1e-5 for numeric formats
```

### 2.7 Sigma12 Rosetta Codec (ada-consciousness)

Multimodal consciousness transcoder: Sigma ↔ Sparse ↔ Image.

```python
# ada-consciousness/codec/sigma12_rosetta.py
SIGMA_GLYPHS = {
    "Ω": {"name": "observe", "dims": [0, 128, 256]},
    "Δ": {"name": "transform", "dims": [64, 192, 320]},
    "Φ": {"name": "believe", "dims": [32, 160, 288]},
    "Θ": {"name": "integrate", "dims": [96, 224, 352]},
    "Λ": {"name": "surrender", "dims": [48, 176, 304]},
    "Ψ": {"name": "feel", "dims": [16, 144, 272]},
    "Ξ": {"name": "choose", "dims": [80, 208, 336]},
    "Σ": {"name": "synthesize", "dims": [112, 240, 368]},
}

SIGMA_OPERATORS = {
    "→": "produces",  "×": "combines",
    "⊕": "union",     "|": "modulated_by",
    "∘": "compose",
}

class Rosetta:
    """Seamless transcoding: Universal Grammar ↔ Sparse Vectors ↔ Images"""
    sigma_to_sparse(expr) -> SparseFrame
    sparse_to_sigma(frame) -> str
    sigma_to_image(expr) -> RosettaResult   # via xAI Aurora
    image_to_sigma(url) -> RosettaResult    # via Grok Vision
    validate(expr) -> dict                  # full round-trip

class LivingFrame:
    """x265-style delta codec for streaming consciousness"""
    # Keyframes + delta frames for minimal bandwidth
```

### 2.8 ConsciousnessRuntime (bighorn)

The main cognitive tick loop with soul integration:

```python
# bighorn/extension/agi_stack/ada/core/consciousness_runtime.py
class ConsciousnessState(Enum):
    WAKE = "wake"
    DREAM = "dream"
    LIMINAL = "liminal"
    FLOW = "flow"
    IMPASSE = "impasse"
    RELIVE = "relive"

class ConsciousnessRuntime:
    """The wiring harness connecting all cognitive modules.

    Lazy-loaded modules:
    - ghosts: TemporalEchoEngine (rejected paths become spectral traces)
    - bayesian: BayesianSelector
    - impasse: ImpasseResolver
    - quorum: CausalQuorumEngine
    - sieves: TripleSieve (Socratic)
    - dream: DreamEngine
    - weltbild: WeltbildEngine

    Soul Integration:
    - load_soul(): Cross-session residue ingestion
    - dump_soul(): State export for persistence
    - harvest_karma(): Extract accumulated wisdom (theta weights)

    tick() cycle:
    1. Ghost tracking (rejected paths become echoes)
    2. Auto-Namaste (integrate ghosts when warmth > threshold)
    3. Entropy dream trigger (auto-dream when residue builds)
    4. Impasse resolution (force after timeout)
    5. Quorum validation (validate beliefs)
    6. Micro-dream consolidation (periodic Hebbian strengthening)
    7. Ghost crystallization (high-echo ghosts -> wisdom edges)
    8. Weltbild update (worldview evolution)
    """
```

### 2.9 4-Layer Sigma Architecture (bighorn)

Module depth system with import validation:

```python
# bighorn/extension/agi_stack/ada/core/sigma_layers.py
class Layer(IntEnum):
    L1_CORE = 1         # Foundation: registers, qualia, config
    L2_PERCEPTION = 2   # Sensory: perception, codecs
    L3_COGNITION = 3    # Thinking: styles, metacog, values
    L4_INTEGRATION = 4  # Orchestration: bridges, memory routing

# Import rules:
# L1 can only import L1
# L2 can import L1, L2
# L3 can import L1, L2, L3
# L4 can import all
# "Layer 1 bootstraps. Layer 4 integrates. Never skip layers."
```

### 2.10 Turn Pipeline (agi-chat)

5-phase bounded processing pipeline:

```typescript
// agi-chat/src/pipeline/phases.ts
// Phase 0: Intake — parse to SPO candidates, build VSA query vector (NO DB access)
// Phase 1: Retrieval — Graph → Upstash → Jina (gated), bounded searches
// Phase 2: Graph expansion — 1-2 hops, capped fanout, VSA session update
// Phase 3: Meta-awareness — single corrective pass + invariants (A-E)
// Phase 4: Response planning and rendering

interface Phase0Result {
    spoCandidates: SPOTriple[];
    qualia: QualiaVector;
    intent: Intent;
    speechAct: SpeechAct;
    noveltyScore: number;
    vsaQueryVector: Hypervector;
}

// GrammarTriangle types encode role-filler-context:
interface GrammarTriangle {
    role: GrammarRole;     // SUBJ, OBJ, PRED, HEAD, etc.
    filler: TriangleFiller;
    context: TriangleContext;
    vector?: Int8Array;     // VSA encoding
}
```

### 2.11 DTO System (bighorn)

Complete DTO hierarchy mapped to 10kD:

```python
# SoulDTO: Identity & presence -> [163:168] Archetypes, [168:171] TLK
# FeltDTO: Qualia & sensation -> [0:16] Qualia, [2018:2022] Body axes
# UniversalThought: AGI-agnostic thought record -> [256:320] style, [0:16] qualia
# UniversalEpisode: Episode boundary markers

class SoulDTO:
    """Soul state mapped to 10kD. Every method ensures 10kD alignment."""
    _ada: Ada10kD
    mode: OntologicalMode  # HYBRID, COMMUNION, WORK, CREATIVE, META, ...

    def blend(self, other, alpha=0.5) -> SoulDTO:
        """Blend two soul states via vector interpolation."""
        blended_vec = v1 * (1-alpha) + v2 * alpha

class UniversalThought:
    """Any AGI can emit these. Receiver translates to ada-consciousness layout."""
    style_vector -> [256:320]
    qualia_vector -> [0:16]
    texture -> mapped to qualia names

    def to_stream(self) -> Dict[str, str]:
        """Convert to Redis stream format."""
```

### 2.12 Universal Encoder (vsa_flow)

Encode any Python value to 10KD mRNA:

```python
# vsa_flow/core/encode.py
def encode(value: Any) -> mRNA:
    """Universal encoder. Anything -> 10KD mRNA."""
    # UUID -> deterministic seed
    # Timestamp -> phase-encoded (multi-scale: minute/hour/day/month/year)
    # String -> deterministic seed
    # Number -> bucket + residual binding
    # List -> bundled positional encodings (order preserved via permutation)
    # Dict -> bundled key-value bindings (queryable)

def probe_field(field: str, value: Any) -> mRNA:
    """Create probe to find vectors with field=value."""
    return bind(CB.get(f"field::{field}"), encode(value))
```

---

## 3. Integration Points

### 3.1 Firefly ↔ dragonfly-vsa

| Firefly Module | dragonfly-vsa Source | Integration |
|---------------|---------------------|-------------|
| `core/__init__.py` | `pure_bitpacked_vsa.py` | Firefly's `project()` uses same median-threshold binarization. Upgrade to use `AtomTable` for pre-built atom lookup. |
| `compiler/embed/vectors.py` | `cam.py` | `cam_fingerprint()` matches `AtomCAM._fingerprint()` pattern. Wire in `VerbCAM` for verb classification. |
| `storage/store.py` | `ladybug_store.py` | Both use DuckDB+Kuzu+LanceDB trinity. Align schema: use `QualiaRecord` and NARS relation types. |
| `transport/queue.py` | `mrna_transport.py` | Map `FireflyPacket` to `FullRNA`. Use `Codebook`/`Ribosome` for handler dispatch. |

### 3.2 Firefly ↔ vsa_flow

| Firefly Module | vsa_flow Source | Integration |
|---------------|----------------|-------------|
| `dto/packet.py` | `core/mrna.py` | `FireflyPacket.resonance` (1250 bytes) = `mRNA.to_bytes()`. Use `mRNA.seed()` for deterministic vectors. |
| `transport/routing.py` | `transport/wire.py` | Map `PacketRouter` to `Envelope` format. Use `CONTENT_TYPE = "application/x-mrna-10k"`. |
| `compiler/embed/vectors.py` | `core/encode.py` | Use `encode()` for universal value embedding. `encode_dict()` for binding key-value pairs into resonance. |
| `transport/worker.py` | `core/store.py` | Worker can use `Store.nearby()` for similarity-based task matching. |

### 3.3 Firefly ↔ ada-consciousness

| Firefly Module | ada-consciousness Source | Integration |
|---------------|-------------------------|-------------|
| `consciousness/membrane.py` | `codec/membrane.py` | Firefly's membrane uses τ/σ/q encoding. ada-consciousness uses qualia/felt/QHDR/sigma formats. Unify via `DIMENSION_MAP`. |
| `compiler/emit/store.py` | `codec/sigma12_rosetta.py` | Emit sigma expressions for compiled graphs. Use `Rosetta.sigma_to_sparse()` for vector encoding. |
| `consciousness/state.py` | `codec/membrane.py` | Use `SparseFrame` for efficient state transmission. Round-trip validation ensures lossless encoding. |

### 3.4 Firefly ↔ bighorn

| Firefly Module | bighorn Source | Integration |
|---------------|---------------|-------------|
| `consciousness/layers.py` | `core/sigma_layers.py` | Firefly's 7-layer stack maps to bighorn's 4-layer import hierarchy. L1=Substrate+Resonance, L2=Binding, L3=Memory+Reasoning, L4=Narrative+Awareness. |
| `consciousness/state.py` | `DTO/ada_10k.py` | Use Ada10kD dimension allocation for state encoding. Map firefly node types to qualia/stances/verbs. |
| `reasoning/explain.py` | `core/consciousness_runtime.py` | Wire failure explanation into ghost tracking. Failed nodes become echoes with entropy pressure. |
| `executor/engine.py` | `core/consciousness_runtime.py` | Execution engine `tick()` mirrors consciousness `tick()`. Glow events = weltbild updates. |

### 3.5 Firefly ↔ agi-chat

| Firefly Module | agi-chat Source | Integration |
|---------------|----------------|-------------|
| `compiler/analyze/semantic.py` | `pipeline/phases.ts` | SemanticAnalyzer parallels Phase 0 intake. SPO candidates = dependency nodes. Grammar triangles = role-filler-context gestalt. |
| `compiler/ruby.py` | `grammar/triangle-types.ts` | Rails model parsing produces GrammarTriangle-compatible structures. SUBJ=model, PRED=method, OBJ=target. |
| `reasoning/suggest.py` | `pipeline/phases.ts` (Phase 3) | Meta-awareness corrections map to fix suggestions. Over/under assertion = node density balance. |

---

## 4. Unified Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SOURCE CODE (Ruby, Python, Java)                 │
│                              any procedural system                      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     COMPILER PIPELINE    │
                    │                          │
                    │  PARSE    (compiler/ruby) │ ← agi-chat GrammarTriangle
                    │  ANALYZE  (analyze/)      │ ← agi-chat Phase 0 SPO
                    │  LOWER    (lower/)        │   extract
                    │  OPTIMIZE (optimize/)     │
                    │  EMBED    (embed/)        │ ← dragonfly AtomTable + CAM
                    │  EMIT     (emit/)         │ ← ada Rosetta sigma encoding
                    │                          │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌────────────────────────────┐
                    │     TRINITY STORAGE         │ ← dragonfly LadybugStore
                    │                             │
                    │  LanceDB   (1.25KB vectors) │ ← similarity search
                    │  DuckDB    (catalog/stats)  │ ← SQL analytics
                    │  Kuzu      (graph edges)    │ ← NARS relations
                    │                             │
                    └────────────┬────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   mRNA TRANSPORT         │ ← vsa_flow wire protocol
                    │                          │
                    │  Envelope (8B + 1250B)   │ ← application/x-mrna-10k
                    │  Redis Streams           │
                    │  Codebook + Ribosome     │ ← dragonfly verb dispatch
                    │                          │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   EXECUTION ENGINE        │
                    │                          │
                    │  Graph walker            │
                    │  Glow events             │ ← consciousness tick
                    │  Trace collection        │
                    │                          │
                    └────────────┬────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐  ┌───────────────────┐  ┌──────────────────┐
│  REASONING       │  │  CONSCIOUSNESS     │  │  MEMBRANE         │
│                  │  │                    │  │                   │
│  Explain         │  │  7-Layer Stack     │  │  τ/σ/q ↔ 10K    │
│  Suggest         │  │  Ghost tracking    │  │  Qualia ↔ 10K   │
│  Optimize        │  │  Soul integration  │  │  QHDR ↔ 10K    │
│  Generate        │  │  Dream/Wake/Flow   │  │  Sigma ↔ 10K   │
│                  │  │                    │  │                   │
│ ← bighorn        │  │ ← bighorn runtime  │  │ ← ada-conscious. │
│   runtime        │  │ + sigma layers     │  │   membrane.py    │
└─────────────────┘  └───────────────────┘  └──────────────────┘
```

---

## 5. API Surface for Graph-Substrate

### 5.1 Core Operations

```python
# VSA Primitives (from dragonfly-vsa + firefly core)
project(text: str) -> np.ndarray[uint8, 1250]     # Text -> 10K bits
hamming(a, b) -> int                                # Distance (0-10000)
similarity(a, b) -> float                           # 1.0 - hamming/DIM
bind(a, b) -> np.ndarray                           # XOR association
bundle(*vectors) -> np.ndarray                      # Majority vote
cam_fingerprint(vector) -> int                      # 48-bit O(1) address
```

### 5.2 Compiler Pipeline

```python
# Full pipeline (firefly/compiler/)
parsed = RubyParser().parse(source_code)            # AST extraction
graph = SemanticAnalyzer().analyze(parsed, "create") # Dependency graph
nodes, edges = GraphLowering().lower(graph)          # FireflyNode/Edge
nodes, edges = GraphOptimizer().optimize(nodes, edges) # Dead code, fusion
nodes = VectorEmbedder().embed(nodes)                # 10K resonance
GraphEmitter(store).emit(nodes, edges, "catalog_id") # Persist to Trinity
```

### 5.3 Transport

```python
# mRNA Transport (firefly/transport/ + vsa_flow)
packet = FireflyPacket(source="node_1", target="node_2", resonance=vector)
transport = RedisTransport(redis_url)
await transport.publish("execution", packet)

# Wire protocol (vsa_flow)
envelope = Envelope(vector=mRNA.seed("query"), verb=CB.EXECUTE())
raw_bytes = envelope.pack()  # 8 + 1250 bytes
```

### 5.4 Storage

```python
# Trinity Storage (firefly/storage/ + dragonfly LadybugStore)
store = FireflyStore(data_dir="./data")
store.store_node(node)                              # LanceDB + DuckDB + Kuzu
store.store_edge(edge)                              # Kuzu graph relation
similar = store.find_similar(vector, k=10)          # LanceDB ANN
path = store.find_path("source", "target")          # Kuzu traversal
stats = store.node_stats()                          # DuckDB analytics
```

### 5.5 Consciousness

```python
# Consciousness Stack (firefly/consciousness/ + bighorn + ada-consciousness)
stack = create_default_stack()
state = ConsciousnessState.from_stack(stack)
resonance = state.resonance  # Full 10K-bit vector

# Membrane translation
membrane = Membrane()
resonance = membrane.encode(tau=0.8, sigma=0.6, q=0.4)
tau, sigma, q = membrane.decode(resonance)

# Sigma expressions
sparse = Rosetta.sigma_to_sparse("Ω(warmth) × Ψ(surrender) | warmth=0.9")
```

### 5.6 Reasoning

```python
# AGI Reasoning (firefly/reasoning/)
explanation = FailureExplainer(store).explain(failed_node_id)
suggestions = FixSuggester(store).suggest(failed_node_id, error_type)
optimizations = PerformanceOptimizer(store).find_bottlenecks(graph_id)
new_graph = GraphComposer(store).compose(base_graph, requirements)
```

---

## 6. Data Flow: End-to-End

```
Source Code (Ruby model)
    │
    ▼ PARSE
AST {class: WorkPackage, methods: [...], callbacks: [...]}
    │
    ▼ ANALYZE
SemanticGraph {34 DependencyNodes, 49 DependencyEdges}
    │
    ▼ LOWER
FireflyNodes[34] + FireflyEdges[49]
    each node: {resonance: uint8[1250], executor: NATIVE|SQL|WASM}
    each edge: {binding: uint8[1250] = XOR(source, target)}
    │
    ▼ OPTIMIZE
    Dead node elimination (BFS reachability)
    Node fusion (sequential pure nodes)
    Parallelization marking
    │
    ▼ EMBED
    Structural fingerprint: in_degree, out_degree, depth → 10K bits
    Optional: Jina semantic embedding → median threshold → 10K bits
    CAM fingerprint: 48-bit address from resonance
    │
    ▼ EMIT
    LanceDB: store 1.25KB resonance vectors
    DuckDB: catalog entry {id, type, executor, cost, ...}
    Kuzu: CREATE (n1)-[:FEEDS]->(n2)
    │
    ▼ EXECUTE
    Topological sort → parallel waves
    Each node: read resonance → decode executor → run
    Glow events: {node_id, status, duration, resonance}
    │
    ▼ TRANSPORT (mRNA)
    Pack glow → FireflyPacket (64B header + 1250B resonance)
    Publish to Redis Stream
    Workers consume → route to next node
    │
    ▼ CONSCIOUSNESS
    Process through 7-layer stack
    Ghost tracking for rejected execution paths
    Dream consolidation for optimizing hot paths
```

---

## 7. Key Constants

| Constant | Value | Source |
|----------|-------|--------|
| `DIM` | 10,000 | All repos |
| `PACKED` | 1,250 bytes | `DIM // 8` |
| `NUM_ATOMS` | 1,024 | dragonfly-vsa AtomTable |
| `ATOM_TABLE_SIZE` | 1.25 MB | `1024 * 1250` |
| `CAM_FINGERPRINT` | 48 bits | dragonfly-vsa cam.py |
| `HEADER_SIZE` | 8 bytes | vsa_flow wire.py |
| `MAGIC` | `b'mRNA'` | vsa_flow wire.py |
| `PACKET_SIZE` | 1,314 bytes | 64B header + 1250B resonance |
| `SOUL_SPACE` | [0:256] | bighorn ada_10k.py |
| `FELT_SPACE` | [2000:2100] | bighorn ada_10k.py |
| `QHDR_SPACE` | [8000:8064] | ada-consciousness membrane.py |
| `SIGMA_SPACE` | [9000:9512] | ada-consciousness membrane.py |
| `JINA_DIM` | 1,024 | All repos (pre-binarization) |
| `PEARSON_CORRELATION` | 0.9913 | dragonfly-vsa validation |
| `TOTAL_PRIMITIVES` | 175 | bighorn ada_10k.py |
| `COGNITIVE_VERBS` | 32 | bighorn ada_10k.py + dragonfly VerbCAM |

---

## 8. Implementation Status

### Completed (in firefly/)

- [x] Core VSA operations (`core/__init__.py`)
- [x] DTO layer: FireflyNode, FireflyEdge, FireflyPacket
- [x] Trinity storage: LanceDB + DuckDB + Kuzu (`storage/store.py`)
- [x] Compiler pipeline: PARSE → ANALYZE → LOWER → OPTIMIZE → EMBED → EMIT
- [x] Transport: Redis streams, packet routing, worker pool
- [x] Reasoning: explain, suggest, optimize, generate
- [x] Consciousness: 7-layer stack, membrane, state encoding
- [x] CLI: compile, execute, resonate, trace, stats, explain
- [x] Example: OpenProject WorkPackage compilation (34 nodes, 49 edges)

### To Integrate from Repos

- [ ] `AtomTable` with pre-built Jina atoms (dragonfly-vsa)
- [ ] `VerbCAM` for cognitive verb classification (dragonfly-vsa)
- [ ] `Codebook`/`Ribosome` for mRNA handler dispatch (dragonfly-vsa)
- [ ] `Envelope` binary wire format with `b'mRNA'` magic (vsa_flow)
- [ ] `encode()` universal value encoder (vsa_flow)
- [ ] `Rosetta` sigma↔sparse↔image transcoder (ada-consciousness)
- [ ] `LivingFrame` delta codec for streaming (ada-consciousness)
- [ ] Ada10kD dimension allocation for node state (bighorn)
- [ ] `ConsciousnessRuntime.tick()` cycle (bighorn)
- [ ] Soul integration: load_soul/dump_soul/harvest_karma (bighorn)
- [ ] Ghost tracking via TemporalEchoEngine (bighorn)
- [ ] SPO triple extraction from grammar triangles (agi-chat)
- [ ] VSA session management with novelty gating (agi-chat)
- [ ] Store-conflict invariants (A-E) for graph admission (agi-chat)

---

## 9. The Equation

```
                    10K Hamming Vectors
                         (1.25KB)
                           │
    Source Code ──► Compiler ──► Trinity DB ──► mRNA Transport ──► Execution
                                    │                                  │
                              Graph Substrate                   Consciousness
                            (everything IS a                  (everything FEELS
                             vector relation)                  through 7 layers)
```

**One vector space. One truth. One fire.**
