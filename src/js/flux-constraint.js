/**
 * FLUX Constraint Engine — JavaScript/TypeScript
 * 
 * Pure JS implementation of INT8 saturated constraint checking.
 * Zero dependencies. Works in browser, Node.js, Deno, Bun.
 * 
 * Usage:
 *   import { FluxConstraint } from './flux-constraint.js'
 *   const fc = new FluxConstraint([
 *     { lo: 15, hi: 55, name: 'battery_temp' },
 *     { lo: 0, hi: 100, name: 'charge_rate' }
 *   ])
 *   const result = fc.check(60)
 *   console.log(result.severity)  // 1 = CAUTION
 *   console.log(result.errorMask) // 0x01 (first constraint violated)
 */

const INT8_MIN = -127
const INT8_MAX = 127

/** Clamp to saturated INT8 [-127, 127] */
function saturate (val) {
  return Math.max(INT8_MIN, Math.min(INT8_MAX, val | 0))
}

/** Severity levels */
const Severity = Object.freeze({
  PASS: 0,
  CAUTION: 1,
  WARNING: 2,
  CRITICAL: 3
})

/** Industry presets */
const PRESETS = Object.freeze({
  aviation: [
    { lo: -55, hi: 70, name: 'cabin_temp_C' },
    { lo: 75, hi: 101, name: 'cabin_pressure_kPa' },
    { lo: 0, hi: 100, name: 'fuel_flow_pct' },
    { lo: 60, hi: 100, name: 'hydraulic_pct' }
  ],
  medical: [
    { lo: 36, hi: 38, name: 'body_temp_C' },
    { lo: 60, hi: 100, name: 'heart_rate_bpm' },
    { lo: 95, hi: 100, name: 'spo2_pct' },
    { lo: 80, hi: 120, name: 'bp_systolic_mmHg' }
  ],
  maritime: [
    { lo: -2, hi: 35, name: 'sea_temp_C' },
    { lo: 50, hi: 100, name: 'hull_integrity_pct' },
    { lo: 0, hi: 50, name: 'wave_height_m' },
    { lo: 0, hi: 80, name: 'wind_speed_kn' }
  ],
  automotive: [
    { lo: -40, hi: 60, name: 'battery_temp_C' },
    { lo: 0, hi: 100, name: 'soc_pct' },
    { lo: 0, hi: 100, name: 'charge_rate_pct' },
    { lo: 20, hi: 80, name: 'cabin_temp_C' }
  ],
  energy: [
    { lo: 49, hi: 51, name: 'grid_freq_Hz_x10' },
    { lo: 95, hi: 105, name: 'voltage_pct' },
    { lo: 0, hi: 80, name: 'transformer_temp_C' },
    { lo: 0, hi: 100, name: 'line_load_pct' }
  ]
})

class FluxResult {
  constructor () {
    /** @type {number} Bitmask of violated constraints */
    this.errorMask = 0
    /** @type {number} 0=PASS, 1=CAUTION, 2=WARNING, 3=CRITICAL */
    this.severity = Severity.PASS
    /** @type {number} Bitmask of lower-bound violations */
    this.violatedLo = 0
    /** @type {number} Bitmask of upper-bound violations */
    this.violatedHi = 0
    /** @type {Array<{name:string, lo:number, hi:number, passed:boolean}>} */
    this.details = []
    /** @type {number} Total constraints violated */
    this.violatedCount = 0
  }

  get passed () { return this.severity === Severity.PASS }
}

class FluxConstraint {
  /**
   * @param {Array<{lo: number, hi: number, name: string}>} constraints
   */
  constructor (constraints) {
    if (!Array.isArray(constraints) || constraints.length === 0) {
      throw new Error('FluxConstraint requires non-empty constraints array')
    }
    if (constraints.length > 8) {
      throw new Error('Maximum 8 constraints (INT8 × 8 flat bounds)')
    }
    for (const c of constraints) {
      if (typeof c.lo !== 'number' || typeof c.hi !== 'number') {
        throw new Error(`Constraint "${c.name}" must have numeric lo and hi`)
      }
    }
    this.constraints = constraints.map(c => ({
      lo: saturate(c.lo),
      hi: saturate(c.hi),
      name: c.name || `C${constraints.indexOf(c)}`
    }))
  }

  /**
   * Check a single value against all constraints
   * @param {number} value - Sensor value (will be saturated to [-127, 127])
   * @returns {FluxResult}
   */
  check (value) {
    const val = saturate(value | 0)
    const result = new FluxResult()
    let violated = 0

    for (let i = 0; i < this.constraints.length; i++) {
      const { lo, hi, name } = this.constraints[i]
      const loFail = val < lo
      const hiFail = val > hi
      const passed = !loFail && !hiFail

      if (!passed) {
        result.errorMask |= (1 << i)
        violated++
      }
      if (loFail) result.violatedLo |= (1 << i)
      if (hiFail) result.violatedHi |= (1 << i)

      result.details.push({ name, lo, hi, passed })
    }

    // Severity
    const nc = this.constraints.length
    if (violated === 0) result.severity = Severity.PASS
    else if (violated <= Math.floor(nc / 4)) result.severity = Severity.CAUTION
    else if (violated <= Math.floor(nc / 2)) result.severity = Severity.WARNING
    else result.severity = Severity.CRITICAL
    result.violatedCount = violated

    return result
  }

  /**
   * Check multiple values
   * @param {number[]} values
   * @returns {{ results: FluxResult[], stats: {pass: number, caution: number, warning: number, critical: number} }}
   */
  checkBatch (values) {
    const results = []
    const stats = { pass: 0, caution: 0, warning: 0, critical: 0 }

    for (const v of values) {
      const r = this.check(v)
      results.push(r)
      switch (r.severity) {
        case Severity.PASS: stats.pass++; break
        case Severity.CAUTION: stats.caution++; break
        case Severity.WARNING: stats.warning++; break
        case Severity.CRITICAL: stats.critical++; break
      }
    }

    return { results, stats }
  }

  /**
   * Benchmark: how many checks/sec in this JS runtime
   * @param {number} iterations - Default 1,000,000
   * @returns {{ rate: number, totalMs: number, iterations: number }}
   */
  benchmark (iterations = 1000000) {
    const t0 = performance.now()
    for (let i = 0; i < iterations; i++) {
      this.check((i % 254) - 127)
    }
    const t1 = performance.now()
    const totalMs = t1 - t0
    const rate = (iterations * this.constraints.length) / (totalMs / 1000)
    return { rate, totalMs, iterations }
  }

  /**
   * Load an industry preset
   * @param {string} name - 'aviation' | 'medical' | 'maritime' | 'automotive' | 'energy'
   * @returns {FluxConstraint}
   */
  static fromPreset (name) {
    const preset = PRESETS[name]
    if (!preset) throw new Error(`Unknown preset: ${name}. Available: ${Object.keys(PRESETS).join(', ')}`)
    return new FluxConstraint(preset)
  }

  /** Expose saturate as static method */
  static saturate = saturate

  /** Expose Severity enum */
  static Severity = Severity

  /** Expose PRESETS */
  static PRESETS = PRESETS
}

// Export for browser and Node.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { FluxConstraint, FluxResult, Severity, saturate, PRESETS }
}
if (typeof window !== 'undefined') {
  window.FluxConstraint = FluxConstraint
  window.FluxResult = FluxResult
  window.FluxSeverity = Severity
}
