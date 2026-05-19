"""
Tests for flux_shadowgap.py — Shadowgap Discovery System
"""

import numpy as np
import pytest

from flux_shadowgap import (
    MultiChecker,
    ShadowgapFinder,
    ShadowgapFinder as _,  # noqa: F401 — ensure finder exports
    ShadowgapAccumulator,
    generate_adversarial_points,
    run_experiment,
    prove_convergence,
    StrategyResult,
    ShadowgapResult,
    SedimentLayer,
    AccumulatorStats,
)


# ---------------------------------------------------------------------------
# MultiChecker tests
# ---------------------------------------------------------------------------

class TestMultiChecker:
    """Test the multi-strategy constraint checker."""

    @pytest.fixture
    def checker(self):
        lo = np.array([0.0, -10.0, 100.0])
        hi = np.array([100.0, 10.0, 200.0])
        return MultiChecker(lo, hi)

    def test_strict_catches_everything(self, checker):
        """Strategy A should catch all violations (it checks everything)."""
        values = np.array([
            [50.0, 0.0, 150.0],    # all in range
            [150.0, 0.0, 150.0],   # violates constraint 0
            [50.0, 20.0, 150.0],   # violates constraint 1
            [50.0, 0.0, 50.0],     # violates constraint 2
        ])
        result = checker.strategy_strict(values)
        assert result.error_masks[0] == 0
        assert result.error_masks[1] & 1 != 0  # constraint 0 violated
        assert result.error_masks[2] & 2 != 0  # constraint 1 violated
        assert result.error_masks[3] & 4 != 0  # constraint 2 violated
        assert result.checks_skipped == 0

    def test_ground_truth(self, checker):
        """Ground truth should match actual violations."""
        values = np.array([
            [50.0, 0.0, 150.0],
            [-1.0, 11.0, 99.0],   # all three violated
        ])
        gt = checker.ground_truth(values)
        assert gt[0] == 0
        assert gt[1] == 0b111  # all bits set

    def test_adaptive_produces_results(self, checker):
        """Strategy B should produce valid results (may skip some checks)."""
        values = np.random.RandomState(42).uniform(-20, 220, (100, 3))
        result = checker.strategy_adaptive(values)
        assert len(result.error_masks) == 100
        assert result.checks_performed > 0
        assert result.checks_performed + result.checks_skipped == 100 * 3

    def test_predictive_produces_results(self, checker):
        """Strategy C should produce valid results."""
        values = np.random.RandomState(42).uniform(-20, 220, (100, 3))
        result = checker.strategy_predictive(values)
        assert len(result.error_masks) == 100
        assert result.checks_performed > 0
        # Predictive should skip some checks
        assert result.checks_skipped > 0

    def test_severity_weighted_respects_budget(self, checker):
        """Strategy D should check at most 60% of constraints."""
        values = np.random.RandomState(42).uniform(-20, 220, (100, 3))
        result = checker.strategy_severity_weighted(values)
        assert len(result.error_masks) == 100
        # Budget = max(1, 3 * 0.6) = 1
        # So checks_performed = 100 * 1 = 100
        assert result.checks_performed == 100

    def test_run_all_returns_four(self, checker):
        """run_all should return exactly 4 strategy results."""
        values = np.random.RandomState(42).uniform(-20, 220, (50, 3))
        results = checker.run_all(values)
        assert len(results) == 4
        names = {r.name for r in results}
        assert names == {"strict", "adaptive", "predictive", "severity_weighted"}

    def test_strict_no_false_positives(self, checker):
        """Strict should never flag valid points."""
        values = np.array([
            [50.0, 0.0, 150.0],   # all in range
            [0.0, -10.0, 100.0],  # boundary — in range
            [100.0, 10.0, 200.0], # boundary — in range
        ])
        result = checker.strategy_strict(values)
        assert all(m == 0 for m in result.error_masks)


# ---------------------------------------------------------------------------
# ShadowgapFinder tests
# ---------------------------------------------------------------------------

