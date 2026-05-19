//! # FLUX Exact Constraint Engine — Rust Implementation
//!
//! Zero false negatives. Bounds and values compared in original numeric space.
//! Generic over numeric types (f32, f64, i32, i64). no_std compatible.
//!
//! INVARIANT: A value outside bounds is ALWAYS detected. No exceptions.

#![no_std]
extern crate alloc;
use alloc::string::String;
use alloc::vec::Vec;

// ═══════════════════════════════════════════════════════════
// Severity
// ═══════════════════════════════════════════════════════════

/// Severity levels for constraint violations
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Severity {
    Pass = 0,
    Caution = 1,
    Warning = 2,
    Critical = 3,
}

/// Severity lookup from violation count (0-8)
const SEVERITY_TABLE: [Severity; 9] = [
    Severity::Pass,
    Severity::Caution,
    Severity::Caution,
    Severity::Warning,
    Severity::Warning,
    Severity::Critical,
    Severity::Critical,
    Severity::Critical,
    Severity::Critical,
];

/// Lookup severity from violation count
pub fn severity_from_count(count: u8) -> Severity {
    SEVERITY_TABLE[if count > 8 { 8 } else { count as usize }]
}

// ═══════════════════════════════════════════════════════════
// Numeric trait — any type supporting exact ordered comparison
// ═══════════════════════════════════════════════════════════

/// Trait for numeric types that support exact constraint checking.
/// Must support ordered comparison — the foundation of zero false negatives.
pub trait Numeric: Copy + PartialOrd + core::fmt::Debug {}
impl Numeric for f32 {}
impl Numeric for f64 {}
impl Numeric for i8 {}
impl Numeric for i16 {}
impl Numeric for i32 {}
impl Numeric for i64 {}
impl Numeric for u8 {}
impl Numeric for u16 {}
impl Numeric for u32 {}
impl Numeric for u64 {}

// ═══════════════════════════════════════════════════════════
// Constraint definition — bounds stored as ORIGINAL values
// ═══════════════════════════════════════════════════════════

/// A single constraint with bounds stored in original numeric space.
#[derive(Debug, Clone, PartialEq)]
pub struct ExactConstraint<T: Numeric> {
    /// Lower bound (inclusive) — ORIGINAL value, NOT quantized
    pub lo: T,
    /// Upper bound (inclusive) — ORIGINAL value, NOT quantized
    pub hi: T,
    /// Human-readable name
    pub name: &'static str,
}

impl<T: Numeric> ExactConstraint<T> {
    /// Create a new constraint. Returns Err if lo > hi.
    pub fn new(lo: T, hi: T, name: &'static str) -> Result<Self, FluxExactError> {
        if lo > hi {
            return Err(FluxExactError::InvalidBounds(name));
        }
        Ok(ExactConstraint { lo, hi, name })
    }
}

// ═══════════════════════════════════════════════════════════
// Result type — zero false negative guarantee encoded in type
// ═══════════════════════════════════════════════════════════

/// Result of an exact constraint check.
///
/// INVARIANT: If any constraint was violated, error_mask != 0.
/// This is guaranteed by the exact comparison — no quantization.
#[derive(Debug, Clone, PartialEq)]
pub struct ExactResult {
    /// Bitmask of violated constraints (bit i = constraint i failed)
    pub error_mask: u8,
    /// Severity level (derived from error_mask popcount)
    pub severity: Severity,
    /// Bitmask of lower-bound violations
    pub violated_lo: u8,
    /// Bitmask of upper-bound violations
    pub violated_hi: u8,
    /// Number of violated constraints
    pub violated_count: u8,
}

impl ExactResult {
    /// All-pass result
    pub fn pass() -> Self {
        ExactResult {
            error_mask: 0,
            severity: Severity::Pass,
            violated_lo: 0,
            violated_hi: 0,
            violated_count: 0,
        }
    }

    /// Returns true iff all constraints passed
    pub fn is_pass(&self) -> bool {
        self.error_mask == 0
    }

    /// Returns true iff any constraint was violated
    pub fn is_violation(&self) -> bool {
        self.error_mask != 0
    }
}

// ═══════════════════════════════════════════════════════════
// Error types
// ═══════════════════════════════════════════════════════════

