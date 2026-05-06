/**
 * FLUX Constraint Engine — TypeScript
 * Fully typed INT8 saturated constraint checking.
 * Zero runtime dependencies.
 *
 * npm install:
 *   Copy this file, import { FluxConstraint } from './flux-constraint'
 */

export const INT8_MIN = -127 as const;
export const INT8_MAX = 127 as const;

export type SeverityLevel = 0 | 1 | 2 | 3;

export const Severity = {
  PASS: 0,
  CAUTION: 1,
  WARNING: 2,
  CRITICAL: 3,
} as const;

export interface ConstraintDef {
  lo: number;
  hi: number;
  name: string;
}

export interface ConstraintDetail {
  name: string;
  lo: number;
  hi: number;
  value: number;
  passed: boolean;
  loViolated: boolean;
  hiViolated: boolean;
}

export interface FluxResult {
  errorMask: number;
  severity: SeverityLevel;
  severityName: string;
  violatedLo: number;
  violatedHi: number;
  violatedCount: number;
  passed: boolean;
  details: ConstraintDetail[];
}

export interface BatchStats {
  pass: number;
  caution: number;
  warning: number;
  critical: number;
}

export interface BenchmarkResult {
  rate: number;
  rateM: number;
  totalMs: number;
  iterations: number;
  constraints: number;
}

export interface PresetMap {
  [key: string]: ConstraintDef[];
}

/** Clamp to saturated INT8 [-127, 127] */
export function saturate(val: number): number {
  return Math.max(INT8_MIN, Math.min(INT8_MAX, val | 0));
}

const SEVERITY_NAMES = ['PASS', 'CAUTION', 'WARNING', 'CRITICAL'] as const;

export const PRESETS: PresetMap = {
  aviation: [
    { lo: -55, hi: 70, name: 'cabin_temp_C' },
    { lo: 75, hi: 101, name: 'cabin_pressure_kPa' },
    { lo: 0, hi: 100, name: 'fuel_flow_pct' },
    { lo: 60, hi: 100, name: 'hydraulic_pct' },
  ],
  automotive: [
    { lo: -40, hi: 60, name: 'battery_temp_C' },
    { lo: 0, hi: 100, name: 'soc_pct' },
    { lo: 0, hi: 100, name: 'charge_rate_pct' },
    { lo: 20, hi: 80, name: 'cabin_temp_C' },
  ],
  maritime: [
    { lo: -2, hi: 35, name: 'sea_temp_C' },
    { lo: 50, hi: 100, name: 'hull_integrity_pct' },
    { lo: 0, hi: 50, name: 'wave_height_m' },
    { lo: 0, hi: 80, name: 'wind_speed_kn' },
  ],
  medical: [
    { lo: 36, hi: 38, name: 'body_temp_C' },
    { lo: 60, hi: 100, name: 'heart_rate_bpm' },
    { lo: 95, hi: 100, name: 'spo2_pct' },
    { lo: 80, hi: 120, name: 'bp_systolic_mmHg' },
  ],
  energy: [
    { lo: 49, hi: 51, name: 'grid_freq_Hz_x10' },
    { lo: 95, hi: 105, name: 'voltage_pct' },
    { lo: 0, hi: 80, name: 'transformer_temp_C' },
    { lo: 0, hi: 100, name: 'line_load_pct' },
  ],
  nuclear: [
    { lo: 0, hi: 110, name: 'neutron_flux_pct' },
    { lo: 0, hi: 65, name: 'core_temp_C_x10' },
    { lo: 72, hi: 100, name: 'pressurizer_pct' },
    { lo: 0, hi: 100, name: 'coolant_flow_pct' },
  ],
  railway: [
    { lo: 0, hi: 100, name: 'speed_pct' },
    { lo: 0, hi: 100, name: 'brake_pressure_pct' },
    { lo: 0, hi: 1, name: 'door_interlock' },
    { lo: 0, hi: 80, name: 'track_temp_C' },
  ],
  robotics: [
    { lo: -100, hi: 100, name: 'joint_torque_pct' },
    { lo: 0, hi: 100, name: 'speed_pct' },
    { lo: 0, hi: 100, name: 'force_pct' },
    { lo: -127, hi: 127, name: 'position_mm' },
  ],
  space: [
    { lo: -40, hi: 50, name: 'temp_C' },
    { lo: 0, hi: 100, name: 'solar_panel_pct' },
    { lo: 0, hi: 100, name: 'propellant_pct' },
    { lo: 0, hi: 100, name: 'battery_pct' },
  ],
  underwater: [
    { lo: 0, hi: 100, name: 'depth_pct' },
    { lo: 0, hi: 100, name: 'battery_pct' },
    { lo: -5, hi: 35, name: 'water_temp_C' },
    { lo: 0, hi: 100, name: 'thruster_pct' },
  ],
};