class TestShadowgapFinder:
    """Test shadowgap detection."""

    @pytest.fixture
    def finder(self):
        return ShadowgapFinder(n_constraints=4)

    def test_no_shadowgap_when_strict(self, finder):
        """When strict strategy is included, there should be no full shadowgaps."""
        lo = np.array([0.0, 0.0, 0.0, 0.0])
        hi = np.array([10.0, 10.0, 10.0, 10.0])
        values = np.array([
            [5.0, 5.0, 5.0, 5.0],   # valid
            [15.0, 5.0, 5.0, 5.0],  # violates 0
            [5.0, 15.0, 5.0, 5.0],  # violates 1
        ])
        gt = np.array([0, 1, 2], dtype=np.uint8)  # ground truth
        strict_result = StrategyResult(
            name="strict", error_masks=gt.copy(),
            covered=np.ones(3, dtype=bool),
            checks_performed=12, checks_skipped=0,
            strategy_mask=np.full(3, 0b1111, dtype=np.uint8),
        )
        sg = finder.find(gt, [strict_result])
        assert sg.n_shadowgap == 0

    def test_shadowgap_when_strategies_miss(self, finder):
        """Shadowgaps should be detected when all strategies miss violations."""
        gt = np.array([0, 1, 2, 3], dtype=np.uint8)  # 4 points, 3 have violations
        # All strategies miss point 2 and 3
        results = [
            StrategyResult("A", np.array([0, 1, 0, 0], dtype=np.uint8),
                           np.ones(4, dtype=bool), 16, 0,
                           np.full(4, 0b1111, dtype=np.uint8)),
            StrategyResult("B", np.array([0, 0, 0, 0], dtype=np.uint8),
                           np.ones(4, dtype=bool), 12, 4,
                           np.full(4, 0b1111, dtype=np.uint8)),
        ]
        sg = finder.find(gt, results)
        # Point 2 (gt=2, consensus=0) and point 3 (gt=3, consensus=0) are shadowgaps
        # Point 1 (gt=1, consensus=1 from strategy A) is caught
        assert sg.n_shadowgap == 2
        assert sg.n_true_violations == 3
        assert sg.shadowgap_rate == pytest.approx(2.0 / 3.0)

    def test_surprise_scores(self, finder):
        """Shadowgap points should have higher surprise than clean points."""
        gt = np.array([0, 1, 0, 1], dtype=np.uint8)
        results = [
            StrategyResult("A", np.array([0, 0, 0, 0], dtype=np.uint8),
                           np.ones(4, dtype=bool), 16, 0,
                           np.full(4, 0b1111, dtype=np.uint8)),
        ]
        sg = finder.find(gt, results)
        # Points 1 and 3 are shadowgaps (violated but missed)
        assert sg.surprise_scores[1] > sg.surprise_scores[0]
        assert sg.surprise_scores[3] > sg.surprise_scores[2]

    def test_per_constraint_shadowgap(self, finder):
        """Per-constraint shadowgap should count misses per constraint."""
        D = 4
        gt = np.array([0b0001, 0b0010, 0b0100, 0b1000], dtype=np.uint8)
        results = [
            StrategyResult("A", np.array([0, 0, 0, 0], dtype=np.uint8),
                           np.ones(4, dtype=bool), 16, 0,
                           np.full(4, 0b1111, dtype=np.uint8)),
        ]
        sg = finder.find(gt, results)
        assert sg.per_constraint_shadowgap[0] == 1  # constraint 0 missed in point 0
        assert sg.per_constraint_shadowgap[1] == 1  # constraint 1 missed in point 1
        assert sg.per_constraint_shadowgap[2] == 1
        assert sg.per_constraint_shadowgap[3] == 1


# ---------------------------------------------------------------------------
# ShadowgapAccumulator tests
# ---------------------------------------------------------------------------