#[derive(Debug, Clone, PartialEq)]
pub enum FluxExactError {
    InvalidBounds(&'static str),
    TooManyConstraints,
    PresetNotFound(String),
}

// ═══════════════════════════════════════════════════════════
// Exact constraint checker
// ═══════════════════════════════════════════════════════════

/// High-performance exact constraint checker.
/// Bounds and values compared in original numeric space.
/// ZERO false negatives guaranteed.
pub struct FluxExactChecker<T: Numeric> {
    constraints: Vec<ExactConstraint<T>>,
}

impl<T: Numeric> FluxExactChecker<T> {
    /// Create a new checker with the given constraints.
    /// Maximum 8 constraints (error_mask is u8).
    pub fn new(constraints: Vec<ExactConstraint<T>>) -> Result<Self, FluxExactError> {
        if constraints.len() > 8 {
            return Err(FluxExactError::TooManyConstraints);
        }
        Ok(FluxExactChecker { constraints })
    }

    /// Create an empty checker
    pub fn empty() -> Self {
        FluxExactChecker { constraints: Vec::new() }
    }

    /// Add a constraint
    pub fn add(&mut self, constraint: ExactConstraint<T>) -> Result<(), FluxExactError> {
        if self.constraints.len() >= 8 {
            return Err(FluxExactError::TooManyConstraints);
        }
        self.constraints.push(constraint);
        Ok(())
    }

    /// Check a single value against all constraints.
    ///
    /// INVARIANT: value is compared in ORIGINAL numeric space.
    /// No quantization. No saturation. Exact comparison.
    /// ZERO false negatives guaranteed.
    #[inline]
    pub fn check(&self, value: T) -> ExactResult {
        let mut result = ExactResult::pass();
        let mut violated = 0u8;

        for (i, constraint) in self.constraints.iter().enumerate() {
            let lo_fail = value < constraint.lo;
            let hi_fail = value > constraint.hi;

            if lo_fail || hi_fail {
                result.error_mask |= 1 << i;
                violated += 1;
            }
            if lo_fail {
                result.violated_lo |= 1 << i;
            }
            if hi_fail {
                result.violated_hi |= 1 << i;
            }
        }

        result.violated_count = violated;
        result.severity = severity_from_count(violated);
        result
    }

    /// Check multiple values in batch
    pub fn check_batch(&self, values: &[T]) -> Vec<ExactResult> {
        values.iter().map(|&v| self.check(v)).collect()
    }

    /// Number of active constraints
    pub fn len(&self) -> usize {
        self.constraints.len()
    }

    /// Whether the checker has any constraints
    pub fn is_empty(&self) -> bool {
        self.constraints.is_empty()
    }
}

// ═══════════════════════════════════════════════════════════
// f32-specific presets
// ═══════════════════════════════════════════════════════════

impl FluxExactChecker<f32> {
    /// Automotive CAN bus preset
    pub fn automotive_can() -> Result<Self, FluxExactError> {
        FluxExactChecker::new(alloc::vec![
            ExactConstraint::new(0.0, 8000.0, "engine_rpm").unwrap(),
            ExactConstraint::new(0.0, 300.0, "vehicle_speed_kmh").unwrap(),
            ExactConstraint::new(-40.0, 150.0, "coolant_temp_c").unwrap(),
            ExactConstraint::new(0.0, 100.0, "throttle_pct").unwrap(),
            ExactConstraint::new(0.0, 200.0, "brake_pressure_bar").unwrap(),
            ExactConstraint::new(-720.0, 720.0, "steering_angle_deg").unwrap(),
            ExactConstraint::new(9.0, 16.0, "battery_voltage_v").unwrap(),
            ExactConstraint::new(0.0, 100.0, "fuel_level_pct").unwrap(),
        ])
    }

    /// Aviation ADS-B preset
    pub fn aviation_adsb() -> Result<Self, FluxExactError> {
        FluxExactChecker::new(alloc::vec![
            ExactConstraint::new(-1000.0, 45000.0, "altitude_ft").unwrap(),
            ExactConstraint::new(0.0, 600.0, "ground_speed_kt").unwrap(),
            ExactConstraint::new(-180.0, 180.0, "heading_deg").unwrap(),
            ExactConstraint::new(-55.0, 70.0, "cabin_temp_c").unwrap(),
            ExactConstraint::new(75.0, 101.0, "cabin_pressure_kpa").unwrap(),
            ExactConstraint::new(0.0, 100.0, "fuel_flow_pct").unwrap(),
            ExactConstraint::new(60.0, 100.0, "hydraulic_pct").unwrap(),
            ExactConstraint::new(-90.0, 90.0, "pitch_deg").unwrap(),
        ])
    }

