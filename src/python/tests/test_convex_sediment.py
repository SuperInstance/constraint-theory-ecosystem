"""
tests/test_convex_sediment.py — Tests for H2+H4 connected theorems

Forgemaster ⚒️ — 2026-05-19
"""

import numpy as np
import pytest

from flux_convex_sediment import (
    ConvexFeasibleRegion,
    SedimentExtremePointBuilder,
    SubmodularPartitionFunction,
    run_connected_experiment,
    run_all_theorems,
)


# ============================================================================
# Helpers
# ============================================================================

def box2d(lo=0.0, hi=4.0):
    return ConvexFeasibleRegion(
        lo=np.array([lo, lo]),
        hi=np.array([hi, hi]),
    )


# ============================================================================
# ConvexFeasibleRegion Tests
# ============================================================================

class TestConvexFeasibleRegion:
    
    def test_inside_box(self):
        r = box2d(0, 4)
        assert r.contains(np.array([1.0, 1.0])) is True
        assert r.contains(np.array([2.0, 3.9])) is True
    
    def test_outside_box(self):
        r = box2d(0, 4)
        assert r.contains(np.array([-1.0, 2.0])) is False
        assert r.contains(np.array([5.0, 2.0])) is False
    
    def test_hyperplane_removes_points(self):
        r = box2d(0, 4)
        # Add hyperplane x + y <= 3 (cuts off corner)
        r.add_supporting_hyperplane(np.array([1.0, 1.0]) / np.sqrt(2), np.array([2.0, 1.0]))
        # Point in cut-off corner should now be excluded
        assert r.contains(np.array([3.5, 3.5])) is False
        # Point well inside should still be included
        assert r.contains(np.array([1.0, 1.0])) is True
    
    def test_volume_decreases_with_hyperplanes(self):
        r = box2d(0, 4)
        vol_before = r.estimate_volume(n_samples=100000)
        
        r.add_supporting_hyperplane(np.array([1.0, 1.0]) / np.sqrt(2), np.array([2.5, 2.5]))
        vol_after = r.estimate_volume(n_samples=100000)
        
        assert vol_after < vol_before, f"Volume should decrease: {vol_before} -> {vol_after}"
    
    def test_convexity_preserved_with_hyperplanes(self):
        """Adding half-plane constraints preserves convexity."""
        r = box2d(0, 4)
        assert r.is_convex() is True
        
        # Add several hyperplanes
        for angle in [0.3, 1.2, 2.5, 4.0]:
            direction = np.array([np.cos(angle), np.sin(angle)])
            r.add_supporting_hyperplane(direction, np.array([3.0, 3.0]))
        
        assert r.is_convex() is True, "Convexity must be preserved after adding half-planes"
    
    def test_classify_batch_matches_individual(self):
        r = box2d(0, 4)
        r.add_supporting_hyperplane(np.array([1.0, 0.5]), np.array([3.0, 2.0]))
        
        points = np.random.uniform(0, 4, size=(100, 2))
        batch = r.classify_batch(points)
        individual = np.array([r.contains(p) for p in points])
        np.testing.assert_array_equal(batch, individual)


# ============================================================================
# Theorem 1: Sediment = Extreme Points
# ============================================================================

class TestTheorem1SedimentExtremePoints:
    
    def test_volume_monotonically_decreases(self):
        """After each sediment layer, feasible volume must not increase."""
        lo = np.array([0.0, 0.0])
        hi = np.array([4.0, 4.0])
        
        truth = [
            (np.array([1.0, 1.0]) / np.sqrt(2), 3.0),
            (np.array([-1.0, 0.5]) / np.sqrt(1.25), 0.5),
        ]
        
        builder = SedimentExtremePointBuilder(lo, hi, seed=42)
        builder.set_ground_truth(truth)
        result = builder.run_experiment(n_points=8000, max_layers=5)
        
        assert result['volume_monotonically_decreases'], \
            f"Volumes not monotonic: {result['volumes']}"
    
    def test_convexity_preserved_every_layer(self):
        """Convexity is preserved after every sediment layer."""
        lo = np.array([0.0, 0.0])
        hi = np.array([4.0, 4.0])
        
        truth = [
            (np.array([1.0, 1.0]) / np.sqrt(2), 3.0),
            (np.array([0.5, -1.0]) / np.sqrt(1.25), 1.0),
            (np.array([-1.0, 0.5]) / np.sqrt(1.25), 0.5),
        ]
        
        builder = SedimentExtremePointBuilder(lo, hi, seed=123)
        builder.set_ground_truth(truth)
        result = builder.run_experiment(n_points=8000, max_layers=5)
        
        assert result['convexity_preserved_every_layer'], \
            "Convexity violated in some layer"
    
    def test_at_least_one_layer_added(self):
        """When ground truth is tighter than box, at least one layer gets added."""
        lo = np.array([0.0, 0.0])
        hi = np.array([4.0, 4.0])
        
        truth = [
            (np.array([1.0, 1.0]) / np.sqrt(2), 2.5),
        ]
        
        builder = SedimentExtremePointBuilder(lo, hi, seed=7)
        builder.set_ground_truth(truth)
        result = builder.run_experiment(n_points=5000, max_layers=3)
        
        assert result['n_layers'] >= 1, "Should add at least one layer"
    
    def test_final_volume_less_than_initial(self):
        """After sediment layers, feasible volume is strictly less."""
        lo = np.array([0.0, 0.0])
        hi = np.array([4.0, 4.0])
        
        truth = [
            (np.array([1.0, 1.0]) / np.sqrt(2), 2.0),
        ]
        
        builder = SedimentExtremePointBuilder(lo, hi, seed=99)
        builder.set_ground_truth(truth)
        result = builder.run_experiment(n_points=5000, max_layers=4)
        
        if result['n_layers'] > 0:
            assert result['final_volume'] < result['initial_volume'] + 1e-6


