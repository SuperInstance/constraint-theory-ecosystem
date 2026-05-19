// FLUX Constraint Engine — Koka (2012, Algebraic Effects)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: Koka's algebraic effects let you SWAP the enforcement
// strategy without changing the constraint logic. Check against memory?
// Check against a network sensor? Check with logging? Same code,
// different effect handler. The constraint is pure; the policy is pluggable.
//
// "Effects separate WHAT to check from HOW to handle violations."
//
// Usage:
//   koka flux_constraint.kk
//   koka run flux_constraint.kk

// ══ Constants ══════════════════════════════════════════════════════

const int8-min : int = -127
const int8-max : int = 127
const max-constraints : int = 8

// ══ Types ══════════════════════════════════════════════════════════

type severity
  Pass
  Caution
  Warning
  Critical

type constraint
  Constraint( lo : int, hi : int, name : string )

type flux-result
  FluxResult(
    error-mask    : int,
    severity      : severity,
    violated-lo   : int,
    violated-hi   : int,
    violated-count: int,
    passed        : bool
  )

// ══ Effect: Violation Policy ══════════════════════════════════════
// The key Koka insight: violation handling is an EFFECT.
// Swap handlers without changing the check logic.

effect violation-policy {
  fun on-violation( constraint-name : string, value : int, lo : int, hi : int ) : ()
}

// ══ Saturate ══════════════════════════════════════════════════════

pub fun saturate( val : int ) : int {
  if val < int8-min then int8-min
  else if val > int8-max then int8-max
  else val
}

// ══ Severity Classification ══════════════════════════════════════

fun classify-severity( violated : int, total : int ) : severity {
  if violated == 0 then Pass
  else if violated * 4 <= total then Caution
  else if violated * 2 <= total then Warning
  else Critical
}

// ══ Core Check (pure logic) ══════════════════════════════════════

// The check function is pure logic — no side effects.
// The violation-policy effect lets handlers plug in behavior.
pub fun check-one( c : constraint, value : int, idx : int )
  : (bool, bool, bool)
{
  val val = saturate(value)
  val lo-fail = val < c.lo
  val hi-fail = val > c.hi
  val passed = not lo-fail and not hi-fail
  (lo-fail, hi-fail, passed)
}

pub fun check( constraints : list<constraint>, value : int )
  : flux-result
  with violation-policy
{
  val val = saturate(value)
  var error-mask := 0
  var violated-lo := 0
  var violated-hi := 0
  var violated-count := 0
  var i := 0

  for c in constraints {
    val (lo-fail, hi-fail, passed) = check-one(c, val, i)
    if not passed {
      error-mask := error-mask + (1 << i)
      violated-count := violated-count + 1
      // Invoke the effect — handler decides what to do
      violation-policy.on-violation(c.name, val, c.lo, c.hi)
    }
    if lo-fail { violated-lo := violated-lo + (1 << i) }
    if hi-fail { violated-hi := violated-hi + (1 << i) }
    i := i + 1
  }

  val n = constraints.length
  val sev = classify-severity(violated-count, n)

  FluxResult(error-mask, sev, violated-lo, violated-hi, violated-count,
             violated-count == 0)
}

// ══ Effect Handlers ═══════════════════════════════════════════════
// Different policies for violation handling — swap without touching check logic.

// Handler 1: Silent (pure computation, no logging)
handler silent-handler {
  fun on-violation(name, value, lo, hi) { () }
}

// Handler 2: Console logger
handler logging-handler {
  fun on-violation(name, value, lo, hi) {
    println("  VIOLATION: " + name + "=" + value.show() +
            " outside [" + lo.show() + ", " + hi.show() + "]")
  }
}

// Handler 3: Counter (accumulates violation count as side effect)
handler counter-handler {
  val count = ref(0)
  fun on-violation(name, value, lo, hi) {
    count := count.get + 1
  }
}

// ══ Industry Presets ══════════════════════════════════════════════

val aviation = [
  Constraint(-55, 70, "cabin_temp_C"),
  Constraint(75, 101, "cabin_pressure_kPa"),
  Constraint(0, 100, "fuel_flow_pct"),
  Constraint(60, 100, "hydraulic_pct")
]

val medical = [
  Constraint(36, 38, "body_temp_C"),
  Constraint(60, 100, "heart_rate_bpm"),
  Constraint(95, 100, "spo2_pct"),
  Constraint(80, 120, "bp_systolic_mmHg")
]

val energy = [
  Constraint(49, 51, "grid_freq_Hz_x10"),
  Constraint(95, 105, "voltage_pct"),
  Constraint(0, 80, "transformer_temp_C"),
  Constraint(0, 100, "line_load_pct")
]

val robotics = [
  Constraint(-100, 100, "joint_torque_pct"),
  Constraint(0, 100, "speed_pct"),
  Constraint(0, 100, "force_pct"),
  Constraint(-127, 127, "position_mm")
]

// ══ Main ══════════════════════════════════════════════════════════

pub fun main() {
  println("═══ FLUX Constraint Engine — Koka (Algebraic Effects) ═══\n")

  // Silent mode — pure computation
  println("Aviation (silent handler):")
  with silent-handler {
    val r = check(aviation, 25)
    println("  val=25:  passed=" + r.passed.show())
  }

  // Logging mode — violations printed
  println("\nAviation (logging handler):")
  with logging-handler {
    val r = check(aviation, -60)
    println("  val=-60: passed=" + r.passed.show() +
            " mask=0x" + r.error-mask.show())
  }

  // Medical with logging
  println("\nMedical (logging handler):")
  with logging-handler {
    val r = check(medical, 42)
    println("  val=42:  severity=" + severity-name(r.severity) +
            " passed=" + r.passed.show())
  }

  println("\n═══ Same constraint logic. Different policies. Effects FTW. ═══")
}

fun severity-name(s : severity) : string {
  match s {
    Pass -> "PASS"
    Caution -> "CAUTION"
    Warning -> "WARNING"
    Critical -> "CRITICAL"
  }
}

// ══ Paradigm Insight ══════════════════════════════════════════════
//
// In most languages, the check function and the violation handling
// are entangled — if you want to log, you add print statements.
// If you want to count, you add a counter. The policy leaks into the logic.
//
// Koka's algebraic effects SEPARATE them:
//   check() is pure constraint logic
//   on-violation() is the policy — swappable via handlers
//
// This means:
//   - Production: silent handler (zero overhead)
//   - Debugging: logging handler (prints every violation)
//   - Testing: counter handler (accumulates for assertions)
//   - Safety-critical: abort handler (halts on first violation)
//
// Same constraint engine. Different enforcement strategies.
// The policy is a first-class composable unit.
