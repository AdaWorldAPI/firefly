# Firefly Core - Rust Implementation

Full-featured Rust crate for **10K Hamming Resonance**.

## Features

- **Zero-copy operations** where possible
- **POPCNT intrinsics** via `count_ones()`
- **Serde serialization** (JSON, hex, bytes)
- **Error handling** with `thiserror`
- **Builder pattern** for nodes
- **Comprehensive tests**
- **Criterion benchmarks**

## Usage

```rust
use firefly_core::{HammingVector, fingerprint, resonate, bundle};
use firefly_core::{FireflyNode, FireflyEdge};

// Create vectors
let v1 = fingerprint("validate_email", "(str) -> bool", "check");
let v2 = fingerprint("validate_phone", "(str) -> bool", "check");

// Operations
let sim = v1.similarity(&v2);
let bound = &v1 ^ &v2;  // XOR binding
let recovered = &bound ^ &v2;  // == v1

// Search
let results = resonate(&query, &corpus, 0.5);

// Bundle (majority vote)
let combined = bundle(&[v1, v2, v3]);

// Nodes
let node = FireflyNode::from_id("my_validator".into());

// Edges (resonance = source ^ target)
let edge = FireflyEdge::from_nodes(&source, &target);
```

## Building

```bash
cd core/hamming/rust
cargo build --release
cargo test
cargo bench
```

## Run Standalone Example

```bash
cargo run --example standalone
```

## Crate Structure

```
rust/
├── Cargo.toml
├── src/
│   ├── lib.rs      # Main entry, roles, fingerprint, resonate, bundle
│   ├── vector.rs   # HammingVector (10K bits)
│   ├── error.rs    # FireflyError
│   ├── node.rs     # FireflyNode with builder
│   └── edge.rs     # FireflyEdge with recovery
├── benches/
│   └── hamming_bench.rs
└── standalone.rs   # Single-file reference implementation
```

## Cross-Language Compatibility

This implementation produces **identical results** to the Python version:

```rust
// Same seed -> same vector
let v = HammingVector::from_seed("test");
// Python: HammingVector.from_seed("test")
// Both produce identical hex output
```

## Benchmarks

Run with:
```bash
cargo bench
```

Typical results on modern x86_64:
- `from_seed`: ~15μs (SHA256 dominated)
- `hamming_distance`: ~200ns (POPCNT)
- `xor_binding`: ~100ns
- `resonate(10k)`: ~2ms
