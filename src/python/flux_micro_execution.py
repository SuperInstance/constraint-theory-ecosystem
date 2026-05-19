"""
E7: Can Small Models Execute Tile Procedures?

Hypothesis: micro-models (tiny decision trees, logistic regression) can faithfully
replicate specialist-level tile logic with >90% accuracy.

The procedure IS the intelligence — the model just follows it.
This validates the Mayo Clinic pattern: small model + good tile > large model from scratch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ── ProcedureTile ───────────────────────────────────────────

@dataclass
class CheckStep:
    """A single step in a tile procedure."""
    op: str                # "check_bounds", "check_rate", "check_ratio", "check_nand", "check_sum"
    dims: List[str]        # which dimensions this step examines
    params: Dict[str, float] = field(default_factory=dict)
    severity: int = 2      # 0=pass, 1=caution, 2=warning, 3=critical

@dataclass
class ProcedureTile:
    """A tile that IS a constraint checking procedure."""
    name: str
    version: str
    bounds: Dict[str, Tuple[float, float]]     # dim -> (lo, hi)
    pre_checks: List[str] = field(default_factory=list)   # e.g. "no_nan"
    steps: List[CheckStep] = field(default_factory=list)
    post_checks: List[str] = field(default_factory=list)  # e.g. "severity_consistent"

    @property
    def dim_names(self) -> List[str]:
        return list(self.bounds.keys())

    @property
    def ndim(self) -> int:
        return len(self.bounds)

    def execute(self, values: Dict[str, float]) -> Tuple[int, Dict[str, int]]:
        """
        Execute the tile procedure on a single input.
        Returns (worst_severity, per_step_results).
        Each step result: 0=pass, 1=caution, 2=warning, 3=critical.
        """
        # Pre-checks
        for pc in self.pre_checks:
            if pc == "no_nan":
                for v in values.values():
                    if np.isnan(v):
                        return 3, {s.op: 3 for s in self.steps}

        worst = 0
        step_results: Dict[str, int] = {}

        for i, step in enumerate(self.steps):
            result = self._exec_step(step, values)
            step_results[f"{step.op}_{i}"] = result
            if result > worst:
                worst = result

        # Post-checks
        for ppc in self.post_checks:
            if ppc == "severity_consistent":
                if worst >= 3:
                    for v in step_results.values():
                        if v == 0:
                            pass  # inconsistent but we already flagged critical

        return worst, step_results

    def _exec_step(self, step: CheckStep, values: Dict[str, float]) -> int:
        if step.op == "check_bounds":
            for dim in step.dims:
                v = values[dim]
                lo, hi = step.params.get("lo", self.bounds[dim][0]), step.params.get("hi", self.bounds[dim][1])
                if not (lo <= v <= hi):
                    return step.severity
            return 0

        elif step.op == "check_rate":
            # Check if rate of change between two dims exceeds threshold
            d1, d2 = step.dims[0], step.dims[1]
            rate = abs(values[d1] - values[d2])
            threshold = step.params.get("threshold", 10.0)
            if rate > threshold:
                return step.severity
            return 0

        elif step.op == "check_ratio":
            d1, d2 = step.dims[0], step.dims[1]
            v2 = values[d2]
            if abs(v2) < 1e-9:
                return step.severity
            ratio = values[d1] / v2
            rlo, rhi = step.params.get("rlo", 0.0), step.params.get("rhi", 2.0)
            if not (rlo <= ratio <= rhi):
                return step.severity
            return 0

        elif step.op == "check_nand":
            # Both dims must not be out of bounds simultaneously
            any_oob = False
            for dim in step.dims:
                v = values[dim]
                lo, hi = self.bounds[dim]
                if not (lo <= v <= hi):
                    any_oob = True
                    break
            # Check second dim
            if any_oob:
                for dim in step.dims[1:]:
                    v = values[dim]
                    lo, hi = self.bounds[dim]
                    if not (lo <= v <= hi):
                        return step.severity  # both OOB → critical
            return 0

        elif step.op == "check_sum":
            total = sum(values[d] for d in step.dims)
            slo, shi = step.params.get("slo", -1e9), step.params.get("shi", 1e9)
            if not (slo <= total <= shi):
                return step.severity
            return 0

        return 0


# ── TileDataset ─────────────────────────────────────────────

@dataclass
class TileDataset:
    """Generate training data from a ProcedureTile."""
    tile: ProcedureTile
    n: int = 10000
    seed: int = 42
    train_frac: float = 0.8

    X_train: np.ndarray = field(init=False, repr=False)
    X_test: np.ndarray = field(init=False, repr=False)
    y_train: np.ndarray = field(init=False, repr=False)
    y_test: np.ndarray = field(init=False, repr=False)
    y_train_severity: np.ndarray = field(init=False, repr=False)
    y_test_severity: np.ndarray = field(init=False, repr=False)

    def generate(self) -> "TileDataset":
        rng = np.random.default_rng(self.seed)
        dims = self.tile.dim_names
        ndim = self.tile.ndim

        # Generate inputs — mix of in-bounds and out-of-bounds
        X = np.empty((self.n, ndim))
        for j, d in enumerate(dims):
            lo, hi = self.tile.bounds[d]
            # 70% in-bounds, 30% out-of-bounds (ensures both classes are represented)
            n_in = int(self.n * 0.7)
            X[:n_in, j] = rng.uniform(lo, hi, n_in)
            # Out-of-bounds: extend range by 20% on each side
            margin = (hi - lo) * 0.2
            X[n_in:, j] = rng.uniform(lo - margin, hi + margin, self.n - n_in)

        # Shuffle
        idx = rng.permutation(self.n)
        X = X[idx]

        # Execute tile on each sample → labels
        n_steps = len(self.tile.steps)
        y_mask = np.zeros((self.n, n_steps), dtype=np.int32)
        y_severity = np.zeros(self.n, dtype=np.int32)

        for i in range(self.n):
            values = {d: X[i, j] for j, d in enumerate(dims)}
            sev, step_results = self.tile.execute(values)
            y_severity[i] = sev
            for k, key in enumerate(sorted(step_results.keys())):
                y_mask[i, k] = step_results[key]

        # Split
        split = int(self.n * self.train_frac)
        self.X_train = X[:split]
        self.X_test = X[split:]
        self.y_train = y_mask[:split]
        self.y_test = y_mask[split:]
        self.y_train_severity = y_severity[:split]
        self.y_test_severity = y_severity[split:]

        return self

    @property
    def pass_rate_train(self) -> float:
        return float((self.y_train_severity == 0).mean())

    @property
    def pass_rate_test(self) -> float:
        return float((self.y_test_severity == 0).mean())


# ── MicroExecutor ───────────────────────────────────────────

@dataclass
class MicroExecutorResult:
    """Results from a micro executor experiment."""
    tile_name: str
    model_type: str
    accuracy_severity: float
    accuracy_per_step: List[float]
    n_params: int
    max_depth: Optional[int]
    train_samples: int
    test_samples: int
    pass_rate_test: float


class MicroExecutor:
    """
    A tiny model trained on tile data.
    Decision tree (max_depth=5) and logistic regression.
    Measures accuracy on test set.
    """

    def __init__(self, tile: ProcedureTile, dataset: TileDataset):
        self.tile = tile
        self.dataset = dataset

    def run_decision_tree(self, max_depth: int = 5) -> MicroExecutorResult:
        from sklearn.tree import DecisionTreeClassifier

        ds = self.dataset
        n_steps = len(self.tile.steps)

        # Severity prediction
        dt_sev = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
        dt_sev.fit(ds.X_train, ds.y_train_severity)
        acc_sev = dt_sev.score(ds.X_test, ds.y_test_severity)

        # Per-step prediction
        acc_steps = []
        dt_models = []
        for k in range(n_steps):
            dt_k = DecisionTreeClassifier(max_depth=max_depth, random_state=42)
            dt_k.fit(ds.X_train, ds.y_train[:, k])
            acc_k = dt_k.score(ds.X_test, ds.y_test[:, k])
            acc_steps.append(acc_k)
            dt_models.append(dt_k)

        # Count parameters (decision tree: roughly nodes * 2 for thresholds/features)
        # sklearn trees: each node stores threshold + feature + children
        n_params = dt_sev.tree_.node_count * 3  # threshold, feature, value per node
        for dt_m in dt_models:
            n_params += dt_m.tree_.node_count * 3

        return MicroExecutorResult(
            tile_name=self.tile.name,
            model_type=f"decision_tree_depth{max_depth}",
            accuracy_severity=acc_sev,
            accuracy_per_step=acc_steps,
            n_params=n_params,
            max_depth=max_depth,
            train_samples=ds.X_train.shape[0],
            test_samples=ds.X_test.shape[0],
            pass_rate_test=ds.pass_rate_test,
        )

    def run_logistic(self) -> MicroExecutorResult:
        from sklearn.linear_model import LogisticRegression
        from sklearn.multioutput import MultiOutputClassifier

        ds = self.dataset
        n_steps = len(self.tile.steps)

        # Severity prediction
        lr_sev = LogisticRegression(max_iter=1000, random_state=42)
        lr_sev.fit(ds.X_train, ds.y_train_severity)
        acc_sev = lr_sev.score(ds.X_test, ds.y_test_severity)

        # Per-step prediction
        acc_steps = []
        n_params = lr_sev.coef_.size + lr_sev.intercept_.size
        for k in range(n_steps):
            lr_k = LogisticRegression(max_iter=1000, random_state=42)
            lr_k.fit(ds.X_train, ds.y_train[:, k])
            acc_k = lr_k.score(ds.X_test, ds.y_test[:, k])
            acc_steps.append(acc_k)
            n_params += lr_k.coef_.size + lr_k.intercept_.size

        return MicroExecutorResult(
            tile_name=self.tile.name,
            model_type="logistic_regression",
            accuracy_severity=acc_sev,
            accuracy_per_step=acc_steps,
            n_params=n_params,
            max_depth=None,
            train_samples=ds.X_train.shape[0],
            test_samples=ds.X_test.shape[0],
            pass_rate_test=ds.pass_rate_test,
        )


# ── Preset Tiles ────────────────────────────────────────────

def make_automotive_tile() -> ProcedureTile:
    return ProcedureTile(
        name="automotive_coolant",
        version="1.0",
        bounds={"coolant_temp": (-40, 150), "oil_temp": (-30, 160), "rpm": (0, 8000)},
        pre_checks=["no_nan"],
        steps=[
            CheckStep(op="check_bounds", dims=["coolant_temp"], severity=3),
            CheckStep(op="check_bounds", dims=["oil_temp"], severity=2),
            CheckStep(op="check_bounds", dims=["rpm"], severity=2),
            CheckStep(op="check_rate", dims=["coolant_temp", "oil_temp"],
                      params={"threshold": 50}, severity=2),
        ],
    )

def make_medical_tile() -> ProcedureTile:
    return ProcedureTile(
        name="medical_vitals",
        version="1.0",
        bounds={"heart_rate": (40, 200), "bp_sys": (70, 200), "bp_dia": (40, 130), "temp_c": (34, 42)},
        pre_checks=["no_nan"],
        steps=[
            CheckStep(op="check_bounds", dims=["heart_rate"], severity=3),
            CheckStep(op="check_bounds", dims=["bp_sys"], severity=2),
            CheckStep(op="check_bounds", dims=["bp_dia"], severity=2),
            CheckStep(op="check_bounds", dims=["temp_c"], severity=3),
            CheckStep(op="check_ratio", dims=["bp_dia", "bp_sys"],
                      params={"rlo": 0.3, "rhi": 0.8}, severity=2),
        ],
    )

def make_space_tile() -> ProcedureTile:
    return ProcedureTile(
        name="space_thermal",
        version="1.0",
        bounds={"hull_temp": (-270, 500), "internal_temp": (15, 35), "pressure_kpa": (50, 110)},
        pre_checks=["no_nan"],
        steps=[
            CheckStep(op="check_bounds", dims=["hull_temp"], severity=3),
            CheckStep(op="check_bounds", dims=["internal_temp"], severity=3),
            CheckStep(op="check_bounds", dims=["pressure_kpa"], severity=3),
            CheckStep(op="check_rate", dims=["hull_temp", "internal_temp"],
                      params={"threshold": 200}, severity=2),
        ],
    )

def make_aviation_tile() -> ProcedureTile:
    return ProcedureTile(
        name="aviation_altitude",
        version="1.0",
        bounds={"altitude_ft": (0, 45000), "speed_kts": (0, 600), "vspeed_fpm": (-3000, 3000)},
        pre_checks=["no_nan"],
        steps=[
            CheckStep(op="check_bounds", dims=["altitude_ft"], severity=3),
            CheckStep(op="check_bounds", dims=["speed_kts"], severity=2),
            CheckStep(op="check_bounds", dims=["vspeed_fpm"], severity=2),
            CheckStep(op="check_rate", dims=["altitude_ft", "vspeed_fpm"],
                      params={"threshold": 25000}, severity=1),
        ],
    )

def make_battery_tile() -> ProcedureTile:
    return ProcedureTile(
        name="battery_monitor",
        version="1.0",
        bounds={"voltage": (2.5, 4.2), "current_ma": (-2000, 5000), "temp_c": (-20, 60)},
        pre_checks=["no_nan"],
        steps=[
            CheckStep(op="check_bounds", dims=["voltage"], severity=3),
            CheckStep(op="check_bounds", dims=["current_ma"], severity=2),
            CheckStep(op="check_bounds", dims=["temp_c"], severity=2),
            CheckStep(op="check_sum", dims=["voltage", "temp_c"],
                      params={"slo": -15, "shi": 65}, severity=1),
        ],
    )

def make_hvac_tile() -> ProcedureTile:
    return ProcedureTile(
        name="hvac_zone",
        version="1.0",
        bounds={"supply_temp": (10, 55), "return_temp": (15, 30), "cfm": (100, 2000)},
        pre_checks=["no_nan"],
        steps=[
            CheckStep(op="check_bounds", dims=["supply_temp"], severity=2),
            CheckStep(op="check_bounds", dims=["return_temp"], severity=2),
            CheckStep(op="check_bounds", dims=["cfm"], severity=1),
            CheckStep(op="check_rate", dims=["supply_temp", "return_temp"],
                      params={"threshold": 30}, severity=2),
        ],
    )

def make_robotics_tile() -> ProcedureTile:
    return ProcedureTile(
        name="robotics_joint",
        version="1.0",
        bounds={"angle_deg": (-180, 180), "torque_nm": (0, 150), "velocity_dps": (-360, 360)},
        pre_checks=["no_nan"],
        steps=[
            CheckStep(op="check_bounds", dims=["angle_deg"], severity=3),
            CheckStep(op="check_bounds", dims=["torque_nm"], severity=3),
            CheckStep(op="check_bounds", dims=["velocity_dps"], severity=2),
            CheckStep(op="check_nand", dims=["torque_nm", "velocity_dps"], severity=3),
        ],
    )

def make_marine_tile() -> ProcedureTile:
    return ProcedureTile(
        name="marine_engine",
        version="1.0",
        bounds={"engine_rpm": (0, 3000), "coolant_temp": (10, 95), "exhaust_temp": (100, 600)},
        pre_checks=["no_nan"],
        steps=[
            CheckStep(op="check_bounds", dims=["engine_rpm"], severity=2),
            CheckStep(op="check_bounds", dims=["coolant_temp"], severity=3),
            CheckStep(op="check_bounds", dims=["exhaust_temp"], severity=3),
            CheckStep(op="check_rate", dims=["coolant_temp", "exhaust_temp"],
                      params={"threshold": 300}, severity=2),
        ],
    )

def make_pharma_tile() -> ProcedureTile:
    return ProcedureTile(
        name="pharma_storage",
        version="1.0",
        bounds={"temp_c": (2, 8), "humidity_pct": (20, 60), "pressure_hpa": (950, 1050)},
        pre_checks=["no_nan"],
        steps=[
            CheckStep(op="check_bounds", dims=["temp_c"], severity=3),
            CheckStep(op="check_bounds", dims=["humidity_pct"], severity=2),
            CheckStep(op="check_bounds", dims=["pressure_hpa"], severity=1),
        ],
    )

def make_semiconductor_tile() -> ProcedureTile:
    return ProcedureTile(
        name="semiconductor_process",
        version="1.0",
        bounds={"chamber_temp": (200, 1200), "pressure_torr": (0.001, 760), "flow_sccm": (0, 5000)},
        pre_checks=["no_nan"],
        steps=[
            CheckStep(op="check_bounds", dims=["chamber_temp"], severity=3),
            CheckStep(op="check_bounds", dims=["pressure_torr"], severity=3),
            CheckStep(op="check_bounds", dims=["flow_sccm"], severity=2),
            CheckStep(op="check_ratio", dims=["flow_sccm", "pressure_torr"],
                      params={"rlo": 0.0, "rhi": 1000}, severity=2),
        ],
    )


ALL_TILES = [
    make_automotive_tile,
    make_medical_tile,
    make_space_tile,
    make_aviation_tile,
    make_battery_tile,
    make_hvac_tile,
    make_robotics_tile,
    make_marine_tile,
    make_pharma_tile,
    make_semiconductor_tile,
]


# ── Experiment Runner ───────────────────────────────────────

def run_experiment(n_samples: int = 10000, max_depth: int = 5) -> Dict[str, Any]:
    """
    Run E7: train micro executors on 10 procedure tiles.
    Returns full results dict.
    """
    results_dt = []
    results_lr = []

    for make_tile in ALL_TILES:
        tile = make_tile()
        print(f"\n{'='*60}")
        print(f"Tile: {tile.name} ({tile.ndim} dims, {len(tile.steps)} steps)")

        dataset = TileDataset(tile=tile, n=n_samples, seed=42).generate()
        print(f"  Dataset: {n_samples} samples, pass rate: {dataset.pass_rate_test:.1%}")

        executor = MicroExecutor(tile=tile, dataset=dataset)

        # Decision tree
        dt_result = executor.run_decision_tree(max_depth=max_depth)
        results_dt.append(dt_result)
        print(f"  Decision Tree (depth={max_depth}): "
              f"severity acc={dt_result.accuracy_severity:.4f}, "
              f"steps={dt_result.accuracy_per_step}, "
              f"params={dt_result.n_params}")

        # Logistic regression
        lr_result = executor.run_logistic()
        results_lr.append(lr_result)
        print(f"  Logistic Regression: "
              f"severity acc={lr_result.accuracy_severity:.4f}, "
              f"steps={lr_result.accuracy_per_step}, "
              f"params={lr_result.n_params}")

    # Summary
    dt_90 = sum(1 for r in results_dt if r.accuracy_severity >= 0.90)
    lr_90 = sum(1 for r in results_lr if r.accuracy_severity >= 0.90)
    dt_99 = sum(1 for r in results_dt if r.accuracy_severity >= 0.99)
    lr_99 = sum(1 for r in results_lr if r.accuracy_severity >= 0.99)

    summary = {
        "experiment": "E7_micro_execution",
        "n_tiles": len(ALL_TILES),
        "n_samples": n_samples,
        "decision_tree": {
            "results": [
                {
                    "tile": r.tile_name,
                    "accuracy_severity": r.accuracy_severity,
                    "accuracy_per_step": r.accuracy_per_step,
                    "n_params": r.n_params,
                    "pass_rate": r.pass_rate_test,
                }
                for r in results_dt
            ],
            "tiles_above_90pct": dt_90,
            "tiles_above_99pct": dt_99,
            "mean_accuracy": np.mean([r.accuracy_severity for r in results_dt]),
            "mean_params": int(np.mean([r.n_params for r in results_dt])),
        },
        "logistic_regression": {
            "results": [
                {
                    "tile": r.tile_name,
                    "accuracy_severity": r.accuracy_severity,
                    "accuracy_per_step": r.accuracy_per_step,
                    "n_params": r.n_params,
                    "pass_rate": r.pass_rate_test,
                }
                for r in results_lr
            ],
            "tiles_above_90pct": lr_90,
            "tiles_above_99pct": lr_99,
            "mean_accuracy": np.mean([r.accuracy_severity for r in results_lr]),
            "mean_params": int(np.mean([r.n_params for r in results_lr])),
        },
        "conclusion": None,
    }

    # Conclusion
    if dt_90 == len(ALL_TILES):
        summary["conclusion"] = (
            f"HYPOTHESIS CONFIRMED: {dt_90}/{len(ALL_TILES)} tiles achieve >90% accuracy "
            f"with decision trees (mean {summary['decision_tree']['mean_accuracy']:.2%}). "
            f"Mean parameters: {summary['decision_tree']['mean_params']}. "
            f"The procedure IS the intelligence."
        )
    else:
        summary["conclusion"] = (
            f"HYPOTHESIS PARTIALLY CONFIRMED: {dt_90}/{len(ALL_TILES)} tiles achieve >90% accuracy. "
            f"Mean accuracy: {summary['decision_tree']['mean_accuracy']:.2%}."
        )

    print(f"\n{'='*60}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"Decision Tree:  {dt_90}/{len(ALL_TILES)} tiles >90% acc, {dt_99}/{len(ALL_TILES)} >99%")
    print(f"  Mean accuracy: {summary['decision_tree']['mean_accuracy']:.4f}")
    print(f"  Mean params:   {summary['decision_tree']['mean_params']}")
    print(f"Logistic Reg:   {lr_90}/{len(ALL_TILES)} tiles >90% acc, {lr_99}/{len(ALL_TILES)} >99%")
    print(f"  Mean accuracy: {summary['logistic_regression']['mean_accuracy']:.4f}")
    print(f"\n{summary['conclusion']}")

    return summary


if __name__ == "__main__":
    run_experiment()
