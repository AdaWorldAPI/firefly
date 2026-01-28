package com.firefly.hamming;

import java.util.*;

/**
 * 10K Hamming Operations - Java
 */
public class Hamming {
    public static final int DIM = 10_000;
    public static final int DIM_U64 = 157;
    public static final long LAST_MASK = (1L << 16) - 1;
    
    public static int popcount64(long x) {
        return Long.bitCount(x);
    }
    
    public static int distance(long[] a, long[] b) {
        int total = 0;
        for (int i = 0; i < DIM_U64; i++) {
            total += popcount64(a[i] ^ b[i]);
        }
        return total;
    }
    
    public static double similarity(long[] a, long[] b) {
        return 1.0 - (double) distance(a, b) / (double) DIM;
    }
    
    public static long[] xorBind(long[] a, long[] b) {
        long[] result = new long[DIM_U64];
        for (int i = 0; i < DIM_U64; i++) {
            result[i] = a[i] ^ b[i];
        }
        result[DIM_U64 - 1] &= LAST_MASK;
        return result;
    }
    
    public static int[] batchDistance(long[] query, long[][] corpus) {
        int[] results = new int[corpus.length];
        for (int i = 0; i < corpus.length; i++) {
            results[i] = distance(query, corpus[i]);
        }
        return results;
    }
    
    public record Match(int index, double similarity) {}
    
    public static List<Match> resonate(long[] query, long[][] corpus, double threshold) {
        List<Match> results = new ArrayList<>();
        for (int i = 0; i < corpus.length; i++) {
            double sim = similarity(query, corpus[i]);
            if (sim >= threshold) {
                results.add(new Match(i, sim));
            }
        }
        results.sort((a, b) -> Double.compare(b.similarity(), a.similarity()));
        return results;
    }
}