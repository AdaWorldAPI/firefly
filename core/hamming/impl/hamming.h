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