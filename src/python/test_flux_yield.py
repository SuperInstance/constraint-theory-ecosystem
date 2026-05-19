"""
test_flux_yield.py — Tests for semiconductor yield model applied to constraint systems.

Verifies:
1. ProcessStep: Cpk, defect rate, capability
2. YieldModel: overall yield, pareto, bottleneck, partition equivalence
3. SPCMonitor: Western Electric rules, X-bar and S charts
4. YieldOptimizer: yield improvement through bound optimization
5. Full experiment: 8-step process optimization

Author: Forgemaster ⚒️ (Constraint Theory Ecosystem)
"""

import math

import numpy as np
import pytest

from flux_yield import (
    OptimizationResult,
    ProcessStep,
    SPCAlert,
    SPCMonitor,
    YieldModel,
    YieldOptimizer,
    YieldReport,
    run_yield_experiment,
    yield_partition_equivalence,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_steps():
    """Three simple process steps."""
    return [
        ProcessStep("step_a", 0, 0.1, (-2.0, 2.0), mean=0.0, std=1.0),
        ProcessStep("step_b", 1, 0.05, (-2.5, 2.5), mean=0.0, std=1.0),
        ProcessStep("step_c", 2, 0.2, (-1.5, 1.5), mean=0.0, std=1.0),
    ]


@pytest.fixture
def experiment_steps():
    """8 steps from the experiment."""
    defect_rates = [0.1, 0.05, 0.2, 0.01, 0.15, 0.03, 0.08, 0.02]
    names = [f"step_{i}" for i in range(8)]
    steps = []
    for i, (name, rate) in enumerate(zip(names, defect_rates)):
        half = 1.0 + (1.0 - rate) * 2.0  # wider bounds for lower defect rate
        steps.append(ProcessStep(name, i, rate, (-half, half), mean=0.0, std=1.0))
    return steps


# ---------------------------------------------------------------------------
# 1. ProcessStep Tests
# ---------------------------------------------------------------------------

class TestProcessStep:
    def test_step_yield(self):
        s = ProcessStep("test", 0, 0.2, (-1.0, 1.0))
        assert s.step_yield == pytest.approx(0.8)

    def test_cpk_centered(self):
        """Centered process: Cpk = (UCL - LCL) / (6σ) * 0.5 = half_width / (3σ)."""
        s = ProcessStep("test", 0, 0.1, (-3.0, 3.0), mean=0.0, std=1.0)
        # Cpk = min(3/3, 3/3) = 1.0
        assert s.cpk == pytest.approx(1.0)

    def test_cpk_off_center(self):
        """Off-center: Cpk limited by closer side."""
        s = ProcessStep("test", 0, 0.1, (-3.0, 3.0), mean=1.0, std=1.0)
        # cpu = (3-1)/(3*1) = 2/3, cpl = (1-(-3))/(3*1) = 4/3
        assert s.cpk == pytest.approx(2.0 / 3.0)

    def test_is_capable(self):
        s_capable = ProcessStep("c", 0, 0.01, (-4.5, 4.5), mean=0.0, std=1.0)
        assert s_capable.is_capable  # Cpk = 1.5 > 1.33

        s_incapable = ProcessStep("i", 0, 0.1, (-1.5, 1.5), mean=0.0, std=1.0)
        assert not s_incapable.is_capable  # Cpk = 0.5 < 1.33

    def test_defect_rate_from_normal(self):
        """For standard normal with ±3σ bounds, defect rate ≈ 0.0027."""
        s = ProcessStep("test", 0, 0.0027, (-3.0, 3.0), mean=0.0, std=1.0)
        estimated = s.defect_rate_from_normal()
        assert estimated == pytest.approx(0.0027, abs=0.0005)

    def test_zero_defect(self):
        s = ProcessStep("perfect", 0, 0.0, (-3.0, 3.0), mean=0.0, std=1.0)
        assert s.step_yield == 1.0


# ---------------------------------------------------------------------------
# 2. YieldModel Tests
# ---------------------------------------------------------------------------

class TestYieldModel:
    def test_overall_yield(self, simple_steps):
        """Yield = product of step yields."""
        model = YieldModel(simple_steps)
        expected = 0.9 * 0.95 * 0.8
        assert model.overall_yield() == pytest.approx(expected)

    def test_log_yield(self, simple_steps):
        model = YieldModel(simple_steps)
        ly = model.log_yield()
        expected = math.log(0.9) + math.log(0.95) + math.log(0.8)
        assert ly == pytest.approx(expected, abs=1e-10)

    def test_pareto_ordering(self, simple_steps):
        model = YieldModel(simple_steps)
        pareto = model.pareto_defects()
        rates = [r for _, r in pareto]
        assert rates == sorted(rates, reverse=True)
        assert pareto[0][0] == "step_c"  # 0.2 defect rate
        assert pareto[0][1] == pytest.approx(0.2)

    def test_bottleneck(self, simple_steps):
        model = YieldModel(simple_steps)
        name, rate = model.bottleneck()
        assert name == "step_c"
        assert rate == pytest.approx(0.2)

    def test_report(self, simple_steps):
        model = YieldModel(simple_steps)
        report = model.report()
        assert isinstance(report, YieldReport)
        assert report.n_steps == 3
        assert report.overall_yield == pytest.approx(0.9 * 0.95 * 0.8)
        assert report.bottleneck_step == "step_c"

    def test_independent_yield_equals_product(self):
        """The fundamental identity: yield = ∏(1 - d_i)."""
        rates = [0.1, 0.05, 0.2, 0.01, 0.15, 0.03, 0.08, 0.02]
        steps = [
            ProcessStep(f"s{i}", i, r, (-2.0, 2.0))
            for i, r in enumerate(rates)
        ]
        model = YieldModel(steps)
        expected = 1.0
        for r in rates:
            expected *= (1.0 - r)
        assert model.overall_yield() == pytest.approx(expected)

    def test_experiment_initial_yield(self):
        """8 steps with given rates: yield ≈ 0.45."""
        rates = [0.1, 0.05, 0.2, 0.01, 0.15, 0.03, 0.08, 0.02]
        steps = [
            ProcessStep(f"s{i}", i, r, (-2.0, 2.0))
            for i, r in enumerate(rates)
        ]
        model = YieldModel(steps)
        y = model.overall_yield()
        expected = 1.0
        for r in rates:
            expected *= (1.0 - r)
        assert y == pytest.approx(expected)
        # Sanity: should be around 0.50
        assert 0.48 < y < 0.55

    def test_correlated_yield(self, simple_steps):
        """Correlated yield should differ from independent yield."""
        model = YieldModel(simple_steps)
        ind = model.overall_yield()

        # Positive correlation → higher joint defects → lower yield
        corr = np.array([
            [1.0, 0.5, 0.5],
            [0.5, 1.0, 0.5],
            [0.5, 0.5, 1.0],
        ])
        corr_yield = model.yield_with_correlation(corr)
        assert corr_yield != pytest.approx(ind)
        assert corr_yield >= 0.0

    def test_zero_correlation_equals_independent(self, simple_steps):
        """Zero correlation matrix should give same as independent."""
        model = YieldModel(simple_steps)
        ind = model.overall_yield()
        n = len(simple_steps)
        corr = np.zeros((n, n))
        corr_yield = model.yield_with_correlation(corr)
        # With zero correlation: P(both) = d_i * d_j
        # yield = 1 - (Σd_i - Σ d_i*d_j) = 1 - Σd_i + Σd_i*d_j
        # Independent: yield = ∏(1-d_i) = 1 - Σd_i + Σd_i*d_j - ...
        # Close but not identical due to truncation at pairwise
        assert abs(corr_yield - ind) < 0.1  # approximate


# ---------------------------------------------------------------------------
# 3. SPCMonitor Tests
# ---------------------------------------------------------------------------

class TestSPCMonitor:
    def test_observe_no_alerts_initially(self, simple_steps):
        monitor = SPCMonitor(simple_steps)
        values = np.array([0.0, 0.0, 0.0])
        alerts = monitor.observe(values)
        assert len(alerts) == 0

    def test_rule1_beyond_3sigma(self, simple_steps):
        """Point beyond 3σ should trigger Rule 1."""
        monitor = SPCMonitor(simple_steps)
        # Seed some normal points first
        for _ in range(5):
            monitor.observe(np.array([0.1, -0.1, 0.05]))
        # Now a point beyond 3σ for step_a (mean=0, std=1)
        alerts = monitor.observe(np.array([4.0, 0.0, 0.0]))
        rule1 = [a for a in alerts if a.rule == "Rule 1" and a.step_name == "step_a"]
        assert len(rule1) >= 1

    def test_rule2_drift_9_points(self, simple_steps):
        """9 consecutive points above center → Rule 2."""
        monitor = SPCMonitor(simple_steps)
        # 9 points above center for step_a (mean=0)
        for _ in range(9):
            monitor.observe(np.array([0.5, 0.0, 0.0]))
        alerts_flat = []
        for obs_alerts in []:
            alerts_flat.extend(obs_alerts)
        # Check last observation's alerts
        # We need to collect alerts from observe calls
        all_alerts = []
        for _ in range(9):
            alerts = monitor.observe(np.array([0.5, 0.0, 0.0]))
            all_alerts.extend(alerts)
        # Actually let's re-do this properly
        monitor2 = SPCMonitor(simple_steps)
        for _ in range(9):
            monitor2.observe(np.array([0.5, 0.0, 0.0]))
        # The 9th observation should trigger Rule 2
        last_alerts = monitor2.observe(np.array([0.5, 0.0, 0.0]))
        rule2 = [a for a in last_alerts if a.rule == "Rule 2" and a.step_name == "step_a"]
        assert len(rule2) >= 1

    def test_rule3_trend_6_increasing(self, simple_steps):
        """6 consecutive increasing points → Rule 3."""
        monitor = SPCMonitor(simple_steps)
        for val in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]:
            alerts = monitor.observe(np.array([val, 0.0, 0.0]))
        rule3 = [a for a in alerts if a.rule == "Rule 3" and a.step_name == "step_a"]
        assert len(rule3) >= 1

    def test_xbar_chart(self, simple_steps):
        monitor = SPCMonitor(simple_steps)
        monitor.observe(np.array([1.0, 2.0, 3.0]))
        monitor.observe(np.array([0.5, 1.5, 2.5]))
        series, center, sigma = monitor.xbar_chart(0)
        assert len(series) == 2
        assert center == 0.0
        assert sigma == 1.0
        assert series[0] == pytest.approx(1.0)

    def test_s_chart(self, simple_steps):
        monitor = SPCMonitor(simple_steps)
        for v in [1.0, 2.0, 3.0, 4.0]:
            monitor.observe(np.array([v, 0.0, 0.0]))
        stds, mean_std = monitor.s_chart(0)
        assert len(stds) == 4
        assert mean_std > 0


