"""
Tests for flux_mayo.py — Mayo Clinic Protocol

Proof that the procedure IS the intelligence:
- Zero false negatives on random inputs
- All edge cases caught
- v1 and v2 both produce correct results
- Refinement produces a valid v2
"""

import numpy as np
import pytest

from flux_mayo import (
    MayoProtocol,
    ProtocolExecutor,
    ProtocolRefiner,
    Step,
    Severity,
    build_automotive_can_protocol,
    run_demonstration,
)


# ── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def can_protocol():
    return build_automotive_can_protocol()

@pytest.fixture
def protocol_and_bounds(can_protocol):
    return can_protocol

@pytest.fixture
def executor(can_protocol):
    protocol, bounds = can_protocol
    return ProtocolExecutor(protocol), bounds


# ── Protocol Construction ───────────────────────────────────

class TestProtocolConstruction:
    def test_protocol_fields(self, protocol_and_bounds):
        protocol, bounds = protocol_and_bounds
        assert protocol.name == "automotive_can_constraint_check"
        assert protocol.version == "1.0.0"
        assert protocol.author == "Claude-Opus-tier"
        assert protocol.target_executor == "Seed-2.0-mini-tier"
        assert protocol.n_constraints == 8
        assert len(bounds) == 8

    def test_protocol_has_steps(self, protocol_and_bounds):
        protocol, _ = protocol_and_bounds
        assert len(protocol.steps) == 5
        assert protocol.steps[0].name == "Validate inputs"
        assert protocol.steps[1].name == "Check each constraint"
        assert protocol.steps[4].name == "Generate proof hash"

    def test_protocol_has_conditions(self, protocol_and_bounds):
        protocol, _ = protocol_and_bounds
        assert len(protocol.pre_conditions) >= 3
        assert len(protocol.post_conditions) >= 3
        assert len(protocol.contingencies) >= 2

    def test_provenance(self, protocol_and_bounds):
        protocol, _ = protocol_and_bounds
        p = protocol.provenance()
        assert p["protocol"] == "automotive_can_constraint_check"
        assert p["version"] == "1.0.0"
        assert p["author"] == "Claude-Opus-tier"


# ── In-Bounds Values ────────────────────────────────────────

