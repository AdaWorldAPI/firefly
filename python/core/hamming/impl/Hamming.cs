/// LadybugDB Hamming Operations - C#
/// Same XOR + POPCOUNT as Python, TypeScript, Rust, Go, C...

using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Security.Cryptography;
using System.Text;

namespace LadybugDB
{
    public class HammingVector
    {
        public const int DIM = 10_000;
        public const int DIM_U64 = 157;
        public const ulong LAST_MASK = (1UL << 16) - 1;

        public ulong[] Data { get; }

        public HammingVector() { Data = new ulong[DIM_U64]; }

        public HammingVector(ulong[] data) { Data = data; }

        public static HammingVector FromSeed(string seed)
        {
            var data = new ulong[DIM_U64];
            using var sha256 = SHA256.Create();
            
            for (int i = 0; i < DIM_U64; i++)
            {
                var input = Encoding.UTF8.GetBytes($"{seed}:{i}");
                var hash = sha256.ComputeHash(input);
                data[i] = BitConverter.ToUInt64(hash, 0);
            }
            data[DIM_U64 - 1] &= LAST_MASK;
            return new HammingVector(data);
        }

        public HammingVector Xor(HammingVector other)
        {
            var result = new ulong[DIM_U64];
            for (int i = 0; i < DIM_U64; i++)
                result[i] = Data[i] ^ other.Data[i];
            result[DIM_U64 - 1] &= LAST_MASK;
            return new HammingVector(result);
        }

        public int Hamming(HammingVector other)
        {
            int total = 0;
            for (int i = 0; i < DIM_U64; i++)
                total += BitOperations.PopCount(Data[i] ^ other.Data[i]);
            return total;
        }

        public double Similarity(HammingVector other) => 1.0 - (double)Hamming(other) / DIM;

        public static HammingVector operator ^(HammingVector a, HammingVector b) => a.Xor(b);
    }

    public static class Ladybug
    {
        public static HammingVector Fingerprint(string name, string signature, string body)
            => HammingVector.FromSeed($"{name}::{signature}::{body}");

        public static List<(int Index, double Similarity)> Resonate(
            HammingVector query, IList<HammingVector> corpus, double threshold = 0.5)
        {
            return corpus
                .Select((v, i) => (Index: i, Similarity: query.Similarity(v)))
                .Where(x => x.Similarity >= threshold)
                .OrderByDescending(x => x.Similarity)
                .ToList();
        }
    }
}