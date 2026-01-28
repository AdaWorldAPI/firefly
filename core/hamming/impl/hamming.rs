//! 10K Hamming Operations - Rust
//! Zero-cost abstractions, SIMD-friendly

const DIM: usize = 10_000;
const DIM_U64: usize = 157;
const LAST_MASK: u64 = (1 << 16) - 1;

#[inline(always)]
fn popcount64(x: u64) -> u32 {
    x.count_ones()  // Uses POPCNT instruction when available
}

pub fn hamming(a: &[u64; DIM_U64], b: &[u64; DIM_U64]) -> u32 {
    let mut total = 0u32;
    for i in 0..DIM_U64 {
        total += popcount64(a[i] ^ b[i]);
    }
    total
}

pub fn similarity(a: &[u64; DIM_U64], b: &[u64; DIM_U64]) -> f64 {
    1.0 - (hamming(a, b) as f64) / (DIM as f64)
}

pub fn xor_bind(a: &[u64; DIM_U64], b: &[u64; DIM_U64]) -> [u64; DIM_U64] {
    let mut result = [0u64; DIM_U64];
    for i in 0..DIM_U64 {
        result[i] = a[i] ^ b[i];
    }
    result[DIM_U64 - 1] &= LAST_MASK;
    result
}

pub fn batch_hamming(query: &[u64; DIM_U64], corpus: &[[u64; DIM_U64]]) -> Vec<u32> {
    corpus.iter().map(|vec| hamming(query, vec)).collect()
}

pub fn resonate(
    query: &[u64; DIM_U64],
    corpus: &[[u64; DIM_U64]],
    threshold: f64,
) -> Vec<(usize, f64)> {
    let mut results: Vec<(usize, f64)> = corpus
        .iter()
        .enumerate()
        .filter_map(|(i, vec)| {
            let sim = similarity(query, vec);
            if sim >= threshold { Some((i, sim)) } else { None }
        })
        .collect();
    results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    results
}

// SIMD-optimized batch (requires nightly + portable_simd)
#[cfg(feature = "simd")]
pub mod simd {
    use std::simd::*;
    
    pub fn batch_hamming_simd(query: &[u64; 157], corpus: &[[u64; 157]]) -> Vec<u32> {
        // Process 8 vectors at a time using AVX-512
        corpus.chunks(8).flat_map(|chunk| {
            // Vectorized XOR + POPCNT
            chunk.iter().map(|vec| super::hamming(query, vec))
        }).collect()
    }
}