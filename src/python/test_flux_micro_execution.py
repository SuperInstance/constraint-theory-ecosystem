"""Tests for flux_micro_execution (E7: Can Small Models Execute Tile Procedures?)"""

import numpy as np
import pytest

from flux_micro_execution import (
    ALL_TILES,
    CheckStep,
    MicroExecutor,
    ProcedureTile,
    TileDataset,
    run_experiment,
)


# ── ProcedureTile Tests ────────────────────────────────────

class TestProcedureTile:
    def test_basic_creation(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10), "y": (-5, 5)},
        )
        assert tile.ndim == 2
        assert tile.dim_names == ["x", "y"]

    def test_check_bounds_pass(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10)},
            steps=[CheckStep(op="check_bounds", dims=["x"], severity=2)],
        )
        sev, results = tile.execute({"x": 5.0})
        assert sev == 0

    def test_check_bounds_fail(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10)},
            steps=[CheckStep(op="check_bounds", dims=["x"], severity=3)],
        )
        sev, results = tile.execute({"x": 15.0})
        assert sev == 3

    def test_check_rate_pass(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"a": (0, 100), "b": (0, 100)},
            steps=[CheckStep(op="check_rate", dims=["a", "b"],
                             params={"threshold": 50}, severity=2)],
        )
        sev, _ = tile.execute({"a": 10.0, "b": 30.0})
        assert sev == 0  # |10-30| = 20 < 50

    def test_check_rate_fail(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"a": (0, 100), "b": (0, 100)},
            steps=[CheckStep(op="check_rate", dims=["a", "b"],
                             params={"threshold": 5}, severity=2)],
        )
        sev, _ = tile.execute({"a": 0.0, "b": 100.0})
        assert sev == 2  # |0-100| = 100 > 5

    def test_check_ratio_pass(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"a": (0, 100), "b": (1, 100)},
            steps=[CheckStep(op="check_ratio", dims=["a", "b"],
                             params={"rlo": 0.5, "rhi": 2.0}, severity=2)],
        )
        sev, _ = tile.execute({"a": 50.0, "b": 40.0})
        assert sev == 0  # 50/40 = 1.25, in [0.5, 2.0]

    def test_check_ratio_fail(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"a": (0, 100), "b": (1, 100)},
            steps=[CheckStep(op="check_ratio", dims=["a", "b"],
                             params={"rlo": 0.5, "rhi": 2.0}, severity=2)],
        )
        sev, _ = tile.execute({"a": 90.0, "b": 10.0})
        assert sev == 2  # 90/10 = 9.0, way above 2.0

    def test_check_sum_pass(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"a": (0, 10), "b": (0, 10)},
            steps=[CheckStep(op="check_sum", dims=["a", "b"],
                             params={"slo": 0, "shi": 20}, severity=2)],
        )
        sev, _ = tile.execute({"a": 5.0, "b": 5.0})
        assert sev == 0

    def test_check_sum_fail(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"a": (0, 10), "b": (0, 10)},
            steps=[CheckStep(op="check_sum", dims=["a", "b"],
                             params={"slo": 0, "shi": 10}, severity=2)],
        )
        sev, _ = tile.execute({"a": 8.0, "b": 8.0})
        assert sev == 2  # 16 > 10

    def test_nan_precheck(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10)},
            pre_checks=["no_nan"],
            steps=[CheckStep(op="check_bounds", dims=["x"], severity=2)],
        )
        sev, _ = tile.execute({"x": float("nan")})
        assert sev == 3

    def test_multiple_steps_worst_wins(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10), "y": (0, 10)},
            steps=[
                CheckStep(op="check_bounds", dims=["x"], severity=1),  # passes
                CheckStep(op="check_bounds", dims=["y"], severity=3),  # fails
            ],
        )
        sev, results = tile.execute({"x": 5.0, "y": 20.0})
        assert sev == 3


# ── TileDataset Tests ──────────────────────────────────────

