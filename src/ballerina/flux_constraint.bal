// FLUX Constraint Engine — Ballerina (2017, Network-Native)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: constraint checking as a NETWORK INTERMEDIARY.
// A service that sits between sensors and control systems,
// enforcing constraints at the network boundary.
// No sensor talks to the controller without passing through constraints.
//
// "Constraints at the network boundary. The checker IS the service.
//  Every sensor reading flows through the constraint layer before
//  reaching the actuator. The network topology IS the safety architecture."

import ballerina/io;

// ══════════════════════════════════════════════════════════════════
//  Constants
// ══════════════════════════════════════════════════════════════════

const INT8_MIN = -127;
const INT8_MAX = 127;
const MAX_CONSTRAINTS = 8;

// ══════════════════════════════════════════════════════════════════
//  Severity Enum
// ══════════════════════════════════════════════════════════════════

enum Severity {
    PASS = 0,
    CAUTION = 1,
    WARNING = 2,
    CRITICAL = 3
}

// ══════════════════════════════════════════════════════════════════
//  Data Structures
// ══════════════════════════════════════════════════════════════════

type Constraint record {
    int lo;
    int hi;
    string name;
};

type ConstraintDetail record {
    string name;
    int lo;
    int hi;
    int value;
    boolean passed;
    boolean lo_violated;
    boolean hi_violated;
};

type FluxResult record {
    int error_mask;
    Severity severity;
    int violated_lo;
    int violated_hi;
    int violated_count;
    boolean passed;
    ConstraintDetail[] details;
};

type BatchResponse record {
    FluxResult[] results;
    record {int pass; int caution; int warning; int critical;} stats;
};

// ══════════════════════════════════════════════════════════════════
//  Core Functions
// ══════════════════════════════════════════════════════════════════

function saturate(int val) returns int {
    if val < INT8_MIN { return INT8_MIN; }
    if val > INT8_MAX { return INT8_MAX; }
    return val;
}

function classifySeverity(int violated, int total) returns Severity {
    if violated == 0 { return PASS; }
    if violated <= total / 4 { return CAUTION; }
    if violated <= total / 2 { return WARNING; }
    return CRITICAL;
}

function checkConstraints(Constraint[] constraints, int value) returns FluxResult {
    int val = saturate(value);
    int errorMask = 0;
    int violatedLo = 0;
    int violatedHi = 0;
    int violatedCount = 0;
    ConstraintDetail[] details = [];

    foreach int i in 0 ..< constraints.length() {
        Constraint c = constraints[i];
        boolean loFail = val < c.lo;
        boolean hiFail = val > c.hi;
        boolean passed = !loFail && !hiFail;

        if !passed {
            errorMask = errorMask | (1 << i);
            violatedCount += 1;
        }
        if loFail { violatedLo = violatedLo | (1 << i); }
        if hiFail { violatedHi = violatedHi | (1 << i); }

        details.push({
            name: c.name,
            lo: c.lo,
            hi: c.hi,
            value: val,
            passed: passed,
            lo_violated: loFail,
            hi_violated: hiFail
        });
    }

    return {
        error_mask: errorMask,
        severity: classifySeverity(violatedCount, constraints.length()),
        violated_lo: violatedLo,
        violated_hi: violatedHi,
        violated_count: violatedCount,
        passed: violatedCount == 0,
        details: details
    };
}

// ══════════════════════════════════════════════════════════════════
//  Industry Presets
// ══════════════════════════════════════════════════════════════════

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

function maritimePreset() returns Constraint[] {
    return [
        {lo: -2, hi: 35, name: "sea_temp_C"},
        {lo: 50, hi: 100, name: "hull_integrity_pct"},
        {lo: 0, hi: 50, name: "wave_height_m"},
        {lo: 0, hi: 80, name: "wind_speed_kn"}
    ];
}

// ══════════════════════════════════════════════════════════════════
//  REST Service — The Checker IS the Service
// ══════════════════════════════════════════════════════════════════

service /flux on new http:Listener(9090) {

    // Single value check against custom constraints
    resource post function check(Constraint[] constraints, int value) returns FluxResult {
        return checkConstraints(constraints, value);
    }

    // Batch check — stream multiple values through the constraint layer
    resource post function batch(Constraint[] constraints, int[] values) returns BatchResponse {
        int passCount = 0;
        int cautionCount = 0;
        int warningCount = 0;
        int criticalCount = 0;
        FluxResult[] results = [];

        foreach int v in values {
            FluxResult r = checkConstraints(constraints, v);
            results.push(r);

            match r.severity {
                PASS => { passCount += 1; }
                CAUTION => { cautionCount += 1; }
                WARNING => { warningCount += 1; }
                CRITICAL => { criticalCount += 1; }
            }
        }

        return {
            results: results,
            stats: {
                pass: passCount,
                caution: cautionCount,
                warning: warningCount,
                critical: criticalCount
            }
        };
    }

    // Preset endpoints — ready-made constraint sets by industry
    resource get function presets/[string preset]() returns Constraint[]|error {
        match preset {
            "aviation" => { return aviationPreset(); }
            "nuclear" => { return nuclearPreset(); }
            "medical" => { return medicalPreset(); }
            "maritime" => { return maritimePreset(); }
            _ => { return error("Unknown preset: " + preset); }
        }
    }

    // Check against a preset
    resource get function presetCheck/[string preset]/[int value]() returns FluxResult|error {
        Constraint[] constraints = [];
        match preset {
            "aviation" => { constraints = aviationPreset(); }
            "nuclear" => { constraints = nuclearPreset(); }
            "medical" => { constraints = medicalPreset(); }
            "maritime" => { constraints = maritimePreset(); }
            _ => { return error("Unknown preset: " + preset); }
        }
        return checkConstraints(constraints, value);
    }
}

// ══════════════════════════════════════════════════════════════════
//  Main — Standalone Test
// ══════════════════════════════════════════════════════════════════

public function main() {
    io:println("═══ FLUX Constraint Engine — Ballerina (Network-Native) ═══");
    io:println("");

    Constraint[] aviation = aviationPreset();
    io:println("  Aviation preset loaded: ", aviation.length(), " constraints");

    foreach int val in [-60, 0, 25, 70, 90, 127] {
        FluxResult r = checkConstraints(aviation, val);
        string status = r.passed ? "✓ PASS" : string `✗ sev=${r.severity}`;
        io:println(string `  val=${val}: ${status} mask=0x${r.error_mask}`);
    }

    io:println("");
    io:println("  Network service: POST /flux/check");
    io:println("  Preset check:    GET  /flux/presetCheck/aviation/60");
    io:println("  Batch mode:      POST /flux/batch");
}
