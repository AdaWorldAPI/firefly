//! 10K Hamming Operations - Zig
const std = @import("std");

pub const DIM: usize = 10_000;
pub const DIM_U64: usize = 157;
pub const LAST_MASK: u64 = (1 << 16) - 1;

pub const Vector = [DIM_U64]u64;

pub fn popcount64(x: u64) u32 {
    return @popCount(x);
}

pub fn distance(a: *const Vector, b: *const Vector) u32 {
    var total: u32 = 0;
    for (0..DIM_U64) |i| {
        total += popcount64(a[i] ^ b[i]);
    }
    return total;
}

pub fn similarity(a: *const Vector, b: *const Vector) f64 {
    return 1.0 - @as(f64, @floatFromInt(distance(a, b))) / @as(f64, DIM);
}

pub fn xorBind(a: *const Vector, b: *const Vector) Vector {
    var result: Vector = undefined;
    for (0..DIM_U64) |i| {
        result[i] = a[i] ^ b[i];
    }
    result[DIM_U64 - 1] &= LAST_MASK;
    return result;
}

pub fn batchDistance(
    query: *const Vector, 
    corpus: []const Vector, 
    out: []u32
) void {
    for (corpus, 0..) |*vec, i| {
        out[i] = distance(query, vec);
    }
}

pub const Match = struct {
    index: usize,
    sim: f64,
};

pub fn resonate(
    allocator: std.mem.Allocator,
    query: *const Vector,
    corpus: []const Vector,
    threshold: f64,
) ![]Match {
    var results = std.ArrayList(Match).init(allocator);
    
    for (corpus, 0..) |*vec, i| {
        const sim = similarity(query, vec);
        if (sim >= threshold) {
            try results.append(.{ .index = i, .sim = sim });
        }
    }
    
    std.sort.sort(Match, results.items, {}, struct {
        fn lessThan(_: void, a: Match, b: Match) bool {
            return a.sim > b.sim;
        }
    }.lessThan);
    
    return results.toOwnedSlice();
}