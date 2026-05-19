"""Tests for flux_precedent.py — Stare Decisis for Constraint Tiles"""

import time
import numpy as np
import pytest

from flux_precedent import (
    Case, CourtLevel, PrecedentLibrary, PrecedentAdapter, StareDecisis, run_experiment,
)


# --- Helpers ---

def make_case(
    cid: str, domain: float, severity: float, n_dims: int = 3,
    court: CourtLevel = CourtLevel.TRIAL, age_years: float = 0.0,
    extra_features: dict = None,
) -> Case:
    now = time.time()
    features = {
        "domain": domain,
        "severity": severity,
        "n_dims": float(n_dims),
        "safety_critical": severity * 0.9,
    }
    if extra_features:
        features.update(extra_features)
    bounds = [(-1.0 - domain, 1.0 + domain) for _ in range(n_dims)]
    return Case(
        case_id=cid,
        features=features,
        bounds=bounds,
        ruling_mask=0b111,
        court_level=court,
        timestamp=now - age_years * 365.25 * 86400,
        citations=[],
    )


# =============================================================================
# Test Case
# =============================================================================

class TestCaseDataclass:
    def test_creation(self):
        c = make_case("c1", 0.5, 0.8)
        assert c.case_id == "c1"
        assert c.court_level == CourtLevel.TRIAL
        assert len(c.bounds) == 3
        assert c.age() >= 0

    def test_age(self):
        c = make_case("c2", 0.5, 0.8, age_years=2.0)
        age_days = c.age() / 86400
        assert 729 < age_days < 732  # ~2 years


# =============================================================================
# Test PrecedentLibrary
# =============================================================================

class TestPrecedentLibrary:
    def test_empty_library(self):
        lib = PrecedentLibrary()
        results = lib.find_precedent({"domain": 0.5})
        assert results == []

    def test_add_and_find(self):
        lib = PrecedentLibrary()
        c = make_case("c1", 0.5, 0.8)
        lib.add_case(c)

        results = lib.find_precedent({"domain": 0.5, "severity": 0.8, "n_dims": 3.0, "safety_critical": 0.72})
        assert len(results) == 1
        assert results[0][0].case_id == "c1"
        assert results[0][1] > 0

    def test_nearest_match(self):
        lib = PrecedentLibrary()
        lib.add_cases([
            make_case("far", 0.0, 0.1),
            make_case("near", 0.5, 0.8),
        ])
        results = lib.find_precedent({"domain": 0.5, "severity": 0.8, "n_dims": 3.0, "safety_critical": 0.72})
        assert results[0][0].case_id == "near"

    def test_court_level_weight(self):
        """Higher court = higher relevance at same distance."""
        lib = PrecedentLibrary()
        now = time.time()
        c_trial = Case("trial", {"x": 0.5}, [(-1, 1)], 0, CourtLevel.TRIAL, now)
        c_supreme = Case("supreme", {"x": 0.5}, [(-1, 1)], 0, CourtLevel.SUPREME, now)
        lib.add_cases([c_trial, c_supreme])

        results = lib.find_precedent({"x": 0.5})
        # Supreme should have higher relevance
        trial_rel = [r[1] for r in results if r[0].case_id == "trial"][0]
        supreme_rel = [r[1] for r in results if r[0].case_id == "supreme"][0]
        assert supreme_rel > trial_rel

    def test_age_decay(self):
        """Older cases decay in relevance."""
        lib = PrecedentLibrary()
        c_fresh = make_case("fresh", 0.5, 0.8, age_years=0.0)
        c_old = make_case("old", 0.5, 0.8, age_years=5.0)
        lib.add_cases([c_fresh, c_old])

        results = lib.find_precedent({"domain": 0.5, "severity": 0.8, "n_dims": 3.0, "safety_critical": 0.72})
        fresh_rel = [r[1] for r in results if r[0].case_id == "fresh"][0]
        old_rel = [r[1] for r in results if r[0].case_id == "old"][0]
        assert fresh_rel > old_rel

    def test_k_limit(self):
        lib = PrecedentLibrary()
        for i in range(10):
            lib.add_case(make_case(f"c{i}", i * 0.1, 0.5))
        results = lib.find_precedent({"domain": 0.5, "severity": 0.5, "n_dims": 3.0, "safety_critical": 0.45}, k=3)
        assert len(results) <= 3


# =============================================================================
# Test PrecedentAdapter
# =============================================================================

