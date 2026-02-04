//! # Firefly: Graph Substrate Compiler
//!
//! Complete Rust implementation of the Firefly graph substrate compiler.
//!
//! ## Modules
//!
//! - **core**: 10K Hamming vectors, XOR binding, similarity search
//! - **dto**: Data transfer objects (Node, Edge, Packet)
//! - **ladybug**: Declarative code graph layer
//! - **storage**: Unified storage (mirrors LanceDB+DuckDB+Kuzu)
//! - **executor**: Graph execution engine
//! - **transport**: Distributed packet transport
//! - **reasoning**: Failure explanation and suggestions
//!
//! ## Example
//!
//! ```rust
//! use firefly::{HammingVector, fingerprint, resonate, bundle};
//! use firefly::dto::{FireflyNode, FireflyEdge, FireflyPacket};
//!
//! // Create fingerprints from code identity
//! let v1 = fingerprint("validate_email", "(str) -> bool", "check format");
//! let v2 = fingerprint("validate_phone", "(str) -> bool", "check format");
//!
//! // XOR binding is self-inverse
//! let bound = &v1 ^ &v2;
//! let recovered = &bound ^ &v2;
//! assert_eq!(v1, recovered);
//! ```

// =============================================================================
// CORE MODULE (Hamming vectors)
// =============================================================================

mod vector;
mod error;

pub use vector::{HammingVector, DIM, DIM_U64, PACKED, LAST_MASK};
pub use error::{FireflyError, Result};

// =============================================================================
// DTO MODULE (Data Transfer Objects)
// =============================================================================

pub mod dto;
pub use dto::{FireflyNode, FireflyEdge, FireflyPacket};

// =============================================================================
// LADYBUG MODULE (Declarative Code Graph)
// =============================================================================

pub mod ladybug;

// =============================================================================
// STORAGE MODULE
// =============================================================================

pub mod storage;

// =============================================================================
// EXECUTOR MODULE
// =============================================================================

pub mod executor;

// =============================================================================
// TRANSPORT MODULE
// =============================================================================

pub mod transport;

// =============================================================================
// REASONING MODULE
// =============================================================================

pub mod reasoning;

// =============================================================================
// GEL MODULE (Graph Execution Language)
// =============================================================================

pub mod gel;
pub use gel::{DistinguishedName, GelQuery, GelExecutor, ExecutionMode, Transaction};

// =============================================================================
// RUBBERDUCK MODULE (Self-Analyzing Audit System)
// =============================================================================

pub mod rubberduck;
pub use rubberduck::{Rubberduck, AuditReport, CodeSmell, SmellType};

// =============================================================================
// CORE FUNCTIONS
// =============================================================================


/// Create a deterministic fingerprint from code identity.
pub fn fingerprint(name: &str, signature: &str, body: &str) -> HammingVector {
    let seed = format!("{}::{}::{}", name, signature, body);
    HammingVector::from_seed(&seed)
}

/// Create a deterministic role vector from a name.
pub fn role_vector(name: &str) -> HammingVector {
    HammingVector::from_seed(name)
}

/// Pre-computed role vectors for node components.
pub mod roles {
    use super::HammingVector;
    use std::sync::LazyLock;

    pub static ROLE_SCHEMA: LazyLock<HammingVector> =
        LazyLock::new(|| HammingVector::from_seed("FIREFLY:NODE:SCHEMA:WHAT"));

    pub static ROLE_LOGIC: LazyLock<HammingVector> =
        LazyLock::new(|| HammingVector::from_seed("FIREFLY:NODE:LOGIC:HOW"));

    pub static ROLE_CONTEXT: LazyLock<HammingVector> =
        LazyLock::new(|| HammingVector::from_seed("FIREFLY:NODE:CONTEXT:WHERE"));

    pub static ROLE_I: LazyLock<HammingVector> =
        LazyLock::new(|| HammingVector::from_seed("FIREFLY:GESTALT:I:SELF"));

    pub static ROLE_THOU: LazyLock<HammingVector> =
        LazyLock::new(|| HammingVector::from_seed("FIREFLY:GESTALT:THOU:OTHER"));

    pub static ROLE_IT: LazyLock<HammingVector> =
        LazyLock::new(|| HammingVector::from_seed("FIREFLY:GESTALT:IT:WORLD"));
}

/// Find all vectors in a corpus that resonate with a query above threshold.
pub fn resonate(
    query: &HammingVector,
    corpus: &[HammingVector],
    threshold: f64,
) -> Vec<(usize, f64)> {
    let mut results: Vec<(usize, f64)> = corpus
        .iter()
        .enumerate()
        .map(|(i, v)| (i, query.similarity(v)))
        .filter(|(_, sim)| *sim >= threshold)
        .collect();

    results.sort_by(|a, b| {
        b.1.partial_cmp(&a.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.0.cmp(&b.0))
    });

    results
}

/// Majority vote superposition of multiple vectors.
pub fn bundle(vectors: &[HammingVector]) -> HammingVector {
    assert!(!vectors.is_empty(), "Cannot bundle empty vector list");

    let threshold = vectors.len() / 2;
    let mut result = [0u64; DIM_U64];

    for bit_pos in 0..DIM {
        let u64_idx = bit_pos / 64;
        let bit_idx = bit_pos % 64;

        let count: usize = vectors
            .iter()
            .filter(|v| (v.data[u64_idx] >> bit_idx) & 1 == 1)
            .count();

        if count > threshold {
            result[u64_idx] |= 1u64 << bit_idx;
        }
    }

    result[DIM_U64 - 1] &= LAST_MASK;
    HammingVector { data: result }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fingerprint_deterministic() {
        let fp1 = fingerprint("test", "() -> void", "body");
        let fp2 = fingerprint("test", "() -> void", "body");
        assert_eq!(fp1.to_hex(), fp2.to_hex());
    }

    #[test]
    fn test_xor_self_inverse() {
        let v1 = HammingVector::from_seed("vector_a");
        let v2 = HammingVector::from_seed("vector_b");
        let bound = &v1 ^ &v2;
        let recovered = &bound ^ &v2;
        assert_eq!(v1.hamming(&recovered), 0);
    }

    #[test]
    fn test_resonate() {
        let query = HammingVector::from_seed("query");
        let corpus = vec![
            HammingVector::from_seed("other"),
            HammingVector::from_seed("query"),
        ];
        let results = resonate(&query, &corpus, 0.5);
        assert_eq!(results[0].0, 1);
    }

    #[test]
    fn test_bundle() {
        let v1 = HammingVector::from_seed("a");
        let v2 = HammingVector::from_seed("b");
        let v3 = HammingVector::from_seed("c");
        let bundled = bundle(&[v1.clone(), v2.clone(), v3.clone()]);
        assert!(bundled.similarity(&v1) > 0.3);
    }
}
