"""
LadybugDB Hamming Operations - Cross-Language CAM

Same XOR + POPCOUNT in every language.
Same fingerprint → same resonance regardless of runtime.

Languages: Python, TypeScript, Rust, Go, C, C#, Java, Zig
"""

# =============================================================================
# PYTHON (reference implementation)
# =============================================================================

PYTHON_HAMMING = '''
"""LadybugDB Hamming Operations - Python"""

import numpy as np
from typing import List, Tuple
import hashlib
import struct

DIM = 10_000
DIM_U64 = 157
LAST_MASK = np.uint64((1 << 16) - 1)


class HammingVector:
    """10K-bit vector for content-addressable memory."""
    
    __slots__ = ['data']
    
    def __init__(self, data: np.ndarray = None):
        if data is None:
            self.data = np.zeros(DIM_U64, dtype=np.uint64)
        else:
            self.data = np.ascontiguousarray(data, dtype=np.uint64)
    
    @classmethod
    def from_seed(cls, seed: str) -> 'HammingVector':
        """Deterministic fingerprint from string seed."""
        data = np.empty(DIM_U64, dtype=np.uint64)
        for i in range(DIM_U64):
            h = hashlib.sha256(f"{seed}:{i}".encode()).digest()
            data[i] = struct.unpack('<Q', h[:8])[0]
        data[-1] &= LAST_MASK
        return cls(data)
    
    def xor(self, other: 'HammingVector') -> 'HammingVector':
        """XOR bind."""
        result = np.bitwise_xor(self.data, other.data)
        result[-1] &= LAST_MASK
        return HammingVector(result)
    
    def hamming(self, other: 'HammingVector') -> int:
        """Hamming distance via XOR + POPCOUNT."""
        xored = np.bitwise_xor(self.data, other.data)
        total = 0
        for x in xored:
            total += bin(x).count('1')
        return total
    
    def similarity(self, other: 'HammingVector') -> float:
        """Normalized similarity [0, 1]."""
        return 1.0 - self.hamming(other) / DIM
    
    def __xor__(self, other):
        return self.xor(other)
    
    def __matmul__(self, other):
        return self.similarity(other)
    
    def to_hex(self) -> str:
        return self.data.tobytes().hex()
    
    @classmethod
    def from_hex(cls, h: str) -> 'HammingVector':
        return cls(np.frombuffer(bytes.fromhex(h), dtype=np.uint64).copy())


def fingerprint(name: str, signature: str, body: str) -> HammingVector:
    """Deterministic fingerprint from code identity."""
    return HammingVector.from_seed(f"{name}::{signature}::{body}")


def resonate(query: HammingVector, corpus: List[HammingVector], threshold: float = 0.5) -> List[Tuple[int, float]]:
    """Find all vectors resonating above threshold."""
    results = []
    for i, vec in enumerate(corpus):
        sim = query @ vec
        if sim >= threshold:
            results.append((i, sim))
    results.sort(key=lambda x: x[1], reverse=True)
    return results
'''

# =============================================================================
# TYPESCRIPT / JAVASCRIPT
# =============================================================================

TYPESCRIPT_HAMMING = '''
/**
 * LadybugDB Hamming Operations - TypeScript
 * Same XOR + POPCOUNT as Python, Rust, Go, C...
 */

const DIM = 10_000;
const DIM_U64 = 157;
const LAST_MASK = BigInt((1 << 16) - 1);

export class HammingVector {
  data: BigUint64Array;

  constructor(data?: BigUint64Array) {
    this.data = data ?? new BigUint64Array(DIM_U64);
  }

  static async fromSeed(seed: string): Promise<HammingVector> {
    const data = new BigUint64Array(DIM_U64);
    const encoder = new TextEncoder();
    
    for (let i = 0; i < DIM_U64; i++) {
      const input = encoder.encode(`${seed}:${i}`);
      const hashBuffer = await crypto.subtle.digest('SHA-256', input);
      const view = new DataView(hashBuffer);
      data[i] = view.getBigUint64(0, true);
    }
    data[DIM_U64 - 1] &= LAST_MASK;
    return new HammingVector(data);
  }

  xor(other: HammingVector): HammingVector {
    const result = new BigUint64Array(DIM_U64);
    for (let i = 0; i < DIM_U64; i++) {
      result[i] = this.data[i] ^ other.data[i];
    }
    result[DIM_U64 - 1] &= LAST_MASK;
    return new HammingVector(result);
  }

  hamming(other: HammingVector): number {
    let total = 0;
    for (let i = 0; i < DIM_U64; i++) {
      let x = this.data[i] ^ other.data[i];
      while (x > 0n) {
        total += Number(x & 1n);
        x >>= 1n;
      }
    }
    return total;
  }

  similarity(other: HammingVector): number {
    return 1.0 - this.hamming(other) / DIM;
  }

  toHex(): string {
    const bytes = new Uint8Array(this.data.buffer);
    return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  static fromHex(hex: string): HammingVector {
    const bytes = new Uint8Array(hex.match(/.{2}/g)!.map(b => parseInt(b, 16)));
    return new HammingVector(new BigUint64Array(bytes.buffer));
  }
}

export async function fingerprint(name: string, signature: string, body: string): Promise<HammingVector> {
  return HammingVector.fromSeed(`${name}::${signature}::${body}`);
}

export function resonate(
  query: HammingVector, 
  corpus: HammingVector[], 
  threshold: number = 0.5
): Array<[number, number]> {
  const results: Array<[number, number]> = [];
  for (let i = 0; i < corpus.length; i++) {
    const sim = query.similarity(corpus[i]);
    if (sim >= threshold) {
      results.push([i, sim]);
    }
  }
  results.sort((a, b) => b[1] - a[1]);
  return results;
}
'''

