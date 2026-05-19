// FLUX Constraint Engine — Odin
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// Usage:
//     constraints := [...]Constraint{{-55, 70, "cabin_temp_C"}, {75, 101, "cabin_pressure_kPa"}}
//     checker := new_checker(constraints[:])
//     result := checker.check(60)
//     fmt.println(result.severity, result.error_mask)

package flux_constraint

import "core:fmt"

INT8_MIN :: i8(-127)
INT8_MAX :: i8(127)

Severity :: enum u8 {
	Pass     = 0,
	Caution  = 1,
	Warning  = 2,
	Critical = 3,
}

Constraint :: struct {
	lo:   i8,
	hi:   i8,
	name: string,
}

FluxResult :: struct {
	error_mask:     u8,
	severity:       Severity,
	violated_lo:    u8,
	violated_hi:    u8,
	violated_count: u8,
	passed:         bool,
}

saturate :: proc(val: i8) -> i8 {
	if val < INT8_MIN do return INT8_MIN
	if val > INT8_MAX do return INT8_MAX
	return val
}

FluxChecker :: struct {
	constraints: [dynamic]Constraint,
}

new_checker :: proc(constraints: []Constraint) -> FluxChecker {
	assert(len(constraints) > 0, "FluxConstraint requires non-empty constraints list")
	assert(len(constraints) <= 8, "Maximum 8 constraints (INT8 x8 flat bounds)")

	checker: FluxChecker
	checker.constraints = make([dynamic]Constraint, len(constraints))
	for c in constraints {
		append(&checker.constraints, Constraint{
			lo   = saturate(c.lo),
			hi   = saturate(c.hi),
			name = c.name,
		})
	}
	return checker
}

check :: proc(checker: FluxChecker, value: i8) -> FluxResult {
	val := saturate(value)
	result: FluxResult
	result.severity = .Pass

	violated: u8 = 0

	for i in 0..<len(checker.constraints) {
		c := checker.constraints[i]
		lo_fail := val < c.lo
		hi_fail := val > c.hi
		passed := !lo_fail && !hi_fail

		if !passed {
			result.error_mask |= u8(1 << u8(i))
			violated += 1
		}
		if lo_fail {
			result.violated_lo |= u8(1 << u8(i))
		}
		if hi_fail {
			result.violated_hi |= u8(1 << u8(i))
		}
	}

	nc := len(checker.constraints)
	if violated == 0 {
		result.severity = .Pass
	} else if violated <= u8(nc / 4) {
		result.severity = .Caution
	} else if violated <= u8(nc / 2) {
		result.severity = .Warning
	} else {
		result.severity = .Critical
	}
	result.violated_count = violated
	result.passed = (violated == 0)

	return result
}

// Industry presets
Preset :: struct {
	name:        string,
	constraints: [dynamic]Constraint,
}

aviation_preset :: proc() -> []Constraint {
	return slice_ptr(&[...]Constraint{
		{-55, 70, "cabin_temp_C"},
		{75, 101, "cabin_pressure_kPa"},
		{0, 100, "fuel_flow_pct"},
		{60, 100, "hydraulic_pct"},
	}[:], 4)
}

automotive_preset :: proc() -> []Constraint {
	return slice_ptr(&[...]Constraint{
		{-40, 60, "battery_temp_C"},
		{0, 100, "soc_pct"},
		{0, 100, "charge_rate_pct"},
		{20, 80, "cabin_temp_C"},
	}[:], 4)
}

medical_preset :: proc() -> []Constraint {
	return slice_ptr(&[...]Constraint{
		{36, 38, "body_temp_C"},
		{60, 100, "heart_rate_bpm"},
		{95, 100, "spo2_pct"},
		{80, 120, "bp_systolic_mmHg"},
	}[:], 4)
}

// Usage example
main :: proc() {
	fmt.println("╔══════════════════════════════════════════════╗")
	fmt.println("║  FLUX Constraint Engine — Odin               ║")
	fmt.println("╚══════════════════════════════════════════════╝")
	fmt.println()

	constraints := aviation_preset()
	checker := new_checker(constraints)

	fmt.println("Aviation preset loaded:")
	for c in checker.constraints {
		fmt.printfln("  {} [{}, {}]", c.name, c.lo, c.hi)
	}

	fmt.println("\nExamples:")
	for val in []i8{-60, 0, 25, 70, 90, 127} {
		result := check(checker, val)
		if result.passed {
			fmt.printfln("  val={}: ✓ mask=0x{:02X}", val, result.error_mask)
		} else {
			fmt.printfln("  val={}: ✗ sev={} mask=0x{:02X}", val, result.severity, result.error_mask)
		}
	}
}
