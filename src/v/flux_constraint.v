// FLUX Constraint Engine — V (vlang)
// Pure INT8 saturated constraint checking. Zero dependencies.

module flux_constraint

const int8_min = -127
const int8_max = 127

pub fn saturate(val int) int {
	return if val < int8_min { int8_min } else if val > int8_max { int8_max } else { val }
}

pub enum Severity {
	pass = 0
	caution = 1
	warning = 2
	critical = 3
}

pub struct Constraint {
pub:
	lo   int
	hi   int
	name string
}

pub struct FluxResult {
pub:
	error_mask    int
	severity      Severity
	violated_lo   int
	violated_hi   int
	violated_count int
	passed        bool
}

pub struct FluxChecker {
pub:
	constraints []Constraint
}

pub fn new_checker(constraints []Constraint) !FluxChecker {
	if constraints.len == 0 {
		return error('Non-empty constraints required')
	}
	if constraints.len > 8 {
		return error('Max 8 constraints')
	}
	return FluxChecker{constraints: constraints}
}

pub fn (fc FluxChecker) check(value int) FluxResult {
	val := saturate(value)
	mut error_mask := 0
	mut violated_lo := 0
	mut violated_hi := 0
	mut violated_count := 0

	for i, c in fc.constraints {
		lo := saturate(c.lo)
		hi := saturate(c.hi)
		lo_fail := val < lo
		hi_fail := val > hi
		if lo_fail || hi_fail {
			error_mask |= (1 << i)
			violated_count++
		}
		if lo_fail { violated_lo |= (1 << i) }
		if hi_fail { violated_hi |= (1 << i) }
	}

	nc := fc.constraints.len
	sev := if violated_count == 0 { Severity.pass }
		else if violated_count <= nc / 4 { Severity.caution }
		else if violated_count <= nc / 2 { Severity.warning }
		else { Severity.critical }

	return FluxResult{
		error_mask: error_mask
		severity: sev
		violated_lo: violated_lo
		violated_hi: violated_hi
		violated_count: violated_count
		passed: sev == .pass
	}
}

pub fn (fc FluxChecker) check_batch(values []int) ([]FluxResult, map[string]int) {
	mut results := []FluxResult{cap: values.len}
	mut stats := {
		'pass':      0
		'caution':   0
		'warning':   0
		'critical':  0
	}
	for v in values {
		r := fc.check(v)
		results << r
		stats[r.severity.str()]++
	}
	return results, stats
}

// Presets
pub fn from_preset(name string) !FluxChecker {
	mut cs := []Capability{}
	match name {
		'aviation' {
			cs = [Constraint{-55, 70, 'cabin_temp_C'}, Constraint{75, 101, 'cabin_pressure_kPa'},
				Constraint{0, 100, 'fuel_flow_pct'}, Constraint{60, 100, 'hydraulic_pct'}]
		}
		'medical' {
			cs = [Constraint{36, 38, 'body_temp_C'}, Constraint{60, 100, 'heart_rate_bpm'},
				Constraint{95, 100, 'spo2_pct'}, Constraint{80, 120, 'bp_systolic_mmHg'}]
		}
		else { return error('Unknown preset: $name') }
	}
	return new_checker(cs)!
}

fn test_saturate() {
	assert saturate(-128) == -127
	assert saturate(128) == 127
	assert saturate(0) == 0
}

fn test_check() {
	fc := new_checker([Constraint{0, 100, 'test'}])!
	r1 := fc.check(50)
	assert r1.passed == true
	r2 := fc.check(150)
	assert r2.passed == false
}
