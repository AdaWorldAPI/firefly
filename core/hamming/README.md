# Hamming Operations - Every Language

**Resonance = XOR + POPCOUNT**

Same operation, same result, every language.

## Supported Languages

| Language | File | Notes |
|----------|------|-------|
| Python | `hamming.py` | Reference implementation |
| TypeScript | `hamming.ts` | Uses BigInt for 64-bit |
| Rust | `hamming.rs` | Uses `count_ones()` intrinsic |
| Go | `hamming.go` | Uses `bits.OnesCount64` |
| C | `hamming.h` | Header-only, AVX-512 optional |
| C++ | `hamming.hpp` | C++20 `std::popcount` |
| Java | `Hamming.java` | `Long.bitCount()` |
| C# | `Hamming.cs` | `BitOperations.PopCount` |
| Ruby | `hamming.rb` | Pure Ruby |
| Zig | `hamming.zig` | `@popCount` builtin |
| WASM | `hamming.wat` | WebAssembly text format |

## Core Operations

```
DIM = 10,000 bits
DIM_U64 = 157 (uint64 array)

hamming(a, b):
    total = 0
    for i in 0..157:
        total += popcount(a[i] XOR b[i])
    return total

similarity(a, b):
    return 1.0 - hamming(a, b) / 10000

resonate(query, corpus, threshold):
    return [(i, sim) for i, sim in enumerate(corpus) 
            if similarity(query, corpus[i]) >= threshold]
```

## Deterministic Guarantee

**Same fingerprint + same operation = same result in EVERY language**

```python
# Python
hamming(a, b)  # → 4823

# Rust  
hamming(&a, &b)  // → 4823

# TypeScript
hamming(a, b)  // → 4823

# Go
Hamming(&a, &b)  // → 4823
```

No floating point drift. No platform differences. Pure integer operations.

## Usage

### Python
```python
from core.hamming import get_implementation

rust_code = get_implementation("rust")
# Use rust_code in your build system
```

### Direct Import
```python
from core.hamming.impl import hamming_py as hamming

dist = hamming.distance(vec_a, vec_b)
```

## Performance

| Language | Single Op | Batch 10K | Notes |
|----------|-----------|-----------|-------|
| C (AVX-512) | ~50 ns | ~15 ns/vec | Hardware POPCNT |
| Rust | ~80 ns | ~20 ns/vec | LLVM vectorizes |
| Go | ~100 ns | ~25 ns/vec | Good codegen |
| Python+Numba | ~270 ns | ~20 ns/vec | JIT compiled |
| TypeScript | ~500 ns | ~100 ns/vec | BigInt overhead |
| Ruby | ~5 μs | ~1 μs/vec | Pure interpreted |
| WASM | ~200 ns | ~50 ns/vec | Browser dependent |

## Why Every Language?

1. **Fingerprints are portable** - Generate in Python, use in Rust
2. **Cross-platform search** - Browser WASM, server Rust, mobile Go
3. **Consistent results** - No "it works differently on my machine"
4. **Future-proof** - New language? Add implementation, same behavior
