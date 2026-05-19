"""
Tests for flux_immune.py — Affinity Maturation for Constraint Bounds
"""

import numpy as np
import pytest

from flux_immune import (
    AffinityFunction,
    ClonalExpansion,
    ImmuneOptimizer,
    ImmuneStats,
    MemoryBCell,
    StandardEvolution,
    _convergence_gen,
    run_experiment,
)


# ---------------------------------------------------------------------------
# AffinityFunction
# ---------------------------------------------------------------------------

class TestAffinityFunction:
    def setup_method(self):
        """4 points in 2D: 2 valid, 2 invalid."""
        self.valid = np.array([[1.0, 1.0], [2.0, 2.0]])
        self.invalid = np.array([[5.0, 5.0], [-5.0, -5.0]])
        self.aff = AffinityFunction(self.valid, self.invalid)

    def test_perfect_bounds(self):
        bounds = [(0.0, 3.0), (0.0, 3.0)]
        a = self.aff(bounds)
        assert a == pytest.approx(1.0, abs=0.01)

    def test_terrible_bounds(self):
        bounds = [(-10.0, 10.0), (-10.0, 10.0)]
        a = self.aff(bounds)
        # Invalid points are inside, so penalty
        assert a < 1.0

    def test_empty_data(self):
        aff = AffinityFunction(
            np.array([]).reshape(0, 2),
            np.array([]).reshape(0, 2),
        )
        assert aff([(0, 1), (0, 1)]) == 0.5

    def test_affinity_range(self):
        bounds = [(0.0, 3.0), (0.0, 3.0)]
        a = self.aff(bounds)
        assert 0.0 <= a <= 1.0

    def test_fn_penalty_heavier(self):
        """False negatives hurt more than false positives."""
        aff_fn_heavy = AffinityFunction(self.valid, self.invalid, fn_weight=1.0, fp_weight=0.1)
        aff_equal = AffinityFunction(self.valid, self.invalid, fn_weight=1.0, fp_weight=1.0)
        # Bounds that let invalid in but keep valid out
        bounds = [(-10.0, 10.0), (-10.0, 10.0)]
        a1 = aff_fn_heavy(bounds)
        a2 = aff_equal(bounds)
        # With equal weights, penalty should be higher
        assert a1 >= a2

    def test_callable(self):
        """AffinityFunction is callable."""
        a = self.aff([(0, 3), (0, 3)])
        assert isinstance(a, float)


# ---------------------------------------------------------------------------
# MemoryBCell
# ---------------------------------------------------------------------------

class TestMemoryBCell:
    def test_creation(self):
        cell = MemoryBCell(bounds=[(0, 1)], affinity=0.9, generation=5, mutations=3)
        assert cell.affinity == 0.9
        assert cell.generation == 5
        assert cell.mutations == 3

    def test_age(self):
        cell = MemoryBCell(bounds=[(0, 1)], affinity=0.9, generation=3)
        assert cell.age(10) == 7
        assert cell.age(3) == 0

    def test_clone(self):
        cell = MemoryBCell(bounds=[(0, 1), (2, 3)], affinity=0.8, generation=1, mutations=5)
        clone = cell.clone()
        assert clone.bounds == cell.bounds
        assert clone.affinity == cell.affinity
        assert clone is not cell
        # Bounds list is a copy
        clone.bounds[0] = (5, 6)
        assert cell.bounds[0] == (0, 1)


# ---------------------------------------------------------------------------
# ClonalExpansion
# ---------------------------------------------------------------------------

class TestClonalExpansion:
    def test_expand_produces_offspring(self):
        elites = [
            MemoryBCell(bounds=[(0, 1), (0, 1)], affinity=0.8, generation=1),
        ]
        clonal = ClonalExpansion(n_clones=5, dims=2)
        offspring = clonal.expand(elites, generation=2)
        assert len(offspring) >= 1
        for bounds in offspring:
            assert len(bounds) == 2
            for lo, hi in bounds:
                assert lo <= hi  # valid bounds

    def test_better_affinity_more_clones(self):
        """Higher affinity should produce more clones."""
        elite_high = MemoryBCell(bounds=[(0, 1)], affinity=0.9, generation=1)
        elite_low = MemoryBCell(bounds=[(0, 1)], affinity=0.3, generation=1)
        clonal = ClonalExpansion(n_clones=20, dims=1)
        offspring_high = clonal.expand([elite_high], 2)
        offspring_low = clonal.expand([elite_low], 2)
        assert len(offspring_high) >= len(offspring_low)

    def test_mutation_preserves_validity(self):
        elites = [
            MemoryBCell(bounds=[(0.0, 1.0), (0.0, 1.0)], affinity=0.5, generation=1),
        ]
        clonal = ClonalExpansion(n_clones=50, dims=2)
        offspring = clonal.expand(elites, generation=2)
        for bounds in offspring:
            for lo, hi in bounds:
                assert lo <= hi


# ---------------------------------------------------------------------------
# ImmuneOptimizer
# ---------------------------------------------------------------------------

