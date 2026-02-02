//! LadybugDB Hamming Operations - Rust (Standalone Version)
//!
//! This is a standalone, single-file implementation compatible with the Python version.
//! For a full-featured crate, see `firefly_core/`.
//!
//! Same XOR + POPCOUNT as Python, TypeScript, Go, C...

use sha2::{Sha256, Digest};

/// Total number of bits in a Hamming vector.
pub const DIM: usize = 10_000;

/// Number of u64 elements needed (ceil(10000/64) = 157).
pub const DIM_U64: usize = 157;

/// Number of packed bytes.
pub const PACKED: usize = 1250;

/// Mask for the last u64 (10000 mod 64 = 16 valid bits).
pub const LAST_MASK: u64 = (1 << 16) - 1;

/// Error type for parsing operations.
#[derive(Debug)]
pub enum HammingError {
    InvalidHex(String),
    InvalidLength(usize, usize),
}

impl std::fmt::Display for HammingError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            HammingError::InvalidHex(s) => write!(f, "Invalid hex: {}", s),
            HammingError::InvalidLength(expected, got) => {
                write!(f, "Invalid length: expected {}, got {}", expected, got)
            }
        }
    }
}

impl std::error::Error for HammingError {}

/// 10,000-bit Hamming vector for content-addressable memory.
#[derive(Clone, PartialEq, Eq, Hash)]
pub struct HammingVector {
    pub data: [u64; DIM_U64],
}

impl Default for HammingVector {
    fn default() -> Self {
        Self::new()
    }
}

impl std::fmt::Debug for HammingVector {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "HammingVector({}...)", &self.to_hex()[..16])
    }
}

impl HammingVector {
    /// Create a new zero vector.
    pub fn new() -> Self {
        Self { data: [0u64; DIM_U64] }
    }

    /// Create a deterministic vector from a seed string.
    ///
    /// Uses iterated SHA256 to produce independent bits across all positions.
    pub fn from_seed(seed: &str) -> Self {
        let mut data = [0u64; DIM_U64];
        for i in 0..DIM_U64 {
            let input = format!("{}:{}", seed, i);
            let hash = Sha256::digest(input.as_bytes());
            data[i] = u64::from_le_bytes(hash[..8].try_into().unwrap());
        }
        // Mask the last element to only have valid bits
        data[DIM_U64 - 1] &= LAST_MASK;
        Self { data }
    }

    /// XOR binding - self-inverse.
    pub fn xor(&self, other: &HammingVector) -> HammingVector {
        let mut result = [0u64; DIM_U64];
        for i in 0..DIM_U64 {
            result[i] = self.data[i] ^ other.data[i];
        }
        result[DIM_U64 - 1] &= LAST_MASK;
        HammingVector { data: result }
    }

    /// Hamming distance via XOR + POPCOUNT.
    ///
    /// CRITICAL: Masks the last u64 to avoid counting garbage bits.
    pub fn hamming(&self, other: &HammingVector) -> u32 {
        let mut total = 0u32;
        // Count all but last
        for i in 0..DIM_U64 - 1 {
            total += (self.data[i] ^ other.data[i]).count_ones();
        }
        // Last element needs masking
        let last_xor = (self.data[DIM_U64 - 1] ^ other.data[DIM_U64 - 1]) & LAST_MASK;
        total += last_xor.count_ones();
        total
    }

    /// Normalized similarity [0, 1].
    pub fn similarity(&self, other: &HammingVector) -> f64 {
        1.0 - (self.hamming(other) as f64) / (DIM as f64)
    }

    /// Convert to hexadecimal string (2500 chars).
    pub fn to_hex(&self) -> String {
        self.data.iter()
            .flat_map(|x| x.to_le_bytes())
            .take(PACKED)
            .map(|b| format!("{:02x}", b))
            .collect()
    }

