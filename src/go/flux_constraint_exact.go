// Package flux — FLUX Exact Constraint Engine
// Zero false negatives. Bounds and values in original numeric space.
//
// INVARIANT: A value outside bounds is ALWAYS detected. No exceptions.

package flux

import (
	"fmt"
	"time"
)

// ═══════════════════════════════════════════════════════════
// Severity levels
// ═══════════════════════════════════════════════════════════

const (
	ExactPass     = 0
	ExactCaution  = 1
	ExactWarning  = 2
	ExactCritical = 3
)

// Severity lookup from violation count
var ExactSeverityTable = [9]int{
	ExactPass,     // 0 violations
	ExactCaution,  // 1
	ExactCaution,  // 2
	ExactWarning,  // 3
	ExactWarning,  // 4
	ExactCritical, // 5
	ExactCritical, // 6
	ExactCritical, // 7
	ExactCritical, // 8
}

// ═══════════════════════════════════════════════════════════
// Constraint definition — bounds as ORIGINAL float64 values
// ═══════════════════════════════════════════════════════════

// ExactConstraintDef defines a single constraint with original bounds
type ExactConstraintDef struct {
	Lo   float64 // Lower bound — ORIGINAL value, NOT quantized
	Hi   float64 // Upper bound — ORIGINAL value, NOT quantized
	Name string  // Human-readable identifier
}

// ═══════════════════════════════════════════════════════════
// Result structure
// ═══════════════════════════════════════════════════════════

// ExactResult contains the result of an exact constraint check
type ExactResult struct {
	ErrorMask    uint8  // Bit i set = constraint i violated
	Severity     int    // From severity table
	ViolatedLo   uint8  // Bitmask of lower-bound violations
	ViolatedHi   uint8  // Bitmask of upper-bound violations
	ViolatedCount int   // Number of violated constraints
}

// Passed returns true iff all constraints passed
func (r *ExactResult) Passed() bool {
	return r.ErrorMask == 0
}

// ═══════════════════════════════════════════════════════════
// Exact constraint checker
// ═══════════════════════════════════════════════════════════

// FluxExactChecker manages up to 8 constraints with exact bounds
type FluxExactChecker struct {
	Constraints []ExactConstraintDef
}

// NewFluxExactChecker creates a new exact constraint checker
func NewFluxExactChecker(constraints []ExactConstraintDef) (*FluxExactChecker, error) {
	if len(constraints) == 0 {
		return nil, fmt.Errorf("requires non-empty constraints")
	}
	if len(constraints) > 8 {
		return nil, fmt.Errorf("maximum 8 constraints")
	}
	for i, c := range constraints {
		if c.Lo > c.Hi {
			return nil, fmt.Errorf("constraint %d (%s): lo (%v) > hi (%v)", i, c.Name, c.Lo, c.Hi)
		}
	}
	return &FluxExactChecker{Constraints: constraints}, nil
}

// Check performs EXACT constraint checking on a single value.
//
// INVARIANT: value is compared in ORIGINAL numeric space.
// No quantization. No saturation. Exact comparison.
// ZERO false negatives guaranteed.
func (fc *FluxExactChecker) Check(value float64) ExactResult {
	result := ExactResult{}
	violated := 0

	for i, c := range fc.Constraints {
		loFail := value < c.Lo
		hiFail := value > c.Hi

		if loFail || hiFail {
			result.ErrorMask |= (1 << uint(i))
			violated++
		}
		if loFail {
			result.ViolatedLo |= (1 << uint(i))
		}
		if hiFail {
			result.ViolatedHi |= (1 << uint(i))
		}
	}

	result.ViolatedCount = violated
	idx := violated
	if idx > 8 {
		idx = 8
	}
	result.Severity = ExactSeverityTable[idx]

	return result
}

// CheckBatch processes multiple values
func (fc *FluxExactChecker) CheckBatch(values []float64) ([]ExactResult, ExactBatchStats) {
	start := time.Now()

	results := make([]ExactResult, len(values))
	stats := ExactBatchStats{TotalChecks: len(values)}

	for i, v := range values {
		results[i] = fc.Check(v)
		if results[i].Passed() {
			stats.PassCount++
		} else {
			stats.ViolationCount++
		}
	}

	stats.ProcessingTime = time.Since(start)
	return results, stats
}