class TestInBounds:
    def test_all_midrange_passes(self, executor):
        exec_inst, bounds = executor
        vals = np.array([
            (lo + hi) / 2 for lo, hi in bounds
        ], dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.passed is True
        assert r.error_mask == 0
        assert r.severity == Severity.PASS

    def test_exact_lower_bounds_pass(self, executor):
        exec_inst, bounds = executor
        vals = np.array([lo for lo, hi in bounds], dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.passed is True
        assert r.error_mask == 0

    def test_exact_upper_bounds_pass(self, executor):
        exec_inst, bounds = executor
        vals = np.array([hi for lo, hi in bounds], dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.passed is True
        assert r.error_mask == 0


# ── Out-of-Bounds Values ────────────────────────────────────

class TestOutOfBounds:
    def test_single_violation_low(self, executor):
        exec_inst, bounds = executor
        vals = np.array([
            (lo + hi) / 2 for lo, hi in bounds
        ], dtype=np.float64)
        vals[0] = bounds[0][0] - 1  # just below lower bound
        r = exec_inst.execute(vals, bounds)
        assert r.passed is False
        assert r.error_mask & 0x01  # bit 0 set
        assert r.error_mask == 0x01  # only bit 0

    def test_single_violation_high(self, executor):
        exec_inst, bounds = executor
        vals = np.array([
            (lo + hi) / 2 for lo, hi in bounds
        ], dtype=np.float64)
        vals[2] = bounds[2][1] + 1  # just above upper bound
        r = exec_inst.execute(vals, bounds)
        assert r.passed is False
        assert r.error_mask & 0x04  # bit 2 set

    def test_all_violated(self, executor):
        exec_inst, bounds = executor
        vals = np.array([
            hi + 100 for lo, hi in bounds
        ], dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.passed is False
        assert r.error_mask == 0xFF  # all 8 bits

    def test_alternating_violations(self, executor):
        exec_inst, bounds = executor
        vals = np.zeros(8, dtype=np.float64)
        for i in range(8):
            if i % 2 == 0:
                vals[i] = bounds[i][1] + 1
            else:
                vals[i] = (bounds[i][0] + bounds[i][1]) / 2
        r = exec_inst.execute(vals, bounds)
        assert r.passed is False
        assert r.error_mask == 0x55  # bits 0, 2, 4, 6


# ── Edge Cases ──────────────────────────────────────────────

class TestEdgeCases:
    def test_nan_detected(self, executor):
        exec_inst, bounds = executor
        vals = np.array([np.nan, 100, 50, 50, 100, 0, 12, 50], dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.passed is False
        assert r.severity == Severity.CRITICAL

    def test_inf_detected(self, executor):
        exec_inst, bounds = executor
        vals = np.array([4000, 150, 80, 50, 100, 0, np.inf, 50], dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.passed is False

    def test_negative_inf(self, executor):
        exec_inst, bounds = executor
        vals = np.array([4000, 150, float('-inf'), 50, 100, 0, 12, 50], dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.passed is False

    def test_all_nan(self, executor):
        exec_inst, bounds = executor
        vals = np.full(8, np.nan, dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.passed is False
        assert r.severity == Severity.CRITICAL

    def test_all_inf(self, executor):
        exec_inst, bounds = executor
        vals = np.full(8, np.inf, dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.passed is False


# ── Severity Classification ─────────────────────────────────

class TestSeverity:
    def test_pass_severity(self, executor):
        exec_inst, bounds = executor
        vals = np.array([(lo + hi) / 2 for lo, hi in bounds], dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.severity == Severity.PASS

    def test_critical_on_nan(self, executor):
        exec_inst, bounds = executor
        vals = np.array([np.nan] + [0.0]*7, dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.severity == Severity.CRITICAL


# ── Post-Conditions ─────────────────────────────────────────

class TestPostConditions:
    def test_no_post_violations_normal(self, executor):
        exec_inst, bounds = executor
        vals = np.array([(lo + hi) / 2 for lo, hi in bounds], dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert len(r.warnings) == 0

    def test_proof_hash_present(self, executor):
        exec_inst, bounds = executor
        vals = np.array([(lo + hi) / 2 for lo, hi in bounds], dtype=np.float64)
        r = exec_inst.execute(vals, bounds)
        assert r.proof_hash != "no-proof"
        assert len(r.proof_hash) == 16


# ── Batch: Zero False Negatives ─────────────────────────────

class TestZeroFalseNegatives:
    def test_1000_random_no_false_negatives(self, executor):
        """The core proof: 1000 random inputs, zero false negatives."""
        exec_inst, bounds = executor
        rng = np.random.default_rng(42)

        for _ in range(500):
            vals = np.array([
                rng.uniform(lo + 0.01, hi - 0.01) for lo, hi in bounds
            ], dtype=np.float64)
            r = exec_inst.execute(vals, bounds)
            assert r.passed is True, f"In-bounds should pass: {vals}"

        for _ in range(500):
            vals = np.array([
                rng.uniform(lo, hi) for lo, hi in bounds
            ], dtype=np.float64)
            n_violate = rng.integers(1, 4)
            violate_indices = rng.choice(8, size=n_violate, replace=False)
            for idx in violate_indices:
                lo, hi = bounds[idx]
                if rng.random() < 0.5:
                    vals[idx] = lo - rng.uniform(0.1, 100)
                else:
                    vals[idx] = hi + rng.uniform(0.1, 100)
            r = exec_inst.execute(vals, bounds)
            assert r.passed is False, f"Out-of-bounds should fail: {vals}"


# ── Refinement ──────────────────────────────────────────────

class TestRefinement:
    def test_refinement_report(self, executor):
        exec_inst, bounds = executor
        rng = np.random.default_rng(42)
        results = []
        for _ in range(100):
            vals = np.array([
                rng.uniform(lo + 0.01, hi - 0.01) for lo, hi in bounds
            ], dtype=np.float64)
            results.append(exec_inst.execute(vals, bounds))

        refiner = ProtocolRefiner()
        protocol = exec_inst.protocol
        report = refiner.refine(protocol, results)
        assert "total_runs" in report
        assert report["total_runs"] == 100
        assert "pass_rate" in report
        assert "suggestions" in report

    def test_v2_builds(self, executor):
        exec_inst, bounds = executor
        refiner = ProtocolRefiner()
        protocol = exec_inst.protocol
        report = refiner.refine(protocol, [])
        v2 = refiner.build_v2(protocol, report)
        assert v2.version == "2.0.0"
        assert v2.name == protocol.name
        assert len(v2.steps) >= len(protocol.steps)

    def test_v2_executes(self, executor):
        exec_inst, bounds = executor
        refiner = ProtocolRefiner()
        protocol = exec_inst.protocol
        report = refiner.refine(protocol, [])
        v2 = refiner.build_v2(protocol, report)
        exec_v2 = ProtocolExecutor(v2)

        vals = np.array([(lo + hi) / 2 for lo, hi in bounds], dtype=np.float64)
        r = exec_v2.execute(vals, bounds)
        assert r.passed is True
        assert r.protocol_version == "2.0.0"

    def test_v2_catches_nan(self, executor):
        exec_inst, bounds = executor
        refiner = ProtocolRefiner()
        protocol = exec_inst.protocol
        v2 = refiner.build_v2(protocol, {})
        exec_v2 = ProtocolExecutor(v2)

        vals = np.array([np.nan, 100, 50, 50, 100, 0, 12, 50], dtype=np.float64)
        r = exec_v2.execute(vals, bounds)
        assert r.passed is False
        assert r.severity == Severity.CRITICAL

    def test_v2_catches_boundary_violations(self, executor):
        exec_inst, bounds = executor
        refiner = ProtocolRefiner()
        protocol = exec_inst.protocol
        v2 = refiner.build_v2(protocol, {})
        exec_v2 = ProtocolExecutor(v2)

        vals = np.array([8001, 150, 80, 50, 100, 0, 12, 50], dtype=np.float64)
        r = exec_v2.execute(vals, bounds)
        assert r.passed is False


# ── Demonstration runs clean ────────────────────────────────

class TestDemonstration:
    def test_demonstration_returns_true(self):
        """The full demonstration runs without error."""
        result = run_demonstration()
        assert result is True, "Demonstration should report zero false negatives"