    /// Parse from hexadecimal string.
    pub fn from_hex(hex: &str) -> Result<Self, HammingError> {
        if hex.len() != PACKED * 2 {
            return Err(HammingError::InvalidLength(PACKED * 2, hex.len()));
        }

        let bytes: Result<Vec<u8>, _> = (0..hex.len())
            .step_by(2)
            .map(|i| {
                u8::from_str_radix(&hex[i..i+2], 16)
                    .map_err(|_| HammingError::InvalidHex(format!("at position {}", i)))
            })
            .collect();

        let bytes = bytes?;
        let mut data = [0u64; DIM_U64];
        for i in 0..DIM_U64 {
            let start = i * 8;
            let end = (start + 8).min(bytes.len());
            if end > start {
                let mut buf = [0u8; 8];
                buf[..end-start].copy_from_slice(&bytes[start..end]);
                data[i] = u64::from_le_bytes(buf);
            }
        }
        data[DIM_U64 - 1] &= LAST_MASK;
        Ok(Self { data })
    }

    /// Convert to raw bytes.
    pub fn to_bytes(&self) -> Vec<u8> {
        self.data.iter()
            .flat_map(|x| x.to_le_bytes())
            .take(PACKED)
            .collect()
    }

    /// Parse from raw bytes.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, HammingError> {
        if bytes.len() != PACKED {
            return Err(HammingError::InvalidLength(PACKED, bytes.len()));
        }

        let mut data = [0u64; DIM_U64];
        for i in 0..DIM_U64 {
            let start = i * 8;
            let end = (start + 8).min(bytes.len());
            if end > start {
                let mut buf = [0u8; 8];
                buf[..end-start].copy_from_slice(&bytes[start..end]);
                data[i] = u64::from_le_bytes(buf);
            }
        }
        data[DIM_U64 - 1] &= LAST_MASK;
        Ok(Self { data })
    }

    /// Population count (number of set bits).
    pub fn popcount(&self) -> u32 {
        let mut total = 0u32;
        for i in 0..DIM_U64 - 1 {
            total += self.data[i].count_ones();
        }
        total += (self.data[DIM_U64 - 1] & LAST_MASK).count_ones();
        total
    }
}

impl std::ops::BitXor for &HammingVector {
    type Output = HammingVector;
    fn bitxor(self, other: Self) -> HammingVector {
        self.xor(other)
    }
}

impl std::ops::BitXor for HammingVector {
    type Output = HammingVector;
    fn bitxor(self, other: Self) -> HammingVector {
        self.xor(&other)
    }
}

/// Create a deterministic fingerprint from code identity.
pub fn fingerprint(name: &str, signature: &str, body: &str) -> HammingVector {
    HammingVector::from_seed(&format!("{}::{}::{}", name, signature, body))
}

