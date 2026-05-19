// FLUX Constraint Engine — AssemblyScript
// Pure INT8 saturated constraint checking. Zero dependencies.
// Compiles to WebAssembly via `asc flux_constraint.ts --outFile flux_constraint.wasm`
//
// Usage:
//     const checker = new FluxChecker([
//         new Constraint(-55, 70, "cabin_temp_C"),
//         new Constraint(75, 101, "cabin_pressure_kPa"),
//     ]);
//     const result = checker.check(60);
//     console.log(result.severity, result.error_mask);

// ── Constants ───────────────────────────────────────────────────────

const INT8_MIN: i8 = -127;
const INT8_MAX: i8 = 127;
const MAX_CONSTRAINTS: u8 = 8;

// ── Severity enum ───────────────────────────────────────────────────

@unmanaged
export enum Severity {
    PASS = 0,
    CAUTION = 1,
    WARNING = 2,
    CRITICAL = 3,
}

// ── Core types ──────────────────────────────────────────────────────

@unmanaged
export class Constraint {
    lo: i8;
    hi: i8;
    name: string;

    constructor(lo: i8, hi: i8, name: string = "C") {
        this.lo = saturate(lo);
        this.hi = saturate(hi);
        this.name = name;
    }
}

@unmanaged
export class FluxResult {
    error_mask: u8;
    severity: Severity;
    violated_lo: u8;
    violated_hi: u8;
    violated_count: u8;
    passed: bool;

    constructor() {
        this.error_mask = 0;
        this.severity = Severity.PASS;
        this.violated_lo = 0;
        this.violated_hi = 0;
        this.violated_count = 0;
        this.passed = true;
    }
}

// ── Saturation ──────────────────────────────────────────────────────

export function saturate(val: i8): i8 {
    if (val < INT8_MIN) return INT8_MIN;
    if (val > INT8_MAX) return INT8_MAX;
    return val;
}

// ── FluxChecker ─────────────────────────────────────────────────────

export class FluxChecker {
    private constraints: StaticArray<Constraint>;
    private _count: u8;

    constructor(constraints: Constraint[]) {
        const len = constraints.length;
        assert(len > 0, "FluxConstraint requires non-empty constraints list");
        assert(len <= MAX_CONSTRAINTS, "Maximum 8 constraints (INT8 x8 flat bounds)");
        this._count = <u8>len;
        this.constraints = new StaticArray<Constraint>(len);
        for (let i: u8 = 0; i < <u8>len; i++) {
            this.constraints[i] = new Constraint(
                constraints[i].lo,
                constraints[i].hi,
                constraints[i].name
            );
        }
    }

    get count(): u8 {
        return this._count;
    }

    check(value: i8): FluxResult {
        const val = saturate(value);
        const result = new FluxResult();
        let violated: u8 = 0;

        for (let i: u8 = 0; i < this._count; i++) {
            const c = this.constraints[i];
            const lo_fail: bool = val < c.lo;
            const hi_fail: bool = val > c.hi;
            const passed: bool = !lo_fail && !hi_fail;

            if (!passed) {
                result.error_mask |= <u8>(1 << i);
                violated++;
            }
            if (lo_fail) {
                result.violated_lo |= <u8>(1 << i);
            }
            if (hi_fail) {
                result.violated_hi |= <u8>(1 << i);
            }
        }

        // Severity classification
        if (violated === 0) {
            result.severity = Severity.PASS;
        } else if (violated <= <u8>(this._count / 4)) {
            result.severity = Severity.CAUTION;
        } else if (violated <= <u8>(this._count / 2)) {
            result.severity = Severity.WARNING;
        } else {
            result.severity = Severity.CRITICAL;
        }
        result.violated_count = violated;
        result.passed = (violated === 0);

        return result;
    }
}

// ── Industry Presets ────────────────────────────────────────────────

export function aviationPreset(): Constraint[] {
    return [
        new Constraint(-55, 70, "cabin_temp_C"),
        new Constraint(75, 101, "cabin_pressure_kPa"),
        new Constraint(0, 100, "fuel_flow_pct"),
        new Constraint(60, 100, "hydraulic_pct"),
    ];
}

export function automotivePreset(): Constraint[] {
    return [
        new Constraint(-40, 60, "battery_temp_C"),
        new Constraint(0, 100, "soc_pct"),
        new Constraint(0, 100, "charge_rate_pct"),
        new Constraint(20, 80, "cabin_temp_C"),
    ];
}

export function medicalPreset(): Constraint[] {
    return [
        new Constraint(36, 38, "body_temp_C"),
        new Constraint(60, 100, "heart_rate_bpm"),
        new Constraint(95, 100, "spo2_pct"),
        new Constraint(80, 120, "bp_systolic_mmHg"),
    ];
}

// ── WASM Export Functions (flat C-style API for host integration) ────

// Memory layout: 32 bytes for constraint storage (8 x {lo: i8, hi: i8, _pad: i16})
const CONSTRAINT_MEM_SIZE: i32 = 32;
const constraintBuffer = new StaticArray<i8>(CONSTRAINT_MEM_SIZE);
let activeConstraintCount: u8 = 0;

export function wasmInit(): void {
    activeConstraintCount = 0;
}

export function wasmAddConstraint(lo: i8, hi: i8): void {
    const idx = <i32>activeConstraintCount;
    if (idx >= MAX_CONSTRAINTS) return;
    constraintBuffer[idx * 4] = saturate(lo);
    constraintBuffer[idx * 4 + 1] = saturate(hi);
    activeConstraintCount++;
}

export function wasmCheck(value: i8): u32 {
    const val = saturate(value);
    let error_mask: u8 = 0;
    let violated: u8 = 0;

    for (let i: u8 = 0; i < activeConstraintCount; i++) {
        const lo = constraintBuffer[<i32>i * 4];
        const hi = constraintBuffer[<i32>i * 4 + 1];
        const lo_fail = val < lo;
        const hi_fail = val > hi;

        if (lo_fail || hi_fail) {
            error_mask |= <u8>(1 << i);
            violated++;
        }
    }

    let sev: u8;
    if (violated === 0) sev = 0;
    else if (violated <= <u8>(activeConstraintCount / 4)) sev = 1;
    else if (violated <= <u8>(activeConstraintCount / 2)) sev = 2;
    else sev = 3;

    // Pack: error_mask(8) | severity(8) | violated_count(8) | passed(8)
    const passed = violated === 0 ? 1 : 0;
    return <u32>(error_mask) |
           (<u32>(sev) << 8) |
           (<u32>(violated) << 16) |
           (<u32>(passed) << 24);
}

// ── Main (demo) ─────────────────────────────────────────────────────

export function main(): void {
    console.log("╔══════════════════════════════════════════════════╗");
    console.log("║  FLUX Constraint Engine — AssemblyScript/WASM    ║");
    console.log("╚══════════════════════════════════════════════════╝");
    console.log("");

    const checker = new FluxChecker(aviationPreset());
    console.log("Aviation preset loaded: " + checker.count.toString() + " constraints");

    console.log("\nExamples:");
    const testVals: i8[] = [-60, 0, 25, 70, 90, 127];
    for (let i = 0; i < testVals.length; i++) {
        const result = checker.check(testVals[i]);
        const status = result.passed
            ? "✓"
            : "✗ sev=" + result.severity.toString();
        console.log("  val=" + testVals[i].toString() + ": " + status + " mask=0x" + result.error_mask.toString(16));
    }

    console.log("\nWASM flat API also available: wasmInit/wasmAddConstraint/wasmCheck");
}