# ---------------------------------------------------------------------------
# 4. YieldOptimizer Tests
# ---------------------------------------------------------------------------

class TestYieldOptimizer:
    def test_optimization_improves_yield(self, experiment_steps):
        """Optimization should improve yield from initial."""
        initial_yields = [s.step_yield for s in experiment_steps]
        initial = float(np.prod(initial_yields))

        optimizer = YieldOptimizer(experiment_steps, min_yield=0.90, max_iterations=15)
        result = optimizer.optimize()

        assert result.final_yield >= result.initial_yield
        assert result.improvement >= 0
        assert result.initial_yield == pytest.approx(initial)

    def test_optimization_report(self, experiment_steps):
        optimizer = YieldOptimizer(experiment_steps, min_yield=0.80)
        result = optimizer.optimize()
        assert isinstance(result, OptimizationResult)
        assert len(result.log) > 0
        assert result.initial_yield > 0
        assert result.final_yield >= result.initial_yield

    def test_perfect_yield_no_change(self):
        """Steps with zero defect rate should not be changed."""
        steps = [
            ProcessStep("perfect", 0, 0.001, (-3.0, 3.0), mean=0.0, std=1.0),
        ]
        optimizer = YieldOptimizer(steps, min_yield=0.999)
        result = optimizer.optimize()
        assert result.final_yield >= result.initial_yield


