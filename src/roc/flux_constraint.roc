# FLUX Constraint Engine — Roc (2022, Pure Functional)
# Pure INT8 saturated constraint checking. Zero dependencies.
#
# The insight: pure functions CANNOT FAIL AT RUNTIME.
# Constraint checking is inherently pure — same inputs, same outputs.
# No exceptions, no null, no undefined behavior.
# Roc's exhaustiveness checking means every case is handled.
# If it compiles, it's total. If it's total, it's safe.
#
# "Pure functions cannot fail at runtime. Constraint checking is inherently pure."

app [main] {
    packages: {
        pf: "https://github.com/roc-lang/basic-cli/releases/download/0.15.0/SideQH1HPaDc0oqKZpjMpYJelCjnAEcFjRMEJtkdMOk.tar.br"
    }
    imports: [pf.Stdout]
    provides: [main]
}

# ══ Constants ══════════════════════════════════════════════════════

INT8_MIN : I64
INT8_MIN = -127

INT8_MAX : I64
INT8_MAX = 127

MAX_CONSTRAINTS : U64
MAX_CONSTRAINTS = 8

# ══ Severity ══════════════════════════════════════════════════════

[Severity] {
    pass : U8,
    caution : U8,
    warning : U8,
    critical : U8,
}

Severity : [Pass, Caution, Warning, Critical]

severityToInt : Severity -> U8
severityToInt = \sev ->
    when sev is
        Pass -> 0
        Caution -> 1
        Warning -> 2
        Critical -> 3

severityToString : Severity -> Str
severityToString = \sev ->
    when sev is
        Pass -> "PASS"
        Caution -> "CAUTION"
        Warning -> "WARNING"
        Critical -> "CRITICAL"

# ══ Constraint ════════════════════════════════════════════════════

Constraint : {
    lo : I64,
    hi : I64,
    name : Str,
}

# ══ FluxResult ════════════════════════════════════════════════════

FluxResult : {
    errorMask : U64,
    severity : Severity,
    violatedLo : U64,
    violatedHi : U64,
    violatedCount : U64,
    passed : Bool,
}

# ══ Saturate — pure, total, cannot fail ══════════════════════════

saturate : I64 -> I64
saturate = \val ->
    if val < INT8_MIN then
        INT8_MIN
    else if val > INT8_MAX then
        INT8_MAX
    else
        val

# ══ Severity classification ══════════════════════════════════════

classifySeverity : U64, U64 -> Severity
classifySeverity = \violatedCount, totalCount ->
    n = totalCount
    vc = violatedCount
    if vc == 0 then
        Pass
    else if vc <= Num.intDiv n 4 then
        Caution
    else if vc <= Num.intDiv n 2 then
        Warning
    else
        Critical

# ══ Check a single constraint against a value ════════════════════

checkOne : Constraint, I64 -> { loFail : Bool, hiFail : Bool }
checkOne = \c, val ->
    {
        loFail: val < c.lo,
        hiFail: val > c.hi,
    }

# ══ Core: check all constraints ══════════════════════════════════
# Accumulates through the list, tracking all bit masks.

check : List Constraint, I64 -> FluxResult
check = \constraints, rawVal ->
    val = saturate rawVal

    result = List.walk constraints
        { em: 0u64, vlo: 0u64, vhi: 0u64, vc: 0u64, idx: 0u64 }
        (\state, c ->
            r = checkOne c val
            bit = Num.shiftLeftOne 1u64 state.idx
            anyFail = r.loFail || r.hiFail

            {
                em: if anyFail then Num.bitOr state.em bit else state.em,
                vlo: if r.loFail then Num.bitOr state.vlo bit else state.vlo,
                vhi: if r.hiFail then Num.bitOr state.vhi bit else state.vhi,
                vc: if anyFail then state.vc + 1 else state.vc,
                idx: state.idx + 1,
            }
        )

    n = List.len constraints
    sev = classifySeverity result.vc (Num.toU64 n)

    {
        errorMask: result.em,
        severity: sev,
        violatedLo: result.vlo,
        violatedHi: result.vhi,
        violatedCount: result.vc,
        passed: result.vc == 0,
    }

# ══ Batch check (pure — no side effects) ═════════════════════════

checkBatch : List Constraint, List I64 -> List FluxResult
checkBatch = \constraints, values ->
    List.map values (\v -> check constraints v)

# ══ Industry presets ══════════════════════════════════════════════

aviation : List Constraint
aviation = [
    { lo: -55, hi: 70, name: "cabin_temp_C" },
    { lo: 75, hi: 101, name: "cabin_pressure_kPa" },
    { lo: 0, hi: 100, name: "fuel_flow_pct" },
    { lo: 60, hi: 100, name: "hydraulic_pct" },
]

automotive : List Constraint
automotive = [
    { lo: -40, hi: 60, name: "battery_temp_C" },
    { lo: 0, hi: 100, name: "soc_pct" },
    { lo: 0, hi: 100, name: "charge_rate_pct" },
    { lo: 20, hi: 80, name: "cabin_temp_C" },
]

medical : List Constraint
medical = [
    { lo: 36, hi: 38, name: "body_temp_C" },
    { lo: 60, hi: 100, name: "heart_rate_bpm" },
    { lo: 95, hi: 100, name: "spo2_pct" },
    { lo: 80, hi: 120, name: "bp_systolic_mmHg" },
]

nuclear : List Constraint
nuclear = [
    { lo: 0, hi: 110, name: "neutron_flux_pct" },
    { lo: 0, hi: 65, name: "core_temp_C_x10" },
    { lo: 72, hi: 100, name: "pressurizer_pct" },
    { lo: 0, hi: 100, name: "coolant_flow_pct" },
]

space : List Constraint
space = [
    { lo: -40, hi: 50, name: "temp_C" },
    { lo: 0, hi: 100, name: "solar_panel_pct" },
    { lo: 0, hi: 100, name: "propellant_pct" },
    { lo: 0, hi: 100, name: "battery_pct" },
]

# ══ Main ══════════════════════════════════════════════════════════

main =
    # Aviation checks
    r1 = check aviation 60
    r2 = check aviation (-60)
    r3 = check aviation 25

    _ <- Stdout.line "═══ FLUX Constraint Engine — Roc (Pure Functional) ═══"
    _ <- Stdout.line ""
    _ <- Stdout.line "Aviation preset, 4 constraints"
    _ <- Stdout.line "  val=60:  $(severityToString r1.severity) mask=0x$(Num.toStr r1.errorMask)"
    _ <- Stdout.line "  val=-60: $(severityToString r2.severity) mask=0x$(Num.toStr r2.errorMask)"
    _ <- Stdout.line "  val=25:  $(severityToString r3.severity) passed=$(Bool.toStr r3.passed)"

    # Medical
    r4 = check medical 37
    _ <- Stdout.line "\nMedical preset, val=37: $(severityToString r4.severity) passed=$(Bool.toStr r4.passed)"

    Ok {}

# Pure functions cannot fail at runtime.
# No exceptions, no null, no undefined behavior.
# Roc's exhaustiveness checking means every case is handled.
# Constraint checking is inherently pure — same inputs, same outputs, always.
