package flux

import (
	"fmt"
	"math"
	"time"
)

// Severity levels for constraint violations
const (
	PASS     = 0
	CAUTION  = 1
	WARNING  = 2
	CRITICAL = 3
)

// FluxResult contains the result of a constraint check
type FluxResult struct {
	ErrorMask   uint8 // Bitmask of violated constraints (0-7)
	Severity    int   // Highest severity level encountered
	ViolatedLo  int8  // Lowest violated threshold
	ViolatedHi  int8  // Highest violated threshold
	CheckedValue int8 // The clamped input value that was checked
}

// FluxConstraint represents a single constraint with thresholds
type FluxConstraint struct {
	LoThreshold int8 // Lower threshold
	HiThreshold int8 // Upper threshold
	Severity    int  // Severity level for this constraint
}

// FluxChecker manages up to 8 constraints per sensor
type FluxChecker struct {
	Constraints [8]FluxConstraint
	NumActive   int // Number of active constraints
	SensorName  string
}

// NewFluxChecker creates a new constraint checker
func NewFluxChecker(sensorName string) *FluxChecker {
	return &FluxChecker{
		SensorName: sensorName,
		NumActive:  0,
	}
}

// AddConstraint adds a constraint (max 8 total)
func (fc *FluxChecker) AddConstraint(loThreshold, hiThreshold int8, severity int) error {
	if fc.NumActive >= 8 {
		return fmt.Errorf("maximum 8 constraints allowed")
	}
	if loThreshold > hiThreshold {
		return fmt.Errorf("low threshold cannot be greater than high threshold")
	}

	fc.Constraints[fc.NumActive] = FluxConstraint{
		LoThreshold: loThreshold,
		HiThreshold: hiThreshold,
		Severity:    severity,
	}
	fc.NumActive++
	return nil
}

// saturateINT8 clamps value to [-127, 127]
func saturateINT8(value int) int8 {
	if value > 127 {
		return 127
	}
	if value < -127 {
		return -127
	}
	return int8(value)
}

// Check performs constraint checking on a single value
func (fc *FluxChecker) Check(value int) FluxResult {
	clampedValue := saturateINT8(value)

	result := FluxResult{
		ErrorMask:    0,
		Severity:     PASS,
		ViolatedLo:   127,
		ViolatedHi:   -127,
		CheckedValue: clampedValue,
	}

	for i := 0; i < fc.NumActive; i++ {
		constraint := fc.Constraints[i]

		if clampedValue < constraint.LoThreshold || clampedValue > constraint.HiThreshold {
			// Constraint violated
			result.ErrorMask |= (1 << uint(i))

			if constraint.Severity > result.Severity {
				result.Severity = constraint.Severity
			}

			if constraint.LoThreshold < result.ViolatedLo {
				result.ViolatedLo = constraint.LoThreshold
			}

			if constraint.HiThreshold > result.ViolatedHi {
				result.ViolatedHi = constraint.HiThreshold
			}
		}
	}

	// Reset violated thresholds if no violations
	if result.ErrorMask == 0 {
		result.ViolatedLo = 0
		result.ViolatedHi = 0
	}

	return result
}

// BatchStats contains statistics from batch processing
type BatchStats struct {
	TotalChecks     int
	ViolationCount  int
	MaxSeverity     int
	AvgSeverity     float64
	ProcessingTime  time.Duration
}

// CheckBatch processes multiple values and returns results with statistics
func (fc *FluxChecker) CheckBatch(values []int) ([]FluxResult, BatchStats) {
	startTime := time.Now()

	results := make([]FluxResult, len(values))
	stats := BatchStats{
		TotalChecks: len(values),
		MaxSeverity: PASS,
	}

	totalSeverity := 0

	for i, value := range values {
		results[i] = fc.Check(value)

		if results[i].ErrorMask != 0 {
			stats.ViolationCount++
		}

		if results[i].Severity > stats.MaxSeverity {
			stats.MaxSeverity = results[i].Severity
		}

		totalSeverity += results[i].Severity
	}

	if len(values) > 0 {
		stats.AvgSeverity = float64(totalSeverity) / float64(len(values))
	}

	stats.ProcessingTime = time.Since(startTime)

	return results, stats
}

