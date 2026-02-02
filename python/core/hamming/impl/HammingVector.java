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