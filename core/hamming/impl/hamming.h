/* 10K Hamming Operations - C */
#ifndef HAMMING_H
#define HAMMING_H

#include <stdint.h>
#include <stdlib.h>

#define DIM 10000
#define DIM_U64 157
#define LAST_MASK ((1ULL << 16) - 1)

typedef uint64_t vector_t[DIM_U64];

static inline int popcount64(uint64_t x) {
#ifdef __POPCNT__
    return __builtin_popcountll(x);
#else
    x = x - ((x >> 1) & 0x5555555555555555ULL);
    x = (x & 0x3333333333333333ULL) + ((x >> 2) & 0x3333333333333333ULL);
    x = (x + (x >> 4)) & 0x0F0F0F0F0F0F0F0FULL;
    return (int)((x * 0x0101010101010101ULL) >> 56);
#endif
}

static inline int hamming(const vector_t a, const vector_t b) {
    int total = 0;
    for (int i = 0; i < DIM_U64; i++) {
        total += popcount64(a[i] ^ b[i]);
    }
    return total;
}

static inline double similarity(const vector_t a, const vector_t b) {
    return 1.0 - (double)hamming(a, b) / (double)DIM;
}

static inline void xor_bind(const vector_t a, const vector_t b, vector_t result) {
    for (int i = 0; i < DIM_U64; i++) {
        result[i] = a[i] ^ b[i];
    }
    result[DIM_U64 - 1] &= LAST_MASK;
}

/* Batch Hamming - caller provides output array */
static inline void batch_hamming(
    const vector_t query,
    const vector_t* corpus,
    int n,
    int* out
) {
    for (int i = 0; i < n; i++) {
        out[i] = hamming(query, corpus[i]);
    }
}

/* AVX-512 optimized batch (if available) */
#ifdef __AVX512F__
#include <immintrin.h>

static inline void batch_hamming_avx512(
    const vector_t query,
    const vector_t* corpus,
    int n,
    int* out
) {
    for (int i = 0; i < n; i++) {
        __m512i total = _mm512_setzero_si512();
        for (int j = 0; j < DIM_U64; j += 8) {
            __m512i a = _mm512_loadu_si512(&query[j]);
            __m512i b = _mm512_loadu_si512(&corpus[i][j]);
            __m512i xored = _mm512_xor_si512(a, b);
            __m512i popcnt = _mm512_popcnt_epi64(xored);
            total = _mm512_add_epi64(total, popcnt);
        }
        out[i] = _mm512_reduce_add_epi64(total);
    }
}
#endif

#endif /* HAMMING_H */