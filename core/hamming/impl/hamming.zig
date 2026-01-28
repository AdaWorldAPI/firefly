//! LadybugDB Hamming Operations - Zig
//! Same XOR + POPCOUNT as Python, TypeScript, Rust, Go, C, C#, Java...

const std = @import("std");

pub const DIM: usize = 10_000;
pub const DIM_U64: usize = 157;
pub const LAST_MASK: u64 = (1 << 16) - 1;

pub const HammingVector = struct {
    data: [DIM_U64]u64,

    pub fn init() HammingVector {
        return .{ .data = [_]u64{0} ** DIM_U64 };
    }

    pub fn xorWith(self: *const HammingVector, other: *const HammingVector) HammingVector {
        var result = HammingVector.init();
        for (0..DIM_U64) |i| {
            result.data[i] = self.data[i] ^ other.data[i];
        }
        result.data[DIM_U64 - 1] &= LAST_MASK;
        return result;
    }

    pub fn hamming(self: *const HammingVector, other: *const HammingVector) u32 {
        var total: u32 = 0;
        for (0..DIM_U64) |i| {
            total += @popCount(self.data[i] ^ other.data[i]);
        }
        return total;
    }

    pub fn similarity(self: *const HammingVector, other: *const HammingVector) f64 {
        return 1.0 - @as(f64, @floatFromInt(self.hamming(other))) / @as(f64, DIM);
    }
};