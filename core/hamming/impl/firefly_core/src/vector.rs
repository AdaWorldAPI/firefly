//! 10,000-bit Hamming vector implementation.
//!
//! This module provides the core `HammingVector` type used throughout Firefly
//! for content-addressable memory and similarity search.

use sha2::{Digest, Sha256};
use serde::{Deserialize, Serialize};
use std::fmt;

use crate::error::{FireflyError, Result};

/// Total number of bits in a Hamming vector.
pub const DIM: usize = 10_000;

/// Number of u64 elements needed to store DIM bits.
/// ceil(10000 / 64) = 157
pub const DIM_U64: usize = 157;

/// Number of packed bytes (DIM / 8).
pub const PACKED: usize = 1250;

/// Mask for the last u64 to only include valid bits.
/// 10000 mod 64 = 16 bits, so we keep only the lower 16 bits.
pub const LAST_MASK: u64 = (1 << 16) - 1;

/// A 10,000-bit Hamming vector for content-addressable memory.
///
/// # Memory Layout
///
/// The vector is stored as an array of 157 `u64` values in little-endian order.
/// The last `u64` only uses the lower 16 bits (since 157*64 = 10048 > 10000).
///
/// # Cross-Language Compatibility
///
/// This implementation is designed to produce identical results to the Python
/// implementation when using the same seeds and operations.
#[derive(Clone, Serialize, Deserialize)]
pub struct HammingVector {
    /// The bit data stored as 157 u64 values.
    pub data: [u64; DIM_U64],
}

impl HammingVector {
    /// Create a new zero vector.
    pub fn new() -> Self {
        Self {
            data: [0u64; DIM_U64],
        }
    }

    /// Create a deterministic vector from a seed string.
    ///
    /// Uses iterated SHA256 hashing to produce independent bits:
    /// - Each u64 chunk is derived from SHA256("{seed}:{index}")
    /// - This ensures no correlation between bit positions
    ///
    /// # Example
    ///
    /// ```rust
    /// use firefly_core::HammingVector;
    ///
    /// let v = HammingVector::from_seed("my_function::signature::body");
    /// ```
    pub fn from_seed(seed: &str) -> Self {
        let mut data = [0u64; DIM_U64];

        for i in 0..DIM_U64 {
            let input = format!("{}:{}", seed, i);
            let hash = Sha256::digest(input.as_bytes());
            // Take first 8 bytes as little-endian u64
            data[i] = u64::from_le_bytes(hash[..8].try_into().unwrap());
        }

        // Mask the last element to only have valid bits
        data[DIM_U64 - 1] &= LAST_MASK;

        Self { data }
    }

    /// Create a random vector (for testing).
    ///
    /// Uses the provided seed for deterministic randomness.
    pub fn random(seed: u64) -> Self {
        // Simple LCG for deterministic randomness
        let mut state = seed;
        let mut data = [0u64; DIM_U64];

        for i in 0..DIM_U64 {
            // LCG parameters from Numerical Recipes
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            data[i] = state;
        }

        data[DIM_U64 - 1] &= LAST_MASK;
        Self { data }
    }

    /// XOR binding with another vector.
    ///
    /// XOR binding is self-inverse: `(a ^ b) ^ b == a`
    ///
    /// This property allows:
    /// - Creating edge resonances: `edge = source ^ target`
    /// - Recovering endpoints: `target = edge ^ source`
    pub fn xor(&self, other: &HammingVector) -> HammingVector {
        let mut result = [0u64; DIM_U64];
        for i in 0..DIM_U64 {
            result[i] = self.data[i] ^ other.data[i];
        }
        result[DIM_U64 - 1] &= LAST_MASK;
        HammingVector { data: result }
    }

    /// Compute Hamming distance to another vector.
    ///
    /// Returns the number of bit positions where the vectors differ.
    /// Range: 0 (identical) to 10,000 (completely opposite).
    ///
    /// # Performance
    ///
    /// Uses native `count_ones()` which compiles to POPCNT on x86_64.
    pub fn hamming(&self, other: &HammingVector) -> u32 {
        let mut total = 0u32;

        // XOR and count differing bits
        for i in 0..DIM_U64 - 1 {
            total += (self.data[i] ^ other.data[i]).count_ones();
        }

        // Last element needs masking to avoid counting garbage bits
        let last_xor = (self.data[DIM_U64 - 1] ^ other.data[DIM_U64 - 1]) & LAST_MASK;
        total += last_xor.count_ones();

        total
    }

    /// Compute normalized similarity to another vector.
    ///
    /// Returns a value between 0.0 (completely different) and 1.0 (identical).
    /// Similarity = 1.0 - (hamming_distance / 10000)
    pub fn similarity(&self, other: &HammingVector) -> f64 {
        1.0 - (self.hamming(other) as f64) / (DIM as f64)
    }

    /// Convert to hexadecimal string.
    ///
    /// The output is 2500 characters (1250 bytes * 2 hex chars per byte).
    pub fn to_hex(&self) -> String {
        self.data
            .iter()
            .flat_map(|x| x.to_le_bytes())
            .take(PACKED)
            .map(|b| format!("{:02x}", b))
            .collect()
    }

