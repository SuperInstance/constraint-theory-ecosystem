// FLUX Constraint Engine — Io (2002, Prototype-based OOP)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: no classes, only prototypes and delegation.
// Constraint checkers are cloned and customized.
// The delegation chain IS the constraint hierarchy.
// Everything is a slot — even methods. Introspection is free.
//
// "No classes. Only prototypes and delegation. Clone a checker,
//  customize it. The prototype chain IS the constraint hierarchy."

// ── Constants ──────────────────────────────────────────────────────

INT8_MIN := -127
INT8_MAX := 127
MAX_CONSTRAINTS := 8

// ── Base Prototype ─────────────────────────────────────────────────
// FluxConstraint is the root prototype. All checkers clone from this.

FluxConstraint := Object clone

FluxConstraint constraints := list()

// Saturate: clamp to INT8 range
FluxConstraint saturate := method(val,
    if(val < INT8_MIN, INT8_MIN,
        if(val > INT8_MAX, INT8_MAX, val)
    )
)

// Add a constraint: {lo, hi, name}
FluxConstraint addConstraint := method(lo, hi, name,
    if(constraints size >= MAX_CONSTRAINTS,
        Exception raise("Maximum 8 constraints (INT8 x8 flat bounds)")
    )
    constraints append(list(saturate(lo), saturate(hi), name))
    self
)

// Severity classification from violation count
FluxConstraint classifySeverity := method(violatedCount, totalConstraints,
    if(violatedCount == 0, "PASS",
        if(violatedCount <= (totalConstraints / 4), "CAUTION",
            if(violatedCount <= (totalConstraints / 2), "WARNING",
                "CRITICAL"
            )
        )
    )
)

// Check a single value against all constraints
FluxConstraint check := method(value,
    val := saturate(value)
    errorMask := 0
    violatedLo := 0
    violatedHi := 0
    violatedCount := 0
    nc := constraints size

    constraints foreach(i, c,
        lo := c at(0)
        hi := c at(1)
        // name := c at(2)
        loFail := val < lo
        hiFail := val > hi
        bit := 2 ** i

        if(loFail or hiFail,
            errorMask = errorMask + bit
            violatedCount = violatedCount + 1
        )
        if(loFail, violatedLo = violatedLo + bit)
        if(hiFail, violatedHi = violatedHi + bit)
    )

    severity := classifySeverity(violatedCount, nc)

    dict := Map clone
    dict atPut("error_mask", errorMask)
    dict atPut("severity", severity)
    dict atPut("violated_lo", violatedLo)
    dict atPut("violated_hi", violatedHi)
    dict atPut("violated_count", violatedCount)
    dict atPut("passed", violatedCount == 0)
    dict atPut("value", val)
    dict
)

// Batch check: returns list of result maps
FluxConstraint checkBatch := method(values,
    values map(v, self check(v))
)

// Pretty-print a result
FluxConstraint printResult := method(result,
    mark := if(result at("passed"), "✓", "✗")
    writeln("  #{mark} val=#{result at("value")} sev=#{result at("severity")} mask=0x#{result at("error_mask") toBase(16)}")
)

// ── Industry Presets as Clones ──────────────────────────────────────
// Each preset clones FluxConstraint and customizes its constraints.
// Further specialization clones the preset (delegation chain).

// Aviation: flight-critical bounds
aviation := FluxConstraint clone
aviation addConstraint(-55, 70, "cabin_temp_C")
aviation addConstraint(75, 101, "cabin_pressure_kPa")
aviation addConstraint(0, 100, "fuel_flow_pct")
aviation addConstraint(60, 100, "hydraulic_pct")

// Medical: patient monitoring
medical := FluxConstraint clone
medical addConstraint(36, 38, "body_temp_C")
medical addConstraint(60, 100, "heart_rate_bpm")
medical addConstraint(95, 100, "spo2_pct")
medical addConstraint(80, 120, "bp_systolic_mmHg")

// Nuclear: reactor safety — clones aviation (delegation) and adds constraints
// Demonstrates prototype chain: nuclear inherits aviation's slots
nuclear := FluxConstraint clone
nuclear addConstraint(0, 110, "neutron_flux_pct")
nuclear addConstraint(0, 65, "core_temp_C_x10")
nuclear addConstraint(72, 100, "pressurizer_pct")
nuclear addConstraint(0, 100, "coolant_flow_pct")

// Robotics: inherits from base
robotics := FluxConstraint clone
robotics addConstraint(-100, 100, "joint_torque_pct")
robotics addConstraint(0, 100, "speed_pct")
robotics addConstraint(0, 100, "force_pct")
robotics addConstraint(-127, 127, "position_mm")

// ── Delegation Example ──────────────────────────────────────────────
// Clone a preset and EXTEND it. The clone delegates unknown messages
// to its parent. This IS the constraint hierarchy.

// A stricter nuclear variant that also monitors aviation parameters
// (demonstrates prototype delegation chain)
nuclearAviation := aviation clone
nuclearAviation constraints = aviation constraints clone
// Add nuclear-specific constraints on top of aviation
nuclearAviation addConstraint(0, 110, "neutron_flux_pct")
nuclearAviation addConstraint(0, 65, "core_temp_C_x10")

// ── Usage Example ───────────────────────────────────────────────────
//
//   // Clone and customize
//   myChecker := FluxConstraint clone
//   myChecker addConstraint(-20, 60, "battery_temp_C")
//   myChecker addConstraint(0, 100, "soc_pct")
//
//   result := myChecker check(70)
//   result at("severity")    // "CAUTION"
//   result at("passed")      // false
//   result at("error_mask")  // 1
//
//   // Use a preset
//   result := aviation check(60)
//   aviation printResult(result)
//
//   // Delegation: nuclearAviation inherits aviation's check method
//   result := nuclearAviation check(60)
//
//   // Introspection: everything is a slot
//   FluxConstraint slotSummary  // lists all methods and data
//   aviation slotSummary        // shows inherited + own slots

// ── Run Demo ────────────────────────────────────────────────────────

"╔══════════════════════════════════════════════════════╗" println
"║  FLUX Constraint Engine — Io (Prototype-based OOP)  ║" println
"╚══════════════════════════════════════════════════════╝" println

"" println
"Aviation preset (4 constraints):" println
aviation constraints foreach(i, c,
    "  #{c at(2)}: [#{c at(0)}, #{c at(1)}]" interpolate println
)

"" println
"Checking values:" println
list(-60, 0, 25, 70, 90, 127) foreach(v,
    result := aviation check(v)
    aviation printResult(result)
)

"" println
"Nuclear preset:" println
result := nuclear check(50)
nuclear printResult(result)

"" println
"Prototype chain (nuclearAviation inherits aviation):" println
"  aviation has #{aviation constraints size} constraints" println
"  nuclearAviation has #{nuclearAviation constraints size} constraints" println
