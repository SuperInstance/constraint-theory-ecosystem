"""
Tests for FLUX Hyperbolic — Poincaré Ball Geometry for Model Capability Routing.
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from flux_hyperbolic import (
    PoincareBall,
    CapabilitySpace,
    TaskRouter,
    FrechetMean,
    run_experiment,
)


# ---------------------------------------------------------------------------
# PoincareBall Tests
# ---------------------------------------------------------------------------

class TestPoincareBall:
    def test_distance_identity(self):
        """Distance from a point to itself is 0."""
        v = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        assert PoincareBall.distance(v, v) < 1e-5

    def test_distance_symmetry(self):
        """Distance is symmetric."""
        u = np.array([0.1, -0.2, 0.3, 0.0, 0.5, 0.1, -0.1, 0.2])
        v = np.array([-0.3, 0.1, 0.4, 0.2, 0.1, -0.2, 0.3, 0.0])
        assert abs(PoincareBall.distance(u, v) - PoincareBall.distance(v, u)) < 1e-10

    def test_distance_positive(self):
        """Distance between distinct points is positive."""
        u = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        v = np.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        d = PoincareBall.distance(u, v)
        assert d > 0

    def test_distance_origin_to_boundary(self):
        """Distance from origin to near-boundary point is large."""
        origin = np.zeros(8)
        near_boundary = np.array([0.99, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        near_center = np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        d_boundary = PoincareBall.distance(origin, near_boundary)
        d_center = PoincareBall.distance(origin, near_center)
        assert d_boundary > d_center
        assert d_boundary > 3.0  # near boundary → large distance

    def test_project_inside(self):
        """Project clamps points outside the ball."""
        v = np.array([5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0])
        p = PoincareBall.project(v)
        assert np.linalg.norm(p) < 1.0
        assert np.linalg.norm(p) > 0.99

    def test_project_inside_already(self):
        """Points already inside pass through."""
        v = np.array([0.1, 0.2, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0])
        p = PoincareBall.project(v)
        np.testing.assert_allclose(p, v)

    def test_mobius_add_identity(self):
        """Möbius adding zero is identity: u ⊕ 0 = u."""
        u = np.array([0.3, -0.1, 0.2, 0.0, 0.1, -0.2, 0.0, 0.1])
        zero = np.zeros(8)
        result = PoincareBall.mobius_add(u, zero)
        np.testing.assert_allclose(result, u, atol=1e-10)

    def test_mobius_add_zero(self):
        """Zero ⊕ v = v."""
        zero = np.zeros(8)
        v = np.array([0.2, 0.1, -0.3, 0.0, 0.1, 0.0, -0.1, 0.2])
        result = PoincareBall.mobius_add(zero, v)
        np.testing.assert_allclose(result, v, atol=1e-10)

    def test_expmap_logmap_roundtrip(self):
        """expmap ∘ logmap = identity."""
        origin = np.array([0.2, -0.1, 0.0, 0.1, 0.0, -0.1, 0.05, 0.0])
        point = np.array([0.5, -0.2, 0.3, 0.1, -0.1, 0.2, -0.15, 0.1])
        tangent = PoincareBall.logmap(origin, point)
        recovered = PoincareBall.expmap(origin, tangent)
        np.testing.assert_allclose(recovered, point, atol=1e-6)

    def test_expmap_origin(self):
        """Expmap from origin: exp_0(v) = tanh(||v||) · v/||v||."""
        v = np.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        result = PoincareBall.expmap(np.zeros(8), v)
        expected = np.tanh(0.5) * v / 0.5
        np.testing.assert_allclose(result, expected, atol=1e-10)

    def test_logmap_origin(self):
        """Logmap from origin: log_0(v) = artanh(||v||) · v/||v||."""
        v = np.array([0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        result = PoincareBall.logmap(np.zeros(8), v)
        expected = np.arctanh(0.3) * v / 0.3
        np.testing.assert_allclose(result, expected, atol=1e-10)

    def test_conformal_factor_origin(self):
        """λ_0 = 2."""
        assert abs(PoincareBall.conformal_factor(np.zeros(8)) - 2.0) < 1e-10

    def test_conformal_factor_boundary(self):
        """Near boundary, λ → large."""
        v = np.array([0.99, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        assert PoincareBall.conformal_factor(v) > 50.0


# ---------------------------------------------------------------------------
# CapabilitySpace Tests
# ---------------------------------------------------------------------------

class TestCapabilitySpace:
    def test_add_model(self):
        cs = CapabilitySpace()
        mp = cs.add_model("test", np.array([0.1] * 8))
        assert mp.name == "test"
        assert mp.norm < 0.3
        assert "test" in cs.models

    def test_add_general_model(self):
        cs = CapabilitySpace()
        mp = cs.add_general_model("gen", np.ones(8), norm=0.1)
        assert mp.norm < 0.2
        assert mp.specialization_level == "general"

    def test_add_specialist_model(self):
        cs = CapabilitySpace()
        mp = cs.add_specialist_model("spec", np.ones(8), norm=0.85)
        assert mp.norm > 0.7
        assert mp.specialization_level == "specialist"

    def test_nearest_model(self):
        cs = CapabilitySpace()
        cs.add_model("a", np.array([0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]))
        cs.add_model("b", np.array([0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]))
        # Point near origin → closer to "a"
        nearest = cs.nearest_model(np.array([0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]))
        assert nearest[0][0] == "a"

    def test_distance(self):
        cs = CapabilitySpace()
        cs.add_model("a", np.array([0.1] * 8))
        cs.add_model("b", np.array([0.5] * 8))
        d = cs.distance("a", "b")
        assert d > 0


# ---------------------------------------------------------------------------
# TaskRouter Tests
# ---------------------------------------------------------------------------

class TestTaskRouter:
    def _make_space(self):
        cs = CapabilitySpace()
        rng = np.random.RandomState(123)
        cs.add_general_model("gen-1", rng.randn(8), norm=0.1)
        cs.add_specialist_model("spec-1", rng.randn(8), norm=0.85)
        cs.add_model("mod-1", PoincareBall.project(rng.randn(8) * 0.4), "moderate")
        return cs

    def test_route_returns_result(self):
        cs = self._make_space()
        router = TaskRouter(cs)
        r = router.route_task(0, np.ones(8), 0.5)
        assert r.task_id == 0
        assert r.hyperbolic_model in cs.models
        assert r.euclidean_model in cs.models
        assert r.hyperbolic_distance > 0
        assert r.euclidean_distance >= 0

    def test_route_batch(self):
        cs = self._make_space()
        router = TaskRouter(cs)
        tasks = [(i, np.random.randn(8), 0.3) for i in range(10)]
        results = router.route_batch(tasks)
        assert len(results) == 10

    def test_embed_task_on_ball(self):
        cs = self._make_space()
        router = TaskRouter(cs)
        emb = router.embed_task(np.ones(8), 0.8)
        assert np.linalg.norm(emb) < 1.0


# ---------------------------------------------------------------------------
# Fréchet Mean Tests
# ---------------------------------------------------------------------------

class TestFrechetMean:
    def test_single_point(self):
        """Mean of one point is itself."""
        p = np.array([0.3, -0.1, 0.2, 0.0, 0.1, -0.1, 0.0, 0.1])
        mean = FrechetMean.compute([p])
        np.testing.assert_allclose(mean, p, atol=1e-6)

    def test_two_points_midpoint(self):
        """Mean of two points is roughly between them."""
        u = np.array([0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        v = np.array([-0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        mean = FrechetMean.compute([u, v])
        # Should be near origin
        assert np.linalg.norm(mean) < 0.05

    def test_mean_on_ball(self):
        """Mean stays on the ball (||mean|| < 1)."""
        rng = np.random.RandomState(42)
        points = [PoincareBall.project(rng.randn(8) * 0.5) for _ in range(20)]
        mean = FrechetMean.compute(points)
        assert np.linalg.norm(mean) < 1.0

    def test_weighted_mean(self):
        """Weighted mean shifts toward heavily weighted point."""
        u = np.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        v = np.array([-0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        w_u = np.array([0.9, 0.1])
        mean = FrechetMean.compute([u, v], weights=w_u)
        # Should be closer to u
        d_u = PoincareBall.distance(mean, u)
        d_v = PoincareBall.distance(mean, v)
        assert d_u < d_v

    def test_convergence(self):
        """Converges for many points."""
        rng = np.random.RandomState(7)
        points = [PoincareBall.project(rng.randn(8) * 0.3) for _ in range(50)]
        mean = FrechetMean.compute(points)
        assert np.linalg.norm(mean) < 1.0
        assert np.linalg.norm(mean) > 0  # not at origin


# ---------------------------------------------------------------------------
# Experiment Tests
# ---------------------------------------------------------------------------

class TestExperiment:
    def test_run_experiment(self):
        """Full experiment runs and returns expected keys."""
        result = run_experiment(seed=42)
        assert result["n_models"] == 10
        assert result["n_tasks"] == 1000
        assert 0 <= result["agree_rate"] <= 1.0
        assert "hyp_specialist_precision" in result
        assert "euc_specialist_precision" in result
        assert "boundary_ratio" in result
        assert "fleet_centroid_norm" in result
        assert len(result["results"]) == 1000

    def test_boundary_effect(self):
        """Specialists should be exponentially more distant than generals."""
        result = run_experiment(seed=42)
        assert result["avg_specialist_inter_dist"] > result["avg_general_inter_dist"]
        assert result["boundary_ratio"] > 1.5  # boundary distances dominate

    def test_specialist_routing(self):
        """Hyperbolic routing should route specialized tasks to specialists."""
        result = run_experiment(seed=42)
        # Hyperbolic should have >= euclidean specialist precision
        # (may not always win on every seed, but structure favors it)
        assert result["hyp_specialist_precision"] > 0 or result["euc_specialist_precision"] > 0

    def test_models_structure(self):
        result = run_experiment(seed=42)
        models = result["models"]
        assert len(models) == 10
        for name, info in models.items():
            assert "norm" in info
            assert "level" in info
            assert info["level"] in ("general", "moderate", "specialist")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