export class FluxConstraint {
  private constraints: Array<{ lo: number; hi: number; name: string }>;

  constructor(constraints: ConstraintDef[]) {
    if (!Array.isArray(constraints) || constraints.length === 0) {
      throw new Error('FluxConstraint requires non-empty constraints array');
    }
    if (constraints.length > 8) {
      throw new Error('Maximum 8 constraints (INT8 × 8 flat bounds)');
    }
    this.constraints = constraints.map((c, i) => ({
      lo: saturate(c.lo),
      hi: saturate(c.hi),
      name: c.name ?? `C${i}`,
    }));
  }

  check(value: number): FluxResult {
    const val = saturate(value);
    let errorMask = 0;
    let violatedLo = 0;
    let violatedHi = 0;
    let violatedCount = 0;
    const details: ConstraintDetail[] = [];

    for (let i = 0; i < this.constraints.length; i++) {
      const { lo, hi, name } = this.constraints[i];
      const loFail = val < lo;
      const hiFail = val > hi;
      const passed = !loFail && !hiFail;

      if (!passed) {
        errorMask |= (1 << i);
        violatedCount++;
      }
      if (loFail) violatedLo |= (1 << i);
      if (hiFail) violatedHi |= (1 << i);

      details.push({ name, lo, hi, value: val, passed, loViolated: loFail, hiViolated: hiFail });
    }

    const nc = this.constraints.length;
    let severity: SeverityLevel;
    if (violatedCount === 0) severity = 0;
    else if (violatedCount <= Math.floor(nc / 4)) severity = 1;
    else if (violatedCount <= Math.floor(nc / 2)) severity = 2;
    else severity = 3;

    return {
      errorMask,
      severity,
      severityName: SEVERITY_NAMES[severity],
      violatedLo,
      violatedHi,
      violatedCount,
      passed: severity === 0,
      details,
    };
  }

  checkBatch(values: number[]): { results: FluxResult[]; stats: BatchStats } {
    const results: FluxResult[] = [];
    const stats: BatchStats = { pass: 0, caution: 0, warning: 0, critical: 0 };

    for (const v of values) {
      const r = this.check(v);
      results.push(r);
      switch (r.severity) {
        case 0: stats.pass++; break;
        case 1: stats.caution++; break;
        case 2: stats.warning++; break;
        case 3: stats.critical++; break;
      }
    }
    return { results, stats };
  }

  benchmark(iterations = 1_000_000): BenchmarkResult {
    const t0 = performance.now();
    for (let i = 0; i < iterations; i++) {
      this.check((i % 254) - 127);
    }
    const t1 = performance.now();
    const totalMs = t1 - t0;
    const rate = (iterations * this.constraints.length) / (totalMs / 1000);
    return { rate, rateM: rate / 1e6, totalMs, iterations, constraints: this.constraints.length };
  }

  static fromPreset(name: string): FluxConstraint {
    const preset = PRESETS[name];
    if (!preset) throw new Error(`Unknown preset: ${name}. Available: ${Object.keys(PRESETS).join(', ')}`);
    return new FluxConstraint(preset);
  }

  static availablePresets(): string[] {
    return Object.keys(PRESETS);
  }
}
