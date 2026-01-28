// 10K Hamming Operations - C#
using System;
using System.Collections.Generic;
using System.Numerics;
using System.Runtime.Intrinsics;
using System.Runtime.Intrinsics.X86;

namespace Firefly.Hamming;

public static class HammingOps
{
    public const int DIM = 10_000;
    public const int DIM_U64 = 157;
    public const ulong LAST_MASK = (1UL << 16) - 1;

    public static int Popcount64(ulong x) => BitOperations.PopCount(x);

    public static int Distance(ReadOnlySpan<ulong> a, ReadOnlySpan<ulong> b)
    {
        int total = 0;
        for (int i = 0; i < DIM_U64; i++)
        {
            total += Popcount64(a[i] ^ b[i]);
        }
        return total;
    }

    public static double Similarity(ReadOnlySpan<ulong> a, ReadOnlySpan<ulong> b)
        => 1.0 - (double)Distance(a, b) / DIM;

    public static ulong[] XorBind(ReadOnlySpan<ulong> a, ReadOnlySpan<ulong> b)
    {
        var result = new ulong[DIM_U64];
        for (int i = 0; i < DIM_U64; i++)
        {
            result[i] = a[i] ^ b[i];
        }
        result[DIM_U64 - 1] &= LAST_MASK;
        return result;
    }

    public static int[] BatchDistance(ReadOnlySpan<ulong> query, ulong[][] corpus)
    {
        var results = new int[corpus.Length];
        for (int i = 0; i < corpus.Length; i++)
        {
            results[i] = Distance(query, corpus[i]);
        }
        return results;
    }

    public readonly record struct Match(int Index, double Sim);

    public static List<Match> Resonate(
        ReadOnlySpan<ulong> query, 
        ulong[][] corpus, 
        double threshold = 0.5)
    {
        var results = new List<Match>();
        for (int i = 0; i < corpus.Length; i++)
        {
            var sim = Similarity(query, corpus[i]);
            if (sim >= threshold)
            {
                results.Add(new Match(i, sim));
            }
        }
        results.Sort((a, b) => b.Sim.CompareTo(a.Sim));
        return results;
    }

    // AVX-512 optimized (if available)
    public static int[] BatchDistanceAvx512(ReadOnlySpan<ulong> query, ulong[][] corpus)
    {
        if (!Avx512F.IsSupported) return BatchDistance(query, corpus);
        
        var results = new int[corpus.Length];
        // AVX-512 implementation here
        return results;
    }
}