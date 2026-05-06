const std = @import("std");
const flux = @import("../src/zig/flux_constraint.zig");

const Vector = struct {
    id: i32,
    value: i32,
    constraints: []const struct { lo: i32, hi: i32 },
    expected: struct {
        error_mask: i32,
        violated_lo: i32,
        violated_hi: i32,
        violated_count: i32,
        passed: bool,
    },
};

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const file = try std.fs.cwd().openFile("tools/golden_vectors.json", .{});
    defer file.close();
    const data = try file.readToEndAlloc(allocator, 50 * 1024 * 1024);
    defer allocator.free(data);

    const parsed = try std.json.parseFromSlice([]const Vector, allocator, data, .{
        .ignore_unknown_fields = true,
    });
    defer parsed.deinit();
    const vectors = parsed.value;

    var mismatches: i32 = 0;
    for (vectors) |v| {
        var cs: [8]flux.Constraint = undefined;
        for (v.constraints, 0..) |c, i| {
            cs[i] = .{ .lo = c.lo, .hi = c.hi };
        }
        const checker = flux.FluxChecker{ .constraints = cs[0..v.constraints.len] };
        const r = checker.check(v.value);
        if (r.error_mask != v.expected.error_mask or r.passed != v.expected.passed) {
            mismatches += 1;
        }
    }

    const stdout = std.io.getStdOut().writer();
    try stdout.print("\nZig: {} vectors, {} mismatches\n", .{ vectors.len, mismatches });
    if (mismatches > 0) std.process.exit(1);
}