// FromPreset loads industry-standard constraint presets
func (fc *FluxChecker) FromPreset(presetName string) error {
	fc.NumActive = 0 // Reset constraints

	switch presetName {
	case "aviation":
		// Aviation sensor constraints (altitude, speed, engine parameters)
		fc.AddConstraint(-100, 100, PASS)      // Normal operation range
		fc.AddConstraint(-80, 80, CAUTION)     // Recommended range
		fc.AddConstraint(-60, 60, WARNING)     // Attention needed
		fc.AddConstraint(-40, 40, CRITICAL)    // Immediate action required

	case "medical":
		// Medical device constraints (vital signs, sensor readings)
		fc.AddConstraint(-50, 50, PASS)        // Normal physiological range
		fc.AddConstraint(-40, 40, CAUTION)     // Monitor closely
		fc.AddConstraint(-30, 30, WARNING)     // Clinical intervention
		fc.AddConstraint(-20, 20, CRITICAL)    // Emergency response

	case "maritime":
		// Maritime navigation constraints (compass, depth, weather)
		fc.AddConstraint(-120, 120, PASS)      // Full operational range
		fc.AddConstraint(-90, 90, CAUTION)     // Weather advisory
		fc.AddConstraint(-60, 60, WARNING)     // Navigation warning
		fc.AddConstraint(-30, 30, CRITICAL)    // Safety critical

	case "automotive":
		// Automotive sensor constraints (engine, safety systems)
		fc.AddConstraint(-110, 110, PASS)      // Normal driving range
		fc.AddConstraint(-85, 85, CAUTION)     // Performance monitoring
		fc.AddConstraint(-55, 55, WARNING)     // System alert
		fc.AddConstraint(-25, 25, CRITICAL)    // Safety shutdown

	case "energy":
		// Energy grid constraints (voltage, current, frequency)
		fc.AddConstraint(-127, 127, PASS)      // Full scale range
		fc.AddConstraint(-100, 100, CAUTION)   // Grid stability
		fc.AddConstraint(-75, 75, WARNING)     // Load shedding
		fc.AddConstraint(-50, 50, CRITICAL)    // Protection trip

	default:
		return fmt.Errorf("unknown preset: %s", presetName)
	}

	return nil
}

// Benchmark measures constraint checking performance
func (fc *FluxChecker) Benchmark(iterations int) (float64, error) {
	if iterations <= 0 {
		return 0, fmt.Errorf("iterations must be positive")
	}

	// Prepare test data
	testValues := make([]int, 1000)
	for i := range testValues {
		testValues[i] = (i % 255) - 127 // Range: -127 to 127
	}

	startTime := time.Now()

	checksPerformed := 0
	for i := 0; i < iterations; i++ {
		for _, value := range testValues {
			fc.Check(value)
			checksPerformed++
		}
	}

	duration := time.Since(startTime)
	checksPerSecond := float64(checksPerformed) / duration.Seconds()

	return checksPerSecond, nil
}

// Unit tests embedded in the same file
// To run: go test

//go:build test
// +build test

import (
	"testing"
)

func TestSaturateINT8(t *testing.T) {
	tests := []struct {
		input    int
		expected int8
	}{
		{0, 0},
		{127, 127},
		{128, 127},
		{-127, -127},
		{-128, -127},
		{1000, 127},
		{-1000, -127},
	}

	for _, test := range tests {
		result := saturateINT8(test.input)
		if result != test.expected {
			t.Errorf("saturateINT8(%d) = %d, expected %d", test.input, result, test.expected)
		}
	}
}

func TestAddConstraint(t *testing.T) {
	fc := NewFluxChecker("test")

	// Test normal addition
	err := fc.AddConstraint(-50, 50, WARNING)
	if err != nil {
		t.Errorf("Failed to add constraint: %v", err)
	}

	// Test invalid threshold order
	err = fc.AddConstraint(50, -50, WARNING)
	if err == nil {
		t.Error("Expected error for invalid threshold order")
	}

	// Test maximum constraints
	for i := 1; i < 8; i++ {
		fc.AddConstraint(-10, 10, PASS)
	}

	err = fc.AddConstraint(-5, 5, PASS)
	if err == nil {
		t.Error("Expected error when adding 9th constraint")
	}
}

