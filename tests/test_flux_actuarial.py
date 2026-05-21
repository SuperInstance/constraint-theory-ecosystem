"""Tests for flux_actuarial — Actuarial Risk Pooling."""

import sys
sys.path.insert(0, "/home/phoenix/.openclaw/workspace/constraint-theory-ecosystem/src/python")

from flux_actuarial import (
    ActuarialChecker, Constraint, RiskPool, Premium, RiskTier,
    GammaPoissonModel, PremiumCalculator, CheckResult,
)

import pytest


# ---------------------------------------------------------------------------
# Constraint tests
# ---------------------------------------------------------------------------

class TestConstraint:
    def test_pass(self):
        c = Constraint("range", lambda v: 0 <= v <= 100)
        assert c.check(50)

    def test_fail(self):
        c = Constraint("range", lambda v: 0 <= v <= 100)
        assert not c.check(-1)

    def test_exception_is_fail(self):
        c = Constraint("type_check", lambda v: v > 0)
        assert not c.check("not_a_number")

    def test_severity_weight(self):
        c = Constraint("critical", lambda v: v > 0, severity=10.0)
        assert c.severity == 10.0


# ---------------------------------------------------------------------------
# Gamma-Poisson Model tests
# ---------------------------------------------------------------------------

class TestGammaPoissonModel:
    def test_posterior_mean_prior_only(self):
        # With no data, posterior mean = prior mean
        mean = GammaPoissonModel.posterior_mean(1.0, 100.0, 0, 0)
        assert abs(mean - 0.01) < 1e-10

    def test_posterior_mean_with_data(self):
        # 5 violations in 100 checks → rate should be ~0.05
        mean = GammaPoissonModel.posterior_mean(1.0, 100.0, 5.0, 100.0)
        expected = (1.0 + 5.0) / (100.0 + 100.0)
        assert abs(mean - expected) < 1e-10

    def test_posterior_variance(self):
        var = GammaPoissonModel.posterior_variance(1.0, 100.0, 5.0, 100.0)
        assert var > 0

    def test_credible_interval(self):
        lo, hi = GammaPoissonModel.credible_interval(1.0, 100.0, 5.0, 100.0)
        assert lo >= 0
        assert hi > lo

    def test_risk_classification(self):
        assert GammaPoissonModel.classify_risk(0.01, 0.05, 0.02) == RiskTier.LOW
        assert GammaPoissonModel.classify_risk(0.05, 0.05, 0.02) == RiskTier.STANDARD
        assert GammaPoissonModel.classify_risk(0.15, 0.05, 0.02) == RiskTier.ELEVATED
        assert GammaPoissonModel.classify_risk(0.25, 0.05, 0.02) == RiskTier.HIGH
        assert GammaPoissonModel.classify_risk(0.50, 0.05, 0.02) == RiskTier.CRITICAL


# ---------------------------------------------------------------------------
# Risk Pool tests
# ---------------------------------------------------------------------------

class TestRiskPool:
    def test_creation(self):
        pool = RiskPool(pool_id="test")
        assert pool.pool_id == "test"
        assert pool.source_count == 0

    def test_violation_rate(self):
        pool = RiskPool(pool_id="test", alpha=1.0, beta=100.0)
        assert abs(pool.pool_violation_rate - 0.01) < 1e-10

    def test_update(self):
        pool = RiskPool(pool_id="test", alpha=1.0, beta=100.0)
        pool.update(True)   # pass
        pool.update(False)  # violation
        pool.update(False)  # violation
        assert pool.total_pool_checks == 3
        assert pool.total_pool_violations == 2


# ---------------------------------------------------------------------------
# Premium Calculator tests
# ---------------------------------------------------------------------------

