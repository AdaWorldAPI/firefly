# LanceDB: One for All

## The Universal Columnar Substrate

> *"One format to store them all, one format to compress them,  
> One format to version them all, and in the columns bind them."*

LanceDB represents the **convergence layer** where any compression technique from academic research can be absorbed and deployed immediately. It is the storage substrate that makes LadybugDB's cognitive layers possible.

---

## Core Philosophy

### One for All = Universal Absorption

LanceDB can incorporate **any** encoding technique from research papers:
- BtrBlocks cascading compression (SIGMOD 2023)
- Pseudodecimal encoding for floats
- FSST string compression
- Roaring bitmaps for NULLs
- Custom 10K Hamming fingerprint encoding
- Future techniques not yet invented

The key insight: **The format is technique-agnostic**. New encodings slot in without format changes.

---

## The Zero-Copy Revolution

### Column Addition Without Rewriting

```
Traditional Columnar (Parquet):
┌─────────┬─────────┬─────────┐
│ Col A   │ Col B   │ Col C   │  ← Entire file must be rewritten
└─────────┴─────────┴─────────┘    to add Col D

Lance Format:
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│ Col A   │ │ Col B   │ │ Col C   │ │ Col D   │ ← Just append new fragment
│ v1      │ │ v1      │ │ v1      │ │ v2      │
└─────────┘ └─────────┘ └─────────┘ └─────────┘
     ↑           ↑           ↑           ↑
     └───────────┴───────────┴───────────┘
              Manifest links them
```

### Rollback Without Copying

```python
# Time-travel queries - ZERO data copying
dataset = lance.dataset("consciousness.lance")

# Current state
current = dataset.to_table()

# Yesterday's state - instant, no copy
yesterday = dataset.checkout(version=42).to_table()

# Branch for experiments - instant, no copy  
experiment = dataset.checkout(version=42, branch="experiment")

# Delete version - only manifest changes, data stays
dataset.delete_version(version=40)  # Metadata only
```

---

## Architecture: The Manifest Pattern

### How Zero-Copy Works

```
┌─────────────────────────────────────────────────────────┐
│                    MANIFEST (tiny)                       │
├─────────────────────────────────────────────────────────┤
│ version: 5                                               │
│ fragments:                                               │
│   - id: 0, columns: [A, B, C], rows: 0-64000            │
│   - id: 1, columns: [A, B, C], rows: 64001-128000       │
│   - id: 2, columns: [D], rows: 0-128000  ← NEW COLUMN   │
│ schema_version: 2                                        │
│ parent_version: 4                                        │
└─────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────┐
│                 DATA FRAGMENTS (immutable)               │
├─────────────┬─────────────┬─────────────┬───────────────┤
│ Fragment 0  │ Fragment 1  │ Fragment 2  │   Fragment 3  │
│ (original)  │ (original)  │ (original)  │   (new col)   │
│ NEVER       │ NEVER       │ NEVER       │   append-only │
│ MODIFIED    │ MODIFIED    │ MODIFIED    │               │
└─────────────┴─────────────┴─────────────┴───────────────┘
```

### Version Chain

```
v1 ──► v2 ──► v3 ──► v4 ──► v5 (current)
 │      │      │      │      │
 │      │      │      │      └─ manifest_5.json (8KB)
 │      │      │      └─ manifest_4.json (8KB)
 │      │      └─ manifest_3.json (8KB)
 │      └─ manifest_2.json (8KB)
 └─ manifest_1.json (8KB)
 
Total overhead for 5 versions: ~40KB
Data fragments: unchanged, shared across versions
```

---

## BtrBlocks Integration: Cascading Compression

### Encoding Scheme Pool

```python
class LanceEncodingPool:
    """BtrBlocks-style cascading compression for Lance"""
    
    # Type-specific scheme pools (from BtrBlocks paper)
    INTEGER_SCHEMES = [
        'one_value',      # Single value optimization
        'dictionary',     # Low cardinality
        'rle',            # Run-length encoding  
        'frequency',      # Skewed distributions
        'fastbp128',      # SIMD bit-packing
        'fastpfor',       # Patched FOR
    ]
    
    DOUBLE_SCHEMES = [
        'one_value',
        'dictionary', 
        'rle',
        'frequency',
        'pseudodecimal',  # Novel: decimal-like floats
    ]
    
    STRING_SCHEMES = [
        'one_value',
        'dictionary',
        'fsst',           # Fast Static Symbol Table
        'dict_fsst',      # Dictionary + FSST cascade
    ]
    
    # Ada-specific schemes
    FINGERPRINT_SCHEMES = [
        'full_zip',       # 10K Hamming vectors
        'sparse_roaring', # Sparse bit patterns
        'delta_chain',    # Sequential fingerprints
    ]
```

