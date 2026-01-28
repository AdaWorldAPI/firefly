/**
 * 10K Hamming Operations - TypeScript
 * Uses BigInt for 64-bit operations
 */

const DIM = 10_000;
const DIM_U64 = 157;
const LAST_MASK = BigInt((1 << 16) - 1);

function popcount64(x: bigint): number {
    x = x - ((x >> 1n) & 0x5555555555555555n);
    x = (x & 0x3333333333333333n) + ((x >> 2n) & 0x3333333333333333n);
    x = (x + (x >> 4n)) & 0x0F0F0F0F0F0F0F0Fn;
    return Number((x * 0x0101010101010101n) >> 56n) & 0xFF;
}

export function hamming(a: bigint[], b: bigint[]): number {
    let total = 0;
    for (let i = 0; i < DIM_U64; i++) {
        total += popcount64(a[i] ^ b[i]);
    }
    return total;
}

export function similarity(a: bigint[], b: bigint[]): number {
    return 1.0 - hamming(a, b) / DIM;
}

export function xorBind(a: bigint[], b: bigint[]): bigint[] {
    const result: bigint[] = new Array(DIM_U64);
    for (let i = 0; i < DIM_U64; i++) {
        result[i] = a[i] ^ b[i];
    }
    result[DIM_U64 - 1] &= LAST_MASK;
    return result;
}

export function batchHamming(query: bigint[], corpus: bigint[][]): number[] {
    return corpus.map(vec => hamming(query, vec));
}

export function resonate(
    query: bigint[], 
    corpus: bigint[][], 
    threshold: number = 0.5
): [number, number][] {
    const results: [number, number][] = [];
    for (let i = 0; i < corpus.length; i++) {
        const sim = similarity(query, corpus[i]);
        if (sim >= threshold) {
            results.push([i, sim]);
        }
    }
    return results.sort((a, b) => b[1] - a[1]);
}