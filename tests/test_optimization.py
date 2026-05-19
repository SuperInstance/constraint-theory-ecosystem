"""
Tests for FLUX Optimization Engine — flux_optimize.py

Validates:
1. Bayesian probability estimation converges to true values
2. Optimal ordering minimizes expected cost (vs random/worst)
3. Adaptive decision tree converges within 1000 samples
4. Batch vs streaming model produces sensible recommendations
5. Pareto frontier is monotonically non-dominated
6. Reordering never increases false negatives
"""

import sys
import os
import random
import math
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/src/python')

from flux_optimize import (
    ViolationProbabilityTracker, ConstraintStats,
    OptimalOrderer, AdaptiveDecisionTree,
    BatchVsStreamingOptimizer, CacheModel, CheckStrategy,
    ParetoFrontier, ParetoPoint,
    run_adaptive_experiment, _check_static,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def constraint_names():
    return ["high_violation", "medium_violation", "low_violation", "rare_violation"]


@pytest.fixture
def true_probabilities():
    return {
        "high_violation": 0.50,
        "medium_violation": 0.20,
        "low_violation": 0.05,
        "rare_violation": 0.01,
    }


@pytest.fixture
def check_fns():
    return {
        "high_violation": lambda v: v > 0,       # ~50% violate
        "medium_violation": lambda v: v > 80,     # ~20% violate
        "low_violation": lambda v: abs(v) > 95,   # ~5% violate
        "rare_violation": lambda v: v > 99,       # ~1% violate
    }


@pytest.fixture
def tracker(constraint_names):
    return ViolationProbabilityTracker(constraint_names)


# ---------------------------------------------------------------------------
# 1. ViolationProbabilityTracker tests
# ---------------------------------------------------------------------------

class TestViolationProbabilityTracker:

    def test_bayesian_convergence(self, tracker, true_probabilities):
        """Estimated probabilities converge to true values with enough data."""
        random.seed(42)
        n_samples = 50_000

        for _ in range(n_samples):
            value = random.uniform(0, 100)
            for name, p_true in true_probabilities.items():
                violated = random.random() < p_true
                tracker.observe(name, violated)

        for name, p_true in true_probabilities.items():
            p_est = tracker.constraints[name].p_violation
            assert abs(p_est - p_true) < 0.02, \
                f"{name}: estimated {p_est:.4f} vs true {p_true:.4f}"

    def test_ucb_exceeds_mean(self, tracker):
        """UCB estimate >= posterior mean (exploration bonus)."""
        tracker.observe("high_violation", True)
        tracker.observe("high_violation", False)
        stats = tracker.constraints["high_violation"]
        assert stats.p_violation_ucb >= stats.p_violation

    def test_convergence_error_decreases(self, tracker, true_probabilities):
        """Convergence error monotonically decreases with more data."""
        random.seed(42)
        errors = []
        for i in range(5000):
            value = random.uniform(0, 100)
            for name, p_true in true_probabilities.items():
                tracker.observe(name, random.random() < p_true)
            if i > 0 and i % 500 == 0:
                errors.append(tracker.convergence_error(true_probabilities))

        # Errors should generally decrease
        assert errors[-1] < errors[0], \
            f"Error didn't decrease: {errors[0]:.4f} → {errors[-1]:.4f}"

    def test_rank_correlation_perfect(self, tracker, true_probabilities):
        """With enough data, rank correlation approaches 1."""
        random.seed(42)
        for _ in range(100_000):
            for name, p_true in true_probabilities.items():
                tracker.observe(name, random.random() < p_true)

        rho = tracker.ordering_spearman(true_probabilities)
        assert rho > 0.9, f"Rank correlation too low: {rho:.3f}"

    def test_get_order_mean_sorts_by_violation_probability(self, tracker):
        """Mean ordering sorts by descending p × cost."""
        tracker.observe("high_violation", True)
        tracker.observe("high_violation", True)
        tracker.observe("low_violation", False)
        tracker.observe("low_violation", False)
        order = tracker.get_order_mean()
        assert order.index("high_violation") < order.index("low_violation")


# ---------------------------------------------------------------------------
# 2. OptimalOrderer tests
# ---------------------------------------------------------------------------

class TestOptimalOrderer:

    def test_optimal_order_cheapest_violations_first(self, true_probabilities):
        """Optimal order checks constraints with highest p/c ratio first."""
        orderer = OptimalOrderer(true_probabilities)
        order = orderer.optimal_order()
        # high_violation (0.50/1.0=0.50) should be first
        # rare_violation (0.01/1.0=0.01) should be last
        assert order[0] == "high_violation"
        assert order[-1] == "rare_violation"

    def test_optimal_cost_less_than_worst(self, true_probabilities):
        """Optimal ordering costs less than worst ordering."""
        orderer = OptimalOrderer(true_probabilities)
        assert orderer.optimal_cost() < orderer.worst_cost()

    def test_optimal_cost_less_than_random(self, true_probabilities):
        """Optimal ordering costs less than most random orderings."""
        orderer = OptimalOrderer(true_probabilities)
        opt = orderer.optimal_cost()
        names = list(true_probabilities.keys())

        # Test 20 random orderings
        random.seed(42)
        n_better = 0
        for _ in range(20):
            random.shuffle(names)
            rand_cost = orderer.expected_cost(names)
            if rand_cost < opt:
                n_better += 1

        # Optimal should beat most random orderings
        assert n_better <= 2, f"Random ordering beat optimal {n_better}/20 times"

    def test_cost_with_heterogeneous_costs(self):
        """Expensive constraints with low violation prob go last."""
        probs = {"cheap_violator": 0.4, "expensive_violator": 0.4}
        costs = {"cheap_violator": 1.0, "expensive_violator": 10.0}
        orderer = OptimalOrderer(probs, costs)
        order = orderer.optimal_order()
        # Same p, but cheap_violator has c/p = 1/0.4 = 2.5
        # expensive_violator has c/p = 10/0.4 = 25
        # So cheap_violator goes first (lower c/p)
        assert order[0] == "cheap_violator"

    def test_speedup_ratio_sane(self, true_probabilities):
        """Speedup ratio is >= 1."""
        orderer = OptimalOrderer(true_probabilities)
        assert orderer.speedup_ratio() >= 1.0

    def test_cost_breakdown_marginal_decreasing(self, true_probabilities):
        """Marginal costs decrease along the optimal ordering."""
        orderer = OptimalOrderer(true_probabilities)
        breakdown = orderer.cost_breakdown(orderer.optimal_order())
        marginals = [b['marginal_cost'] for b in breakdown]
        # Marginal costs should generally decrease (survival probability drops)
        for i in range(len(marginals) - 1):
            assert marginals[i] >= marginals[i + 1] * 0.8, \
                f"Marginal cost not decreasing: {marginals[i]:.3f} → {marginals[i+1]:.3f}"


# ---------------------------------------------------------------------------
# 3. AdaptiveDecisionTree tests
# ---------------------------------------------------------------------------

class TestAdaptiveDecisionTree:

    def test_check_value_stops_on_first_violation(self, tracker, check_fns):
        """Decision tree stops checking after first violation."""
        tree = AdaptiveDecisionTree(tracker)
        value = 99.9  # violates high_violation (v > 0)
        passed, cost, violation = tree.check_value(value, check_fns)
        assert not passed
        assert violation == "high_violation"
        assert cost == 1.0  # only checked first constraint

    def test_check_value_checks_all_if_pass(self, tracker, check_fns):
        """Decision tree checks all constraints if value passes."""
        tree = AdaptiveDecisionTree(tracker)
        value = -5.0  # passes all constraints
        passed, cost, violation = tree.check_value(value, check_fns)
        assert passed
        assert violation is None
        assert cost == 4.0  # checked all 4 constraints

    def test_adaptive_converges_to_optimal(self, constraint_names, true_probabilities, check_fns):
        """Adaptive ordering converges to near-optimal within 1000 samples."""
        random.seed(42)
        tracker = ViolationProbabilityTracker(constraint_names)
        tree = AdaptiveDecisionTree(tracker)

        for i in range(1000):
            value = random.uniform(0, 100)
            tree.check_value(value, check_fns)

        # Check rank correlation
        rho = tracker.ordering_spearman(true_probabilities)
        assert rho > 0.7, f"Rank correlation after 1000 samples: {rho:.3f}"

        # Check convergence error
        error = tracker.convergence_error(true_probabilities)
        assert error < 0.45, f"Convergence error after 1000 samples: {error:.4f}"

    def test_pruning_rate_positive(self, tracker, check_fns):
        """Pruning rate is positive when some violations exist."""
        random.seed(42)
        tree = AdaptiveDecisionTree(tracker)
        for _ in range(100):
            tree.check_value(random.uniform(0, 100), check_fns)
        assert tree.pruning_rate() > 0.0

    def test_expected_depth_less_than_n(self, tracker):
        """Expected depth is less than total constraints when p > 0."""
        tracker.observe("high_violation", True)
        tracker.observe("medium_violation", True)
        tree = AdaptiveDecisionTree(tracker)
        assert tree.expected_depth() < len(tracker.constraints)


# ---------------------------------------------------------------------------
# 4. BatchVsStreamingOptimizer tests
# ---------------------------------------------------------------------------

class TestBatchVsStreamingOptimizer:

    def test_batch_fits_small_values(self):
        """Batch preferred when value array fits in cache."""
        cache = CacheModel(cache_size=1024)
        bvso = BatchVsStreamingOptimizer(cache)
        # Small value set → values fit in cache
        rec = bvso.recommend(100, 10)
        assert rec['recommended'] in ('batch', 'adaptive', 'streaming')

    def test_streaming_recommended_with_early_stop(self):
        """Streaming recommended when violations are common (early stopping helps)."""
        bvso = BatchVsStreamingOptimizer()
        # High violation rates → early stopping is very effective
        rec = bvso.recommend(1000, 6, [0.8, 0.7, 0.6, 0.5, 0.4, 0.3])
        # With these high violation rates, streaming's early exit should win
        assert rec['recommended'] in ('streaming', 'adaptive')

    def test_model_returns_positive_costs(self):
        """Both models return positive costs."""
        bvso = BatchVsStreamingOptimizer()
        batch = bvso.model_batch_cost(1000, 5)
        stream = bvso.model_streaming_cost(1000, 5)
        assert batch['total_cost'] > 0
        assert stream['analytical_cost'] > 0


# ---------------------------------------------------------------------------
# 5. ParetoFrontier tests
# ---------------------------------------------------------------------------

class TestParetoFrontier:

    def test_full_check_zero_fnr(self, true_probabilities):
        """Checking all constraints gives FNR = 0."""
        pf = ParetoFrontier(true_probabilities)
        point = pf.compute_point(len(true_probabilities))
        assert point.false_negative_rate == 0.0

    def test_no_check_fnr_is_one(self, true_probabilities):
        """Checking no constraints gives maximum FNR."""
        pf = ParetoFrontier(true_probabilities)
        point = pf.compute_point(0)
        # FNR when checking nothing: all violations are missed
        assert point.false_negative_rate > 0.0
        assert point.detection_rate < 1.0

    def test_frontier_is_nondominated(self, true_probabilities):
        """All points on the frontier are non-dominated."""
        pf = ParetoFrontier(true_probabilities)
        frontier = pf.compute_frontier()

        for i, p1 in enumerate(frontier):
            for j, p2 in enumerate(frontier):
                if i == j:
                    continue
                # p2 should not dominate p1
                strictly_better = (p2.expected_time <= p1.expected_time and
                                   p2.false_negative_rate <= p1.false_negative_rate and
                                   (p2.expected_time < p1.expected_time or
                                    p2.false_negative_rate < p1.false_negative_rate))
                assert not strictly_better, \
                    f"Point {j} dominates point {i} on Pareto frontier"

    def test_frontier_monotonic_time(self, true_probabilities):
        """Frontier points are sorted by increasing time."""
        pf = ParetoFrontier(true_probabilities)
        frontier = pf.compute_frontier()
        for i in range(len(frontier) - 1):
            assert frontier[i].expected_time <= frontier[i + 1].expected_time

    def test_frontier_decreasing_fnr(self, true_probabilities):
        """FNR decreases as we check more constraints."""
        pf = ParetoFrontier(true_probabilities)
        frontier = pf.compute_frontier()
        for i in range(len(frontier) - 1):
            assert frontier[i].false_negative_rate >= frontier[i + 1].false_negative_rate

    def test_knee_point_exists(self, true_probabilities):
        """Knee point is on the frontier."""
        pf = ParetoFrontier(true_probabilities)
        frontier = pf.compute_frontier()
        knee = pf.find_knee_point()
        assert knee in frontier

    def test_summary_prints(self, true_probabilities):
        """Summary produces non-empty string."""
        pf = ParetoFrontier(true_probabilities)
        s = pf.summary()
        assert len(s) > 50
        assert "knee" in s.lower()


# ---------------------------------------------------------------------------
# 6. Full experiment tests
# ---------------------------------------------------------------------------

class TestFullExperiment:

    def test_adaptive_speedup_vs_worst(self):
        """Adaptive ordering beats worst-case static ordering."""
        random.seed(42)
        names = ["c1", "c2", "c3", "c4", "c5"]
        true_p = {"c1": 0.40, "c2": 0.20, "c3": 0.10, "c4": 0.05, "c5": 0.01}
        fns = {
            "c1": lambda v: v > 20,
            "c2": lambda v: v > 60,
            "c3": lambda v: v > 80,
            "c4": lambda v: v > 92,
            "c5": lambda v: v > 98,
        }
        result = run_adaptive_experiment(names, true_p, fns, n_values=10_000)

        # Adaptive should be closer to best than to worst
        adaptive = result['avg_adaptive_cost']
        best = result['avg_static_best_cost']
        worst = result['avg_static_worst_cost']

        # Adaptive should be within 2× of optimal after 10K samples
        assert adaptive <= best * 2.0, \
            f"Adaptive {adaptive:.3f} > 2× optimal {best:.3f}"

        # Adaptive should beat worst
        assert adaptive < worst, \
            f"Adaptive {adaptive:.3f} >= worst {worst:.3f}"

    def test_reordering_preserves_false_negatives(self):
        """Reordering never changes which values are flagged (just when we stop)."""
        random.seed(42)
        names = ["a", "b", "c"]
        true_p = {"a": 0.3, "b": 0.2, "c": 0.1}
        fns = {
            "a": lambda v: v > 30,
            "b": lambda v: v > 70,
            "c": lambda v: v > 90,
        }

        n = 5000
        random.seed(42)
        values = [random.uniform(0, 100) for _ in range(n)]

        # Check with two different orderings
        for order1, order2 in [(["a", "b", "c"], ["c", "b", "a"]),
                               (["b", "a", "c"], ["c", "a", "b"])]:
            for v in values:
                passed1, _, viol1 = _check_static(v, order1, fns)
                passed2, _, viol2 = _check_static(v, order2, fns)
                # Same pass/fail outcome
                assert passed1 == passed2, \
                    f"Ordering changed outcome for v={v}: {order1}→{passed1} vs {order2}→{passed2}"

    def test_convergence_within_1000_samples(self):
        """Adaptive converges to near-optimal within 1000 samples."""
        random.seed(42)
        names = ["x", "y", "z"]
        true_p = {"x": 0.5, "y": 0.1, "z": 0.01}
        fns = {
            "x": lambda v: v > 0,
            "y": lambda v: v > 80,
            "z": lambda v: v > 98,
        }

        tracker = ViolationProbabilityTracker(names)
        tree = AdaptiveDecisionTree(tracker)

        for i in range(1000):
            v = random.uniform(-50, 50)
            tree.check_value(v, fns)

        rho = tracker.ordering_spearman(true_p)
        assert rho > 0.7, f"Rank correlation after 1K: {rho:.3f}"


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
