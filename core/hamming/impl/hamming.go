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