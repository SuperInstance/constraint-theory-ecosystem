// FLUX Constraint Engine — Koka (2012, Algebraic Effects)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: SWAP enforcement strategies as EFFECTS. Koka's
// algebraic effects let you define what "checking" means separately
// from the check logic. The same code can check synchronously,
// asynchronously, with logging, or with recovery — by swapping
// the EFFECT HANDLER. The enforcement is orthogonal to the logic.
//
// "The check is pure logic. The enforcement is a handler.
//  Swap the handler, change the behavior. The logic never changes."

// ══ Constants ═══════════════════════════════════════════════════

const int8-min : int = -127
const int8-max : int = 127
const max-constraints : int = 8

// ══ Severity ═════════════════════════════════════════════════════

type severity =
  | Pass
  | Caution
  | Warning
  | Critical

fun severity-name(s : severity) : string {
  match s {
    Pass     -> "PASS"
    Caution  -> "CAUTION"
    Warning  -> "WARNING"
    Critical -> "CRITICAL"
  }
}

// ══ Saturate ═════════════════════════════════════════════════════

fun saturate(val : int) : int {
  if val < int8-min then int8-min
  else if val > int8-max then int8-max
  else val
}

// ══ Constraint ═══════════════════════════════════════════════════

type constraint = {
  lo   : int,
  hi   : int,
  name : string
}

// ══ FluxResult ═══════════════════════════════════════════════════

type flux-result = {
  error-mask    : int,
  severity      : severity,
  violated-lo   : int,
  violated-hi   : int,
  violated-count : int,
  passed        : bool
}

// ══ Core check logic — PURE, no effects ════════════════════════

fun check-raw(constraints : list<constraint>, value : int) : flux-result {
  val val = saturate(value)
  var error-mask = 0
  var violated-lo = 0
  var violated-hi = 0
  var violated-count = 0
  var idx = 0

  for c in constraints {
    val lo-fail = val < c.lo
    val hi-fail = val > c.hi
    if lo-fail || hi-fail {
      error-mask := error-mask | (1 << idx)
      violated-count := violated-count + 1
    }
    if lo-fail { violated-lo := violated-lo | (1 << idx) }
    if hi-fail { violated-hi := violated-hi | (1 << idx) }
    idx := idx + 1
  }

  val nc = list-length(constraints)
  val sev = if violated-count == 0 then Pass
            else if violated-count * 4 <= nc then Caution
            else if violated-count * 2 <= nc then Warning
            else Critical

  { error-mask, severity = sev, violated-lo, violated-hi, violated-count, passed = violated-count == 0 }
}

// ══ Effect: constraint enforcement ══════════════════════════════
// The KEY insight: enforcement is an EFFECT. The check logic is pure.
// The handler decides what happens on violation.

effect constraint {
  fun violate(result : flux-result, constraint-name : string) : flux-result
}

// ══ Check with effect ═══════════════════════════════════════════
// This function checks constraints and invokes the `violate` effect
// if any constraint fails. The HANDLER decides what to do.

fun check(constraints : list<constraint>, value : int) : flux-result {
  val result = check-raw(constraints, value)
  if !result.passed {
    // Invoke effect — handler decides what happens
    with constraint { violate(result, constraints[0].name) }
  } else {
    result
  }
}

// ══ Handlers: different enforcement strategies ══════════════════

// Handler 1: Silent — just return the result (default)
handler silent = {
  return(x) -> x
  fun constraint.violate(result, name) -> result
}

// Handler 2: Logging — print violations to console
handler logging = {
  return(x) -> x
  fun constraint.violate(result, name) {
    println("VIOLATION: " ++ name ++ " severity=" ++ severity-name(result.severity))
    result
  }
}

// Handler 3: Strict — throw exception on any violation
handler strict = {
  return(x) -> x
  fun constraint.violate(result, name) {
    error("Constraint violation: " ++ name ++ " [" ++ int-to-string(result.error-mask) ++ "]")
  }
}

// Handler 4: Recovery — apply corrective action and continue
handler recover(f : (flux-result) -> flux-result) = {
  return(x) -> x
  fun constraint.violate(result, name) {
    println("RECOVERING: " ++ name)
    f(result)  // Apply recovery function
  }
}

// ══ Presets ═════════════════════════════════════════════════════

val aviation = [
  { lo = -55, hi = 70,  name = "cabin_temp_C" },
  { lo = 75,  hi = 101, name = "cabin_pressure_kPa" },
  { lo = 0,   hi = 100, name = "fuel_flow_pct" },
  { lo = 60,  hi = 100, name = "hydraulic_pct" }
]

val automotive = [
  { lo = -40, hi = 60,  name = "battery_temp_C" },
  { lo = 0,   hi = 100, name = "soc_pct" },
  { lo = 0,   hi = 100, name = "charge_rate_pct" },
  { lo = 20,  hi = 80,  name = "cabin_temp_C" }
]

val nuclear = [
  { lo = 0,   hi = 110, name = "neutron_flux_pct" },
  { lo = 0,   hi = 65,  name = "core_temp_C_x10" },
  { lo = 72,  hi = 100, name = "pressurizer_pct" },
  { lo = 0,   hi = 100, name = "coolant_flow_pct" }
]

// ══ Demo ═════════════════════════════════════════════════════════

fun main() {
  println("═══ FLUX Constraint Engine — Koka ═══")
  println("")

  // Same check logic, different enforcement strategies:

  // Silent: just returns result
  println("── Silent handler ──")
  with silent {
    val r = check(aviation, 60)
    println("  val=60: " ++ severity-name(r.severity) ++ " mask=0x" ++ int-to-string(r.error-mask))
  }

  // Logging: prints violations
  println("── Logging handler ──")
  with logging {
    val r = check(aviation, 60)
    println("  val=60: " ++ severity-name(r.severity) ++ " mask=0x" ++ int-to-string(r.error-mask))
  }

  // Strict: would throw on violation (commented out to avoid crash)
  // with strict {
  //   val r = check(aviation, -60)
  // }

  // Recovery: applies correction and continues
  println("── Recovery handler ──")
  with recover(fn(r) { println("  → Applied recovery action"); r }) {
    val r = check(aviation, 60)
    println("  val=60: " ++ severity-name(r.severity))
  }
}

// ══ Paradigm Insight ═════════════════════════════════════════════
//
// Koka's algebraic effects separate WHAT the check does from
// WHAT HAPPENS on violation. The check logic is ALWAYS the same.
// The handler is swappable at the call site.
//
// In a fleet of agents:
// - Agent A uses `silent` handler (monitoring only)
// - Agent B uses `logging` handler (audit trail)
// - Agent C uses `strict` handler (fail-fast)
// - Agent D uses `recover` handler (auto-remediation)
//
// SAME CHECK CODE. DIFFERENT BEHAVIOR. ZERO CODE DUPLICATION.
// The effect handler IS the enforcement policy.
// The enforcement policy IS the effect handler.
// This is the deepest insight: check logic and enforcement
// are ORTHOGONAL dimensions. Koka makes this explicit.
