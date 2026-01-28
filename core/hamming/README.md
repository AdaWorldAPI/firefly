# LadybugDB Hamming Operations

**Resonance = XOR + POPCOUNT**

Same `HammingVector` class in 8 languages. Identical behavior guaranteed.

## Languages

| Language | File | Class |
|----------|------|-------|
| Python | `hamming.py` | `HammingVector` |
| TypeScript | `hamming.ts` | `HammingVector` |
| Rust | `hamming.rs` | `HammingVector` |
| Go | `hamming.go` | `HammingVector` |
| C | `hamming.h` | `HammingVector` |
| C# | `Hamming.cs` | `HammingVector` |
| Java | `HammingVector.java` | `HammingVector` |
| Zig | `hamming.zig` | `HammingVector` |

## API (Every Language)

```
DIM = 10,000 bits
DIM_U64 = 157 (uint64 array)

class HammingVector:
    data: [157]uint64
    
    from_seed(seed: string) -> HammingVector  # Deterministic from SHA256
    xor(other) -> HammingVector               # XOR bind
    hamming(other) -> int                     # Distance = popcount(xor)
    similarity(other) -> float                # 1.0 - hamming/10000
    to_hex() -> string                        # Serialize
    from_hex(hex) -> HammingVector            # Deserialize

fingerprint(name, signature, body) -> HammingVector
resonate(query, corpus, threshold) -> [(index, similarity)]
```

## Deterministic Guarantee

**Same seed → same fingerprint in EVERY language**

```python
# Python
v = HammingVector.from_seed("my::code::def foo(): pass")
print(v.to_hex())  # → "a1b2c3..."

# Rust
let v = HammingVector::from_seed("my::code::def foo(): pass");
println!("{}", v.to_hex());  // → "a1b2c3..." (IDENTICAL)

# Go
v := FromSeed("my::code::def foo(): pass")
fmt.Println(v.ToHex())  // → "a1b2c3..." (IDENTICAL)
```

## Core Algorithm

```
from_seed(seed):
    for i in 0..157:
        hash = SHA256(f"{seed}:{i}")
        data[i] = little_endian_u64(hash[0:8])
    data[156] &= LAST_MASK
    return HammingVector(data)

hamming(a, b):
    total = 0
    for i in 0..157:
        total += popcount(a.data[i] XOR b.data[i])
    return total

similarity(a, b):
    return 1.0 - hamming(a, b) / 10000
```

## Why Cross-Language?

1. **Generate fingerprint in Python → search in Rust**
2. **Store hex in database → load in any language**
3. **Browser WASM → Server Go → Mobile Swift** (coming)
4. **Same code = same identity everywhere**