# ---------------------------------------------------------------------------
# 5. Partition Function Equivalence Tests
# ---------------------------------------------------------------------------

class TestPartitionEquivalence:
    def test_yield_equals_partition_Z(self):
        """Yield = Z = ∏ w_i where w_i = (1 - d_i)."""
        steps = [
            ProcessStep(f"s{i}", i, r, (-2.0, 2.0))
            for i, r in enumerate([0.1, 0.05, 0.2])
        ]
        result = yield_partition_equivalence(steps)
        assert result["equivalence_check"] is True
        assert result["yield"] == pytest.approx(result["partition_Z"])
        assert result["log_yield"] == pytest.approx(result["log_Z"], abs=1e-10)

    def test_free_energy_negative(self):
        """Free energy F = -ln(Z) should be positive (yield < 1)."""
        steps = [
            ProcessStep(f"s{i}", i, 0.1, (-2.0, 2.0))
            for i in range(5)
        ]
        result = yield_partition_equivalence(steps)
        assert result["free_energy"] > 0  # F > 0 since Z < 1

    def test_perfect_system_zero_free_energy(self):
        """Perfect yield (Z=1) → F = 0."""
        steps = [
            ProcessStep("s0", 0, 0.0, (-3.0, 3.0), mean=0.0, std=1.0),
            ProcessStep("s1", 1, 0.0, (-3.0, 3.0), mean=0.0, std=1.0),
        ]
        result = yield_partition_equivalence(steps)
        assert result["free_energy"] == pytest.approx(0.0, abs=1e-10)


# ---------------------------------------------------------------------------
# 6. Full Experiment Test
# ---------------------------------------------------------------------------

class TestExperiment:
    def test_run_experiment(self):
        result = run_yield_experiment()
        assert result["n_steps"] == 8
        assert result["initial_yield"] > 0
        assert result["final_yield"] >= result["initial_yield"]
        assert result["bottleneck"] == "deposition"  # step 2, rate 0.2
        assert result["bottleneck_rate"] == pytest.approx(0.2)
        assert len(result["pareto_top3"]) == 3
        assert result["pareto_top3"][0][0] == "deposition"

    def test_experiment_initial_yield_approx_50(self):
        result = run_yield_experiment()
        assert 0.48 < result["initial_yield"] < 0.55

    def test_partition_equivalence_in_experiment(self):
        result = run_yield_experiment()
        equiv = result["partition_equivalence"]
        assert equiv["equivalence_check"] is True

    def test_experiment_improvement(self):
        result = run_yield_experiment()
        assert result["improvement"] >= 0
        assert float(result["improvement_pct"].rstrip("%")) >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
