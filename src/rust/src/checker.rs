//! Core JIT checker — standalone implementation for the CLI
//!
//! This is the zero-overhead constraint checker, matching the C hot path.
//! Extracted from flux-vm-v3/jit.rs for standalone CLI use.

use std::fmt;

pub const MAX_CONSTRAINTS: usize = 8;

// ── Error type ──

#[derive(Debug, Clone, PartialEq)]
pub enum CheckerError {
    InvalidBounds(String),
    NoConstraints,
    TooManyConstraints(usize),
    InvalidRange { index: usize, lo: f64, hi: f64 },
    UnknownPreset(String),
}

impl fmt::Display for CheckerError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidBounds(msg) => write!(f, "invalid bounds: {}", msg),
            Self::NoConstraints => write!(f, "no constraints provided"),
            Self::TooManyConstraints(n) => {
                write!(f, "too many constraints: {} (max {})", n, MAX_CONSTRAINTS)
            }
            Self::InvalidRange { index, lo, hi } => {
                write!(f, "constraint {}: lo ({}) > hi ({})", index, lo, hi)
            }
            Self::UnknownPreset(name) => write!(f, "unknown preset: {}", name),
        }
    }
}

impl std::error::Error for CheckerError {}

// ── Severity ──

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Severity {
    Pass,
    Caution,
    Warning,
    Critical,
}

const SEVERITY_TABLE: [Severity; 9] = [
    Severity::Pass,
    Severity::Caution,
    Severity::Warning,
    Severity::Warning,
    Severity::Critical,
    Severity::Critical,
    Severity::Critical,
    Severity::Critical,
    Severity::Critical,
];

pub fn classify_severity(mask: u8) -> Severity {
    let count = mask.count_ones() as usize;
    SEVERITY_TABLE[if count > 8 { 8 } else { count }]
}

// ── Presets ──

pub type Preset = (&'static str, Vec<(f64, f64, &'static str)>);

pub fn all_presets() -> Vec<Preset> {
    vec![
        ("automotive_can", vec![
            (0.0, 8000.0, "engine_rpm"),
            (0.0, 300.0, "vehicle_speed_kmh"),
            (-40.0, 150.0, "coolant_temp_c"),
            (0.0, 100.0, "throttle_pct"),
            (0.0, 200.0, "brake_pressure_bar"),
            (-720.0, 720.0, "steering_angle_deg"),
            (9.0, 16.0, "battery_voltage_v"),
            (0.0, 100.0, "fuel_level_pct"),
        ]),
        ("aviation_adsb", vec![
            (-1000.0, 45000.0, "altitude_ft"),
            (0.0, 600.0, "ground_speed_kt"),
            (-180.0, 180.0, "heading_deg"),
            (-55.0, 70.0, "cabin_temp_c"),
            (75.0, 101.0, "cabin_pressure_kpa"),
            (0.0, 100.0, "fuel_flow_pct"),
            (60.0, 100.0, "hydraulic_pct"),
            (-90.0, 90.0, "pitch_deg"),
        ]),
        ("medical_fhir", vec![
            (36.1, 37.8, "body_temp_c"),
            (60.0, 100.0, "heart_rate_bpm"),
            (95.0, 100.0, "spo2_pct"),
            (80.0, 120.0, "bp_systolic_mmhg"),
            (60.0, 100.0, "bp_diastolic_mmhg"),
            (12.0, 20.0, "respiratory_rate"),
            (7.35, 7.45, "ph"),
            (0.0, 300.0, "glucose_mg_dl"),
        ]),
        ("energy_scada", vec![
            (49.0, 51.0, "grid_freq_hz"),
            (0.9, 1.1, "voltage_pu"),
            (0.0, 80.0, "transformer_temp_c"),
            (0.0, 100.0, "line_load_pct"),
            (0.0, 500.0, "current_a"),
            (-100.0, 100.0, "power_factor_offset"),
            (0.0, 360.0, "phase_angle_deg"),
            (0.0, 50.0, "thd_pct"),
        ]),
        ("industrial_plc", vec![
            (0.0, 300.0, "pressure_psi"),
            (-20.0, 120.0, "temp_c"),
            (0.0, 100.0, "flow_rate_pct"),
            (0.0, 5000.0, "rpm"),
            (0.0, 360.0, "angle_deg"),
            (0.0, 100.0, "vibration_pct"),
            (380.0, 480.0, "voltage_v"),
            (45.0, 65.0, "freq_hz"),
        ]),
        ("iot_environmental", vec![
            (-40.0, 85.0, "temp_c"),
            (0.0, 100.0, "humidity_pct"),
            (300.0, 1100.0, "pressure_hpa"),
            (0.0, 1000.0, "co2_ppm"),
            (0.0, 500.0, "pm25_ugm3"),
            (0.0, 100.0, "noise_db"),
            (0.0, 100000.0, "lux"),
            (0.0, 20.0, "wind_ms"),
        ]),
        ("robotics_ros", vec![
            (-3.14159, 3.14159, "joint_angle_rad"),
            (-10.0, 10.0, "angular_vel_rads"),
            (-5.0, 5.0, "linear_vel_ms"),
            (0.0, 100.0, "torque_pct"),
            (-180.0, 180.0, "orientation_deg"),
            (0.0, 10.0, "gripper_force_n"),
            (0.0, 30.0, "battery_voltage_v"),
            (0.0, 100.0, "motor_temp_pct"),
        ]),
        ("telecom_5g", vec![
            (-120.0, -20.0, "rsrp_dbm"),
            (-130.0, -30.0, "rsrq_db"),
            (-30.0, 0.0, "sinr_db"),
            (0.0, 100.0, "signal_pct"),
            (0.0, 50000.0, "throughput_mbps"),
            (0.0, 100.0, "latency_pct"),
            (0.0, 100.0, "packet_loss_pct"),
            (-40.0, 85.0, "device_temp_c"),
        ]),
        ("marine_nmea", vec![
            (0.0, 60.0, "speed_knots"),
            (-180.0, 180.0, "longitude_deg"),
            (-90.0, 90.0, "latitude_deg"),
            (-10.0, 10.0, "pitch_deg"),
            (-30.0, 30.0, "roll_deg"),
            (0.0, 1100.0, "depth_m"),
            (800.0, 1100.0, "pressure_hpa"),
            (-20.0, 50.0, "water_temp_c"),
        ]),
        ("satellite_telemetry", vec![
            (-100.0, 100.0, "angular_rate_degs"),
            (-180.0, 180.0, "attitude_deg"),
            (0.0, 100.0, "solar_panel_pct"),
            (0.0, 100.0, "battery_pct"),
            (-40.0, 85.0, "temp_c"),
            (0.0, 2000.0, "altitude_km"),
            (0.0, 100.0, "data_rate_pct"),
            (0.0, 100.0, "link_quality_pct"),
        ]),
    ]
}