# ============================================================================
# Theorem 2: Submodular Partition Function
# ============================================================================

class TestTheorem2SubmodularPartition:
    
    def _make_spf(self, n_constraints=6, n_points=20000, seed=42):
        """Create a SubmodularPartitionFunction with half-plane constraints in 2D."""
        rng = np.random.default_rng(seed)
        
        angles = np.array([0.3, 1.0, 1.7, 2.8, 3.7, 4.8])[:n_constraints]
        normals = np.column_stack([np.cos(angles), np.sin(angles)])
        offsets = np.array([2.0, 1.8, 2.2, 1.9, 2.1, 1.7])[:n_constraints]
        
        lo = np.array([-3.0, -3.0])
        hi = np.array([3.0, 3.0])
        points = rng.uniform(lo, hi, size=(n_points, 2))
        
        # Compute masks
        masks = np.zeros(n_points, dtype=int)
        for i in range(n_constraints):
            violated = points @ normals[i] > offsets[i] + 1e-12
            masks |= (violated.astype(int) << i)
        
        # Use the SubmodularPartitionFunction class with box constraints
        # on the projected dimensions. But since our constraints are half-planes,
        # we'll directly set Z.
        
        Z = {}
        for m in masks:
            Z[m] = Z.get(m, 0) + 1
        
        # Create SPF with dummy box constraints and override Z
        spf = SubmodularPartitionFunction(
            [(lo[i], hi[i]) for i in range(2)],  # dummy, unused
            seed=seed
        )
        spf._Z = Z
        spf._log_Z = {m: np.log(max(c, 1)) for m, c in Z.items()}
        return spf
    
    def test_submodularity_no_violations(self):
        """log Z should be submodular: f(A)+f(B) >= f(A∪B)+f(A∩B)."""
        spf = self._make_spf(n_constraints=6, n_points=30000, seed=42)
        result = spf.verify_submodularity()
        
        assert result['is_submodular'], \
            f"Found {result['n_violations']} submodularity violations. " \
            f"Min gap: {result['min_gap']:.6f}"
    
    def test_submodularity_mean_gap_positive(self):
        """Mean submodularity gap should be non-negative."""
        spf = self._make_spf(n_constraints=6, n_points=30000, seed=42)
        result = spf.verify_submodularity()
        
        assert result['mean_gap'] >= -1e-10, \
            f"Mean gap should be >= 0, got {result['mean_gap']:.6f}"
    
    def test_submodularity_different_seeds(self):
        """Submodularity holds across different random seeds."""
        for seed in [42, 123, 7, 999]:
            spf = self._make_spf(n_constraints=6, n_points=20000, seed=seed)
            result = spf.verify_submodularity()
            assert result['is_submodular'], \
                f"Submodularity violated at seed={seed}: {result['n_violations']} violations"


# ============================================================================
# Connected Experiment: Sediment → Submodularity
# ============================================================================

class TestConnectedExperiment:
    
    def test_connected_runs_without_error(self):
        """The connected experiment completes without raising."""
        result = run_connected_experiment(n_constraints=6, n_points=10000, seed=42)
        assert 'stages' in result
        assert len(result['stages']) == 6
    
    def test_submodularity_gap_non_negative(self):
        """Mean submodularity gap is non-negative at each stage."""
        result = run_connected_experiment(n_constraints=6, n_points=10000, seed=42)
        for stage in result['stages']:
            assert stage['mean_submodularity_gap'] >= -1e-6, \
                f"Stage {stage['layer']}: negative gap {stage['mean_submodularity_gap']}"
    
    def test_feasible_fraction_decreases(self):
        """As more constraints activate, fewer points are feasible."""
        result = run_connected_experiment(n_constraints=6, n_points=10000, seed=42)
        fractions = [s['feasible_fraction'] for s in result['stages']]
        for i in range(len(fractions) - 1):
            assert fractions[i] >= fractions[i + 1] - 1e-6, \
                f"Feasible fraction not decreasing: stage {i} -> {i+1}"


# ============================================================================
# Full Integration Test
# ============================================================================

class TestFullIntegration:
    
    def test_run_all_theorems(self):
        """Full experiment pipeline runs and produces consistent results."""
        result = run_all_theorems(seed=42)
        
        # Theorem 1 checks
        t1 = result['theorem1_sediment_extreme_points']
        assert 'n_layers' in t1
        assert 'volumes' in t1
        
        # Theorem 2 checks
        t2 = result['theorem2_submodular_partition']
        assert t2['is_submodular'], f"Theorem 2 submodularity violated: {t2['n_submodularity_violations']}"
        
        # Connected checks
        conn = result['connected_experiment']
        assert len(conn['stages']) > 0
