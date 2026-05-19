// FLUX Constraint Engine — Wren (2013, Tiny VM)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: Wren is ~4000 lines of C. The entire VM fits in L1 cache.
// For embedded constraint checking, this means the INTERPRETER overhead
// is negligible. No JIT. No GC pauses. Predictable, tiny, fast.
// Constraints in your game. Constraints in your IoT device.
// Constraints everywhere, because the VM is free.
//
// "The VM is 4000 lines. The constraint engine is 100.
//  Together they fit in L1 cache. That's the point."

// ══ Constants ══════════════════════════════════════════════════════

var INT8_MIN = -127
var INT8_MAX = 127
var MAX_CONSTRAINTS = 8

// ══ Severity ══════════════════════════════════════════════════════

class Severity {
  static PASS    { 0 }
  static CAUTION { 1 }
  static WARNING { 2 }
  static CRITICAL{ 3 }

  static name(val) {
    if (val == 0) return "PASS"
    if (val == 1) return "CAUTION"
    if (val == 2) return "WARNING"
    return "CRITICAL"
  }
}

// ══ Saturate ══════════════════════════════════════════════════════

static saturate(val) {
  if (val < INT8_MIN) return INT8_MIN
  if (val > INT8_MAX) return INT8_MAX
  return val
}

// ══ Constraint ════════════════════════════════════════════════════

class Constraint {
  construct new(lo, hi, name) {
    _lo = saturate(lo)
    _hi = saturate(hi)
    _name = name
  }
  lo    { _lo }
  hi    { _hi }
  name  { _name }
  toString { "%(_name): [%(_lo), %(_hi)]" }
}

// ══ FluxResult ═══════════════════════════════════════════════════

class FluxResult {
  construct new() {
    _errorMask = 0
    _severity = 0
    _violatedLo = 0
    _violatedHi = 0
    _violatedCount = 0
    _passed = true
  }

  errorMask     { _errorMask }
  severity      { _severity }
  severityName  { Severity.name(_severity) }
  violatedLo    { _violatedLo }
  violatedHi    { _violatedHi }
  violatedCount { _violatedCount }
  passed        { _passed }

  setViolation(i, loFail, hiFail) {
    var bit = 1 << i
    if (loFail || hiFail) {
      _errorMask = _errorMask | bit
      _violatedCount = _violatedCount + 1
      _passed = false
    }
    if (loFail) { _violatedLo = _violatedLo | bit }
    if (hiFail) { _violatedHi = _violatedHi | bit }
  }

  finalize(n) {
    if (_violatedCount == 0) {
      _severity = 0  // PASS
    } else if (n > 0 && _violatedCount <= (n / 4)) {
      _severity = 1  // CAUTION
    } else if (n > 0 && _violatedCount <= (n / 2)) {
      _severity = 2  // WARNING
    } else {
      _severity = 3  // CRITICAL
    }
  }

  toString { "FluxResult(%(severityName), mask=0x%(errorMask), passed=%(_passed))" }
}

// ══ FluxChecker ══════════════════════════════════════════════════

class FluxChecker {
  construct new(constraints) {
    if (constraints.count == 0 || constraints.count > MAX_CONSTRAINTS) {
      Fiber.abort("Constraints must be 1-%(MAX_CONSTRAINTS), got %(constraints.count)")
    }
    _constraints = constraints
  }

  check(rawVal) {
    var val = saturate(rawVal)
    var result = FluxResult.new()
    var n = _constraints.count

    for (i in 0...n) {
      var c = _constraints[i]
      var loFail = val < c.lo
      var hiFail = val > c.hi
      result.setViolation(i, loFail, hiFail)
    }

    result.finalize(n)
    return result
  }

  checkBatch(values) {
    var results = []
    for (v in values) {
      results.add(check(v))
    }
    return results
  }

  count { _constraints.count }
}

// ══ Industry Presets ══════════════════════════════════════════════

class Presets {
  static aviation {
    FluxChecker.new([
      Constraint.new(-55, 70, "cabin_temp_C"),
      Constraint.new(75, 101, "cabin_pressure_kPa"),
      Constraint.new(0, 100, "fuel_flow_pct"),
      Constraint.new(60, 100, "hydraulic_pct")
    ])
  }

  static automotive {
    FluxChecker.new([
      Constraint.new(-40, 60, "battery_temp_C"),
      Constraint.new(0, 100, "soc_pct"),
      Constraint.new(0, 100, "charge_rate_pct"),
      Constraint.new(20, 80, "cabin_temp_C")
    ])
  }

  static nuclear {
    FluxChecker.new([
      Constraint.new(0, 110, "neutron_flux_pct"),
      Constraint.new(0, 65, "core_temp_C_x10"),
      Constraint.new(72, 100, "pressurizer_pct"),
      Constraint.new(0, 100, "coolant_flow_pct")
    ])
  }

  static medical {
    FluxChecker.new([
      Constraint.new(36, 38, "body_temp_C"),
      Constraint.new(60, 100, "heart_rate_bpm"),
      Constraint.new(95, 100, "spo2_pct"),
      Constraint.new(80, 120, "bp_systolic_mmHg")
    ])
  }

  static maritime {
    FluxChecker.new([
      Constraint.new(-2, 35, "sea_temp_C"),
      Constraint.new(50, 100, "hull_integrity_pct"),
      Constraint.new(0, 50, "wave_height_m"),
      Constraint.new(0, 80, "wind_speed_kn")
    ])
  }
}

// ══ Main ══════════════════════════════════════════════════════════

System.print("═══ FLUX Constraint Engine — Wren (Tiny VM) ═══")
System.print("")

var fc = Presets.aviation
System.print("  Aviation val=60:  %(fc.check(60))")
System.print("  Aviation val=25:  %(fc.check(25))")
System.print("  Aviation val=-60: %(fc.check(-60))")

System.print("")
var med = Presets.medical
System.print("  Medical val=37:   %(med.check(37))")
System.print("  Medical val=42:   %(med.check(42))")

System.print("")
System.print("Wren VM: ~4000 lines of C. Fits in L1 cache.")
System.print("Constraints in your game. Constraints in your IoT device.")
System.print("The overhead is the VM, and the VM is free.")

// Wren teaches us that constraint checking should be EVERYWHERE.
// When the VM overhead is negligible, you check EVERY value.
// Not just critical paths — ALL paths. The cost is free.
// That's the world constraint theory is building toward.
