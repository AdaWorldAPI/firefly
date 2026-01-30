//! # Firefly Core: 10K Hamming Resonance Engine
//!
//! This crate provides the core primitives for the Firefly graph substrate compiler:
//!
//! - **10,000-bit Hamming vectors** for content-addressable memory
//! - **XOR binding** for self-inverse composition
//! - **Majority superposition** for combining vectors
//! - **Similarity search** via Hamming distance
//!
//! ## Design Invariants
//!
//! - All vectors are exactly 10,000 bits (1,250 bytes)
//! - Deterministic: same seed always produces same vector
//! - Cross-language compatible with Python implementation
//!
//! ## Example
//!
//! ```rust
//! use firefly_core::{HammingVector, fingerprint, resonate};
//!
//! // Create vectors from code identity
//! let v1 = fingerprint("validate_email", "(str) -> bool", "check format");
//! let v2 = fingerprint("validate_phone", "(str) -> bool", "check format");
//!
//! // Similar functions have similar fingerprints
//! let similarity = v1.similarity(&v2);
//! assert!(similarity > 0.4);
//!
//! // XOR binding is self-inverse
//! let bound = &v1 ^ &v2;
//! let recovered = &bound ^ &v2;
//! assert!(v1.similarity(&recovered) > 0.99);
//! ```

mod vector;
mod error;
mod node;
mod edge;

pub use vector::{HammingVector, DIM, DIM_U64, PACKED, LAST_MASK};
pub use error::{FireflyError, Result};
pub use node::FireflyNode;
pub use edge::FireflyEdge;

use sha2::{Sha256, Digest};

/// Create a deterministic fingerprint from code identity.
///
/// The fingerprint uniquely identifies a code construct by combining:
/// - `name`: The function/method name
/// - `signature`: The type signature
/// - `body`: The implementation body (or hash thereof)
///
/// # Example
///
/// ```rust
/// use firefly_core::fingerprint;
///
/// let fp = fingerprint("add", "(i32, i32) -> i32", "a + b");
/// ```
pub fn fingerprint(name: &str, signature: &str, body: &str) -> HammingVector {
    let seed = format!("{}::{}::{}", name, signature, body);
    HammingVector::from_seed(&seed)
}

/// Create a deterministic role vector from a name.
///
/// Role vectors are used for binding components with specific semantic roles:
/// - `FIREFLY:NODE:SCHEMA:WHAT` - The input/output schema
/// - `FIREFLY:NODE:LOGIC:HOW` - The execution logic
/// - `FIREFLY:NODE:CONTEXT:WHERE` - The graph context
///
/// Unlike simple hash tiling, this produces independent bits across all 10K positions.
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
///
/// Returns a vector of (index, similarity) pairs, sorted by similarity descending.
///
/// # Arguments
///
/// * `query` - The query vector to match against
/// * `corpus` - The corpus of vectors to search
/// * `threshold` - Minimum similarity (0.0 to 1.0) to include in results
///
/// # Example
///
/// ```rust
/// use firefly_core::{HammingVector, resonate};
///
/// let query = HammingVector::from_seed("search_term");
/// let corpus = vec![
///     HammingVector::from_seed("item_1"),
///     HammingVector::from_seed("item_2"),
/// ];
///
/// let results = resonate(&query, &corpus, 0.5);
/// for (idx, sim) in results {
///     println!("Item {} has similarity {:.3}", idx, sim);
/// }
/// ```
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

    // Sort by similarity descending, with stable ordering for equal similarities
    results.sort_by(|a, b| {
        b.1.partial_cmp(&a.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.0.cmp(&b.0))
    });

    results
}

/// Majority vote superposition of multiple vectors.
///
/// Creates a new vector where each bit is set if it's set in more than half
/// of the input vectors. This allows combining multiple concepts while
/// preserving similarity to all of them.
///
/// # Panics
///
/// Panics if the input slice is empty.
pub fn bundle(vectors: &[HammingVector]) -> HammingVector {
    assert!(!vectors.is_empty(), "Cannot bundle empty vector list");

    let threshold = vectors.len() / 2;
    let mut result = [0u64; DIM_U64];

    // Count set bits at each position across all vectors
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

    // Apply mask to last element
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
    fn test_fingerprint_different() {
        let fp1 = fingerprint("test1", "() -> void", "body");
        let fp2 = fingerprint("test2", "() -> void", "body");
        assert_ne!(fp1.to_hex(), fp2.to_hex());
        // But they should have some similarity due to shared components
        assert!(fp1.similarity(&fp2) > 0.3);
    }

    #[test]
    fn test_xor_self_inverse() {
        let v1 = HammingVector::from_seed("vector_a");
        let v2 = HammingVector::from_seed("vector_b");

        let bound = &v1 ^ &v2;
        let recovered = &bound ^ &v2;

        // Should recover v1 exactly
        assert_eq!(v1.hamming(&recovered), 0);
    }

    #[test]
    fn test_resonate() {
        let query = HammingVector::from_seed("query");
        let corpus = vec![
            HammingVector::from_seed("similar_query"),
            HammingVector::from_seed("completely_different_xyz"),
            HammingVector::from_seed("query"), // Exact match
        ];

        let results = resonate(&query, &corpus, 0.5);

        // Exact match should be first
        assert!(!results.is_empty());
        assert_eq!(results[0].0, 2); // Index of exact match
        assert!((results[0].1 - 1.0).abs() < 0.001); // Similarity should be 1.0
    }

    #[test]
    fn test_bundle() {
        let v1 = HammingVector::from_seed("concept_a");
        let v2 = HammingVector::from_seed("concept_b");
        let v3 = HammingVector::from_seed("concept_c");

        let bundled = bundle(&[v1.clone(), v2.clone(), v3.clone()]);

        // Bundle should be somewhat similar to all inputs
        assert!(bundled.similarity(&v1) > 0.3);
        assert!(bundled.similarity(&v2) > 0.3);
        assert!(bundled.similarity(&v3) > 0.3);
    }

    #[test]
    fn test_role_vectors_distinct() {
        use roles::*;
        assert!(ROLE_SCHEMA.similarity(&*ROLE_LOGIC) < 0.6);
        assert!(ROLE_LOGIC.similarity(&*ROLE_CONTEXT) < 0.6);
        assert!(ROLE_SCHEMA.similarity(&*ROLE_CONTEXT) < 0.6);
    }
}
