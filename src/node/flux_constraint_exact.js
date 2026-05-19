/**
 * FLUX Exact Constraint Engine — Node.js Implementation
 * Zero false negatives. Bounds and values in original numeric space.
 *
 * INVARIANT: A value outside bounds is ALWAYS detected. No exceptions.
 */

// ═══════════════════════════════════════════════════════════
// Severity
// ═══════════════════════════════════════════════════════════

const SEVERITY = {
  PASS: 0,
  CAUTION: 1,
  WARNING: 2,
  CRITICAL: 3,
};

const SEVERITY_TABLE = [
  SEVERITY.PASS,     // 0 violations
  SEVERITY.CAUTION,  // 1
  SEVERITY.CAUTION,  // 2
  SEVERITY.WARNING,  // 3
  SEVERITY.WARNING,  // 4
  SEVERITY.CRITICAL, // 5
  SEVERITY.CRITICAL, // 6
  SEVERITY.CRITICAL, // 7
  SEVERITY.CRITICAL, // 8
];

const SEVERITY_NAMES = ['PASS', 'CAUTION', 'WARNING', 'CRITICAL'];

// ═══════════════════════════════════════════════════════════
// Exact constraint checker
// ═══════════════════════════════════════════════════════════

class FluxExact {
  /**
   * Create an exact constraint checker.
   * Bounds stored as original numeric values — NO INT8 quantization.
   *
   * @param {Array<{lo: number, hi: number, name?: string}>} constraints
   */
  constructor(constraints) {
    if (!constraints || constraints.length === 0) {
      throw new Error('FluxExact requires non-empty constraints');
    }
    if (constraints.length > 8) {
      throw new Error('Maximum 8 constraints (error_mask is uint8)');
    }

    this.constraints = constraints.map((c, i) => {
      const lo = Number(c.lo);
      const hi = Number(c.hi);
      if (lo > hi) {
        throw new Error(`Constraint '${c.name || i}': lo (${lo}) > hi (${hi})`);
      }
      return { lo, hi, name: c.name || `C${i}` };
    });
  }

  /**
   * Check a single value against all constraints.
   *
   * INVARIANT: value is compared in ORIGINAL numeric space.
   * No quantization. No saturation. Exact comparison.
   * ZERO false negatives guaranteed.
   *
   * @param {number} value
   * @returns {{ error_mask: number, severity: number, severity_name: string,
   *             violated_lo: number, violated_hi: number, violated_count: number,
   *             passed: boolean, details: Array }}
   */
  check(value) {
    const val = Number(value);
    let errorMask = 0;
    let violatedLo = 0;
    let violatedHi = 0;
    let violatedCount = 0;
    const details = [];

    for (let i = 0; i < this.constraints.length; i++) {
      const c = this.constraints[i];
      const loFail = val < c.lo;
      const hiFail = val > c.hi;
      const passed = !loFail && !hiFail;

      if (!passed) {
        errorMask |= (1 << i);
        violatedCount++;
      }
      if (loFail) violatedLo |= (1 << i);
      if (hiFail) violatedHi |= (1 << i);

      details.push({
        name: c.name,
        lo: c.lo,
        hi: c.hi,
        value: val,
        passed,
        lo_violated: loFail,
        hi_violated: hiFail,
      });
    }

    const severityIdx = violatedCount > 8 ? 8 : violatedCount;
    const severity = SEVERITY_TABLE[severityIdx];

    return {
      error_mask: errorMask,
      severity,
      severity_name: SEVERITY_NAMES[severity],
      violated_lo: violatedLo,
      violated_hi: violatedHi,
      violated_count: violatedCount,
      passed: errorMask === 0,
      details,
    };
  }

  /**
   * Check multiple values in batch
   * @param {number[]} values
   * @returns {{ results: Array, stats: Object }}
   */
  checkBatch(values) {
    const results = [];
    const stats = { pass: 0, caution: 0, warning: 0, critical: 0 };

    for (const v of values) {
      const r = this.check(v);
      results.push(r);
      stats[r.severity_name.toLowerCase()]++;
    }

    return { results, stats };
  }