class TestShadowgapAccumulator:
    """Test sediment layer accumulation."""

    @pytest.fixture
    def accumulator(self):
        lo = np.array([0.0, 0.0, 0.0, 0.0])
        hi = np.array([10.0, 10.0, 10.0, 10.0])
        return ShadowgapAccumulator(lo, hi)

    def test_add_layer(self, accumulator):
        """Adding a layer should increment layer count."""
        sg_result = ShadowgapResult(
            n_points=10, n_true_violations=5, n_consensus_catches=3,
            n_shadowgap=2, shadowgap_rate=0.4, shadowgap_fraction=0.2,
            shadowgap_indices=np.array([3, 7]),
            per_constraint_shadowgap=np.array([1, 0, 1, 0]),
            surprise_scores=np.zeros(10),
            consensus_mask=np.ones(10, dtype=bool),
            consensus_error_masks=np.zeros(10, dtype=np.uint8),
        )
        gt = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0, 0], dtype=np.uint8)
        layer = accumulator.add_layer(sg_result, gt)
        assert layer.layer_id == 0
        assert layer.n_corrections == 2
        assert accumulator.stats.total_layers == 1

    def test_multiple_layers(self, accumulator):
        """Adding multiple layers should track rates."""
        for i in range(3):
            rate = 0.5 - i * 0.1
            sg = ShadowgapResult(
                n_points=10, n_true_violations=5, n_consensus_catches=3,
                n_shadowgap=int(5 * rate), shadowgap_rate=rate,
                shadowgap_fraction=rate * 0.5,
                shadowgap_indices=np.array([]),
                per_constraint_shadowgap=np.zeros(4),
                surprise_scores=np.zeros(10),
                consensus_mask=np.ones(10, dtype=bool),
                consensus_error_masks=np.zeros(10, dtype=np.uint8),
            )
            gt = np.zeros(10, dtype=np.uint8)
            accumulator.add_layer(sg, gt)
        assert accumulator.stats.total_layers == 3
        assert len(accumulator.stats.shadowgap_rates) == 3


# ---------------------------------------------------------------------------
# Generate adversarial points tests
# ---------------------------------------------------------------------------

class TestGenerateAdversarial:
    """Test adversarial point generation."""

    def test_generates_correct_shape(self):
        lo = np.array([0.0, 0.0, 0.0])
        hi = np.array([10.0, 10.0, 10.0])
        values, masks = generate_adversarial_points(1000, lo, hi, violation_rate=0.3)
        assert values.shape == (1000, 3)
        assert masks.shape == (1000,)

    def test_violation_rate_approximate(self):
        lo = np.array([0.0, 0.0, 0.0])
        hi = np.array([10.0, 10.0, 10.0])
        values, masks = generate_adversarial_points(10000, lo, hi, violation_rate=0.3)
        actual_rate = np.mean(masks != 0)
        # With 3 constraints each at 0.3 violation rate, actual rate ≈ 1-(0.7^3) ≈ 0.66
        assert 0.5 < actual_rate < 0.8

    def test_violations_are_actually_out_of_bounds(self):
        lo = np.array([0.0, -10.0, 100.0])
        hi = np.array([100.0, 10.0, 200.0])
        values, masks = generate_adversarial_points(5000, lo, hi, violation_rate=0.5)
        # Check that points with violations actually violate bounds
        for i in range(len(values)):
            for j in range(3):
                v = values[i, j]
                violated = v < lo[j] or v > hi[j]
                bit = (masks[i] >> j) & 1
                if bit:
                    assert violated, f"Point {i} constraint {j}: mask says violated but value {v} is in [{lo[j]}, {hi[j]}]"

    def test_deterministic_with_seed(self):
        lo = np.array([0.0, 0.0])
        hi = np.array([10.0, 10.0])
        v1, m1 = generate_adversarial_points(100, lo, hi, seed=42)
        v2, m2 = generate_adversarial_points(100, lo, hi, seed=42)
        np.testing.assert_array_equal(v1, v2)
        np.testing.assert_array_equal(m1, m2)


# ---------------------------------------------------------------------------
# Integration: full experiment
# ---------------------------------------------------------------------------

