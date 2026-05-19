// SPDX-License-Identifier: MIT
// FLUX Constraint Engine — Solidity (2015, Smart Contract)
// Pure INT8 saturated constraint checking. Zero dependencies.
//
// The insight: Solidity runs on the EVM — constraints become ON-CHAIN
// INVARIANTS. Once deployed, the constraint check is immutable.
// No one can bypass it. No one can change it. The blockchain IS the auditor.
// For safety-critical systems, this means constraint enforcement with
// cryptographic proof of execution.
//
// "On-chain invariants. Immutable enforcement. The blockchain IS the auditor."

pragma solidity ^0.8.19;

// ══ Constants ══════════════════════════════════════════════════════

int8 constant INT8_MIN = -127;
int8 constant INT8_MAX = 127;
uint8 constant MAX_CONSTRAINTS = 8;

// ══ Severity ══════════════════════════════════════════════════════

enum Severity {
    Pass,
    Caution,
    Warning,
    Critical
}

// ══ Constraint ════════════════════════════════════════════════════

struct Constraint {
    int8 lo;
    int8 hi;
    string name;
}

// ══ FluxResult ═══════════════════════════════════════════════════

struct FluxResult {
    uint8 errorMask;
    Severity severity;
    uint8 violatedLo;
    uint8 violatedHi;
    uint8 violatedCount;
    bool passed;
}

// ══ Events ═══════════════════════════════════════════════════════

event ConstraintChecked(
    string indexed preset,
    int8 value,
    uint8 errorMask,
    Severity severity,
    bool passed
);

event CriticalViolation(
    string indexed preset,
    int8 value,
    uint8 errorMask,
    uint256 timestamp
);

// ══ Core Contract ════════════════════════════════════════════════

contract FluxConstraintEngine {

    // ══ Saturate ════════════════════════════════════════════════════

    function saturate(int256 val) public pure returns (int8) {
        if (val < int256(INT8_MIN)) return INT8_MIN;
        if (val > int256(INT8_MAX)) return INT8_MAX;
        return int8(val);
    }

    // ══ Severity classification ════════════════════════════════════

    function classifySeverity(uint8 vc, uint8 n) public pure returns (Severity) {
        if (vc == 0) return Severity.Pass;
        if (n > 0 && vc <= n / 4) return Severity.Caution;
        if (n > 0 && vc <= n / 2) return Severity.Warning;
        return Severity.Critical;
    }

    // ══ Core check ═════════════════════════════════════════════════

    function check(Constraint[] memory constraints, int256 rawVal)
        public pure returns (FluxResult memory)
    {
        require(constraints.length > 0, "Non-empty constraints required");
        require(constraints.length <= MAX_CONSTRAINTS, "Max 8 constraints");

        int8 val = saturate(rawVal);
        uint8 em = 0;
        uint8 vlo = 0;
        uint8 vhi = 0;
        uint8 vc = 0;
        uint8 n = uint8(constraints.length);

        for (uint8 i = 0; i < n; i++) {
            bool loFail = val < constraints[i].lo;
            bool hiFail = val > constraints[i].hi;
            bool anyFail = loFail || hiFail;
            uint8 bit = 1 << i;

            if (anyFail) em |= bit;
            if (loFail) vlo |= bit;
            if (hiFail) vhi |= bit;
            if (anyFail) vc++;
        }

        return FluxResult({
            errorMask: em,
            severity: classifySeverity(vc, n),
            violatedLo: vlo,
            violatedHi: vhi,
            violatedCount: vc,
            passed: vc == 0
        });
    }

    // ══ Batch check ════════════════════════════════════════════════

    function checkBatch(Constraint[] memory constraints, int256[] memory values)
        public pure returns (FluxResult[] memory)
    {
        FluxResult[] memory results = new FluxResult[](values.length);
        for (uint256 i = 0; i < values.length; i++) {
            results[i] = check(constraints, values[i]);
        }
        return results;
    }

    // ══ Industry Presets ════════════════════════════════════════════

    function aviation() public pure returns (Constraint[] memory) {
        Constraint[] memory c = new Constraint[](4);
        c[0] = Constraint(-55, 70, "cabin_temp_C");
        c[1] = Constraint(75, 101, "cabin_pressure_kPa");
        c[2] = Constraint(0, 100, "fuel_flow_pct");
        c[3] = Constraint(60, 100, "hydraulic_pct");
        return c;
    }

    function automotive() public pure returns (Constraint[] memory) {
        Constraint[] memory c = new Constraint[](4);
        c[0] = Constraint(-40, 60, "battery_temp_C");
        c[1] = Constraint(0, 100, "soc_pct");
        c[2] = Constraint(0, 100, "charge_rate_pct");
        c[3] = Constraint(20, 80, "cabin_temp_C");
        return c;
    }

    function nuclear() public pure returns (Constraint[] memory) {
        Constraint[] memory c = new Constraint[](4);
        c[0] = Constraint(0, 110, "neutron_flux_pct");
        c[1] = Constraint(0, 65, "core_temp_C_x10");
        c[2] = Constraint(72, 100, "pressurizer_pct");
        c[3] = Constraint(0, 100, "coolant_flow_pct");
        return c;
    }

    function medical() public pure returns (Constraint[] memory) {
        Constraint[] memory c = new Constraint[](4);
        c[0] = Constraint(36, 38, "body_temp_C");
        c[1] = Constraint(60, 100, "heart_rate_bpm");
        c[2] = Constraint(95, 100, "spo2_pct");
        c[3] = Constraint(80, 120, "bp_systolic_mmHg");
        return c;
    }

    function maritime() public pure returns (Constraint[] memory) {
        Constraint[] memory c = new Constraint[](4);
        c[0] = Constraint(-2, 35, "sea_temp_C");
        c[1] = Constraint(50, 100, "hull_integrity_pct");
        c[2] = Constraint(0, 50, "wave_height_m");
        c[3] = Constraint(0, 80, "wind_speed_kn");
        return c;
    }

    // ══ Preset check with event logging ════════════════════════════

    function checkPreset(string memory presetName, int256 value)
        public returns (FluxResult memory)
    {
        Constraint[] memory constraints;
        bytes32 sel = keccak256(bytes(presetName));

        if (sel == keccak256("aviation")) {
            constraints = aviation();
        } else if (sel == keccak256("automotive")) {
            constraints = automotive();
        } else if (sel == keccak256("nuclear")) {
            constraints = nuclear();
        } else if (sel == keccak256("medical")) {
            constraints = medical();
        } else if (sel == keccak256("maritime")) {
            constraints = maritime();
        } else {
            revert("Unknown preset");
        }

        FluxResult memory r = check(constraints, value);
        emit ConstraintChecked(presetName, saturate(value), r.errorMask, r.severity, r.passed);

        if (r.severity == Severity.Critical) {
            emit CriticalViolation(presetName, saturate(value), r.errorMask, block.timestamp);
        }

        return r;
    }
}

// Solidity teaches us that constraint enforcement can be IMMUTABLE.
// Once deployed, the check runs forever — unchanged, unbypassable.
// The blockchain IS the auditor. Every check is a transaction.
// For safety-critical systems, this is the ultimate enforcement:
// cryptographic proof that the constraint was checked, when, by whom.