    /// Parse from hexadecimal string.
    ///
    /// # Errors
    ///
    /// Returns `FireflyError::InvalidHex` if the string is not valid hex
    /// or has incorrect length.
    pub fn from_hex(hex: &str) -> Result<Self> {
        if hex.len() != PACKED * 2 {
            return Err(FireflyError::InvalidHex(format!(
                "Expected {} hex chars, got {}",
                PACKED * 2,
                hex.len()
            )));
        }

        let bytes: Vec<u8> = (0..hex.len())
            .step_by(2)
            .map(|i| {
                u8::from_str_radix(&hex[i..i + 2], 16)
                    .map_err(|_| FireflyError::InvalidHex(format!("Invalid hex at position {}", i)))
            })
            .collect::<Result<Vec<u8>>>()?;

        let mut data = [0u64; DIM_U64];
        for i in 0..DIM_U64 {
            let start = i * 8;
            let end = (start + 8).min(bytes.len());
            if end > start {
                let mut buf = [0u8; 8];
                buf[..end - start].copy_from_slice(&bytes[start..end]);
                data[i] = u64::from_le_bytes(buf);
            }
        }

        // Ensure mask is applied
        data[DIM_U64 - 1] &= LAST_MASK;

        Ok(Self { data })
    }

    /// Convert to raw bytes (little-endian).
    pub fn to_bytes(&self) -> Vec<u8> {
        self.data
            .iter()
            .flat_map(|x| x.to_le_bytes())
            .take(PACKED)
            .collect()
    }

    /// Parse from raw bytes.
    ///
    /// # Errors
    ///
    /// Returns error if bytes length is not exactly PACKED (1250).
    pub fn from_bytes(bytes: &[u8]) -> Result<Self> {
        if bytes.len() != PACKED {
            return Err(FireflyError::InvalidLength(format!(
                "Expected {} bytes, got {}",
                PACKED,
                bytes.len()
            )));
        }

        let mut data = [0u64; DIM_U64];
        for i in 0..DIM_U64 {
            let start = i * 8;
            let end = (start + 8).min(bytes.len());
            if end > start {
                let mut buf = [0u8; 8];
                buf[..end - start].copy_from_slice(&bytes[start..end]);
                data[i] = u64::from_le_bytes(buf);
            }
        }

        data[DIM_U64 - 1] &= LAST_MASK;
        Ok(Self { data })
    }

    /// Get the number of set bits (population count).
    pub fn popcount(&self) -> u32 {
        let mut total = 0u32;
        for i in 0..DIM_U64 - 1 {
            total += self.data[i].count_ones();
        }
        total += (self.data[DIM_U64 - 1] & LAST_MASK).count_ones();
        total
    }

    /// Check if a specific bit is set.
    ///
    /// # Panics
    ///
    /// Panics if `bit_index >= DIM`.
    pub fn get_bit(&self, bit_index: usize) -> bool {
        assert!(bit_index < DIM, "Bit index out of range");
        let u64_idx = bit_index / 64;
        let bit_idx = bit_index % 64;
        (self.data[u64_idx] >> bit_idx) & 1 == 1
    }

    /// Set a specific bit.
    ///
    /// # Panics
    ///
    /// Panics if `bit_index >= DIM`.
    pub fn set_bit(&mut self, bit_index: usize, value: bool) {
        assert!(bit_index < DIM, "Bit index out of range");
        let u64_idx = bit_index / 64;
        let bit_idx = bit_index % 64;

        if value {
            self.data[u64_idx] |= 1u64 << bit_idx;
        } else {
            self.data[u64_idx] &= !(1u64 << bit_idx);
        }
    }
}

impl Default for HammingVector {
    fn default() -> Self {
        Self::new()
    }
}

impl fmt::Debug for HammingVector {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "HammingVector(popcount={}, hex={}...)",
            self.popcount(),
            &self.to_hex()[..16]
        )
    }
}

impl fmt::Display for HammingVector {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "HammingVector[{}]", &self.to_hex()[..32])
    }
}

impl PartialEq for HammingVector {
    fn eq(&self, other: &Self) -> bool {
        self.data == other.data
    }
}

impl Eq for HammingVector {}

impl std::hash::Hash for HammingVector {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.data.hash(state);
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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_is_zero() {
        let v = HammingVector::new();
        assert_eq!(v.popcount(), 0);
    }

    #[test]
    fn test_from_seed_deterministic() {
        let v1 = HammingVector::from_seed("test");
        let v2 = HammingVector::from_seed("test");
        assert_eq!(v1, v2);
    }

    #[test]
    fn test_from_seed_different() {
        let v1 = HammingVector::from_seed("test1");
        let v2 = HammingVector::from_seed("test2");
        assert_ne!(v1, v2);
    }

    #[test]
    fn test_xor_self_is_zero() {
        let v = HammingVector::from_seed("test");
        let xored = &v ^ &v;
        assert_eq!(xored.popcount(), 0);
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
    fn test_similarity_self_is_one() {
        let v = HammingVector::from_seed("test");
        assert!((v.similarity(&v) - 1.0).abs() < 0.0001);
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
    fn test_get_set_bit() {
        let mut v = HammingVector::new();
        assert!(!v.get_bit(42));
        v.set_bit(42, true);
        assert!(v.get_bit(42));
        v.set_bit(42, false);
        assert!(!v.get_bit(42));
    }

    #[test]
    fn test_last_mask_applied() {
        let v = HammingVector::from_seed("test");
        // Bits 16-63 of the last u64 should be zero
        assert_eq!(v.data[DIM_U64 - 1] & !LAST_MASK, 0);
    }

    #[test]
    fn test_popcount_matches_hamming_from_zero() {
        let v = HammingVector::from_seed("test");
        let zero = HammingVector::new();
        assert_eq!(v.popcount(), v.hamming(&zero));
    }

    #[test]
    fn test_invalid_hex_length() {
        let result = HammingVector::from_hex("abc");
        assert!(result.is_err());
    }

    #[test]
    fn test_invalid_bytes_length() {
        let result = HammingVector::from_bytes(&[0u8; 100]);
        assert!(result.is_err());
    }
}
