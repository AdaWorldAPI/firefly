// 10K Hamming Operations - C++20
#pragma once

#include <array>
#include <vector>
#include <algorithm>
#include <bit>
#include <cstdint>

namespace hamming {

constexpr size_t DIM = 10'000;
constexpr size_t DIM_U64 = 157;
constexpr uint64_t LAST_MASK = (1ULL << 16) - 1;

using Vector = std::array<uint64_t, DIM_U64>;

[[nodiscard]] constexpr int popcount64(uint64_t x) noexcept {
    return std::popcount(x);
}

[[nodiscard]] constexpr int distance(const Vector& a, const Vector& b) noexcept {
    int total = 0;
    for (size_t i = 0; i < DIM_U64; ++i) {
        total += popcount64(a[i] ^ b[i]);
    }
    return total;
}

[[nodiscard]] constexpr double similarity(const Vector& a, const Vector& b) noexcept {
    return 1.0 - static_cast<double>(distance(a, b)) / static_cast<double>(DIM);
}

[[nodiscard]] constexpr Vector xor_bind(const Vector& a, const Vector& b) noexcept {
    Vector result{};
    for (size_t i = 0; i < DIM_U64; ++i) {
        result[i] = a[i] ^ b[i];
    }
    result[DIM_U64 - 1] &= LAST_MASK;
    return result;
}

[[nodiscard]] std::vector<int> batch_distance(
    const Vector& query, 
    const std::vector<Vector>& corpus
) {
    std::vector<int> results(corpus.size());
    std::transform(corpus.begin(), corpus.end(), results.begin(),
        [&query](const Vector& v) { return distance(query, v); });
    return results;
}

struct Match {
    size_t index;
    double sim;
    
    bool operator<(const Match& other) const { return sim > other.sim; }
};

[[nodiscard]] std::vector<Match> resonate(
    const Vector& query,
    const std::vector<Vector>& corpus,
    double threshold = 0.5
) {
    std::vector<Match> results;
    results.reserve(corpus.size() / 10);  // Estimate 10% match
    
    for (size_t i = 0; i < corpus.size(); ++i) {
        double sim = similarity(query, corpus[i]);
        if (sim >= threshold) {
            results.push_back({i, sim});
        }
    }
    
    std::sort(results.begin(), results.end());
    return results;
}

} // namespace hamming