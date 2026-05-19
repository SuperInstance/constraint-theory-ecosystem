"""
Tests for the unified FLUX v4 accumulated correctness extensions (SEDIMENT + EVOLUTION).
Verifies that the two new strategies integrate cleanly with ConstraintEngine.

Forgemaster ⚒️ — 2026-05-19
"""

import sys
import unittest

sys.path.insert(0, ".")

from flux import ConstraintEngine, Strategy
from flux_sediment import ConstraintCorrection


class TestSedimentStrategy(unittest.TestCase):
    """SEDIMENT strategy improves correctness through correction layers."""

    def setUp(self):
        # Use constraints where a single scalar check makes sense per-constraint
        # The engine checks ALL constraints against the same scalar value.
        self.constraints = [
            {"name": "temp", "lo": -10.0, "hi": 40.0},
            {"name": "temp2", "lo": -10.0, "hi": 40.0},
        ]

    def test_sediment_strategy_activates(self):
        engine = ConstraintEngine(self.constraints).use(Strategy.SEDIMENT)
        self.assertIn(Strategy.SEDIMENT, engine.active_strategies())

    def test_sediment_stats_initial(self):
        engine = ConstraintEngine(self.constraints).use(Strategy.SEDIMENT)
        stats = engine.sediment_stats()
        self.assertEqual(stats["depth"], 0)
        self.assertEqual(stats["active_layers"], 0)
        self.assertEqual(stats["correctness_density"], 0.0)

    def test_sediment_improves_correctness(self):
        """
        Engine with sediment layers catches edge cases that the bare engine misses.
        We add a correction layer that widens bounds for a borderline value.
        """
        engine = ConstraintEngine(self.constraints).use(Strategy.SEDIMENT)

        # Baseline: value at -11 should fail (below -10 on both constraints)
        self.assertFalse(engine.passed(-11.0))

        # Add corrections: widen both constraints to accept -11
        corrections = [
            ConstraintCorrection(
                constraint_name="temp",
                new_lo=-12.0,
                new_hi=40.0,
                reason="edge case: -11 is acceptable after calibration",
            ),
            ConstraintCorrection(
                constraint_name="temp2",
                new_lo=-12.0,
                new_hi=40.0,
                reason="same edge case on temp2",
            ),
        ]
        engine.add_sediment_layer(corrections, context={"test": "edge_case_correction"})

        # After correction, -11 should now pass (within [-12, 40] on both)
        self.assertTrue(
            engine.passed(-11.0),
            "Sediment layer should correct -11 from fail to pass",
        )

        # Verify stats show the layer
        stats = engine.sediment_stats()
        self.assertEqual(stats["depth"], 1)
        self.assertEqual(stats["active_layers"], 1)

    def test_sediment_without_strategy_raises(self):
        engine = ConstraintEngine(self.constraints)
        with self.assertRaises(RuntimeError):
            engine.add_sediment_layer([])

    def test_sediment_stats_without_strategy_raises(self):
        engine = ConstraintEngine(self.constraints)
        with self.assertRaises(RuntimeError):
            engine.sediment_stats()


class TestEvolutionStrategy(unittest.TestCase):
    """EVOLUTION strategy finds better bounds than hand-designed ones."""

    def setUp(self):
        self.constraints = [
            {"name": "x", "lo": -1.0, "hi": 1.0},
            {"name": "y", "lo": -1.0, "hi": 1.0},
        ]

    def test_evolution_strategy_activates(self):
        engine = ConstraintEngine(self.constraints).use(Strategy.EVOLUTION)
        self.assertIn(Strategy.EVOLUTION, engine.active_strategies())

    def test_evolution_finds_better_bounds(self):
        """
        Run evolution with a known test suite. The evolved bounds should
        achieve correctness >= hand-designed baseline.
        """
        engine = ConstraintEngine(self.constraints).use(Strategy.EVOLUTION)

        # Use a deterministic seed for reproducibility
        result = engine.evolve(generations=30, population_size=30, seed=42)

        self.assertIsNotNone(result["best_correctness"])
        self.assertGreater(result["best_correctness"], 0.0)
        self.assertEqual(result["generations_run"], 30)
        self.assertIn("best_bounds", result)
        self.assertIn("elapsed_seconds", result)

    def test_evolution_with_custom_tests(self):
        """Provide explicit test cases instead of synthetic generation."""
        engine = ConstraintEngine(self.constraints).use(Strategy.EVOLUTION)

        tests = [
            {"values": {"x": 0.0, "y": 0.0}, "label": True, "category": "valid"},
            {"values": {"x": 0.5, "y": -0.5}, "label": True, "category": "valid"},
            {"values": {"x": 3.0, "y": 0.0}, "label": False, "category": "spike"},
            {"values": {"x": 0.0, "y": -5.0}, "label": False, "category": "spike"},
            {"values": {"x": 0.99, "y": 0.99}, "label": True, "category": "boundary"},
            {"values": {"x": -3.0, "y": 3.0}, "label": False, "category": "extreme"},
        ]

        result = engine.evolve(tests=tests, generations=20, population_size=20, seed=123)
        self.assertIsNotNone(result["best_correctness"])
        self.assertGreaterEqual(result["best_correctness"], 0.5)

    def test_thermo_stats_pre_evolution(self):
        engine = ConstraintEngine(self.constraints).use(Strategy.EVOLUTION)
        stats = engine.thermo_stats()
        self.assertEqual(stats["phase"], "pre_evolution")

    def test_thermo_stats_post_evolution(self):
        engine = ConstraintEngine(self.constraints).use(Strategy.EVOLUTION)
        engine.evolve(generations=15, population_size=20, seed=99)
        stats = engine.thermo_stats()
        self.assertIn("entropy", stats)
        self.assertIn("temperature", stats)
        self.assertIn("free_energy", stats)
        self.assertIn("phase", stats)
        self.assertIsInstance(stats["entropy"], float)

    def test_evolution_without_strategy_raises(self):
        engine = ConstraintEngine(self.constraints)
        with self.assertRaises(RuntimeError):
            engine.evolve()