func TestBasicCheck(t *testing.T) {
	fc := NewFluxChecker("test")
	fc.AddConstraint(-50, 50, WARNING)

	// Test within bounds
	result := fc.Check(25)
	if result.ErrorMask != 0 {
		t.Error("Expected no violations for value within bounds")
	}

	// Test out of bounds
	result = fc.Check(75)
	if result.ErrorMask == 0 {
		t.Error("Expected violation for value out of bounds")
	}

	if result.Severity != WARNING {
		t.Errorf("Expected severity %d, got %d", WARNING, result.Severity)
	}
}

func TestMultipleConstraints(t *testing.T) {
	fc := NewFluxChecker("test")
	fc.AddConstraint(-100, 100, PASS)
	fc.AddConstraint(-50, 50, CAUTION)
	fc.AddConstraint(-25, 25, WARNING)
	fc.AddConstraint(-10, 10, CRITICAL)

	result := fc.Check(75)

	// Should violate constraints 1, 2, and 3 (bits 1, 2, 3 set)
	expectedMask := uint8(0b00001110)
	if result.ErrorMask != expectedMask {
		t.Errorf("Expected error mask %08b, got %08b", expectedMask, result.ErrorMask)
	}

	if result.Severity != CRITICAL {
		t.Errorf("Expected CRITICAL severity, got %d", result.Severity)
	}
}

func TestCheckBatch(t *testing.T) {
	fc := NewFluxChecker("test")
	fc.AddConstraint(-50, 50, WARNING)

	values := []int{-25, 0, 25, 75, -75}
	results, stats := fc.CheckBatch(values)

	if len(results) != len(values) {
		t.Errorf("Expected %d results, got %d", len(values), len(results))
	}

	if stats.TotalChecks != len(values) {
		t.Errorf("Expected %d total checks, got %d", len(values), stats.TotalChecks)
	}

	if stats.ViolationCount != 2 {
		t.Errorf("Expected 2 violations, got %d", stats.ViolationCount)
	}
}

func TestFromPreset(t *testing.T) {
	fc := NewFluxChecker("test")

	presets := []string{"aviation", "medical", "maritime", "automotive", "energy"}

	for _, preset := range presets {
		err := fc.FromPreset(preset)
		if err != nil {
			t.Errorf("Failed to load preset %s: %v", preset, err)
		}

		if fc.NumActive == 0 {
			t.Errorf("Preset %s loaded no constraints", preset)
		}
	}

	// Test invalid preset
	err := fc.FromPreset("invalid")
	if err == nil {
		t.Error("Expected error for invalid preset")
	}
}

func TestBenchmark(t *testing.T) {
	fc := NewFluxChecker("test")
	fc.FromPreset("aviation")

	rate, err := fc.Benchmark(10)
	if err != nil {
		t.Errorf("Benchmark failed: %v", err)
	}

	if rate <= 0 {
		t.Errorf("Expected positive benchmark rate, got %f", rate)
	}

	// Test invalid iterations
	_, err = fc.Benchmark(0)
	if err == nil {
		t.Error("Expected error for zero iterations")
	}
}

func TestSaturationBehavior(t *testing.T) {
	fc := NewFluxChecker("test")
	fc.AddConstraint(-50, 50, WARNING)

	// Test extreme values get saturated
	result := fc.Check(1000)
	if result.CheckedValue != 127 {
		t.Errorf("Expected saturated value 127, got %d", result.CheckedValue)
	}

	result = fc.Check(-1000)
	if result.CheckedValue != -127 {
		t.Errorf("Expected saturated value -127, got %d", result.CheckedValue)
	}
}

func TestViolatedThresholds(t *testing.T) {
	fc := NewFluxChecker("test")
	fc.AddConstraint(-30, 30, WARNING)
	fc.AddConstraint(-60, 60, CAUTION)

	result := fc.Check(45)

	if result.ViolatedLo != -30 {
		t.Errorf("Expected violated_lo -30, got %d", result.ViolatedLo)
	}

	if result.ViolatedHi != 30 {
		t.Errorf("Expected violated_hi 30, got %d", result.ViolatedHi)
	}
}

// Benchmark function for go test -bench
func BenchmarkFluxCheck(b *testing.B) {
	fc := NewFluxChecker("benchmark")
	fc.FromPreset("aviation")

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		fc.Check((i % 255) - 127)
	}
}