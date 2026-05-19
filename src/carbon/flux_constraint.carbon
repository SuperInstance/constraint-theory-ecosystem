// FLUX Constraint Engine — Carbon
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// Usage:
//     var checker = FluxChecker({
//         {.lo = -55, .hi = 70, .name = "cabin_temp_C"},
//         {.lo = 75, .hi = 101, .name = "cabin_pressure_kPa"},
//     });
//     var result = checker.Check(60);
//     Print(result.severity, result.error_mask);

package FluxConstraint api;

// ── Core types ──────────────────────────────────────────────────────

const INT8_MIN: i8 = -127;
const INT8_MAX: i8 = 127;

enum Severity : u8 {
    Pass = 0,
    Caution = 1,
    Warning = 2,
    Critical = 3,
}

struct Constraint {
    var lo: i8;
    var hi: i8;
    var name: String;

    fn Make(lo_val: i8, hi_val: i8, name_val: String) -> Self {
        return {.lo = Saturate(lo_val),
                .hi = Saturate(hi_val),
                .name = name_val};
    }
}

struct FluxResult {
    var error_mask: u8;
    var severity: Severity;
    var violated_lo: u8;
    var violated_hi: u8;
    var violated_count: u8;
    var passed: bool;

    fn Make() -> Self {
        return {.error_mask = 0,
                .severity = Severity.Pass,
                .violated_lo = 0,
                .violated_hi = 0,
                .violated_count = 0,
                .passed = true};
    }
}

// ── Saturation ──────────────────────────────────────────────────────

fn Saturate(val: i8) -> i8 {
    if (val < INT8_MIN) { return INT8_MIN; }
    if (val > INT8_MAX) { return INT8_MAX; }
    return val;
}

// ── Checker ─────────────────────────────────────────────────────────

class FluxChecker {
    var constraints: Array[Constraint];
    var count: u8;

    fn Make(constraints_in: Array[Constraint]) -> Self {
        var n = constraints_in.Size();
        assert(n > 0, "FluxConstraint requires non-empty constraints list");
        assert(n <= 8, "Maximum 8 constraints (INT8 x8 flat bounds)");
        return {.constraints = constraints_in,
                .count = n as u8};
    }

    fn Check[addr me: Self*](val_in: i8) -> FluxResult {
        var val = Saturate(val_in);
        var result = FluxResult.Make();
        var violated: u8 = 0;

        for (i: u8 in range(me.count)) {
            let c = me.constraints[i];
            let lo_fail = val < c.lo;
            let hi_fail = val > c.hi;
            let passed = not lo_fail and not hi_fail;

            if (not passed) {
                result.error_mask |= (1 as u8) << i;
                violated += 1;
            }
            if (lo_fail) {
                result.violated_lo |= (1 as u8) << i;
            }
            if (hi_fail) {
                result.violated_hi |= (1 as u8) << i;
            }
        }

        // Severity classification
        if (violated == 0) {
            result.severity = Severity.Pass;
        } else if (violated <= me.count / 4) {
            result.severity = Severity.Caution;
        } else if (violated <= me.count / 2) {
            result.severity = Severity.Warning;
        } else {
            result.severity = Severity.Critical;
        }
        result.violated_count = violated;
        result.passed = (violated == 0);

        return result;
    }
}

// ── Industry Presets ────────────────────────────────────────────────

fn AviationPreset() -> Array[Constraint] {
    return {
        Constraint.Make(-55, 70, "cabin_temp_C"),
        Constraint.Make(75, 101, "cabin_pressure_kPa"),
        Constraint.Make(0, 100, "fuel_flow_pct"),
        Constraint.Make(60, 100, "hydraulic_pct"),
    };
}

fn AutomotivePreset() -> Array[Constraint] {
    return {
        Constraint.Make(-40, 60, "battery_temp_C"),
        Constraint.Make(0, 100, "soc_pct"),
        Constraint.Make(0, 100, "charge_rate_pct"),
        Constraint.Make(20, 80, "cabin_temp_C"),
    };
}

fn MedicalPreset() -> Array[Constraint] {
    return {
        Constraint.Make(36, 38, "body_temp_C"),
        Constraint.Make(60, 100, "heart_rate_bpm"),
        Constraint.Make(95, 100, "spo2_pct"),
        Constraint.Make(80, 120, "bp_systolic_mmHg"),
    };
}

// ── Usage Example ───────────────────────────────────────────────────

fn Main() -> i32 {
    Print("╔══════════════════════════════════════════════╗");
    Print("║  FLUX Constraint Engine — Carbon             ║");
    Print("╚══════════════════════════════════════════════╝");
    Print("");

    var constraints = AviationPreset();
    var checker = FluxChecker.Make(constraints);

    Print("Aviation preset loaded:");
    for (i: u8 in range(checker.count)) {
        let c = checker.constraints[i];
        Print("  {0} [{1}, {2}]", c.name, c.lo, c.hi);
    }

    Print("\nExamples:");
    let test_vals = {-60, 0, 25, 70, 90, 127};
    for (val in test_vals) {
        var result = checker.Check(val);
        if (result.passed) {
            Print("  val={0}: ✓ mask=0x{1:02X}", val, result.error_mask);
        } else {
            Print("  val={0}: ✗ sev={1} mask=0x{2:02X}",
                  val, result.severity, result.error_mask);
        }
    }

    return 0;
}