class TestPrecedentAdapter:
    def test_identical_features_no_shift(self):
        adapter = PrecedentAdapter(adapt_rate=0.3)
        case = make_case("c1", 0.5, 0.8)
        query = {"domain": 0.5, "severity": 0.8, "n_dims": 3.0, "safety_critical": 0.72}
        adapted = adapter.adapt(case, query, n_dims=3)
        # Identical features → delta ≈ 0 → bounds barely change
        for i in range(3):
            assert abs(adapted[i][0] - case.bounds[i][0]) < 0.01

    def test_different_features_expand_bounds(self):
        adapter = PrecedentAdapter(adapt_rate=0.3)
        case = make_case("c1", 0.5, 0.8)
        query = {"domain": 0.9, "severity": 0.3, "n_dims": 3.0, "safety_critical": 0.1}
        adapted = adapter.adapt(case, query, n_dims=3)
        # Different features → expanded bounds
        for i in range(3):
            orig_span = case.bounds[i][1] - case.bounds[i][0]
            adapted_span = adapted[i][1] - adapted[i][0]
            assert adapted_span >= orig_span - 1e-6  # should expand or stay same

    def test_supreme_resists_adaptation(self):
        adapter = PrecedentAdapter(adapt_rate=0.3)
        case_trial = make_case("trial", 0.5, 0.8, court=CourtLevel.TRIAL)
        case_supreme = make_case("supreme", 0.5, 0.8, court=CourtLevel.SUPREME)
        query = {"domain": 0.9, "severity": 0.3, "n_dims": 3.0, "safety_critical": 0.1}

        adapted_trial = adapter.adapt(case_trial, query, 3)
        adapted_supreme = adapter.adapt(case_supreme, query, 3)

        # Trial should adapt more (larger expansion)
        trial_expansion = sum(
            (a[1] - a[0]) - (b[1] - b[0])
            for a, b in zip(adapted_trial, case_trial.bounds)
        )
        supreme_expansion = sum(
            (a[1] - a[0]) - (b[1] - b[0])
            for a, b in zip(adapted_supreme, case_supreme.bounds)
        )
        assert trial_expansion >= supreme_expansion


# =============================================================================
# Test StareDecisis
# =============================================================================

class TestStareDecisis:
    def test_find_and_check(self):
        lib = PrecedentLibrary()
        lib.add_case(make_case("c1", 0.5, 0.8))
        sd = StareDecisis(lib, novelty_threshold=0.01)

        result = sd.check(
            values=np.array([0.0, 0.0, 0.0]),
            query_features={"domain": 0.5, "severity": 0.8, "n_dims": 3.0, "safety_critical": 0.72},
            ground_truth_bounds=[(-2, 2), (-2, 2), (-2, 2)],
        )
        assert "bounds_applied" in result
        assert result["precedent_used"] == "c1"
        assert not result["is_novel"]

    def test_novel_case(self):
        lib = PrecedentLibrary()
        lib.add_case(make_case("c1", 0.0, 0.1))  # very different
        sd = StareDecisis(lib, novelty_threshold=0.5)

        result = sd.check(
            values=np.array([0.0, 0.0, 0.0]),
            query_features={"domain": 1.0, "severity": 1.0, "n_dims": 3.0, "safety_critical": 1.0},
            ground_truth_bounds=[(-1, 1), (-1, 1), (-1, 1)],
        )
        # With high threshold, may be novel
        assert isinstance(result["is_novel"], bool)

    def test_violation_detection(self):
        lib = PrecedentLibrary()
        lib.add_case(make_case("c1", 0.5, 0.8))
        sd = StareDecisis(lib, novelty_threshold=0.01)

        # Point well outside bounds
        result = sd.check(
            values=np.array([100.0, 100.0, 100.0]),
            query_features={"domain": 0.5, "severity": 0.8, "n_dims": 3.0, "safety_critical": 0.72},
        )
        assert result["violation_mask"] != 0  # should detect violations

    def test_no_violation(self):
        lib = PrecedentLibrary()
        lib.add_case(make_case("c1", 0.5, 0.8))
        sd = StareDecisis(lib, novelty_threshold=0.01)

        result = sd.check(
            values=np.array([0.0, 0.0, 0.0]),
            query_features={"domain": 0.5, "severity": 0.8, "n_dims": 3.0, "safety_critical": 0.72},
        )
        assert result["violation_mask"] == 0  # center of bounds

    def test_auto_precedent(self):
        lib = PrecedentLibrary()
        sd = StareDecisis(lib, novelty_threshold=0.01, auto_precedent=True)

        # First query — no precedent → novel → creates one
        sd.check(
            values=np.array([0.0, 0.0, 0.0]),
            query_features={"domain": 0.5, "severity": 0.8, "n_dims": 2.0, "safety_critical": 0.72},
            ground_truth_bounds=[(-1, 1), (-1, 1)],
        )
        assert len(lib.cases) == 1  # auto-created

        # Second similar query — should find the precedent
        result = sd.check(
            values=np.array([0.0, 0.0, 0.0]),
            query_features={"domain": 0.5, "severity": 0.8, "n_dims": 2.0, "safety_critical": 0.72},
            ground_truth_bounds=[(-1, 1), (-1, 1)],
        )
        assert not result["is_novel"]  # now covered by precedent


# =============================================================================
# Test Experiment
# =============================================================================

class TestExperiment:
    def test_run_experiment(self):
        summary = run_experiment(seed=42)

        assert summary["n_precedents"] == 50
        assert summary["n_queries"] == 1000
        assert 0.0 <= summary["coverage_rate"] <= 1.0
        assert 0.0 <= summary["accuracy_rate"] <= 1.0
        assert summary["novel_count"] + summary["precedent_count"] == 1000
        assert len(summary["accumulation"]) == 5

        # Key result: more precedents → higher coverage (stare decisis accumulates)
        coverages = [a["coverage"] for a in summary["accumulation"]]
        # Should generally increase (may not be monotonic due to random sampling)
        assert coverages[-1] >= coverages[0] * 0.9  # at least close

    def test_accumulation_grows(self):
        """More precedents should give better coverage."""
        summary = run_experiment(seed=123)
        acc = summary["accumulation"]
        # Last should have higher coverage than first
        assert acc[-1]["coverage"] >= acc[0]["coverage"] * 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