class TestPremiumCalculator:
    def test_calculate_initial(self):
        calc = PremiumCalculator()
        pool = RiskPool(pool_id="test", alpha=1.0, beta=100.0)
        premium = calc.calculate("s1", pool, 0.0, 0.0)
        assert premium.source_id == "s1"
        assert premium.pool_id == "test"
        assert premium.risk_tier == RiskTier.STANDARD

    def test_high_violation_source(self):
        calc = PremiumCalculator()
        pool = RiskPool(pool_id="test", alpha=5.0, beta=100.0)
        pool.update(True)
        pool.update(False)
        pool.update(False)
        # Source with many violations
        premium = calc.calculate("bad_sensor", pool, 50.0, 100.0)
        assert premium.final_premium > 0.5  # Should be checked frequently

    def test_tier_floor(self):
        """Every tier has a minimum checking probability."""
        calc = PremiumCalculator()
        pool = RiskPool(pool_id="test", alpha=0.01, beta=10000.0)
        premium = calc.calculate("good_sensor", pool, 0.0, 1000.0)
        # Even very low risk sources have a floor
        assert premium.final_premium >= 0.01


# ---------------------------------------------------------------------------
# Actuarial Checker integration tests
# ---------------------------------------------------------------------------

class TestActuarialChecker:
    def _make_checker(self):
        ac = ActuarialChecker()
        ac.create_pool("sensors", constraints=[
            Constraint("range", lambda v: 0 <= v <= 100),
            Constraint("positive", lambda v: v > 0),
        ])
        for i in range(10):
            ac.register_source(f"s{i}", pool_id="sensors")
        return ac

    def test_create_pool(self):
        ac = ActuarialChecker()
        pool = ac.create_pool("test_pool")
        assert "test_pool" in ac.pools

    def test_register_source(self):
        ac = ActuarialChecker()
        ac.create_pool("sensors")
        premium = ac.register_source("s1", pool_id="sensors")
        assert premium.source_id == "s1"

    def test_register_unknown_pool_raises(self):
        ac = ActuarialChecker()
        with pytest.raises(ValueError):
            ac.register_source("s1", pool_id="nonexistent")

    def test_check_pass(self):
        ac = self._make_checker()
        # Run enough checks that at least some get through premium gate
        passed = 0
        for _ in range(100):
            result = ac.check("s0", 50)
            if result.checked and result.passed:
                passed += 1
        assert passed > 0

    def test_check_fail(self):
        ac = self._make_checker()
        failed = 0
        for _ in range(100):
            result = ac.check("s0", -1)
            if result.checked and not result.passed:
                failed += 1
        assert failed > 0

    def test_premium_adapts(self):
        """High-violation sources should get higher premiums over time."""
        ac = ActuarialChecker()
        ac.create_pool("sensors", constraints=[
            Constraint("range", lambda v: 0 <= v <= 100),
        ])
        ac.register_source("good_sensor", pool_id="sensors")
        ac.register_source("bad_sensor", pool_id="sensors")

        # Feed violations to bad_sensor, passes to good_sensor
        for _ in range(50):
            ac.check("good_sensor", 50)   # always passes
        for _ in range(50):
            ac.check("bad_sensor", -1)     # always fails

        # Force rebalance
        ac.rebalance_pool("sensors")

        good_premium = ac.get_premium("good_sensor")
        bad_premium = ac.get_premium("bad_sensor")
        # Bad sensor should have higher premium
        assert bad_premium.final_premium >= good_premium.final_premium

    def test_rebalance_pool(self):
        ac = self._make_checker()
        report = ac.rebalance_pool("sensors")
        assert report.source_count == 10
        assert report.pool_violation_rate >= 0

    def test_efficiency_stats(self):
        ac = self._make_checker()
        stats = ac.efficiency_stats()
        assert stats["total_sources"] == 10
        assert "checks_saved_pct" in stats

    def test_unknown_source_raises(self):
        ac = ActuarialChecker()
        ac.create_pool("sensors")
        with pytest.raises(ValueError):
            ac.check("unknown", 50)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
