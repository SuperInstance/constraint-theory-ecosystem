// FLUX Constraint Engine — Zig
// Zero-dependency INT8 saturated constraint checking
// Compiles with: zig build

const std = @import("std");

pub const INT8_MIN: i8 = -127;
pub const INT8_MAX: i8 = 127;

pub const Severity = enum(u8) {
    pass = 0,
    caution = 1,
    warning = 2,
    critical = 3,
};

pub const ConstraintDef = struct {
    lo: i8,
    hi: i8,
    name: []const u8,
};

pub const FluxResult = struct {
    error_mask: u8 = 0,
    severity: Severity = .pass,
    violated_lo: u8 = 0,
    violated_hi: u8 = 0,
    violated_count: u8 = 0,
    passed: bool = true,
};

pub fn saturate(val: i32) i8 {
    return @intCast(@max(-127, @min(127, val)));
}

pub const FluxChecker = struct {
    constraints: []const ConstraintDef,

    pub fn init(constraints: []const ConstraintDef) !FluxChecker {
        if (constraints.len == 0) return error.EmptyConstraints;
        if (constraints.len > 8) return error.TooManyConstraints;
        return FluxChecker{ .constraints = constraints };
    }

    pub fn check(self: FluxChecker, value: i32) FluxResult {
        const val = saturate(value);
        var result = FluxResult{};
        var violated: u8 = 0;

        for (self.constraints, 0..) |c, i| {
            const lo = saturate(@as(i32, @intCast(c.lo)));
            const hi = saturate(@as(i32, @intCast(c.hi)));
            const lo_fail = val < lo;
            const hi_fail = val > hi;

            if (lo_fail or hi_fail) {
                result.error_mask |= @as(u8, 1) << @intCast(i);
                violated += 1;
            }
            if (lo_fail) result.violated_lo |= @as(u8, 1) << @intCast(i);
            if (hi_fail) result.violated_hi |= @as(u8, 1) << @intCast(i);
        }

        const nc = self.constraints.len;
        if (violated == 0) {
            result.severity = .pass;
        } else if (violated <= @intCast(nc / 4)) {
            result.severity = .caution;
            result.passed = false;
        } else if (violated <= @intCast(nc / 2)) {
            result.severity = .warning;
            result.passed = false;
        } else {
            result.severity = .critical;
            result.passed = false;
        }
        result.violated_count = violated;
        return result;
    }

    pub fn checkBatch(self: FluxChecker, values: []const i32, allocator: std.mem.Allocator) ![]FluxResult {
        var results = try allocator.alloc(FluxResult, values.len);
        for (values, 0..) |v, i| {
            results[i] = self.check(v);
        }
        return results;
    }
};

// ──── Presets ────

pub const aviation = [_]ConstraintDef{
    .{ .lo = -55, .hi = 70, .name = "cabin_temp_C" },
    .{ .lo = 75, .hi = 101, .name = "cabin_pressure_kPa" },
    .{ .lo = 0, .hi = 100, .name = "fuel_flow_pct" },
    .{ .lo = 60, .hi = 100, .name = "hydraulic_pct" },
};

pub const medical = [_]ConstraintDef{
    .{ .lo = 36, .hi = 38, .name = "body_temp_C" },
    .{ .lo = 60, .hi = 100, .name = "heart_rate_bpm" },
    .{ .lo = 95, .hi = 100, .name = "spo2_pct" },
    .{ .lo = 80, .hi = 120, .name = "bp_systolic_mmHg" },
};

pub const maritime = [_]ConstraintDef{
    .{ .lo = -2, .hi = 35, .name = "sea_temp_C" },
    .{ .lo = 50, .hi = 100, .name = "hull_integrity_pct" },
    .{ .lo = 0, .hi = 50, .name = "wave_height_m" },
    .{ .lo = 0, .hi = 80, .name = "wind_speed_kn" },
};

pub const automotive = [_]ConstraintDef{
    .{ .lo = -40, .hi = 60, .name = "battery_temp_C" },
    .{ .lo = 0, .hi = 100, .name = "soc_pct" },
    .{ .lo = 0, .hi = 100, .name = "charge_rate_pct" },
    .{ .lo = 20, .hi = 80, .name = "cabin_temp_C" },
};

pub const energy = [_]ConstraintDef{
    .{ .lo = 49, .hi = 51, .name = "grid_freq_Hz_x10" },
    .{ .lo = 95, .hi = 105, .name = "voltage_pct" },
    .{ .lo = 0, .hi = 80, .name = "transformer_temp_C" },
    .{ .lo = 0, .hi = 100, .name = "line_load_pct" },
};

// ──── Tests ────

test "saturate boundaries" {
    try std.testing.expectEqual(@as(i8, -127), saturate(-128));
    try std.testing.expectEqual(@as(i8, -127), saturate(-1000));
    try std.testing.expectEqual(@as(i8, 127), saturate(128));
    try std.testing.expectEqual(@as(i8, 127), saturate(1000));
    try std.testing.expectEqual(@as(i8, -127), saturate(-127));
    try std.testing.expectEqual(@as(i8, 0), saturate(0));
    try std.testing.expectEqual(@as(i8, 50), saturate(50));
}

test "single constraint pass" {
    var checker = try FluxChecker.init(&.{
        .{ .lo = 0, .hi = 100, .name = "test" },
    });
    const result = checker.check(50);
    try std.testing.expect(result.passed);
    try std.testing.expect(result.severity == .pass);
    try std.testing.expectEqual(@as(u8, 0), result.error_mask);
}

test "single constraint fail" {
    var checker = try FluxChecker.init(&.{
        .{ .lo = 0, .hi = 100, .name = "test" },
    });
    const result = checker.check(150);
    try std.testing.expect(!result.passed);
    try std.testing.expect(result.error_mask != 0);
}

test "multi constraint mixed" {
    var checker = try FluxChecker.init(&.{
        .{ .lo = 0, .hi = 50, .name = "a" },
        .{ .lo = 0, .hi = 100, .name = "b" },
        .{ .lo = -10, .hi = 10, .name = "c" },
    });
    // value=30: a fails (30<=50 ok), b passes, c fails (30>10)
    const result = checker.check(30);
    try std.testing.expect(!result.passed);
}

test "severity critical" {
    var checker = try FluxChecker.init(&.{
        .{ .lo = 0, .hi = 10, .name = "a" },
        .{ .lo = 0, .hi = 10, .name = "b" },
        .{ .lo = 0, .hi = 10, .name = "c" },
        .{ .lo = 0, .hi = 10, .name = "d" },
    });
    const result = checker.check(50);
    try std.testing.expect(result.severity == .critical);
    try std.testing.expectEqual(@as(u8, 4), result.violated_count);
}

test "preset loading" {
    var checker = try FluxChecker.init(&aviation);
    try std.testing.expectEqual(@as(usize, 4), checker.constraints.len);
}

test "saturation in check" {
    var checker = try FluxChecker.init(&.{
        .{ .lo = -50, .hi = 50, .name = "test" },
    });
    // 200 saturates to 127, which is > 50
    const result = checker.check(200);
    try std.testing.expect(!result.passed);
}
