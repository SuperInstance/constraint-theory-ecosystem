// FLUX Constraint Engine — Pony (2014, Actor + Capability)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: Pony has the actor model WITH reference capabilities.
// Zero data races at compile time. For constraints, this means:
//   - Each sensor is an ACTOR that checks constraints autonomously
//   - Results are sent as MESSAGES (asynchronous, no locks)
//   - Reference capabilities prove no data sharing bugs
//   - The system cannot deadlock (Pony's guarantee)
//
// "Every sensor is an actor. Every check is a message. Zero data races.
//  The compiler proves it. No locks. No deadlocks. No shared mutable state."

use "collections"

// ══ Constants ══════════════════════════════════════════════════════

primitive _INT8Min is I8(-127)
primitive _INT8Max is I8(127)

// ══ Severity ══════════════════════════════════════════════════════

primitive Pass
primitive Caution
primitive Warning
primitive Critical

type Severity is (Pass | Caution | Warning | Critical)

// ══ Constraint ════════════════════════════════════════════════════

class Constraint
  let lo: I8
  let hi: I8
  let name: String

  new create(lo': I8, hi': I8, name': String) =>
    lo = lo'
    hi = hi'
    name = name'

// ══ FluxResult ═══════════════════════════════════════════════════

class FluxResult
  var error_mask: U8 = 0
  var severity: Severity = Pass
  var violated_lo: U8 = 0
  var violated_hi: U8 = 0
  var violated_count: U8 = 0
  var passed: Bool = true

  fun string(): String =>
    let sev_str = match severity
    | Pass => "PASS"
    | Caution => "CAUTION"
    | Warning => "WARNING"
    | Critical => "CRITICAL"
    end
    "FluxResult(" + sev_str + ", mask=0x" + error_mask.string() + ")"

// ══ Saturate ══════════════════════════════════════════════════════

fun saturate(val: I16): I8 =>
  if val < (-127).i16() then
    -127
  elseif val > 127 then
    127
  else
    val.i8()
  end

// ══ Severity classification ══════════════════════════════════════

fun classify_severity(vc: U8, n: U8): Severity =>
  if vc == 0 then Pass
  elseif (n > 0) and (vc <= (n / 4)) then Caution
  elseif (n > 0) and (vc <= (n / 2)) then Warning
  else Critical
  end

// ══ Core check (pure function) ═══════════════════════════════════

fun check(constraints: Array[Constraint box], raw_val: I16): FluxResult iso^ =>
  let result = recover FluxResult end
  let val = saturate(raw_val)
  var em: U8 = 0
  var vlo: U8 = 0
  var vhi: U8 = 0
  var vc: U8 = 0
  let n = constraints.size().u8()

  for i in Range(0, constraints.size()) do
    let c = constraints(i)?
    let lo_fail = val < c.lo
    let hi_fail = val > c.hi
    let any_fail = lo_fail or hi_fail
    let bit: U8 = 1 << i.u8()

    if any_fail then em = em or bit end
    if lo_fail then vlo = vlo or bit end
    if hi_fail then vhi = vhi or bit end
    if any_fail then vc = vc + 1 end
  end

  result.error_mask = em
  result.severity = classify_severity(vc, n)
  result.violated_lo = vlo
  result.violated_hi = vhi
  result.violated_count = vc
  result.passed = (vc == 0)
  consume result

// ══ Batch check actor ═════════════════════════════════════════════
// The ACTOR pattern: each check runs autonomously, results sent via messages.

actor ConstraintChecker
  let _constraints: Array[Constraint]
  let _env: Env

  new create(env: Env, constraints: Array[Constraint]) =>
    _env = env
    _constraints = consume constraints

  be check_value(raw_val: I16) =>
    let result = check(_constraints, raw_val)
    _env.out.print("  val=" + raw_val.string() + ": " + result.string())

  be check_batch(values: Array[I16] val) =>
    _env.out.print("  Batch check: " + values.size().string() + " values")
    for v in values.values() do
      check_value(v)
    end

// ══ Industry Presets ══════════════════════════════════════════════

fun aviation_preset(): Array[Constraint] iso^ =>
  recover
    [as Constraint:
      Constraint(-55, 70, "cabin_temp_C")
      Constraint(75, 101, "cabin_pressure_kPa")
      Constraint(0, 100, "fuel_flow_pct")
      Constraint(60, 100, "hydraulic_pct")
    ]
  end

fun automotive_preset(): Array[Constraint] iso^ =>
  recover
    [as Constraint:
      Constraint(-40, 60, "battery_temp_C")
      Constraint(0, 100, "soc_pct")
      Constraint(0, 100, "charge_rate_pct")
      Constraint(20, 80, "cabin_temp_C")
    ]
  end

fun nuclear_preset(): Array[Constraint] iso^ =>
  recover
    [as Constraint:
      Constraint(0, 110, "neutron_flux_pct")
      Constraint(0, 65, "core_temp_C_x10")
      Constraint(72, 100, "pressurizer_pct")
      Constraint(0, 100, "coolant_flow_pct")
    ]
  end

// ══ Main ══════════════════════════════════════════════════════════

actor Main
  new create(env: Env) =>
    env.out.print("═══ FLUX Constraint Engine — Pony (Actor + Capability) ═══")
    env.out.print("")

    let constraints = aviation_preset()

    // Synchronous check
    let r1 = check(constraints, 60)
    env.out.print("  Aviation val=60: " + r1.string())

    let r2 = check(constraints, 25)
    env.out.print("  Aviation val=25: " + r2.string())

    let r3 = check(constraints, -60)
    env.out.print("  Aviation val=-60: " + r3.string())

    env.out.print("")
    env.out.print("Pony guarantees: zero data races, no deadlocks.")
    env.out.print("Every sensor is an actor. Every check is a message.")
    env.out.print("Reference capabilities prove it at compile time.")

// Pony teaches us that constraint checking in distributed systems
// is an ACTOR problem. Each sensor checks autonomously, reports
// via messages. No shared mutable state. No locks. No deadlocks.
// The compiler PROVES there are no data races.
// For fleet-wide constraint monitoring, this is the architecture.
