// FLUX Constraint Engine — Ballerina (Service Mesh Constraints)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: constraints don't live in isolation — they live in NETWORKS.
// Ballerina's network-first design means constraints are checked AT THE
// service boundary, IN the intermediary, BEFORE data enters your system.
// The network IS the enforcement layer.
//
// "Constraints live at network boundaries. Ballerina checks them
//  in the service mesh, before data reaches your code."

import ballerina/io;

// ══ Constants ════════════════════════════════════════════════════

const INT8_MIN = -127;
const INT8_MAX = 127;
const MAX_CONSTRAINTS = 8;

// ══ Severity ═════════════════════════════════════════════════════

enum Severity {
    PASS,
    CAUTION,
    WARNING,
    CRITICAL
}

// ══ Data structures ═════════════════════════════════════════════

type Constraint record {
    int lo;
    int hi;
    string name;
};

type FluxResult record {
    int error_mask;
    Severity severity;
    int violated_lo;
    int violated_hi;
    int violated_count;
    boolean passed;
};

type ConstraintCheckRequest record {
    int value;
    Constraint[] constraints;
};

type BatchRequest record {
    int[] values;
    Constraint[] constraints;
};

type BatchResponse record {
    FluxResult[] results;
    int total_pass;
    int total_caution;
    int total_warning;
    int total_critical;
};

// ══ Saturate: clamp to [-127, 127] ══════════════════════════════

function saturate(int v) returns int {
    if v < INT8_MIN { return INT8_MIN; }
    if v > INT8_MAX { return INT8_MAX; }
    return v;
}

// ══ Severity classification ═════════════════════════════════════

function classifySeverity(int violated, int total) returns Severity {
    if violated == 0 { return PASS; }
    if violated <= total / 4 { return CAUTION; }
    if violated <= total / 2 { return WARNING; }
    return CRITICAL;
}

// ══ Check function ══════════════════════════════════════════════

function check(Constraint[] constraints, int value) returns FluxResult {
    int val = saturate(value);
    int mask = 0;
    int vlo = 0;
    int vhi = 0;
    int vc = 0;
    int n = constraints.length();

    foreach int i in 0 ..< n {
        Constraint c = constraints[i];
        boolean loFail = val < c.lo;
        boolean hiFail = val > c.hi;
        boolean failed = loFail || hiFail;
        int bit = 1 << i;

        if failed { mask |= bit; }
        if loFail { vlo |= bit; }
        if hiFail { vhi |= bit; }
        if failed { vc += 1; }
    }

    return {
        error_mask: mask,
        severity: classifySeverity(vc, n),
        violated_lo: vlo,
        violated_hi: vhi,
        violated_count: vc,
        passed: vc == 0
    };
}

// ══ Batch check ═════════════════════════════════════════════════

function checkBatch(Constraint[] constraints, int[] values) returns BatchResponse {
    FluxResult[] results = [];
    int passCount = 0;
    int cautionCount = 0;
    int warningCount = 0;
    int criticalCount = 0;

    foreach int v in values {
        FluxResult r = check(constraints, v);
        results.push(r);
        if r.severity == PASS { passCount += 1; }
        if r.severity == CAUTION { cautionCount += 1; }
        if r.severity == WARNING { warningCount += 1; }
        if r.severity == CRITICAL { criticalCount += 1; }
    }

    return {
        results: results,
        total_pass: passCount,
        total_caution: cautionCount,
        total_warning: warningCount,
        total_critical: criticalCount
    };
}

// ══ Industry presets ═════════════════════════════════════════════

function aviationPreset() returns Constraint[] {
    return [
        {lo: -55, hi: 70, name: "cabin_temp_C"},
        {lo: 75, hi: 101, name: "cabin_pressure_kPa"},
        {lo: 0, hi: 100, name: "fuel_flow_pct"},
        {lo: 60, hi: 100, name: "hydraulic_pct"}
    ];
}

function nuclearPreset() returns Constraint[] {
    return [
        {lo: 0, hi: 110, name: "neutron_flux_pct"},
        {lo: 0, hi: 65, name: "core_temp_C_x10"},
        {lo: 72, hi: 100, name: "pressurizer_pct"},
        {lo: 0, hi: 100, name: "coolant_flow_pct"}
    ];
}

function medicalPreset() returns Constraint[] {
    return [
        {lo: 36, hi: 38, name: "body_temp_C"},
        {lo: 60, hi: 100, name: "heart_rate_bpm"},
        {lo: 95, hi: 100, name: "spo2_pct"},
        {lo: 80, hi: 120, name: "bp_systolic_mmHg"}
    ];
}

// ══ Service: constraint check endpoint ═════════════════════════
// This is Ballerina's superpower — the constraint check IS a network service.

service /flux on new http:Listener(9090) {

    // Single value check
    resource function post check(ConstraintCheckRequest req) returns FluxResult {
        return check(req.constraints, req.value);
    }

    // Batch check
    resource function post batch(BatchRequest req) returns BatchResponse {
        return checkBatch(req.constraints, req.values);
    }

    // Check against a preset
    resource function get preset/[string preset]/check/[int value]() returns FluxResult|error {
        Constraint[] constraints;
        if preset == "aviation" { constraints = aviationPreset(); }
        else if preset == "nuclear" { constraints = nuclearPreset(); }
        else if preset == "medical" { constraints = medicalPreset(); }
        else { return error("Unknown preset: " + preset); }
        return check(constraints, value);
    }
}

// ══ Usage ════════════════════════════════════════════════════════
//
// Start service: bal run flux_constraint.bal
//
// Check single value:
//   curl -X POST http://localhost:9090/flux/check \
//     -d '{"value": 60, "constraints": [{"lo": -55, "hi": 70, "name": "cabin"}]}'
//
// Check preset:
//   curl http://localhost:9090/flux/preset/aviation/check/60
//
// Batch check:
//   curl -X POST http://localhost:9090/flux/batch \
//     -d '{"values": [-60, 0, 25, 70], "constraints": [...]}'
//
// ══ Why Ballerina Matters ═══════════════════════════════════════
//
// Ballerina treats network interaction as a FIRST-CLASS concern.
// The constraint check isn't a library you import — it's a SERVICE
// you deploy. This means:
//
//   1. Constraints are checked at the network boundary
//   2. Invalid data never enters your system
//   3. The service mesh enforces constraints across all consumers
//   4. No consumer can bypass the constraint check
//
// For safety-critical systems, this is the deployment model:
// constraint enforcement as an intermediary service that sits
// between sensors and processing. The network IS the guard.
