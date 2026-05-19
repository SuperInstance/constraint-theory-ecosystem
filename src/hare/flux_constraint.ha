// FLUX Constraint Engine — Hare
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// Usage:
//     let constraints = [
//         constraint { lo = -55, hi = 70, name = "cabin_temp_C" },
//         constraint { lo = 75, hi = 101, name = "cabin_pressure_kPa" },
//     ];
//     let result = check(constraints, 60);

use fmt;

def INT8_MIN: i8 = -127;
def INT8_MAX: i8 = 127;

export type severity = enum u8 {
	PASS     = 0,
	CAUTION  = 1,
	WARNING  = 2,
	CRITICAL = 3,
};

export type constraint = struct {
	lo:   i8,
	hi:   i8,
	name: const *char,
};

export type flux_result = struct {
	error_mask:     u8,
	severity:       severity,
	violated_lo:    u8,
	violated_hi:    u8,
	violated_count: u8,
	passed:         bool,
};

export fn saturate(val: i8) i8 = {
	if (val < INT8_MIN) return INT8_MIN;
	if (val > INT8_MAX) return INT8_MAX;
	return val;
};

export fn check(constraints: []constraint, value: i8) flux_result = {
	let val = saturate(value);
	let result = flux_result {
		error_mask = 0,
		severity = severity::PASS,
		violated_lo = 0,
		violated_hi = 0,
		violated_count = 0,
		passed = true,
	};

	let violated: u8 = 0;
	const nc = len(constraints);

	for (let i = 0z; i < nc; i += 1) {
		const c = constraints[i];
		const lo_fail = val < c.lo;
		const hi_fail = val > c.hi;
		const passed = !lo_fail && !hi_fail;

		if (!passed) {
			result.error_mask |= (1 << i): u8;
			violated += 1;
		};
		if (lo_fail) {
			result.violated_lo |= (1 << i): u8;
		};
		if (hi_fail) {
			result.violated_hi |= (1 << i): u8;
		};
	};

	// Severity classification
	if (violated == 0) {
		result.severity = severity::PASS;
	} else if (violated <= nc / 4) {
		result.severity = severity::CAUTION;
	} else if (violated <= nc / 2) {
		result.severity = severity::WARNING;
	} else {
		result.severity = severity::CRITICAL;
	};
	result.violated_count = violated;
	result.passed = (violated == 0);

	return result;
};

// Industry presets — aviation
export fn aviation_preset() []constraint = {
	static let presets = [
		constraint { lo = -55, hi = 70, name = "cabin_temp_C" },
		constraint { lo = 75, hi = 101, name = "cabin_pressure_kPa" },
		constraint { lo = 0, hi = 100, name = "fuel_flow_pct" },
		constraint { lo = 60, hi = 100, name = "hydraulic_pct" },
	];
	return presets;
};

// Industry presets — medical
export fn medical_preset() []constraint = {
	static let presets = [
		constraint { lo = 36, hi = 38, name = "body_temp_C" },
		constraint { lo = 60, hi = 100, name = "heart_rate_bpm" },
		constraint { lo = 95, hi = 100, name = "spo2_pct" },
		constraint { lo = 80, hi = 120, name = "bp_systolic_mmHg" },
	];
	return presets;
};

// Industry presets — energy
export fn energy_preset() []constraint = {
	static let presets = [
		constraint { lo = 49, hi = 51, name = "grid_freq_Hz_x10" },
		constraint { lo = 95, hi = 105, name = "voltage_pct" },
		constraint { lo = 0, hi = 80, name = "transformer_temp_C" },
		constraint { lo = 0, hi = 100, name = "line_load_pct" },
	];
	return presets;
};

export fn main() void = {
	fmt::println("╔══════════════════════════════════════════╗")!;
	fmt::println("║  FLUX Constraint Engine — Hare           ║")!;
	fmt::println("╚══════════════════════════════════════════╝")!;
	fmt::println()!;

	const constraints = aviation_preset();
	fmt::println("Aviation preset loaded:")!;
	for (let i = 0z; i < len(constraints); i += 1) {
		const c = constraints[i];
		fmt::printfln("  {} [{}, {}]", c.name, c.lo, c.hi)!;
	};

	fmt::println("\nExamples:")!;
	const test_vals = [-60, 0, 25, 70, 90, 127]: []i8;
	for (let j = 0z; j < len(test_vals); j += 1) {
		const result = check(constraints, test_vals[j]);
		if (result.passed) {
			fmt::printfln("  val={}: ✓ mask=0x{:02X}", test_vals[j], result.error_mask)!;
		} else {
			fmt::printfln("  val={}: ✗ sev={} mask=0x{:02X}",
				test_vals[j], result.severity: u8, result.error_mask)!;
		};
	};
};