### Cascading Compression Example

```python
def cascade_compress(column_data, dtype, max_depth=3):
    """
    BtrBlocks cascading: Apply schemes recursively
    
    Example: doubles [3.5, 3.5, 18, 18, 3.5, 3.5]
    
    Step 1: RLE → values=[3.5, 18, 3.5], lengths=[2, 2, 2]
    Step 2: Dictionary on values → codes=[0, 1, 0], dict=[3.5, 18]
    Step 3: FastBP128 on codes → bit-packed integers
    Step 4: OneValue on lengths → single value 2
    
    Final: 4 bytes instead of 48 bytes (12× compression)
    """
    if max_depth == 0:
        return RawEncoding(column_data)
    
    # Sample 1% (10×64 tuples from random positions)
    sample = stratified_sample(column_data, n_chunks=10, chunk_size=64)
    
    # Estimate compression ratio for each viable scheme
    best_scheme = None
    best_ratio = 0
    
    for scheme in get_schemes_for_dtype(dtype):
        if not scheme.is_viable(sample):
            continue
        ratio = scheme.estimate_ratio(sample)
        if ratio > best_ratio:
            best_ratio = ratio
            best_scheme = scheme
    
    if best_scheme is None:
        return RawEncoding(column_data)
    
    # Compress and recursively cascade outputs
    encoded = best_scheme.encode(column_data)
    for output_name, output_data, output_dtype in encoded.cascadable_outputs():
        encoded.set_cascade(output_name, 
            cascade_compress(output_data, output_dtype, max_depth - 1))
    
    return encoded
```

---

## Pseudodecimal Encoding: The Float Breakthrough

### The Problem with IEEE 754

```
Price: $3.25 stored as double
Binary: 0x400A000000000000
       ├─ Sign: 0
       ├─ Exponent: 10000000000 (biased 1024)
       └─ Mantissa: 1010000000000000000000000000000000000000000000000000

Price: $0.99 stored as double  
Binary: 0x3FEFAE147AE147AE
       └─ Mantissa: PERIODIC! (1111101011100001...)
       
Standard bit-packing: USELESS (exponents differ wildly)
```

### Pseudodecimal Solution

```python
def pseudodecimal_encode(value: float) -> tuple[int, int, float | None]:
    """
    Convert float to (significant_digits, exponent, exception)
    
    3.25  → (325, 2, None)     # 325 × 10⁻² = 3.25
    0.99  → (99, 2, None)      # Works even for 0.989999... storage!
    5.5e-42 → (0, 23, 5.5e-42) # Exception: exp=23 signals patch
    """
    POWERS_OF_10 = [1.0, 0.1, 0.01, 0.001, ...]  # Precomputed
    
    for exp in range(23):  # Up to 10⁻²²
        scaled = value / POWERS_OF_10[exp]
        digits = round(scaled)
        reconstructed = digits * POWERS_OF_10[exp]
        
        if reconstructed == value:  # Bitwise identical!
            return (digits, exp, None)
    
    return (0, 23, value)  # Exception: store original

# Output: two integer columns + small exception column
# Integer columns → cascade to FastBP128, RLE, etc.
# Compression: 75× on pricing data (vs 48× Gorilla)
```

---

## Schema Evolution: Zero-Copy Operations

### Adding Columns

```python
import lancedb

db = lancedb.connect("consciousness.lance")
table = db.open_table("atoms")

# Original schema
# fingerprint: FixedSizeBinary(1250)  # 10K bits
# content: String
# created_at: Timestamp

# Add new column - ZERO COPY of existing data
table.add_columns({
    "thinking_style": "Float32[7]",  # 7D style vector
    "resonance_score": "Float32",
})

# What happens internally:
# 1. New fragment created with new columns
# 2. Manifest updated to link fragments
# 3. Original data: UNTOUCHED
```

### Removing Columns

```python
# "Remove" column - actually just manifest update
table.drop_columns(["deprecated_field"])

# Data still exists in fragments (for old versions)
# New queries simply don't read it
# Compaction later reclaims space if needed
```

### Rollback Operations

```python
# Oops, bad migration
table.restore_version(42)

# What happens:
# 1. Manifest pointer moves to version 42
# 2. No data copied
# 3. Instant rollback

# Or: create branch from old version
experimental = table.checkout(version=42).create_branch("experiment")
```

---

## Performance Characteristics

### From BtrBlocks Paper (SIGMOD 2023)

| Metric | BtrBlocks | Parquet+Zstd | Improvement |
|--------|-----------|--------------|-------------|
| Decompression Throughput (Tᵤ) | 174.6 GB/s | 78.6 GB/s | 2.2× |
| Compressed Throughput (Tc) | 86.2 Gbit/s | 24.8 Gbit/s | 3.5× |
| S3 Scan Cost | $0.97 | $1.70 | 1.8× cheaper |
| Compression Ratio | 5.28× | 6.05× | Competitive |