/// Find vectors resonating above threshold, sorted by similarity descending.
pub fn resonate(query: &HammingVector, corpus: &[HammingVector], threshold: f64) -> Vec<(usize, f64)> {
    let mut results: Vec<(usize, f64)> = corpus.iter()
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

// =============================================================================
// EXAMPLE MAIN
// =============================================================================

fn main() {
    println!("=== Firefly Hamming Operations (Standalone Rust) ===\n");

    // Create vectors from code identity
    let v1 = fingerprint("validate_email", "(str) -> bool", "check format");
    let v2 = fingerprint("validate_phone", "(str) -> bool", "check format");
    let v3 = fingerprint("calculate_tax", "(f64) -> f64", "tax * rate");

    println!("Created 3 fingerprints:");
    println!("  v1 (validate_email): {:?}", v1);
    println!("  v2 (validate_phone): {:?}", v2);
    println!("  v3 (calculate_tax):  {:?}", v3);

    // Similarity
    println!("\nSimilarities:");
    println!("  v1 <-> v2: {:.4} (both validators)", v1.similarity(&v2));
    println!("  v1 <-> v3: {:.4} (different types)", v1.similarity(&v3));
    println!("  v2 <-> v3: {:.4} (different types)", v2.similarity(&v3));

    // XOR binding is self-inverse
    println!("\nXOR binding demonstration:");
    let bound = &v1 ^ &v2;
    let recovered = &bound ^ &v2;
    println!("  v1 ^ v2 = bound");
    println!("  bound ^ v2 = recovered");
    println!("  v1 == recovered: {}", v1 == recovered);

    // Bundle (majority superposition)
    println!("\nBundle (majority vote):");
    let bundled = bundle(&[v1.clone(), v2.clone(), v3.clone()]);
    println!("  bundled similarity to v1: {:.4}", bundled.similarity(&v1));
    println!("  bundled similarity to v2: {:.4}", bundled.similarity(&v2));
    println!("  bundled similarity to v3: {:.4}", bundled.similarity(&v3));

    // Resonate (search)
    println!("\nResonate search (threshold=0.4):");
    let corpus = vec![v1.clone(), v2.clone(), v3.clone()];
    let query = fingerprint("check_email", "(str) -> bool", "validate");
    let results = resonate(&query, &corpus, 0.4);
    for (idx, sim) in results {
        let name = match idx {
            0 => "validate_email",
            1 => "validate_phone",
            2 => "calculate_tax",
            _ => "unknown",
        };
        println!("  {} (idx={}): similarity={:.4}", name, idx, sim);
    }

    // Performance info
    println!("\nVector stats:");
    println!("  Dimension: {} bits", DIM);
    println!("  Packed size: {} bytes", PACKED);
    println!("  v1 popcount: {} bits set", v1.popcount());

    println!("\n=== Done ===");
}

// =============================================================================
// TESTS
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_from_seed_deterministic() {
        let v1 = HammingVector::from_seed("test");
        let v2 = HammingVector::from_seed("test");
        assert_eq!(v1, v2);
    }

    #[test]
    fn test_xor_self_inverse() {
        let v1 = HammingVector::from_seed("a");
        let v2 = HammingVector::from_seed("b");
        let bound = &v1 ^ &v2;
        let recovered = &bound ^ &v2;
        assert_eq!(v1, recovered);
    }

    #[test]
    fn test_hamming_self_is_zero() {
        let v = HammingVector::from_seed("test");
        assert_eq!(v.hamming(&v), 0);
    }

    #[test]
    fn test_last_mask_applied() {
        let v = HammingVector::from_seed("test");
        assert_eq!(v.data[DIM_U64 - 1] & !LAST_MASK, 0);
    }

    #[test]
    fn test_hex_roundtrip() {
        let v1 = HammingVector::from_seed("test");
        let hex = v1.to_hex();
        let v2 = HammingVector::from_hex(&hex).unwrap();
        assert_eq!(v1, v2);
    }

    #[test]
    fn test_bytes_roundtrip() {
        let v1 = HammingVector::from_seed("test");
        let bytes = v1.to_bytes();
        assert_eq!(bytes.len(), PACKED);
        let v2 = HammingVector::from_bytes(&bytes).unwrap();
        assert_eq!(v1, v2);
    }

    #[test]
    fn test_resonate_finds_exact_match() {
        let query = HammingVector::from_seed("query");
        let corpus = vec![
            HammingVector::from_seed("other"),
            HammingVector::from_seed("query"), // exact match
        ];
        let results = resonate(&query, &corpus, 0.5);
        assert!(!results.is_empty());
        assert_eq!(results[0].0, 1); // index of exact match
        assert!((results[0].1 - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_bundle() {
        let v1 = HammingVector::from_seed("a");
        let v2 = HammingVector::from_seed("b");
        let v3 = HammingVector::from_seed("c");
        let bundled = bundle(&[v1.clone(), v2.clone(), v3.clone()]);
        // Bundled should be somewhat similar to all inputs
        assert!(bundled.similarity(&v1) > 0.3);
        assert!(bundled.similarity(&v2) > 0.3);
        assert!(bundled.similarity(&v3) > 0.3);
    }
}