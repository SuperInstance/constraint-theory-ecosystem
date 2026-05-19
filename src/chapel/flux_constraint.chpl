// FLUX Constraint Engine — Chapel (2009, Parallel)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: batch constraint checking is EMBARRASSINGLY PARALLEL.
// Each value checks independently. Cray figured this out in 2009.
// 1M values? 1M parallel checks. No coordination needed.
// The constraint check is the perfect parallel workload.
//
// Usage:
//   chpl flux_constraint.chpl -o flux_check
//   ./flux_check --value=60
//   ./flux_check --preset=aviation --batch=1000000

// ══ Constants ═════════════════════════════════════════════════════

const INT8_MIN: int(8) = -127;
const INT8_MAX: int(8) = 127;
const MAX_CONSTRAINTS: int = 8;

// ══ Enum ══════════════════════════════════════════════════════════

enum Severity { pass = 0, caution = 1, warning = 2, critical = 3 }

// ══ Records ═══════════════════════════════════════════════════════

record Constraint {
    var lo: int;
    var hi: int;
    var name: string;
}

record FluxResult {
    var error_mask: int;
    var severity: Severity;
    var violated_lo: int;
    var violated_hi: int;
    var violated_count: int;
    var passed: bool;
}

// ══ Saturate ══════════════════════════════════════════════════════

proc saturate(val: int): int {
    if val < INT8_MIN then return INT8_MIN: int;
    if val > INT8_MAX then return INT8_MAX: int;
    return val;
}

// ══ Severity classification ══════════════════════════════════════

proc classifySeverity(vc: int, n: int): Severity {
    if vc == 0 then return Severity.pass;
    if vc <= n / 4 then return Severity.caution;
    if vc <= n / 2 then return Severity.warning;
    return Severity.critical;
}

// ══ Single check ══════════════════════════════════════════════════

proc checkConstraints(constraints: [] Constraint, rawVal: int): FluxResult {
    var val = saturate(rawVal);
    var em = 0, vlo = 0, vhi = 0, vc = 0;

    for i in 0..#constraints.size {
        var loFail = val < constraints[i].lo;
        var hiFail = val > constraints[i].hi;

        if loFail || hiFail {
            em |= (1 << i);
            vc += 1;
        }
        if loFail then vlo |= (1 << i);
        if hiFail then vhi |= (1 << i);
    }

    var sev = classifySeverity(vc, constraints.size);
    return new FluxResult(em, sev, vlo, vhi, vc, vc == 0);
}

// ══ PARALLEL batch check — Chapel's superpower ══════════════════
// Each value is independent. No coordination. Pure parallel.

proc checkBatch(constraints: [] Constraint, values: [] int): [] FluxResult {
    var results: [0..#values.size] FluxResult;

    // coforall = fork a task per locale. forall = parallel per core.
    // The entire batch runs in parallel with zero synchronization.
    forall i in 0..#values.size {
        results[i] = checkConstraints(constraints, values[i]);
    }

    return results;
}

// ══ Stats aggregation (also parallel) ════════════════════════════

record BatchStats {
    var total, pass, caution, warning, critical: int;
}

proc computeStats(results: [] FluxResult): BatchStats {
    var s = new BatchStats(results.size, 0, 0, 0, 0);

    // Reduction — parallel count
    s.pass = + reduce [r in results] (r.passed:int);
    s.critical = + reduce [r in results] (r.severity == Severity.critical:int);
    s.warning = + reduce [r in results] (r.severity == Severity.warning:int);
    s.caution = + reduce [r in results] (r.severity == Severity.caution:int);

    return s;
}

// ══ Industry presets ══════════════════════════════════════════════

