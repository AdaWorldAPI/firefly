// 10K Hamming Operations - Go
package hamming

import (
    "math/bits"
    "sort"
)

const (
    DIM     = 10000
    DIM_U64 = 157
    LAST_MASK = (1 << 16) - 1
)

type Vector [DIM_U64]uint64

func Hamming(a, b *Vector) int {
    total := 0
    for i := 0; i < DIM_U64; i++ {
        total += bits.OnesCount64(a[i] ^ b[i])
    }
    return total
}

func Similarity(a, b *Vector) float64 {
    return 1.0 - float64(Hamming(a, b))/float64(DIM)
}

func XorBind(a, b *Vector) Vector {
    var result Vector
    for i := 0; i < DIM_U64; i++ {
        result[i] = a[i] ^ b[i]
    }
    result[DIM_U64-1] &= LAST_MASK
    return result
}

func BatchHamming(query *Vector, corpus []Vector) []int {
    results := make([]int, len(corpus))
    for i := range corpus {
        results[i] = Hamming(query, &corpus[i])
    }
    return results
}

type Match struct {
    Index      int
    Similarity float64
}

func Resonate(query *Vector, corpus []Vector, threshold float64) []Match {
    var results []Match
    for i := range corpus {
        sim := Similarity(query, &corpus[i])
        if sim >= threshold {
            results = append(results, Match{i, sim})
        }
    }
    sort.Slice(results, func(i, j int) bool {
        return results[i].Similarity > results[j].Similarity
    })
    return results
}