class TestTileDataset:
    def test_generation(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10), "y": (-5, 5)},
            steps=[CheckStep(op="check_bounds", dims=["x"], severity=2)],
        )
        ds = TileDataset(tile=tile, n=100, seed=42).generate()
        assert ds.X_train.shape == (80, 2)
        assert ds.X_test.shape == (20, 2)
        assert ds.y_train_severity.shape == (80,)
        assert ds.y_test_severity.shape == (20,)

    def test_has_both_classes(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10)},
            steps=[CheckStep(op="check_bounds", dims=["x"], severity=2)],
        )
        ds = TileDataset(tile=tile, n=1000, seed=42).generate()
        # Should have both pass and fail
        assert 0 in ds.y_train_severity
        assert 2 in ds.y_train_severity

    def test_pass_rate_sensible(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10)},
            steps=[CheckStep(op="check_bounds", dims=["x"], severity=2)],
        )
        ds = TileDataset(tile=tile, n=1000, seed=42).generate()
        # 70% in-bounds + margin generation, pass rate should be reasonable
        assert 0.5 < ds.pass_rate_train < 0.98


# ── MicroExecutor Tests ────────────────────────────────────

class TestMicroExecutor:
    def test_decision_tree_accuracy(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10)},
            steps=[CheckStep(op="check_bounds", dims=["x"], severity=2)],
        )
        ds = TileDataset(tile=tile, n=1000, seed=42).generate()
        executor = MicroExecutor(tile=tile, dataset=ds)
        result = executor.run_decision_tree(max_depth=5)
        # Simple bounds checking should be nearly perfect
        assert result.accuracy_severity > 0.95

    def test_logistic_accuracy(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10)},
            steps=[CheckStep(op="check_bounds", dims=["x"], severity=2)],
        )
        ds = TileDataset(tile=tile, n=1000, seed=42).generate()
        executor = MicroExecutor(tile=tile, dataset=ds)
        result = executor.run_logistic()
        assert result.accuracy_severity > 0.90

    def test_model_type_labels(self):
        tile = ProcedureTile(
            name="test", version="1.0",
            bounds={"x": (0, 10)},
            steps=[CheckStep(op="check_bounds", dims=["x"], severity=2)],
        )
        ds = TileDataset(tile=tile, n=500, seed=42).generate()
        executor = MicroExecutor(tile=tile, dataset=ds)
        dt = executor.run_decision_tree()
        lr = executor.run_logistic()
        assert dt.model_type == "decision_tree_depth5"
        assert lr.model_type == "logistic_regression"


# ── Preset Tiles Tests ─────────────────────────────────────

class TestPresets:
    def test_all_tiles_instantiable(self):
        for make_tile in ALL_TILES:
            tile = make_tile()
            assert tile.ndim >= 1
            assert len(tile.steps) >= 1

    def test_all_tiles_executable(self):
        for make_tile in ALL_TILES:
            tile = make_tile()
            values = {d: (lo + hi) / 2 for d, (lo, hi) in tile.bounds.items()}
            sev, results = tile.execute(values)
            assert sev == 0  # midpoint should always pass
            assert len(results) == len(tile.steps)

    def test_all_tiles_fail_on_oob(self):
        for make_tile in ALL_TILES:
            tile = make_tile()
            # Push all dims out of bounds
            values = {d: hi + 100 for d, (lo, hi) in tile.bounds.items()}
            sev, results = tile.execute(values)
            assert sev > 0  # should detect violation

    def test_ten_tiles(self):
        assert len(ALL_TILES) == 10


# ── Integration Test ────────────────────────────────────────

class TestExperiment:
    def test_experiment_runs(self):
        summary = run_experiment(n_samples=1000, max_depth=5)
        assert summary["n_tiles"] == 10
        assert len(summary["decision_tree"]["results"]) == 10
        assert len(summary["logistic_regression"]["results"]) == 10
        assert summary["decision_tree"]["tiles_above_90pct"] >= 0
        assert summary["conclusion"] is not None

    def test_experiment_hypothesis(self):
        """The key test: do most tiles achieve >90% with decision trees?"""
        summary = run_experiment(n_samples=5000, max_depth=5)
        dt_90 = summary["decision_tree"]["tiles_above_90pct"]
        # Expect at least 8/10 tiles to hit 90%
        assert dt_90 >= 8, f"Only {dt_90}/10 tiles hit 90% — hypothesis in danger"
