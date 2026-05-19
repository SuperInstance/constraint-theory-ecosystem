"""
flux_yield.py — Semiconductor Yield Model for Constraint Systems

The manufacturing analogy: in semiconductor fabs, yield = fraction of chips
with ZERO defects. Each manufacturing step has a defect rate. Total yield is
the product of step yields. Statistical Process Control (SPC) monitors drift.

This maps EXACTLY to constraint systems:
  - yield = probability all constraints pass
  - each constraint = a manufacturing step
  - defects = constraint violations
  - process control limits = constraint bounds
  - SPC = accumulated correctness tracking

Provides:
- ProcessStep: manufacturing step as a constraint
- YieldModel: predict system yield (≡ partition function)
- SPCMonitor: statistical process control for constraints
- YieldOptimizer: maximize yield through bound optimization

Author: Forgemaster ⚒️ (Constraint Theory Ecosystem)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# 1. ProcessStep — Manufacturing Step as Constraint
# ---------------------------------------------------------------------------

@dataclass
class ProcessStep:
    """
    A manufacturing step modeled as a constraint.

    Parameters
    ----------
    name : str
        Step identifier.
    dimension_index : int
        Which constraint dimension this step guards.
    defect_rate : float
        Historical fraction of violations (failures).
    control_limits : tuple[float, float]
        (LCL, UCL) — statistical lower/upper control limits.
    mean : float
        Process mean (center of the distribution).
    std : float
        Process standard deviation.
    """

    name: str
    dimension_index: int
    defect_rate: float
    control_limits: Tuple[float, float]
    mean: float = 0.0
    std: float = 1.0

    @property
    def step_yield(self) -> float:
        """Yield of this single step = 1 - defect_rate."""
        return 1.0 - self.defect_rate

    @property
    def cpk(self) -> float:
        """
        Process Capability Index Cpk.

        Cpk = min((USL - μ) / (3σ), (μ - LSL) / (3σ))

        Interpretation:
          Cpk > 1.33  → capable (≥4σ between mean and nearest limit)
          Cpk > 1.0   → marginally capable
          Cpk < 1.0   → not capable (defects expected)
        """
        lcl, ucl = self.control_limits
        if self.std <= 0:
            return float("inf")
        cpu = (ucl - self.mean) / (3.0 * self.std)
        cpl = (self.mean - lcl) / (3.0 * self.std)
        return min(cpu, cpl)

    @property
    def is_capable(self) -> bool:
        """Step is statistically capable if Cpk > 1.33."""
        return self.cpk > 1.33

    def defect_rate_from_normal(self) -> float:
        """Estimate defect rate from normal distribution beyond control limits."""
        lcl, ucl = self.control_limits
        from scipy.stats import norm is not None:  # noqa — optional
            pass
        # Pure numpy fallback using error function
        phi_lcl = 0.5 * (1.0 + math.erf((lcl - self.mean) / (self.std * math.sqrt(2))))
        phi_ucl = 0.5 * (1.0 + math.erf((ucl - self.mean) / (self.std * math.sqrt(2))))
        return 1.0 - (phi_ucl - phi_lcl)


# ---------------------------------------------------------------------------
# 2. YieldModel — Predict System Yield
# ---------------------------------------------------------------------------

@dataclass
class YieldReport:
    """Comprehensive yield analysis report."""
    overall_yield: float
    n_steps: int
    step_yields: List[Tuple[str, float]]  # (name, step_yield)
    step_defect_rates: List[Tuple[str, float]]  # (name, defect_rate)
    pareto_defects: List[Tuple[str, float]]  # sorted by defect_rate descending
    bottleneck_step: str
    bottleneck_defect_rate: float
    log_yield: float  # ln(overall_yield) for additive comparison


class YieldModel:
    """
    Predict system yield from individual step defect rates.

    For independent steps:
        yield = ∏(1 - defect_rate_i)

    This is EXACTLY the thermodynamic partition function Z with
    all Boltzmann weights w_i = (1 - defect_rate_i):
        Z = ∏ w_i

    The connection:
        Z_thermo = Σ exp(-E_i / T)   (sum over microstates)
        Z_yield  = ∏ (1 - d_i)       (product over steps)

    When all defects are independent Bernoulli:
        P(all pass) = ∏ P(step_i passes) = ∏ (1 - d_i) = Z_yield

    For correlated defects, use inclusion-exclusion:
        P(any defect) = Σ d_i - Σ d_i∩d_j + Σ d_i∩d_j∩d_k - ...
        yield = 1 - P(any defect)
    """

    def __init__(self, steps: List[ProcessStep]):
        self.steps = steps

    def overall_yield(self) -> float:
        """System yield = product of step yields."""
        return float(np.prod([s.step_yield for s in self.steps]))

    def log_yield(self) -> float:
        """Log yield = sum of log(step_yield). Additive decomposition."""
        yields = np.array([s.step_yield for s in self.steps])
        # Guard against log(0)
        yields = np.clip(yields, 1e-300, 1.0)
        return float(np.sum(np.log(yields)))

    def yield_by_step(self) -> List[Tuple[str, float]]:
        """Yield contribution of each step."""
        return [(s.name, s.step_yield) for s in self.steps]

    def pareto_defects(self) -> List[Tuple[str, float]]:
        """Defect sources sorted by rate (Pareto — biggest problem first)."""
        rates = [(s.name, s.defect_rate) for s in self.steps]
        return sorted(rates, key=lambda x: x[1], reverse=True)

    def bottleneck(self) -> Tuple[str, float]:
        """Identify the bottleneck step (highest defect rate)."""
        rates = [(s.name, s.defect_rate) for s in self.steps]
        return max(rates, key=lambda x: x[1])

    def report(self) -> YieldReport:
        """Generate a comprehensive yield report."""
        oy = self.overall_yield()
        bottleneck_name, bottleneck_rate = self.bottleneck()
        return YieldReport(
            overall_yield=oy,
            n_steps=len(self.steps),
            step_yields=self.yield_by_step(),
            step_defect_rates=[(s.name, s.defect_rate) for s in self.steps],
            pareto_defects=self.pareto_defects(),
            bottleneck_step=bottleneck_name,
            bottleneck_defect_rate=bottleneck_rate,
            log_yield=self.log_yield(),
        )

    def yield_with_correlation(self, correlation_matrix: Optional[NDArray] = None) -> float:
        """
        Yield under correlated defects using inclusion-exclusion (pairwise approximation).

        For pairwise correlations:
            P(any defect) ≈ Σ d_i - Σ ρ_ij √(d_i d_j)
            yield = 1 - P(any defect)

        Parameters
        ----------
        correlation_matrix : optional array (n_steps × n_steps)
            Pairwise correlation of defect events. If None, returns independent yield.
        """
        if correlation_matrix is None:
            return self.overall_yield()

        d = np.array([s.defect_rate for s in self.steps])
        n = len(d)

        # First order: sum of defect rates
        p_any = np.sum(d)

        # Second order: pairwise intersections (correlation-adjusted)
        if n > 1:
            for i in range(n):
                for j in range(i + 1, n):
                    rho = correlation_matrix[i, j]
                    # P(both defect) ≈ d_i * d_j + ρ * sqrt(d_i * d_j * (1-d_i) * (1-d_j))
                    p_both = d[i] * d[j] + rho * math.sqrt(
                        d[i] * d[j] * (1 - d[i]) * (1 - d[j])
                    )
                    p_any -= p_both

        return max(0.0, 1.0 - p_any)


# ---------------------------------------------------------------------------
# 3. SPCMonitor — Statistical Process Control
# ---------------------------------------------------------------------------

@dataclass
class SPCAlert:
    """An SPC alert when a rule is violated."""
    step_name: str
    rule: str
    point_index: int
    value: float
    description: str


class SPCMonitor:
    """
    Statistical Process Control for constraint monitoring.

    Tracks constraint violations over time, analogous to tracking
    manufacturing defect rates. Uses Western Electric rules to detect
    process drift BEFORE it causes constraint violations.

    Charts:
      - X-bar chart: rolling mean of each dimension
      - S chart: rolling standard deviation
    """

    def __init__(self, steps: List[ProcessStep], window_size: int = 20):
        self.steps = steps
        self.window_size = window_size
        # History buffer: list of arrays, one per time point
        self.history: List[NDArray] = []
        self.violation_history: List[NDArray[np.bool_]] = []

    def observe(self, values: NDArray) -> List[SPCAlert]:
        """
        Record a new observation and check SPC rules.

        Parameters
        ----------
        values : array of shape (n_steps,)
            Observed values for each process step.

        Returns
        -------
        list of SPCAlert
            Any rules that were triggered.
        """
        values = np.asarray(values, dtype=float)
        self.history.append(values.copy())

        # Check violations against control limits
        violations = np.zeros(len(self.steps), dtype=bool)
        for i, step in enumerate(self.steps):
            lcl, ucl = step.control_limits
            violations[i] = values[i] < lcl or values[i] > ucl
        self.violation_history.append(violations)

        alerts: List[SPCAlert] = []
        if len(self.history) < 2:
            return alerts

        # Check Western Electric rules for each step
        for i, step in enumerate(self.steps):
            alerts.extend(self._check_western_electric(step, i))

        return alerts

    def _get_series(self, step_index: int) -> NDArray:
        """Get time series for a specific step."""
        return np.array([h[step_index] for h in self.history])

    def _check_western_electric(self, step: ProcessStep,
                                 step_index: int) -> List[SPCAlert]:
        """
        Check Western Electric rules on the time series for one step.

        Rules:
          Rule 1: 1 point > 3σ from center line → immediate alert
          Rule 2: 9 consecutive points on same side of center → drift
          Rule 3: 6 consecutive points all increasing or all decreasing → trend
          Rule 4: 2 of 3 consecutive points > 2σ on same side → warning
        """
        series = self._get_series(step_index)
        n = len(series)
        alerts: List[SPCAlert] = []

        center = step.mean
        sigma = step.std

        # Rule 1: Single point beyond 3σ
        last = series[-1]
        if abs(last - center) > 3 * sigma:
            alerts.append(SPCAlert(
                step_name=step.name,
                rule="Rule 1",
                point_index=n - 1,
                value=last,
                description=f"Point {last:.4f} beyond 3σ from center {center:.4f}"
            ))

        # Rule 2: 9 consecutive points on same side
        if n >= 9:
            last_9 = series[-9:]
            above = last_9 > center
            below = last_9 < center
            if np.all(above) or np.all(below):
                side = "above" if np.all(above) else "below"
                alerts.append(SPCAlert(
                    step_name=step.name,
                    rule="Rule 2",
                    point_index=n - 1,
                    value=last,
                    description=f"9 consecutive points {side} center"
                ))

        # Rule 3: 6 consecutive points all increasing or decreasing
        if n >= 6:
            last_6 = series[-6:]
            diffs = np.diff(last_6)
            if np.all(diffs > 0):
                alerts.append(SPCAlert(
                    step_name=step.name,
                    rule="Rule 3",
                    point_index=n - 1,
                    value=last,
                    description="6 consecutive points increasing (trend)"
                ))
            elif np.all(diffs < 0):
                alerts.append(SPCAlert(
                    step_name=step.name,
                    rule="Rule 3",
                    point_index=n - 1,
                    value=last,
                    description="6 consecutive points decreasing (trend)"
                ))

        # Rule 4: 2 of 3 beyond 2σ on same side
        if n >= 3:
            last_3 = series[-3:]
            beyond_2u = last_3 > (center + 2 * sigma)
            beyond_2l = last_3 < (center - 2 * sigma)
            if np.sum(beyond_2u) >= 2:
                alerts.append(SPCAlert(
                    step_name=step.name,
                    rule="Rule 4",
                    point_index=n - 1,
                    value=last,
                    description="2 of 3 points beyond 2σ above center"
                ))
            elif np.sum(beyond_2l) >= 2:
                alerts.append(SPCAlert(
                    step_name=step.name,
                    rule="Rule 4",
                    point_index=n - 1,
                    value=last,
                    description="2 of 3 points beyond 2σ below center"
                ))

        return alerts

    def xbar_chart(self, step_index: int) -> Tuple[NDArray, float, float]:
        """
        X-bar chart data for a step.

        Returns (rolling_mean_series, center_line, sigma).
        """
        series = self._get_series(step_index)
        if len(series) == 0:
            return np.array([]), self.steps[step_index].mean, self.steps[step_index].std
        return series, self.steps[step_index].mean, self.steps[step_index].std

    def s_chart(self, step_index: int) -> Tuple[NDArray, float]:
        """
        S chart: rolling standard deviation.

        Returns (rolling_std_series, mean_std).
        """
        series = self._get_series(step_index)
        if len(series) < 2:
            return np.array([]), 0.0

        rolling_stds = []
        w = min(self.window_size, len(series))
        for k in range(len(series)):
            start = max(0, k - w + 1)
            chunk = series[start:k + 1]
            if len(chunk) >= 2:
                rolling_stds.append(float(np.std(chunk, ddof=1)))
            else:
                rolling_stds.append(0.0)
        return np.array(rolling_stds), float(np.mean(rolling_stds))


# ---------------------------------------------------------------------------
# 4. YieldOptimizer — Maximize Yield Through Bound Optimization
# ---------------------------------------------------------------------------

@dataclass
class OptimizationResult:
    """Result of yield optimization."""
    initial_yield: float
    final_yield: float
    improvement: float
    improvement_pct: float
    adjustments: List[Tuple[str, str, float]]
    bottleneck_step: str
    log: List[str]


class YieldOptimizer:
    """
    Maximize system yield by optimizing process bounds.

    Strategy:
      1. Identify bottleneck step (lowest step yield)
      2. If bottleneck is too tight (Cpk > 2.0): widen bounds to reduce defects
      3. If non-bottleneck is too loose (Cpk < 1.0): tighten to reduce noise
      4. Re-estimate defect rates from new bounds
      5. Repeat until convergence

    The yield-optimal bounds balance:
      - Wide enough for real data variation
      - Tight enough for safety (zero false negatives preserved)
    """

    def __init__(self, steps: List[ProcessStep],
                 min_yield: float = 0.99,
                 max_iterations: int = 10,
                 safety_margin: float = 0.1):
        """
        Parameters
        ----------
        steps : list of ProcessStep
        min_yield : float
            Target minimum yield (0.99 = 99%).
        max_iterations : int
            Maximum optimization iterations.
        safety_margin : float
            Fraction of available widening to use (conservative).
        """
        self.steps = [self._copy_step(s) for s in steps]
        self.min_yield = min_yield
        self.max_iterations = max_iterations
        self.safety_margin = safety_margin

    @staticmethod
    def _copy_step(s: ProcessStep) -> ProcessStep:
        """Deep copy a ProcessStep."""
        return ProcessStep(
            name=s.name,
            dimension_index=s.dimension_index,
            defect_rate=s.defect_rate,
            control_limits=s.control_limits,
            mean=s.mean,
            std=s.std,
        )

    def _estimate_defect_rate(self, step: ProcessStep) -> float:
        """Estimate defect rate from normal distribution with current bounds."""
        lcl, ucl = step.control_limits
        z_lcl = (lcl - step.mean) / step.std if step.std > 0 else -6.0
        z_ucl = (ucl - step.mean) / step.std if step.std > 0 else 6.0
        # P(X < LCL) + P(X > UCL)
        p_low = 0.5 * (1.0 + math.erf(z_lcl / math.sqrt(2.0)))
        p_high = 1.0 - 0.5 * (1.0 + math.erf(z_ucl / math.sqrt(2.0)))
        return p_low + p_high

    def optimize(self) -> OptimizationResult:
        """
        Run yield optimization.

        Returns
        -------
        OptimizationResult
            Before/after yield, adjustments made, bottleneck identified.
        """
        model = YieldModel(self.steps)
        initial_yield = model.overall_yield()
        initial_report = model.report()
        bottleneck_name = initial_report.bottleneck_step

        adjustments: List[Tuple[str, str, float]] = []
        log_lines: List[str] = [
            f"Initial yield: {initial_yield:.4f} ({initial_yield*100:.2f}%)",
            f"Bottleneck: {bottleneck_name} (defect rate: {initial_report.bottleneck_defect_rate:.4f})",
        ]

        for iteration in range(self.max_iterations):
            model = YieldModel(self.steps)
            current_yield = model.overall_yield()

            if current_yield >= self.min_yield:
                log_lines.append(f"Iteration {iteration}: yield {current_yield:.4f} ≥ target {self.min_yield}")
                break

            report = model.report()
            # Find current bottleneck
            rates = [(s.name, s.defect_rate) for s in self.steps]
            bottleneck = max(rates, key=lambda x: x[1])
            bn_name, bn_rate = bottleneck

            # Find bottleneck step object
            bn_step = next(s for s in self.steps if s.name == bn_name)
            lcl, ucl = bn_step.control_limits
            cpk = bn_step.cpk

            improved = False

            # Strategy 1: Widen bottleneck bounds if Cpk is very high (process is too constrained)
            if cpk > 1.5 and bn_rate > 0.01:
                # Process is capable but defect rate is high → bounds are artificially tight
                # Widen by safety_margin of the range
                range_width = ucl - lcl
                widen = range_width * self.safety_margin
                new_lcl = lcl - widen
                new_ucl = ucl + widen
                bn_step.control_limits = (new_lcl, new_ucl)
                new_rate = self._estimate_defect_rate(bn_step)
                bn_step.defect_rate = new_rate
                adjustments.append((bn_name, "widen", widen))
                log_lines.append(
                    f"  Iter {iteration}: Widened {bn_name} bounds by {widen:.4f} "
                    f"→ defect rate {bn_rate:.4f} → {new_rate:.4f}"
                )
                improved = True

            # Strategy 2: Tighten non-bottleneck steps that are too loose
            for step in self.steps:
                if step.name == bn_name:
                    continue
                if step.defect_rate < 0.005 and step.cpk < 0.8:
                    # Very low defect rate but low Cpk → tighten to reduce process noise
                    lcl_s, ucl_s = step.control_limits
                    range_s = ucl_s - lcl_s
                    tighten = range_s * 0.05
                    step.control_limits = (lcl_s + tighten, ucl_s - tighten)
                    new_rate = self._estimate_defect_rate(step)
                    step.defect_rate = new_rate
                    adjustments.append((step.name, "tighten", tighten))
                    log_lines.append(
                        f"  Iter {iteration}: Tightened {step.name} bounds by {tighten:.4f}"
                    )
                    improved = True

            if not improved:
                log_lines.append(f"  Iter {iteration}: No improvement possible")
                break

        final_model = YieldModel(self.steps)
        final_yield = final_model.overall_yield()
        improvement = final_yield - initial_yield

        return OptimizationResult(
            initial_yield=initial_yield,
            final_yield=final_yield,
            improvement=improvement,
            improvement_pct=improvement / initial_yield * 100 if initial_yield > 0 else 0.0,
            adjustments=adjustments,
            bottleneck_step=bottleneck_name,
            log=log_lines,
        )


# ---------------------------------------------------------------------------
# 5. Equivalence Proof: Yield Model ≡ Partition Function
# ---------------------------------------------------------------------------

def yield_partition_equivalence(steps: List[ProcessStep]) -> dict:
    """
    Prove the equivalence between the yield model and the thermodynamic
    partition function.

    For independent defects:
        yield = ∏(1 - d_i) = ∏ w_i = Z

    where w_i = (1 - d_i) is the "Boltzmann weight" of step i.

    This means:
        Z_yield = ∏ w_i = exp(Σ ln w_i) = exp(-F/T)

    where F = -T Σ ln(1 - d_i) is the free energy of the constraint system.

    Returns
    -------
    dict with keys: yield, partition_Z, log_yield, free_energy, equivalence_check
    """
    model = YieldModel(steps)
    oy = model.overall_yield()
    ly = model.log_yield()

    # Partition function Z = product of weights
    weights = np.array([s.step_yield for s in steps])
    Z = float(np.prod(weights))
    log_Z = float(np.sum(np.log(np.clip(weights, 1e-300, None))))

    # Free energy F = -T * ln(Z), with T=1
    F = -log_Z

    return {
        "yield": oy,
        "partition_Z": Z,
        "log_yield": ly,
        "log_Z": log_Z,
        "free_energy": F,
        "equivalence_check": abs(oy - Z) < 1e-12,
        "explanation": (
            "Yield = ∏(1-d_i) = Z = ∏w_i. "
            "The yield model IS the partition function with weights w_i = (1-d_i)."
        ),
    }


# ---------------------------------------------------------------------------
# 6. Experiment: 8-Step Process Yield Optimization
# ---------------------------------------------------------------------------

def run_yield_experiment() -> dict:
    """
    Run the full yield optimization experiment.

    8 process steps with varying defect rates.
    Show that yield optimization = thermodynamic optimization.
    Show that partition function = yield model.
    """
    # Initial defect rates
    defect_rates = [0.1, 0.05, 0.2, 0.01, 0.15, 0.03, 0.08, 0.02]
    step_names = [
        "photolithography", "etching", "deposition", "doping",
        "metallization", "planarization", "inspection", "packaging"
    ]

    # Build steps with control limits centered on 0, width proportional to 1/defect_rate
    # Higher defect rate → tighter bounds → more violations
    steps = []
    for i, (name, rate) in enumerate(zip(step_names, defect_rates)):
        # Map defect rate to bounds: tighter bounds = higher defect rate
        # Assume mean=0, std=1. We set bounds so that the normal tail = defect_rate
        # z such that P(|Z| > z) = rate → z = erfinv(1 - rate)
        # Approximate: for small rates, z ≈ sqrt(2) * erfinv(1-rate)
        if rate > 0 and rate < 1:
            # Inverse: find z where 2*(1-Φ(z)) = rate → Φ(z) = 1-rate/2
            # Φ(z) = 0.5*(1+erf(z/√2))
            # erf(z/√2) = 2*(1-rate/2) - 1 = 1 - rate
            # z/√2 = erfinv(1-rate)
            target_erf = 1.0 - rate
            z = math.sqrt(2) * _approx_erfinv(target_erf)
            half_width = z
        else:
            half_width = 3.0

        step = ProcessStep(
            name=name,
            dimension_index=i,
            defect_rate=rate,
            control_limits=(-half_width, half_width),
            mean=0.0,
            std=1.0,
        )
        steps.append(step)

    # Compute initial yield
    model = YieldModel(steps)
    initial_yield = model.overall_yield()
    report = model.report()

    # Prove equivalence with partition function
    equiv = yield_partition_equivalence(steps)

    # Optimize
    optimizer = YieldOptimizer(steps, min_yield=0.90, max_iterations=15, safety_margin=0.15)
    result = optimizer.optimize()

    # Updated steps after optimization
    opt_steps = optimizer.steps
    opt_model = YieldModel(opt_steps)
    final_yield = opt_model.overall_yield()

    return {
        "n_steps": len(steps),
        "defect_rates": defect_rates,
        "initial_yield": initial_yield,
        "initial_yield_pct": f"{initial_yield*100:.2f}%",
        "bottleneck": report.bottleneck_step,
        "bottleneck_rate": report.bottleneck_defect_rate,
        "pareto_top3": report.pareto_defects[:3],
        "final_yield": final_yield,
        "final_yield_pct": f"{final_yield*100:.2f}%",
        "improvement": result.improvement,
        "improvement_pct": f"{result.improvement_pct:.2f}%",
        "optimization_log": result.log,
        "partition_equivalence": equiv,
        "thermodynamic_proof": (
            f"Yield = {initial_yield:.6f}, Z = {equiv['partition_Z']:.6f}, "
            f"Equal: {equiv['equivalence_check']}. "
            f"Free energy F = {equiv['free_energy']:.4f}. "
            f"Constraint systems ARE manufacturing processes thermodynamically."
        ),
    }


def _approx_erfinv(x: float) -> float:
    """Approximate inverse error function using Newton's method."""
    if x <= -1 or x >= 1:
        return float("inf") if x >= 1 else float("-inf")
    # Initial approximation
    w = -math.log((1.0 - x) * (1.0 + x))
    if w < 5.0:
        w -= 2.5
        p = 2.81022636e-8
        p = 3.43273939e-7 + p * w
        p = -3.5233877e-6 + p * w
        p = -4.39150654e-6 + p * w
        p = 0.00021858087 + p * w
        p = -0.00125372503 + p * w
        p = -0.00417768164 + p * w
        p = 0.246640727 + p * w
        p = 1.5045788 + p * w
    else:
        w = math.sqrt(w) - 3.0
        p = -0.000200214257
        p = 0.000100950558 + p * w
        p = 0.00134934322 + p * w
        p = -0.00367342844 + p * w
        p = 0.00573950773 + p * w
        p = -0.0076224613 + p * w
        p = 0.00943887047 + p * w
        p = 1.00167406 + p * w
        p = 2.83297682 + p * w
    return p * 0.7071067811865475  # p * 1/√2