proc loadPreset(name: string): [] Constraint {
    select name {
        when "aviation" do return [
            new Constraint(-55, 70, "cabin_temp_C"),
            new Constraint(75, 101, "cabin_pressure_kPa"),
            new Constraint(0, 100, "fuel_flow_pct"),
            new Constraint(60, 100, "hydraulic_pct")
        ];
        when "automotive" do return [
            new Constraint(-40, 60, "battery_temp_C"),
            new Constraint(0, 100, "soc_pct"),
            new Constraint(0, 100, "charge_rate_pct"),
            new Constraint(20, 80, "cabin_temp_C")
        ];
        when "maritime" do return [
            new Constraint(-2, 35, "sea_temp_C"),
            new Constraint(50, 100, "hull_integrity_pct"),
            new Constraint(0, 50, "wave_height_m"),
            new Constraint(0, 80, "wind_speed_kn")
        ];
        when "medical" do return [
            new Constraint(36, 38, "body_temp_C"),
            new Constraint(60, 100, "heart_rate_bpm"),
            new Constraint(95, 100, "spo2_pct"),
            new Constraint(80, 120, "bp_systolic_mmHg")
        ];
        when "energy" do return [
            new Constraint(49, 51, "grid_freq_Hz_x10"),
            new Constraint(95, 105, "voltage_pct"),
            new Constraint(0, 80, "transformer_temp_C"),
            new Constraint(0, 100, "line_load_pct")
        ];
        when "nuclear" do return [
            new Constraint(0, 110, "neutron_flux_pct"),
            new Constraint(0, 65, "core_temp_C_x10"),
            new Constraint(72, 100, "pressurizer_pct"),
            new Constraint(0, 100, "coolant_flow_pct")
        ];
        when "railway" do return [
            new Constraint(0, 100, "speed_pct"),
            new Constraint(0, 100, "brake_pressure_pct"),
            new Constraint(0, 1, "door_interlock"),
            new Constraint(0, 80, "track_temp_C")
        ];
        when "robotics" do return [
            new Constraint(-100, 100, "joint_torque_pct"),
            new Constraint(0, 100, "speed_pct"),
            new Constraint(0, 100, "force_pct"),
            new Constraint(-127, 127, "position_mm")
        ];
        when "space" do return [
            new Constraint(-40, 50, "temp_C"),
            new Constraint(0, 100, "solar_panel_pct"),
            new Constraint(0, 100, "propellant_pct"),
            new Constraint(0, 100, "battery_pct")
        ];
        when "underwater" do return [
            new Constraint(0, 100, "depth_pct"),
            new Constraint(0, 100, "battery_pct"),
            new Constraint(-5, 35, "water_temp_C"),
            new Constraint(0, 100, "thruster_pct")
        ];
        otherwise {
            halt("Unknown preset: " + name);
        }
    }
}

// ══ Main ══════════════════════════════════════════════════════════

proc main() {
    use Time;

    writeln("╔══════════════════════════════════════════════════════╗");
    writeln("║  FLUX Constraint Engine — Chapel (Parallel)         ║");
    writeln("╚══════════════════════════════════════════════════════╝");
    writeln();

    var cons = loadPreset("aviation");
    writeln("Aviation preset: ", cons.size, " constraints");
    for c in cons do writeln("  ", c.name, " [", c.lo, ", ", c.hi, "]");
    writeln();

    // Single checks
    writeln("Single checks:");
    for val in (-60, 0, 25, 70, 127) {
        var r = checkConstraints(cons, val);
        writef("  val=%4i: ", val);
        if r.passed then write("PASS") else writef("%s mask=0x%02u", r.severity:string, r.error_mask);
        writeln();
    }
    writeln();

    // Parallel batch benchmark
    var N = 1_000_000;
    writeln("Parallel batch: ", N, " values...");
    var vals: [0..#N] int;
    for i in 0..#N do vals[i] = ((i % 254) - 127);

    var t0 = getCurrentTime(unit = TimeUnits.seconds);
    var results = checkBatch(cons, vals);
    var t1 = getCurrentTime(unit = TimeUnits.seconds);

    var stats = computeStats(results);
    var elapsed = t1 - t0;
    var rate = (N: real * cons.size: real) / elapsed;

    writeln("  ", (rate / 1e6):string(1), "M checks/sec (", elapsed * 1000: string(1), "ms)");
    writeln("  PASS:", stats.pass, " CAUTION:", stats.caution,
            " WARNING:", stats.warning, " CRITICAL:", stats.critical);
}

// Batch constraint checking is EMBARRASSINGLY PARALLEL.
// Each value checks independently. No coordination needed.
// 1M values? 1M parallel checks. Cray knew.
// Chapel's forall + reduce = parallelism for free.