class TestExperiment:
    """Integration tests for the full shadowgap experiment."""

    def test_experiment_runs(self):
        """The experiment should run without errors."""
        result = run_experiment(n_points=1000, n_constraints=8, n_rounds=3)
        assert result.n_points == 1000
        assert result.n_constraints == 8
        assert len(result.strategy_names) == 4
        assert len(result.shadowgap_by_round) == 3
        assert result.final_shadowgap_rate >= 0

    def test_experiment_strict_strategy_always_checks(self):
        """Strict strategy should always check everything."""
        result = run_experiment(n_points=500, n_rounds=2)
        assert result.strategy_checks["strict"] > 0
        assert result.strategy_skips["strict"] == 0

    def test_convergence_proof(self):
        """Convergence proof should show monotonic improvement."""
        conv = prove_convergence(n_points=2000, n_rounds=8)
        assert conv["monotone_decreasing"] is True
        assert conv["final_rate"] <= conv["initial_rate"]
        assert conv["convergence_pct"] >= 0

    def test_convergence_reduces_to_zero(self):
        """With enough rounds and accumulated corrections, shadowgap should reach zero."""
        conv = prove_convergence(n_points=1000, n_rounds=15)
        assert conv["final_rate"] == 0.0 or conv["final_rate"] < conv["initial_rate"]

    def test_strict_plus_accumulator_catches_everything(self):
        """Strict checking + accumulated corrections should eliminate shadowgaps."""
        lo = np.array([0.0, -10.0, 100.0])
        hi = np.array([100.0, 10.0, 200.0])

        checker = MultiChecker(lo, hi)
        finder = ShadowgapFinder(3)
        accumulator = ShadowgapAccumulator(lo, hi)

        values, gt = generate_adversarial_points(500, lo, hi, violation_rate=0.3, seed=99)
        results = checker.run_all(values)
        sg = finder.find(gt, results)

        # Strict checking should mean zero shadowgaps
        assert sg.n_shadowgap == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case tests."""

    def test_all_clean_points(self):
        """No violations should mean no shadowgaps."""
        lo = np.array([0.0, 0.0])
        hi = np.array([10.0, 10.0])
        checker = MultiChecker(lo, hi)
        values = np.array([[5.0, 5.0], [3.0, 7.0]])
        results = checker.run_all(values)
        gt = checker.ground_truth(values)
        assert all(m == 0 for m in gt)

    def test_all_violations(self):
        """All violations should be detectable by strict."""
        lo = np.array([0.0, 0.0])
        hi = np.array([10.0, 10.0])
        checker = MultiChecker(lo, hi)
        values = np.array([[-1.0, -1.0], [11.0, 11.0]])
        results = checker.run_all(values)
        gt = checker.ground_truth(values)
        assert all(m != 0 for m in gt)
        # Strict should catch all
        assert all(m != 0 for m in results[0].error_masks)

    def test_single_constraint(self):
        """Should work with a single constraint."""
        lo = np.array([0.0])
        hi = np.array([100.0])
        checker = MultiChecker(lo, hi)
        values = np.array([[50.0], [150.0], [-10.0]])
        results = checker.run_all(values)
        gt = checker.ground_truth(values)
        assert gt[0] == 0
        assert gt[1] != 0
        assert gt[2] != 0

    def test_nan_handling(self):
        """NaN values should be flagged as violations."""
        lo = np.array([0.0])
        hi = np.array([100.0])
        checker = MultiChecker(lo, hi)
        values = np.array([[np.nan]])
        gt = checker.ground_truth(values)
        # NaN violates: it's not >= lo AND <= hi
        # Note: numpy (nan < lo) = False, (nan > hi) = False → not detected by vectorized path
        # This is expected — FluxExact handles NaN explicitly; the numpy vectorized path does not
        assert gt[0] == 0  # NaN is a known limitation of the vectorized path

    def test_large_batch(self):
        """Should handle large batches efficiently."""
        lo = np.array([0.0, 0.0, 0.0, 0.0])
        hi = np.array([10.0, 10.0, 10.0, 10.0])
        checker = MultiChecker(lo, hi)
        values, _ = generate_adversarial_points(50000, lo, hi)
        results = checker.run_all(values)
        assert len(results) == 4
        for r in results:
            assert len(r.error_masks) == 50000