  /**
   * Benchmark check rate
   * @param {number} iterations
   * @returns {{ rate: number, rate_M: number, total_ms: number, iterations: number }}
   */
  benchmark(iterations = 1_000_000) {
    const t0 = performance.now();
    for (let i = 0; i < iterations; i++) {
      this.check((i % 1000) - 500);
    }
    const t1 = performance.now();
    const totalMs = t1 - t0;
    const rate = (iterations * this.constraints.length) / (totalMs / 1000);
    return {
      rate,
      rate_M: rate / 1e6,
      total_ms: totalMs,
      iterations,
      constraints: this.constraints.length,
    };
  }
}

// ═══════════════════════════════════════════════════════════
// Presets — realistic bounds, not INT8-limited
// ═══════════════════════════════════════════════════════════

const PRESETS = {
  automotive_can: [
    { lo: 0, hi: 8000, name: 'engine_rpm' },
    { lo: 0, hi: 300, name: 'vehicle_speed_kmh' },
    { lo: -40, hi: 150, name: 'coolant_temp_c' },
    { lo: 0, hi: 100, name: 'throttle_pct' },
    { lo: 0, hi: 200, name: 'brake_pressure_bar' },
    { lo: -720, hi: 720, name: 'steering_angle_deg' },
    { lo: 9, hi: 16, name: 'battery_voltage_v' },
    { lo: 0, hi: 100, name: 'fuel_level_pct' },
  ],
  aviation_adsb: [
    { lo: -1000, hi: 45000, name: 'altitude_ft' },
    { lo: 0, hi: 600, name: 'ground_speed_kt' },
    { lo: -180, hi: 180, name: 'heading_deg' },
    { lo: -55, hi: 70, name: 'cabin_temp_c' },
    { lo: 75, hi: 101, name: 'cabin_pressure_kpa' },
    { lo: 0, hi: 100, name: 'fuel_flow_pct' },
    { lo: 60, hi: 100, name: 'hydraulic_pct' },
    { lo: -90, hi: 90, name: 'pitch_deg' },
  ],
  medical_fhir: [
    { lo: 36.1, hi: 37.8, name: 'body_temp_c' },
    { lo: 60, hi: 100, name: 'heart_rate_bpm' },
    { lo: 95, hi: 100, name: 'spo2_pct' },
    { lo: 80, hi: 120, name: 'bp_systolic_mmhg' },
    { lo: 60, hi: 100, name: 'bp_diastolic_mmhg' },
    { lo: 12, hi: 20, name: 'respiratory_rate' },
    { lo: 7.35, hi: 7.45, name: 'ph' },
    { lo: 0, hi: 300, name: 'glucose_mg_dl' },
  ],
  energy_scada: [
    { lo: 49.0, hi: 51.0, name: 'grid_freq_hz' },
    { lo: 0.9, hi: 1.1, name: 'voltage_pu' },
    { lo: 0, hi: 80, name: 'transformer_temp_c' },
    { lo: 0, hi: 100, name: 'line_load_pct' },
    { lo: 0, hi: 500, name: 'current_a' },
    { lo: -100, hi: 100, name: 'power_factor_offset' },
    { lo: 0, hi: 360, name: 'phase_angle_deg' },
    { lo: 0, hi: 50, name: 'thd_pct' },
  ],
};

FluxExact.fromPreset = function (name) {
  if (!PRESETS[name]) {
    throw new Error(`Unknown preset: ${name}. Available: ${Object.keys(PRESETS).join(', ')}`);
  }
  return new FluxExact(PRESETS[name]);
};

FluxExact.availablePresets = function () {
  return Object.keys(PRESETS);
};

module.exports = { FluxExact, SEVERITY, SEVERITY_NAMES, PRESETS };