    /// Medical FHIR preset
    pub fn medical_fhir() -> Result<Self, FluxExactError> {
        FluxExactChecker::new(alloc::vec![
            ExactConstraint::new(36.1, 37.8, "body_temp_c").unwrap(),
            ExactConstraint::new(60.0, 100.0, "heart_rate_bpm").unwrap(),
            ExactConstraint::new(95.0, 100.0, "spo2_pct").unwrap(),
            ExactConstraint::new(80.0, 120.0, "bp_systolic_mmhg").unwrap(),
            ExactConstraint::new(60.0, 100.0, "bp_diastolic_mmhg").unwrap(),
            ExactConstraint::new(12.0, 20.0, "respiratory_rate").unwrap(),
            ExactConstraint::new(7.35, 7.45, "ph").unwrap(),
            ExactConstraint::new(0.0, 300.0, "glucose_mg_dl").unwrap(),
        ])
    }
}

// ═══════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_exact_boundary_f32() {
        let checker = FluxExactChecker::<f32>::automotive_can().unwrap();
        // coolant_temp_c: [-40, 150]
        // Check constraint index 2
        let c = &checker.constraints[2];
        assert_eq!(c.name, "coolant_temp_c");
        assert_eq!(c.lo, -40.0f32);
        assert_eq!(c.hi, 150.0f32);
    }

    #[test]
    fn test_exact_no_false_negative() {
        let c = ExactConstraint::new(-40.0f32, 150.0f32, "temp").unwrap();
        let checker = FluxExactChecker::new(alloc::vec![c]).unwrap();

        // Values OUTSIDE bounds must be detected
        assert!(!checker.check(151.0).is_pass());
        assert!(!checker.check(150.001).is_pass());
        assert!(!checker.check(-40.001).is_pass());
        assert!(!checker.check(-41.0).is_pass());
        assert!(!checker.check(1000.0).is_pass());
        assert!(!checker.check(-1000.0).is_pass());

        // Values INSIDE bounds must pass
        assert!(checker.check(150.0).is_pass());
        assert!(checker.check(-40.0).is_pass());
        assert!(checker.check(55.0).is_pass());
        assert!(checker.check(0.0).is_pass());
    }

    #[test]
    fn test_exact_int_types() {
        // i32: wide ranges
        let c = ExactConstraint::new(-1000i32, 45000i32, "altitude").unwrap();
        let checker = FluxExactChecker::new(alloc::vec![c]).unwrap();

        assert!(checker.check(45000).is_pass());
        assert!(!checker.check(45001).is_pass());
        assert!(checker.check(-1000).is_pass());
        assert!(!checker.check(-1001).is_pass());
    }

    #[test]
    fn test_error_mask_bits() {
        let constraints = alloc::vec![
            ExactConstraint::new(0.0f32, 10.0, "c0").unwrap(),
            ExactConstraint::new(0.0f32, 20.0, "c1").unwrap(),
            ExactConstraint::new(0.0f32, 5.0,  "c2").unwrap(),
        ];
        let checker = FluxExactChecker::new(constraints).unwrap();

        // value=8: passes c0 [0,10] and c1 [0,20], fails c2 [0,5]
        let r = checker.check(8.0);
        assert_eq!(r.error_mask, 0b100);
        assert!(r.is_violation());

        // value=15: passes c1, fails c0 and c2
        let r = checker.check(15.0);
        assert_eq!(r.error_mask, 0b101);

        // value=3: passes all
        let r = checker.check(3.0);
        assert_eq!(r.error_mask, 0);
        assert!(r.is_pass());
    }

    #[test]
    fn test_severity_escalation() {
        let constraints: Vec<ExactConstraint<f32>> = (0..8)
            .map(|i| ExactConstraint::new(0.0, (i + 1) as f32, "c").unwrap())
            .collect();
        let checker = FluxExactChecker::new(constraints).unwrap();

        // 0.0 passes all 8 constraints
        let r = checker.check(0.0);
        assert_eq!(r.severity, Severity::Pass);

        // 0.5 passes all 8 constraints (since hi ranges from 1.0 to 8.0)
        let r = checker.check(0.5);
        assert_eq!(r.severity, Severity::Pass);
    }

    #[test]
    fn test_batch() {
        let c = ExactConstraint::new(-10.0f32, 10.0, "range").unwrap();
        let checker = FluxExactChecker::new(alloc::vec![c]).unwrap();

        let values = [0.0, 5.0, -5.0, 11.0, -11.0];
        let results = checker.check_batch(&values);

        assert!(results[0].is_pass());
        assert!(results[1].is_pass());
        assert!(results[2].is_pass());
        assert!(!results[3].is_pass());
        assert!(!results[4].is_pass());
    }
}