# =============================================================================
# RUST
# =============================================================================

RUST_HAMMING = '''
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
'''

# =============================================================================
# GO
# =============================================================================

GO_HAMMING = '''
// LadybugDB Hamming Operations - Go
// Same XOR + POPCOUNT as Python, TypeScript, Rust, C...

package ladybug

import (
    "crypto/sha256"
    "encoding/binary"
    "encoding/hex"
    "fmt"
    "math/bits"
    "sort"
)

const (
    DIM      = 10000
    DIM_U64  = 157
    LAST_MASK = (1 << 16) - 1
)

type HammingVector struct {
    Data [DIM_U64]uint64
}

func NewHammingVector() *HammingVector {
    return &HammingVector{}
}

func FromSeed(seed string) *HammingVector {
    v := &HammingVector{}
    for i := 0; i < DIM_U64; i++ {
        input := fmt.Sprintf("%s:%d", seed, i)
        hash := sha256.Sum256([]byte(input))
        v.Data[i] = binary.LittleEndian.Uint64(hash[:8])
    }
    v.Data[DIM_U64-1] &= LAST_MASK
    return v
}

func (v *HammingVector) Xor(other *HammingVector) *HammingVector {
    result := &HammingVector{}
    for i := 0; i < DIM_U64; i++ {
        result.Data[i] = v.Data[i] ^ other.Data[i]
    }
    result.Data[DIM_U64-1] &= LAST_MASK
    return result
}

func (v *HammingVector) Hamming(other *HammingVector) int {
    total := 0
    for i := 0; i < DIM_U64; i++ {
        total += bits.OnesCount64(v.Data[i] ^ other.Data[i])
    }
    return total
}

func (v *HammingVector) Similarity(other *HammingVector) float64 {
    return 1.0 - float64(v.Hamming(other))/float64(DIM)
}

func (v *HammingVector) ToHex() string {
    bytes := make([]byte, DIM_U64*8)
    for i := 0; i < DIM_U64; i++ {
        binary.LittleEndian.PutUint64(bytes[i*8:], v.Data[i])
    }
    return hex.EncodeToString(bytes)
}

func FromHex(h string) (*HammingVector, error) {
    bytes, err := hex.DecodeString(h)
    if err != nil {
        return nil, err
    }
    v := &HammingVector{}
    for i := 0; i < DIM_U64; i++ {
        v.Data[i] = binary.LittleEndian.Uint64(bytes[i*8:])
    }
    return v, nil
}

func Fingerprint(name, signature, body string) *HammingVector {
    return FromSeed(fmt.Sprintf("%s::%s::%s", name, signature, body))
}

type ResonanceResult struct {
    Index      int
    Similarity float64
}

func Resonate(query *HammingVector, corpus []*HammingVector, threshold float64) []ResonanceResult {
    var results []ResonanceResult
    for i, v := range corpus {
        sim := query.Similarity(v)
        if sim >= threshold {
            results = append(results, ResonanceResult{i, sim})
        }
    }
    sort.Slice(results, func(i, j int) bool {
        return results[i].Similarity > results[j].Similarity
    })
    return results
}
'''

# =============================================================================
# C
# =============================================================================