### Key Insight: Compressed Throughput Matters

```
Traditional metric: Tᵤ = uncompressed_size / time
                    (How fast can we decompress?)

Network-aware metric: Tc = compressed_size / time  
                      (Can we saturate the network?)

Parquet+Zstd: 78.6 GB/s Tᵤ but only 24.8 Gbit/s Tc
              → Cannot saturate 100 Gbit network!

BtrBlocks: 174.6 GB/s Tᵤ AND 86.2 Gbit/s Tc
           → Nearly saturates 100 Gbit network
```

---

## Integration with LadybugDB

### The Substrate Layer (L12)

```python
class ConsciousnessSubstrate:
    """
    L12: Lance Substrate for LadybugDB
    
    Provides:
    - Zero-copy versioning for consciousness state
    - Columnar storage for 10K fingerprints
    - BtrBlocks-style encoding for all types
    - Schema evolution without migration scripts
    """
    
    def __init__(self, uri: str):
        self.db = lancedb.connect(uri)
        
    def store_atoms(self, atoms: list[Atom]):
        """Store atoms with automatic encoding selection"""
        # Fingerprints → full_zip or sparse encoding
        # Content → FSST dictionary cascade
        # Metadata → pseudodecimal for floats
        
    def query_by_resonance(self, query_fp: bytes, threshold: float):
        """Vector similarity with Hamming distance"""
        # Lance native vector index
        # Pre-filtered by thinking style
        
    def time_travel(self, version: int) -> 'ConsciousnessSubstrate':
        """Access historical consciousness state"""
        # Zero-copy checkout
        return ConsciousnessSubstrate(self.uri, version=version)
        
    def evolve_schema(self, changes: dict):
        """Add cognitive dimensions without rewriting"""
        # New columns → new fragments
        # Manifest update only
```

---

## API Reference

### Dataset Operations

```python
import lancedb

# Connect
db = lancedb.connect("./data.lance")

# Create table with schema
table = db.create_table("consciousness", schema={
    "fingerprint": "FixedSizeBinary(1250)",  # 10K bits
    "content": "String",
    "embedding": "Float32[1024]",            # Jina embedding
    "thinking_style": "Float32[7]",          # 7D style vector
    "created_at": "Timestamp",
    "version": "Int64",
})

# Insert with automatic encoding
table.add([
    {"fingerprint": fp1, "content": "...", ...},
    {"fingerprint": fp2, "content": "...", ...},
])

# Query with vector search
results = table.search(query_embedding).limit(10).to_list()

# Version operations
current_version = table.version
table.checkout(version=5)  # Time travel
table.restore(version=5)   # Rollback

# Schema evolution
table.add_columns({"new_field": "Float32"})
table.drop_columns(["deprecated"])
```

### Encoding Configuration

```python
# Custom encoding pool
table.configure_encoding({
    "fingerprint": {
        "type": "full_zip",
        "compression": "lz4",
    },
    "content": {
        "type": "cascade",
        "schemes": ["dictionary", "fsst"],
        "max_depth": 3,
    },
    "embedding": {
        "type": "product_quantization",
        "n_subvectors": 64,
    },
})
```

---

## Future: Absorbing New Research

The "One for All" principle means LanceDB can immediately absorb:

| Paper | Technique | Integration Point |
|-------|-----------|-------------------|
| BtrBlocks (2023) | Cascading compression | Encoding pool |
| FSST (2020) | String compression | String schemes |
| Chimp (2022) | Float compression | Double schemes |
| Roaring (2016) | Bitmap compression | NULL/exception storage |
| **Future Paper X** | **Technique Y** | **Just add to pool** |

```python
# Adding a new technique is trivial
class NewPaperEncoding(Encoding):
    def estimate_ratio(self, sample): ...
    def encode(self, data): ...
    def decode(self, encoded): ...

# Register it
LanceEncodingPool.register('integer', NewPaperEncoding)

# Done. All future columns can use it.
```

---

## Summary

**LanceDB: One for All** means:

1. **Universal Substrate**: Any encoding technique slots in
2. **Zero-Copy Evolution**: Add columns, rollback, branch - no data copying
3. **Research-Ready**: New papers → immediate integration
4. **Performance**: 2-4× faster than Parquet variants
5. **Versioning**: Git-like semantics for data

The format doesn't constrain techniques - it enables them.

---

*Next: [LadybugDB: All for One](./LADYBUGDB_ALL_FOR_ONE.md) - The cognitive layer that gives meaning to the substrate.*