class TestImmuneOptimizer:
    def setup_method(self):
        np.random.seed(42)
        self.valid = np.array([[1.0, 2.0], [1.5, 2.5], [2.0, 3.0]])
        self.invalid = np.array([[10.0, 10.0], [-10.0, -10.0]])
        self.aff = AffinityFunction(self.valid, self.invalid)

    def test_initialization(self):
        opt = ImmuneOptimizer(dims=2, population_size=10, affinity_fn=self.aff)
        assert len(opt.population) == 10
        assert len(opt.affinities) == 10
        assert len(opt.memory) == 0

    def test_step_advances_generation(self):
        opt = ImmuneOptimizer(dims=2, population_size=10, affinity_fn=self.aff)
        stats = opt.step()
        assert stats.generation == 1
        assert stats.best_affinity >= 0
        assert stats.mean_affinity >= 0

    def test_run_improves(self):
        opt = ImmuneOptimizer(
            dims=2, population_size=20, affinity_fn=self.aff,
            init_bounds=[(-5, 5), (-5, 5)], init_spread=2.0,
        )
        initial_best = max(opt.affinities)
        opt.run(generations=50)
        _, final_best = opt.best
        assert final_best >= initial_best

    def test_memory_populates(self):
        opt = ImmuneOptimizer(
            dims=2, population_size=20, memory_size=3, affinity_fn=self.aff,
            init_bounds=[(-5, 5), (-5, 5)], init_spread=2.0,
        )
        opt.run(generations=20)
        assert len(opt.memory) >= 1
        assert all(isinstance(c, MemoryBCell) for c in opt.memory)

    def test_mutation_rate_adapts(self):
        opt = ImmuneOptimizer(dims=2, mu_max=0.5)
        # Quadratic + floor: μ(a) = μ_max * (1-a)² + μ_floor
        # μ_floor = 0.05
        assert opt.mutation_rate(0.0) == pytest.approx(0.55)  # far → max + floor
        assert opt.mutation_rate(1.0) == pytest.approx(0.05)  # at optimal → floor only
        assert opt.mutation_rate(0.5) == pytest.approx(0.175) # halfway → (0.5*0.25)+0.05
        # Monotonically decreasing
        assert opt.mutation_rate(0.0) > opt.mutation_rate(0.5) > opt.mutation_rate(1.0)

    def test_best_returns_tuple(self):
        opt = ImmuneOptimizer(dims=2, population_size=10, affinity_fn=self.aff)
        bounds, aff = opt.best
        assert len(bounds) == 2
        assert 0 <= aff <= 1

    def test_history_length(self):
        opt = ImmuneOptimizer(dims=2, population_size=10, affinity_fn=self.aff)
        opt.run(generations=10)
        assert len(opt.history) == 10


# ---------------------------------------------------------------------------
# StandardEvolution
# ---------------------------------------------------------------------------

class TestStandardEvolution:
    def setup_method(self):
        np.random.seed(42)
        self.valid = np.array([[1.0, 2.0], [1.5, 2.5], [2.0, 3.0]])
        self.invalid = np.array([[10.0, 10.0], [-10.0, -10.0]])
        self.aff = AffinityFunction(self.valid, self.invalid)

    def test_step(self):
        evo = StandardEvolution(dims=2, population_size=10, affinity_fn=self.aff)
        stats = evo.step()
        assert stats.generation == 1
        assert stats.memory_size == 0  # no memory
        assert stats.mean_mutation_rate == 0.25  # fixed

    def test_run_improves(self):
        evo = StandardEvolution(
            dims=2, population_size=20, affinity_fn=self.aff,
            init_bounds=[(-5, 5), (-5, 5)], init_spread=2.0,
        )
        initial_best = max(evo.affinities)
        evo.run(generations=50)
        _, final_best = evo.best
        assert final_best >= initial_best


# ---------------------------------------------------------------------------
# Experiment Comparison
# ---------------------------------------------------------------------------

class TestExperiment:
    def test_run_experiment_returns_results(self):
        results = run_experiment(
            dims=4, generations=30, n_valid=50, n_invalid=20,
            seed=42, verbose=False,
        )
        assert "immune_best_affinity" in results
        assert "std_best_affinity" in results
        assert "advantage" in results
        assert "target" in results
        assert len(results["target"]) == 4

    def test_both_converge_something(self):
        results = run_experiment(
            dims=4, generations=50, n_valid=100, n_invalid=50,
            seed=42, verbose=False,
        )
        assert results["immune_best_affinity"] > 0.5
        assert results["std_best_affinity"] > 0.3

    def test_deterministic_with_seed(self):
        r1 = run_experiment(dims=3, generations=20, seed=123, verbose=False)
        r2 = run_experiment(dims=3, generations=20, seed=123, verbose=False)
        assert r1["immune_best_affinity"] == r2["immune_best_affinity"]
        assert r1["std_best_affinity"] == r2["std_best_affinity"]


# ---------------------------------------------------------------------------
# Convergence Generation
# ---------------------------------------------------------------------------

class TestConvergence:
    def test_convergence_found(self):
        history = [
            ImmuneStats(generation=1, best_affinity=0.5, mean_affinity=0.3,
                        worst_affinity=0.1, memory_size=1, mean_mutation_rate=0.3),
            ImmuneStats(generation=2, best_affinity=0.92, mean_affinity=0.7,
                        worst_affinity=0.4, memory_size=2, mean_mutation_rate=0.2),
        ]
        assert _convergence_gen(history, threshold=0.9) == 2

    def test_convergence_not_found(self):
        history = [
            ImmuneStats(generation=1, best_affinity=0.5, mean_affinity=0.3,
                        worst_affinity=0.1, memory_size=1, mean_mutation_rate=0.3),
        ]
        assert _convergence_gen(history, threshold=0.9) == -1