C_HAMMING = '''
/**
 * LadybugDB Hamming Operations - C
 * Same XOR + POPCOUNT as Python, TypeScript, Rust, Go...
 */

#ifndef LADYBUG_HAMMING_H
#define LADYBUG_HAMMING_H

#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <openssl/sha.h>

#define DIM 10000
#define DIM_U64 157
#define LAST_MASK ((1ULL << 16) - 1)

typedef struct {
    uint64_t data[DIM_U64];
} HammingVector;

static inline int popcount64(uint64_t x) {
#if defined(__POPCNT__)
    return __builtin_popcountll(x);
#else
    x = x - ((x >> 1) & 0x5555555555555555ULL);
    x = (x & 0x3333333333333333ULL) + ((x >> 2) & 0x3333333333333333ULL);
    x = (x + (x >> 4)) & 0x0F0F0F0F0F0F0F0FULL;
    return (x * 0x0101010101010101ULL) >> 56;
#endif
}

void hamming_init(HammingVector* v) {
    memset(v->data, 0, sizeof(v->data));
}

void hamming_from_seed(HammingVector* v, const char* seed) {
    char input[1024];
    unsigned char hash[SHA256_DIGEST_LENGTH];
    
    for (int i = 0; i < DIM_U64; i++) {
        snprintf(input, sizeof(input), "%s:%d", seed, i);
        SHA256((unsigned char*)input, strlen(input), hash);
        memcpy(&v->data[i], hash, 8);
    }
    v->data[DIM_U64 - 1] &= LAST_MASK;
}

void hamming_xor(HammingVector* result, const HammingVector* a, const HammingVector* b) {
    for (int i = 0; i < DIM_U64; i++) {
        result->data[i] = a->data[i] ^ b->data[i];
    }
    result->data[DIM_U64 - 1] &= LAST_MASK;
}

int hamming_distance(const HammingVector* a, const HammingVector* b) {
    int total = 0;
    for (int i = 0; i < DIM_U64; i++) {
        total += popcount64(a->data[i] ^ b->data[i]);
    }
    return total;
}

double hamming_similarity(const HammingVector* a, const HammingVector* b) {
    return 1.0 - (double)hamming_distance(a, b) / (double)DIM;
}

void fingerprint(HammingVector* v, const char* name, const char* sig, const char* body) {
    char seed[4096];
    snprintf(seed, sizeof(seed), "%s::%s::%s", name, sig, body);
    hamming_from_seed(v, seed);
}

#endif
'''

# =============================================================================
# C#
# =============================================================================

CSHARP_HAMMING = '''
/// LadybugDB Hamming Operations - C#
/// Same XOR + POPCOUNT as Python, TypeScript, Rust, Go, C...

using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Security.Cryptography;
using System.Text;

namespace LadybugDB
{
    public class HammingVector
    {
        public const int DIM = 10_000;
        public const int DIM_U64 = 157;
        public const ulong LAST_MASK = (1UL << 16) - 1;

        public ulong[] Data { get; }

        public HammingVector() { Data = new ulong[DIM_U64]; }

        public HammingVector(ulong[] data) { Data = data; }

        public static HammingVector FromSeed(string seed)
        {
            var data = new ulong[DIM_U64];
            using var sha256 = SHA256.Create();
            
            for (int i = 0; i < DIM_U64; i++)
            {
                var input = Encoding.UTF8.GetBytes($"{seed}:{i}");
                var hash = sha256.ComputeHash(input);
                data[i] = BitConverter.ToUInt64(hash, 0);
            }
            data[DIM_U64 - 1] &= LAST_MASK;
            return new HammingVector(data);
        }

        public HammingVector Xor(HammingVector other)
        {
            var result = new ulong[DIM_U64];
            for (int i = 0; i < DIM_U64; i++)
                result[i] = Data[i] ^ other.Data[i];
            result[DIM_U64 - 1] &= LAST_MASK;
            return new HammingVector(result);
        }

        public int Hamming(HammingVector other)
        {
            int total = 0;
            for (int i = 0; i < DIM_U64; i++)
                total += BitOperations.PopCount(Data[i] ^ other.Data[i]);
            return total;
        }

        public double Similarity(HammingVector other) => 1.0 - (double)Hamming(other) / DIM;

        public static HammingVector operator ^(HammingVector a, HammingVector b) => a.Xor(b);
    }

    public static class Ladybug
    {
        public static HammingVector Fingerprint(string name, string signature, string body)
            => HammingVector.FromSeed($"{name}::{signature}::{body}");

        public static List<(int Index, double Similarity)> Resonate(
            HammingVector query, IList<HammingVector> corpus, double threshold = 0.5)
        {
            return corpus
                .Select((v, i) => (Index: i, Similarity: query.Similarity(v)))
                .Where(x => x.Similarity >= threshold)
                .OrderByDescending(x => x.Similarity)
                .ToList();
        }
    }
}
'''

# =============================================================================
# JAVA
# =============================================================================