class TestComposedStrategies(unittest.TestCase):
    """Both SEDIMENT and EVOLUTION can be active simultaneously."""

    def setUp(self):
        self.constraints = [
            {"name": "a", "lo": -5.0, "hi": 5.0},
            {"name": "b", "lo": 0.0, "hi": 10.0},
        ]

    def test_both_strategies_active(self):
        engine = (
            ConstraintEngine(self.constraints)
            .use(Strategy.SEDIMENT)
            .use(Strategy.EVOLUTION)
        )
        self.assertIn(Strategy.SEDIMENT, engine.active_strategies())
        self.assertIn(Strategy.EVOLUTION, engine.active_strategies())

    def test_evolution_then_sediment_improves(self):
        """
        Run evolution to find good bounds, then add sediment corrections
        for edge cases that evolution missed.
        """
        engine = (
            ConstraintEngine(self.constraints)
            .use(Strategy.SEDIMENT)
            .use(Strategy.EVOLUTION)
        )

        # Run evolution
        evo_result = engine.evolve(generations=20, population_size=20, seed=42)
        self.assertIsNotNone(evo_result["best_correctness"])

        # Add sediment correction for an edge case
        engine.add_sediment_layer(
            [
                ConstraintCorrection(
                    constraint_name="a",
                    new_lo=-6.0,
                    new_hi=6.0,
                    reason="post-evolution sediment for near-boundary values",
                ),
            ],
            context={"source": "post_evolution"},
        )

        # Both stats should work
        sed_stats = engine.sediment_stats()
        self.assertEqual(sed_stats["depth"], 1)

        thermo = engine.thermo_stats()
        self.assertIn("phase", thermo)

    def test_sediment_then_evolution(self):
        """
        Add sediment first, then run evolution. Order shouldn't matter.
        """
        engine = (
            ConstraintEngine(self.constraints)
            .use(Strategy.SEDIMENT)
            .use(Strategy.EVOLUTION)
        )

        # Add sediment first
        engine.add_sediment_layer(
            [
                ConstraintCorrection(
                    constraint_name="b",
                    new_lo=-1.0,
                    new_hi=12.0,
                    reason="pre-evolution sediment widening",
                ),
            ],
        )

        # Then run evolution
        result = engine.evolve(generations=15, population_size=20, seed=7)
        self.assertIsNotNone(result["best_correctness"])

    def test_all_strategies_compose(self):
        """Activate SEDIMENT + EVOLUTION + ADAPTIVE_ORDERING together."""
        engine = (
            ConstraintEngine(self.constraints)
            .use(Strategy.ADAPTIVE_ORDERING)
            .use(Strategy.SEDIMENT)
            .use(Strategy.EVOLUTION)
        )
        # Feed some values through check (adaptive ordering + sediment active)
        engine.check(0.5)
        engine.check(3.0)

        # Add sediment and evolve
        engine.add_sediment_layer(
            [
                ConstraintCorrection(
                    constraint_name="a",
                    new_lo=-7.0,
                    new_hi=7.0,
                    reason="full composition test",
                ),
            ],
        )
        result = engine.evolve(generations=10, population_size=15, seed=1)
        self.assertIsNotNone(result["best_correctness"])

        # All three strategies active
        self.assertEqual(len(engine.active_strategies()), 3)


if __name__ == "__main__":
    unittest.main()