// ── JIT Checker ──

pub struct JitChecker {
    lo: Vec<f64>,
    hi: Vec<f64>,
    n: usize,
}

unsafe impl Sync for JitChecker {}
unsafe impl Send for JitChecker {}

impl JitChecker {
    pub fn from_pairs(pairs: &[(f64, f64)]) -> Result<Self, CheckerError> {
        if pairs.is_empty() {
            return Err(CheckerError::NoConstraints);
        }
        if pairs.len() > MAX_CONSTRAINTS {
            return Err(CheckerError::TooManyConstraints(pairs.len()));
        }
        for (i, (lo, hi)) in pairs.iter().enumerate() {
            if lo > hi {
                return Err(CheckerError::InvalidRange {
                    index: i,
                    lo: *lo,
                    hi: *hi,
                });
            }
        }
        Ok(Self {
            lo: pairs.iter().map(|(l, _)| *l).collect(),
            hi: pairs.iter().map(|(_, h)| *h).collect(),
            n: pairs.len(),
        })
    }

    pub fn from_preset(name: &str) -> Result<Self, CheckerError> {
        let presets = all_presets();
        let preset = presets
            .iter()
            .find(|(n, _)| *n == name)
            .ok_or_else(|| CheckerError::UnknownPreset(name.into()))?;
        let pairs: Vec<(f64, f64)> = preset.1.iter().map(|(lo, hi, _)| (*lo, *hi)).collect();
        Self::from_pairs(&pairs)
    }

    /// **HOT PATH** — zero-overhead constraint check.
    /// Returns 0 if all pass, bitmask of violated constraints otherwise.
    /// NaN violates all constraints.
    #[inline(always)]
    pub fn check(&self, value: f64) -> u8 {
        if value.is_nan() {
            return (1u8 << self.n) - 1;
        }
        let mut mask: u8 = 0;
        for i in 0..self.n {
            if value < self.lo[i] || value > self.hi[i] {
                mask |= 1 << i;
            }
        }
        mask
    }

    /// Batch check — auto-vectorization-friendly
    pub fn check_batch(&self, values: &[f64]) -> Vec<u8> {
        values.iter().map(|&v| self.check(v)).collect()
    }

    pub fn n_constraints(&self) -> usize { self.n }
    pub fn lo(&self) -> &[f64] { &self.lo }
    pub fn hi(&self) -> &[f64] { &self.hi }
}