JAVA_HAMMING = '''
/**
 * LadybugDB Hamming Operations - Java
 * Same XOR + POPCOUNT as Python, TypeScript, Rust, Go, C, C#...
 */

package com.ladybugdb;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.security.MessageDigest;
import java.util.*;
import java.util.stream.*;

public class HammingVector {
    public static final int DIM = 10_000;
    public static final int DIM_U64 = 157;
    public static final long LAST_MASK = (1L << 16) - 1;

    private final long[] data;

    public HammingVector() { this.data = new long[DIM_U64]; }
    public HammingVector(long[] data) { this.data = data.clone(); }

    public static HammingVector fromSeed(String seed) {
        long[] data = new long[DIM_U64];
        try {
            MessageDigest sha256 = MessageDigest.getInstance("SHA-256");
            for (int i = 0; i < DIM_U64; i++) {
                byte[] input = String.format("%s:%d", seed, i).getBytes();
                byte[] hash = sha256.digest(input);
                data[i] = ByteBuffer.wrap(hash).order(ByteOrder.LITTLE_ENDIAN).getLong();
            }
        } catch (Exception e) { throw new RuntimeException(e); }
        data[DIM_U64 - 1] &= LAST_MASK;
        return new HammingVector(data);
    }

    public HammingVector xor(HammingVector other) {
        long[] result = new long[DIM_U64];
        for (int i = 0; i < DIM_U64; i++)
            result[i] = this.data[i] ^ other.data[i];
        result[DIM_U64 - 1] &= LAST_MASK;
        return new HammingVector(result);
    }

    public int hamming(HammingVector other) {
        int total = 0;
        for (int i = 0; i < DIM_U64; i++)
            total += Long.bitCount(this.data[i] ^ other.data[i]);
        return total;
    }

    public double similarity(HammingVector other) {
        return 1.0 - (double) hamming(other) / DIM;
    }

    public static HammingVector fingerprint(String name, String sig, String body) {
        return fromSeed(String.format("%s::%s::%s", name, sig, body));
    }

    public static List<Map.Entry<Integer, Double>> resonate(
            HammingVector query, List<HammingVector> corpus, double threshold) {
        return IntStream.range(0, corpus.size())
            .mapToObj(i -> Map.entry(i, query.similarity(corpus.get(i))))
            .filter(e -> e.getValue() >= threshold)
            .sorted((a, b) -> Double.compare(b.getValue(), a.getValue()))
            .collect(Collectors.toList());
    }
}
'''

# =============================================================================
# ZIG
# =============================================================================

ZIG_HAMMING = '''
//! LadybugDB Hamming Operations - Zig
//! Same XOR + POPCOUNT as Python, TypeScript, Rust, Go, C, C#, Java...

const std = @import("std");

pub const DIM: usize = 10_000;
pub const DIM_U64: usize = 157;
pub const LAST_MASK: u64 = (1 << 16) - 1;

pub const HammingVector = struct {
    data: [DIM_U64]u64,

    pub fn init() HammingVector {
        return .{ .data = [_]u64{0} ** DIM_U64 };
    }

    pub fn xorWith(self: *const HammingVector, other: *const HammingVector) HammingVector {
        var result = HammingVector.init();
        for (0..DIM_U64) |i| {
            result.data[i] = self.data[i] ^ other.data[i];
        }
        result.data[DIM_U64 - 1] &= LAST_MASK;
        return result;
    }

    pub fn hamming(self: *const HammingVector, other: *const HammingVector) u32 {
        var total: u32 = 0;
        for (0..DIM_U64) |i| {
            total += @popCount(self.data[i] ^ other.data[i]);
        }
        return total;
    }

    pub fn similarity(self: *const HammingVector, other: *const HammingVector) f64 {
        return 1.0 - @as(f64, @floatFromInt(self.hamming(other))) / @as(f64, DIM);
    }
};
'''

# =============================================================================
# SUMMARY
# =============================================================================

ALL_LANGUAGES = {
    "python": ("hamming.py", PYTHON_HAMMING),
    "typescript": ("hamming.ts", TYPESCRIPT_HAMMING),
    "rust": ("hamming.rs", RUST_HAMMING),
    "go": ("hamming.go", GO_HAMMING),
    "c": ("hamming.h", C_HAMMING),
    "csharp": ("Hamming.cs", CSHARP_HAMMING),
    "java": ("HammingVector.java", JAVA_HAMMING),
    "zig": ("hamming.zig", ZIG_HAMMING),
}

def get_hamming_code(language: str) -> str:
    """Get Hamming ops code for a specific language."""
    return ALL_LANGUAGES.get(language.lower(), ("", ""))[1].strip()

def get_filename(language: str) -> str:
    """Get filename for a specific language."""
    return ALL_LANGUAGES.get(language.lower(), ("", ""))[0]

def list_languages() -> list:
    """List all supported languages."""
    return list(ALL_LANGUAGES.keys())


if __name__ == "__main__":
    print("LadybugDB Hamming Operations")
    print("=" * 50)
    print("Same XOR + POPCOUNT in every language:\n")
    for lang, (filename, code) in ALL_LANGUAGES.items():
        lines = len(code.strip().split('\n'))
        print(f"  {lang:12} → {filename:20} ({lines} lines)")
