//! LadybugDB Hamming Operations - Rust
//! Same XOR + POPCOUNT as Python, TypeScript, Go, C...

use sha2::{Sha256, Digest};

const DIM: usize = 10_000;
const DIM_U64: usize = 157;
const LAST_MASK: u64 = (1 << 16) - 1;

#[derive(Clone)]
pub struct HammingVector {
    pub data: [u64; DIM_U64],
}

impl HammingVector {
    pub fn new() -> Self {
        Self { data: [0u64; DIM_U64] }
    }

    pub fn from_seed(seed: &str) -> Self {
        let mut data = [0u64; DIM_U64];
        for i in 0..DIM_U64 {
            let input = format!("{}:{}", seed, i);
            let hash = Sha256::digest(input.as_bytes());
            data[i] = u64::from_le_bytes(hash[..8].try_into().unwrap());
        }
        data[DIM_U64 - 1] &= LAST_MASK;
        Self { data }
    }

    pub fn xor(&self, other: &HammingVector) -> HammingVector {
        let mut result = [0u64; DIM_U64];
        for i in 0..DIM_U64 {
            result[i] = self.data[i] ^ other.data[i];
        }
        result[DIM_U64 - 1] &= LAST_MASK;
        HammingVector { data: result }
    }

    pub fn hamming(&self, other: &HammingVector) -> u32 {
        let mut total = 0u32;
        for i in 0..DIM_U64 {
            total += (self.data[i] ^ other.data[i]).count_ones();
        }
        total
    }

    pub fn similarity(&self, other: &HammingVector) -> f64 {
        1.0 - (self.hamming(other) as f64) / (DIM as f64)
    }

    pub fn to_hex(&self) -> String {
        self.data.iter()
            .flat_map(|x| x.to_le_bytes())
            .map(|b| format!("{:02x}", b))
            .collect()
    }

    pub fn from_hex(hex: &str) -> Self {
        let bytes: Vec<u8> = (0..hex.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&hex[i..i+2], 16).unwrap())
            .collect();
        let mut data = [0u64; DIM_U64];
        for i in 0..DIM_U64 {
            data[i] = u64::from_le_bytes(bytes[i*8..(i+1)*8].try_into().unwrap());
        }
        Self { data }
    }
}

impl std::ops::BitXor for &HammingVector {
    type Output = HammingVector;
    fn bitxor(self, other: Self) -> HammingVector {
        self.xor(other)
    }
}

pub fn fingerprint(name: &str, signature: &str, body: &str) -> HammingVector {
    HammingVector::from_seed(&format!("{}::{}::{}", name, signature, body))
}

pub fn resonate(query: &HammingVector, corpus: &[HammingVector], threshold: f64) -> Vec<(usize, f64)> {
    let mut results: Vec<(usize, f64)> = corpus.iter()
        .enumerate()
        .map(|(i, v)| (i, query.similarity(v)))
        .filter(|(_, sim)| *sim >= threshold)
        .collect();
    results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    results
}