// ExactBatchStats contains statistics from batch processing
type ExactBatchStats struct {
	TotalChecks    int
	PassCount      int
	ViolationCount int
	ProcessingTime time.Duration
}

// ═══════════════════════════════════════════════════════════
// Presets
// ═══════════════════════════════════════════════════════════

// PresetAutomotiveCAN returns the automotive CAN bus constraint preset
func PresetAutomotiveCAN() []ExactConstraintDef {
	return []ExactConstraintDef{
		{Lo: 0, Hi: 8000, Name: "engine_rpm"},
		{Lo: 0, Hi: 300, Name: "vehicle_speed_kmh"},
		{Lo: -40, Hi: 150, Name: "coolant_temp_c"},
		{Lo: 0, Hi: 100, Name: "throttle_pct"},
		{Lo: 0, Hi: 200, Name: "brake_pressure_bar"},
		{Lo: -720, Hi: 720, Name: "steering_angle_deg"},
		{Lo: 9, Hi: 16, Name: "battery_voltage_v"},
		{Lo: 0, Hi: 100, Name: "fuel_level_pct"},
	}
}

// PresetAviationADSB returns the aviation ADS-B constraint preset
func PresetAviationADSB() []ExactConstraintDef {
	return []ExactConstraintDef{
		{Lo: -1000, Hi: 45000, Name: "altitude_ft"},
		{Lo: 0, Hi: 600, Name: "ground_speed_kt"},
		{Lo: -180, Hi: 180, Name: "heading_deg"},
		{Lo: -55, Hi: 70, Name: "cabin_temp_c"},
		{Lo: 75, Hi: 101, Name: "cabin_pressure_kpa"},
		{Lo: 0, Hi: 100, Name: "fuel_flow_pct"},
		{Lo: 60, Hi: 100, Name: "hydraulic_pct"},
		{Lo: -90, Hi: 90, Name: "pitch_deg"},
	}
}

// PresetMedicalFHIR returns the medical FHIR constraint preset
func PresetMedicalFHIR() []ExactConstraintDef {
	return []ExactConstraintDef{
		{Lo: 36.1, Hi: 37.8, Name: "body_temp_c"},
		{Lo: 60, Hi: 100, Name: "heart_rate_bpm"},
		{Lo: 95, Hi: 100, Name: "spo2_pct"},
		{Lo: 80, Hi: 120, Name: "bp_systolic_mmhg"},
		{Lo: 60, Hi: 100, Name: "bp_diastolic_mmhg"},
		{Lo: 12, Hi: 20, Name: "respiratory_rate"},
		{Lo: 7.35, Hi: 7.45, Name: "ph"},
		{Lo: 0, Hi: 300, Name: "glucose_mg_dl"},
	}
}

// PresetEnergySCADA returns the energy SCADA constraint preset
func PresetEnergySCADA() []ExactConstraintDef {
	return []ExactConstraintDef{
		{Lo: 49.0, Hi: 51.0, Name: "grid_freq_hz"},
		{Lo: 0.9, Hi: 1.1, Name: "voltage_pu"},
		{Lo: 0, Hi: 80, Name: "transformer_temp_c"},
		{Lo: 0, Hi: 100, Name: "line_load_pct"},
		{Lo: 0, Hi: 500, Name: "current_a"},
		{Lo: -100, Hi: 100, Name: "power_factor_offset"},
		{Lo: 0, Hi: 360, Name: "phase_angle_deg"},
		{Lo: 0, Hi: 50, Name: "thd_pct"},
	}
}

// Benchmark measures constraint checking performance
func (fc *FluxExactChecker) Benchmark(iterations int) (float64, error) {
	if iterations <= 0 {
		return 0, fmt.Errorf("iterations must be positive")
	}

	start := time.Now()
	for i := 0; i < iterations; i++ {
		fc.Check(float64((i % 1000) - 500))
	}
	duration := time.Since(start)

	checksPerSec := float64(iterations) / duration.Seconds()
	return checksPerSec, nil
}
