"""
FLUX Optimization Engine — Adaptive Constraint Checking
========================================================
Optimal ordering, online learning, adaptive decision trees,
batch-vs-streaming analysis, and Pareto frontiers.

Zero external dependencies beyond stdlib.
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable, Sequence
from enum import Enum


# ---------------------------------------------------------------------------
# 1. ViolationProbabilityTracker — Bayesian online estimation of p_i
# ---------------------------------------------------------------------------

@dataclass
class ConstraintStats:
    """Bayesian posterior for one constraint's violation probability."""
    name: str
    check_cost: float = 1.0  # time units to evaluate this constraint
    alpha: float = 1.0       # Beta prior successes (passes)
    beta: float = 1.0        # Beta prior failures (violations)
    total_checks: int = 0
    total_violations: int = 0

    @property
    def p_violation(self) -> float:
        """Posterior mean of violation probability."""
        return self.beta / (self.alpha + self.beta)

    @property
    def p_violation_ucb(self) -> float:
        """Upper confidence bound (UCB1-style) for exploration."""
        n = self.total_checks
        if n == 0:
            return 1.0
        return self.p_violation + math.sqrt(2.0 * math.log(max(n, 1)) / n)

    @property
    def p_violation_thompson(self) -> float:
        """Sample from Beta posterior for Thompson sampling."""
        return random.betavariate(self.beta, self.alpha)

    def observe(self, violated: bool) -> None:
        """Update posterior with observation."""
        self.total_checks += 1
        if violated:
            self.total_violations += 1
            self.beta += 1.0
        else:
            self.alpha += 1.0

    def reset(self) -> None:
        self.alpha = 1.0
        self.beta = 1.0
        self.total_checks = 0
        self.total_violations = 0


class ViolationProbabilityTracker:
    """Tracks violation probabilities for multiple constraints using Bayesian updating."""

    def __init__(self, constraint_names: List[str], costs: Optional[List[float]] = None):
        costs = costs or [1.0] * len(constraint_names)
        self.constraints: Dict[str, ConstraintStats] = {
            name: ConstraintStats(name=name, check_cost=c)
            for name, c in zip(constraint_names, costs)
        }
        self.order_history: List[List[str]] = []
        self.current_order: List[str] = list(constraint_names)

    def observe(self, name: str, violated: bool) -> None:
        """Record observation for a constraint."""
        self.constraints[name].observe(violated)

    def get_order_mean(self) -> List[str]:
        """Optimal ordering by descending violation probability × cost."""
        return self._order_by(lambda s: s.p_violation * s.check_cost, reverse=True)

    def get_order_ucb(self) -> List[str]:
        """UCB-based ordering for exploration."""
        return self._order_by(lambda s: s.p_violation_ucb * s.check_cost, reverse=True)

    def get_order_thompson(self) -> List[str]:
        """Thompson sampling ordering."""
        return self._order_by(lambda s: s.p_violation_thompson * s.check_cost, reverse=True)

    def _order_by(self, key: Callable[[ConstraintStats], float], reverse: bool = True) -> List[str]:
        ordered = sorted(self.constraints.values(), key=key, reverse=reverse)
        result = [c.name for c in ordered]
        self.current_order = result
        return result

    def convergence_error(self, true_probabilities: Dict[str, float]) -> float:
        """Mean absolute error between estimated and true violation probabilities."""
        errors = []
        for name, true_p in true_probabilities.items():
            if name in self.constraints:
                errors.append(abs(self.constraints[name].p_violation - true_p))
        return sum(errors) / len(errors) if errors else 0.0

    def ordering_spearman(self, true_probabilities: Dict[str, float]) -> float:
        """Spearman rank correlation between estimated and true ordering."""
        est_order = self.get_order_mean()
        true_order = sorted(true_probabilities.keys(),
                           key=lambda n: true_probabilities[n], reverse=True)

        n = len(est_order)
        if n <= 1:
            return 1.0

        est_ranks = {name: i for i, name in enumerate(est_order)}
        true_ranks = {name: i for i, name in enumerate(true_order)}

        d_sq_sum = sum((est_ranks[name] - true_ranks[name]) ** 2
                       for name in est_order)
        return 1.0 - 6.0 * d_sq_sum / (n * (n * n - 1))


# ---------------------------------------------------------------------------
# 2. OptimalOrderer — Knuth's optimal search ordering
# ---------------------------------------------------------------------------

class OptimalOrderer:
    """
    Computes optimal static checking order given violation probabilities.

    Theorem (Optimal Stopping for Constraints):
    If constraint i has violation probability p_i and check cost c_i,
    the optimal order (minimizing expected total checking time) is:

        Sort by c_i / p_i in ascending order
        (equivalently: sort by p_i / c_i in descending order)

    Proof sketch:
    Expected cost of checking in order σ = Σ_j c_{σ(j)} × Π_{k<j}(1 - p_{σ(k)})
    Minimizing this is equivalent to sorting by c_i/p_i (exchange argument).
    """

    def __init__(self, probabilities: Dict[str, float],
                 costs: Optional[Dict[str, float]] = None):
        self.probabilities = probabilities
        self.costs = costs or {k: 1.0 for k in probabilities}

    def optimal_order(self) -> List[str]:
        """Sort constraints by c_i/p_i ascending (or p_i/c_i descending)."""
        def sort_key(name: str) -> float:
            p = max(self.probabilities.get(name, 0.001), 1e-10)
            c = self.costs.get(name, 1.0)
            return c / p  # ascending = cheapest violations first
        return sorted(self.probabilities.keys(), key=sort_key)

    def expected_cost(self, order: List[str]) -> float:
        """Expected checking cost for a given ordering."""
        cost = 0.0
        survival = 1.0  # probability we reach this constraint
        for name in order:
            c = self.costs.get(name, 1.0)
            p = self.probabilities.get(name, 0.0)
            cost += survival * c
            survival *= (1.0 - p)
        return cost

    def optimal_cost(self) -> float:
        return self.expected_cost(self.optimal_order())

    def worst_cost(self) -> float:
        """Cost of the worst possible ordering."""
        return self.expected_cost(list(reversed(self.optimal_order())))

    def speedup_ratio(self) -> float:
        """Ratio: worst-case cost / optimal cost."""
        opt = self.optimal_cost()
        worst = self.worst_cost()
        return worst / opt if opt > 0 else float('inf')

    def cost_breakdown(self, order: List[str]) -> List[Dict]:
        """Detailed cost breakdown per constraint in order."""
        result = []
        survival = 1.0
        for name in order:
            c = self.costs.get(name, 1.0)
            p = self.probabilities.get(name, 0.0)
            result.append({
                'name': name,
                'cost': c,
                'p_violation': p,
                'marginal_cost': survival * c,
                'survival_prob': survival,
            })
            survival *= (1.0 - p)
        return result


# ---------------------------------------------------------------------------
# 3. AdaptiveDecisionTree — optimal check-once decision tree
# ---------------------------------------------------------------------------

class AdaptiveDecisionTree:
    """
    Builds an optimal decision tree for constraint checking.

    Strategy: check constraints in order, stop on first violation.
    This is optimal when:
    - Constraints are independent (or approximately so)
    - We only need to find ONE violation (any violation)
    - Costs are additive

    The optimal tree is a simple ordered chain (not a branching tree)
    because we only have binary outcomes (pass/fail) per constraint.
    """

    def __init__(self, tracker: ViolationProbabilityTracker):
        self.tracker = tracker
        self.check_count = 0

    def build_tree(self) -> List[Dict]:
        """Build decision tree as ordered list of constraint checks."""
        order = self.tracker.get_order_mean()
        tree = []
        for i, name in enumerate(order):
            stats = self.tracker.constraints[name]
            tree.append({
                'step': i,
                'constraint': name,
                'p_violation': stats.p_violation,
                'cost': stats.check_cost,
                'stop_on_violation': True,
                'cumulative_cost_if_all_pass': sum(
                    self.tracker.constraints[n].check_cost for n in order[:i+1]
                ),
            })
        return tree

    def check_value(self, value: float,
                    constraint_fns: Dict[str, Callable[[float], bool]]) -> Tuple[bool, float, Optional[str]]:
        """
        Check a value against constraints in adaptive order.
        Returns (passed, total_cost, first_violation).
        """
        order = self.tracker.get_order_mean()
        total_cost = 0.0
        self.check_count += 1

        for name in order:
            stats = self.tracker.constraints[name]
            cost = stats.check_cost
            total_cost += cost

            if name in constraint_fns:
                violated = constraint_fns[name](value)
                self.tracker.observe(name, violated)

                if violated:
                    return False, total_cost, name

        return True, total_cost, None

    def expected_depth(self) -> float:
        """Expected number of constraints checked before stopping."""
        order = self.tracker.get_order_mean()
        expected = 0.0
        survival = 1.0
        for i, name in enumerate(order):
            p = self.tracker.constraints[name].p_violation
            expected += survival  # we check this one
            survival *= (1.0 - p)
        return expected

    def pruning_rate(self) -> float:
        """Fraction of checks saved vs checking all constraints."""
        n = len(self.tracker.constraints)
        if n == 0:
            return 0.0
        return 1.0 - self.expected_depth() / n


# ---------------------------------------------------------------------------
# 4. BatchVsStreamingOptimizer — cache-aware strategy selection
# ---------------------------------------------------------------------------

class CheckStrategy(Enum):
    BATCH = "batch"         # All values × constraint 1, then all × constraint 2, ...
    STREAMING = "streaming"  # Value 1 × all constraints, then value 2 × all constraints, ...
    ADAPTIVE = "adaptive"    # Batch until cache pressure, then switch


@dataclass
class CacheModel:
    """Simple cache behavior model."""
    cache_size: int = 256       # number of cache lines
    line_size: int = 64         # bytes per cache line
    value_size: int = 4         # bytes per value (e.g., float32)
    constraint_size: int = 32   # bytes per constraint state
    cache_miss_penalty: float = 10.0  # miss cost in time units
    cache_hit_cost: float = 1.0      # hit cost in time units

    def working_set_values(self, n_values: int) -> int:
        """Cache lines needed for n values."""
        total_bytes = n_values * self.value_size
        return math.ceil(total_bytes / self.line_size)

    def working_set_constraints(self, n_constraints: int) -> int:
        """Cache lines needed for n constraint states."""
        total_bytes = n_constraints * self.constraint_size
        return math.ceil(total_bytes / self.line_size)

    def fits_in_cache(self, n_lines: int) -> bool:
        return n_lines <= self.cache_size


class BatchVsStreamingOptimizer:
    """
    Models cache behavior to select optimal checking strategy.

    Key insight:
    - BATCH is optimal when: value array fits in cache, constraints don't
      (iterate values in inner loop — values stay hot in cache)
    - STREAMING is optimal when: constraint states fit in cache, values don't
      (iterate constraints in inner loop — constraints stay hot)
    - With early stopping: streaming is preferred because we skip values
      that fail early constraints (amortizes miss cost)
    """

    def __init__(self, cache: Optional[CacheModel] = None):
        self.cache = cache or CacheModel()

    def model_batch_cost(self, n_values: int, n_constraints: int,
                         violation_probs: Optional[List[float]] = None,
                         costs: Optional[List[float]] = None) -> Dict:
        """Model batch strategy cost."""
        costs = costs or [1.0] * n_constraints
        violation_probs = violation_probs or [0.5] * n_constraints

        value_lines = self.cache.working_set_values(n_values)
        constraint_lines = self.cache.working_set_constraints(n_constraints)

        values_fit = self.cache.fits_in_cache(value_lines)

        # For each constraint pass:
        # - Load all values (one-time if they fit in cache)
        # - Load constraint state (one miss per constraint pass)
        total_cost = 0.0
        survival = 1.0

        for i in range(n_constraints):
            c = costs[i]
            p = violation_probs[i] if i < len(violation_probs) else 0.5

            # Value access pattern: sequential → cache-friendly after first miss
            if values_fit:
                value_access_cost = n_values * self.cache.cache_hit_cost
            else:
                # Values don't fit: cache thrashing
                value_access_cost = n_values * self.cache.cache_miss_penalty * 0.3

            # Constraint state: loaded once per pass
            constraint_access_cost = self.cache.cache_miss_penalty + \
                max(0, n_values - 1) * self.cache.cache_hit_cost

            # Only check values that haven't been eliminated yet
            n_surviving = int(n_values * survival)
            pass_cost = (value_access_cost + constraint_access_cost) * c
            total_cost += pass_cost * survival  # weight by fraction surviving
            survival *= (1.0 - p)

        return {
            'strategy': 'batch',
            'total_cost': total_cost,
            'values_fit_cache': values_fit,
            'value_lines': value_lines,
            'constraint_lines': constraint_lines,
        }

    def model_streaming_cost(self, n_values: int, n_constraints: int,
                             violation_probs: Optional[List[float]] = None,
                             costs: Optional[List[float]] = None) -> Dict:
        """Model streaming strategy cost."""
        costs = costs or [1.0] * n_constraints
        violation_probs = violation_probs or [0.5] * n_constraints

        value_lines = self.cache.working_set_values(1)  # one value at a time
        constraint_lines = self.cache.working_set_constraints(n_constraints)

        constraints_fit = self.cache.fits_in_cache(constraint_lines)

        total_cost = 0.0
        # With early stopping, expected checks per value
        for val_idx in range(n_values):
            val_cost = 0.0
            survival = 1.0  # for this value, do we proceed to next constraint?

            for i in range(n_constraints):
                c = costs[i]
                p = violation_probs[i] if i < len(violation_probs) else 0.5

                # Value: already in register (streaming)
                value_access_cost = self.cache.cache_hit_cost

                # Constraint: sequential access → cache-friendly if fit
                if constraints_fit:
                    constraint_access_cost = self.cache.cache_hit_cost
                else:
                    constraint_access_cost = self.cache.cache_miss_penalty

                val_cost += (value_access_cost + constraint_access_cost) * c

                # Early stopping: only continue if passed so far
                if random.random() < p:  # violated — stop checking this value
                    break

            total_cost += val_cost

        # Analytical expected cost
        expected_checks_per_value = 0.0
        survival = 1.0
        for i in range(n_constraints):
            c = costs[i]
            p = violation_probs[i] if i < len(violation_probs) else 0.5
            expected_checks_per_value += c * survival
            survival *= (1.0 - p)

        if constraints_fit:
            analytical_cost = n_values * expected_checks_per_value * self.cache.cache_hit_cost
        else:
            analytical_cost = n_values * expected_checks_per_value * \
                (self.cache.cache_hit_cost + self.cache.cache_miss_penalty / n_constraints)

        return {
            'strategy': 'streaming',
            'analytical_cost': analytical_cost,
            'constraints_fit_cache': constraints_fit,
            'value_lines': value_lines,
            'constraint_lines': constraint_lines,
            'expected_checks_per_value': expected_checks_per_value,
        }

    def recommend(self, n_values: int, n_constraints: int,
                  violation_probs: Optional[List[float]] = None,
                  costs: Optional[List[float]] = None) -> Dict:
        """Recommend optimal strategy."""
        batch = self.model_batch_cost(n_values, n_constraints, violation_probs, costs)
        stream = self.model_streaming_cost(n_values, n_constraints, violation_probs, costs)

        batch_cost = batch['total_cost']
        stream_cost = stream['analytical_cost']

        if batch_cost < stream_cost * 0.9:
            strategy = CheckStrategy.BATCH
            reason = "Values fit in cache, batch minimizes constraint state loads"
        elif stream_cost < batch_cost * 0.9:
            strategy = CheckStrategy.STREAMING
            reason = "Early stopping saves more than cache re-warming costs"
        else:
            strategy = CheckStrategy.ADAPTIVE
            reason = "Costs comparable; use streaming with early-exit optimization"

        return {
            'recommended': strategy.value,
            'reason': reason,
            'batch_cost': batch_cost,
            'streaming_cost': stream_cost,
            'speedup': max(batch_cost, stream_cost) / max(min(batch_cost, stream_cost), 1e-10),
            'batch_details': batch,
            'streaming_details': stream,
        }


# ---------------------------------------------------------------------------
# 5. ParetoFrontier — false-negative vs time tradeoff
# ---------------------------------------------------------------------------

@dataclass
class ParetoPoint:
    """A point on the Pareto frontier."""
    n_constraints_checked: int
    constraint_names: List[str]
    expected_time: float
    false_negative_rate: float
    detection_rate: float  # 1 - FNR

    @property
    def time_per_detection(self) -> float:
        if self.detection_rate <= 0:
            return float('inf')
        return self.expected_time / self.detection_rate


class ParetoFrontier:
    """
    Computes the Pareto frontier for false-negative rate vs checking time.

    The fundamental tradeoff:
    - Check MORE constraints → lower FNR but more time
    - Check FEWER constraints → higher FNR but less time
    - The Pareto frontier is the set of non-dominated points

    Analytical result:
    For independent constraints with violation probabilities p_1, ..., p_n
    and costs c_1, ..., c_n:

    If we check the k most "efficient" constraints (sorted by p_i/c_i descending),
    the FNR and expected time are:

        FNR(k) = Π_{i=1}^{k} (1 - p_i) × Π_{i=k+1}^{n} 1  -- NO, this is wrong

    Actually:
    - A false negative occurs when a value has violations in UNCHECKED constraints
    - FNR(k) = P(violation only in unchecked constraints | at least one violation)
    - For the full check (k=n): FNR = 0
    - For no check (k=0): FNR = 1 (we detect nothing... well, we reject nothing)

    More precisely:
    - We CHECK k constraints
    - A value passes if it passes ALL k checked constraints
    - False negative = value passes checked k, but would fail some unchecked constraint
    - FNR(k) = P(passes first k) × P(fails some of remaining n-k) / P(any violation)
    """

    def __init__(self, probabilities: Dict[str, float],
                 costs: Optional[Dict[str, float]] = None):
        self.probabilities = probabilities
        self.costs = costs or {k: 1.0 for k in probabilities}
        self.names = list(probabilities.keys())
        self.n = len(self.names)

    def compute_point(self, k: int, ordered_names: Optional[List[str]] = None) -> ParetoPoint:
        """Compute Pareto point for checking first k constraints."""
        if ordered_names is None:
            # Default: check constraints with highest violation probability first
            ordered_names = sorted(self.names,
                                   key=lambda n: self.probabilities[n] / self.costs[n],
                                   reverse=True)

        checked = ordered_names[:k]
        unchecked = ordered_names[k:]

        # Expected checking time
        expected_time = 0.0
        survival = 1.0
        for name in checked:
            c = self.costs[name]
            expected_time += survival * c
            survival *= (1.0 - self.probabilities[name])

        # False negative rate
        # P(passes all checked)
        p_passes_checked = 1.0
        for name in checked:
            p_passes_checked *= (1.0 - self.probabilities[name])

        # P(fails some unchecked)
        p_fails_unchecked = 1.0
        for name in unchecked:
            p_fails_unchecked *= (1.0 - self.probabilities[name])
        p_fails_unchecked = 1.0 - p_fails_unchecked

        # FNR = P(passes checked AND fails unchecked) / P(fails any)
        p_any_violation = 1.0
        for name in self.names:
            p_any_violation *= (1.0 - self.probabilities[name])
        p_any_violation = 1.0 - p_any_violation

        if p_any_violation > 0:
            fnr = (p_passes_checked * p_fails_unchecked) / p_any_violation
        else:
            fnr = 0.0

        return ParetoPoint(
            n_constraints_checked=k,
            constraint_names=checked,
            expected_time=expected_time,
            false_negative_rate=fnr,
            detection_rate=1.0 - fnr,
        )

    def compute_frontier(self) -> List[ParetoPoint]:
        """Compute full Pareto frontier (all non-dominated points)."""
        # Order constraints by efficiency (p/c descending)
        ordered = sorted(self.names,
                        key=lambda n: self.probabilities[n] / self.costs[n],
                        reverse=True)

        # Generate all possible k values
        all_points = [self.compute_point(k, ordered) for k in range(self.n + 1)]

        # Filter to Pareto-optimal points (non-dominated)
        frontier = []
        for point in all_points:
            dominated = False
            for other in all_points:
                if other is point:
                    continue
                # other dominates point if it's better in both objectives
                if (other.expected_time <= point.expected_time and
                    other.false_negative_rate <= point.false_negative_rate and
                    (other.expected_time < point.expected_time or
                     other.false_negative_rate < point.false_negative_rate)):
                    dominated = True
                    break
            if not dominated:
                frontier.append(point)

        return sorted(frontier, key=lambda p: p.expected_time)

    def find_knee_point(self) -> ParetoPoint:
        """Find the 'knee' of the Pareto curve — best marginal return."""
        frontier = self.compute_frontier()
        if len(frontier) <= 2:
            return frontier[-1]  # full check

        # Maximize curvature: largest drop in FNR per unit time
        best_point = frontier[1]  # skip k=0 (check nothing)
        best_ratio = 0.0

        for i in range(1, len(frontier)):
            if i + 1 < len(frontier):
                # Marginal improvement
                dt = frontier[i + 1].expected_time - frontier[i].expected_time
                df = frontier[i].false_negative_rate - frontier[i + 1].false_negative_rate
                if dt > 0:
                    ratio = df / dt
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_point = frontier[i]

        return best_point

    def summary(self) -> str:
        """Human-readable summary of the Pareto frontier."""
        frontier = self.compute_frontier()
        knee = self.find_knee_point()

        lines = ["Pareto Frontier: FNR vs Checking Time", "=" * 50]
        for p in frontier:
            marker = " ← knee" if p is knee else ""
            lines.append(
                f"  k={p.n_constraints_checked:2d} | "
                f"time={p.expected_time:6.2f} | "
                f"FNR={p.false_negative_rate:.4f} | "
                f"detection={p.detection_rate:.4f}{marker}"
            )
        lines.append(f"\nKnee point: check {knee.n_constraints_checked} constraints "
                     f"(FNR={knee.false_negative_rate:.4f}, time={knee.expected_time:.2f})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience: run a full adaptive optimization experiment
# ---------------------------------------------------------------------------

def run_adaptive_experiment(
    constraint_names: List[str],
    true_probabilities: Dict[str, float],
    check_fns: Dict[str, Callable[[float], bool]],
    n_values: int = 100_000,
    costs: Optional[Dict[str, float]] = None,
) -> Dict:
    """
    Full experiment: start with unknown probabilities, learn online.
    """
    costs_list = [costs.get(n, 1.0) for n in constraint_names] if costs else None

    tracker = ViolationProbabilityTracker(constraint_names, costs_list)
    tree = AdaptiveDecisionTree(tracker)

    # Static orderers for comparison
    static_worst = OptimalOrderer(
        {n: true_probabilities[n] for n in constraint_names}, costs)
    worst_order = list(reversed(static_worst.optimal_order()))
    static_best = OptimalOrderer(
        {n: true_probabilities[n] for n in constraint_names}, costs)
    best_order = static_best.optimal_order()

    # Tracking
    adaptive_costs = []
    static_best_costs = []
    static_worst_costs = []
    convergence_errors = []
    rank_correlations = []

    sample_interval = max(1, n_values // 100)

    for i in range(n_values):
        value = random.uniform(-100, 100)

        # Adaptive check
        _, adaptive_cost, _ = tree.check_value(value, check_fns)
        adaptive_costs.append(adaptive_cost)

        # Static best check
        _, best_cost, _ = _check_static(value, best_order, check_fns, costs)
        static_best_costs.append(best_cost)

        # Static worst check
        _, worst_cost, _ = _check_static(value, worst_order, check_fns, costs)
        static_worst_costs.append(worst_cost)

        if i % sample_interval == 0 and i > 0:
            convergence_errors.append(tracker.convergence_error(true_probabilities))
            rank_correlations.append(tracker.ordering_spearman(true_probabilities))

    # Final results
    return {
        'n_values': n_values,
        'avg_adaptive_cost': sum(adaptive_costs) / len(adaptive_costs),
        'avg_static_best_cost': sum(static_best_costs) / len(static_best_costs),
        'avg_static_worst_cost': sum(static_worst_costs) / len(static_worst_costs),
        'final_convergence_error': tracker.convergence_error(true_probabilities),
        'final_rank_correlation': tracker.ordering_spearman(true_probabilities),
        'convergence_errors': convergence_errors,
        'rank_correlations': rank_correlations,
        'estimated_probabilities': {n: tracker.constraints[n].p_violation
                                    for n in constraint_names},
        'true_probabilities': true_probabilities,
        'false_negatives_changed': False,  # reordering never changes FN rate
    }


def _check_static(value: float, order: List[str],
                  check_fns: Dict[str, Callable[[float], bool]],
                  costs: Optional[Dict[str, float]] = None) -> Tuple[bool, float, Optional[str]]:
    """Check value against constraints in fixed order."""
    costs = costs or {}
    total_cost = 0.0
    for name in order:
        c = costs.get(name, 1.0)
        total_cost += c
        if name in check_fns and check_fns[name](value):
            return False, total_cost, name
    return True, total_cost, None


# ---------------------------------------------------------------------------
# Main: quick demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("FLUX Optimization Engine — Demo")
    print("=" * 60)

    # Example: 6 constraints with different violation probabilities
    names = ["range_check", "type_check", "bounds_check", "format_check",
             "dependency_check", "policy_check"]
    true_p = {
        "range_check": 0.30,
        "type_check": 0.02,
        "bounds_check": 0.15,
        "format_check": 0.40,
        "dependency_check": 0.05,
        "policy_check": 0.10,
    }
    costs = {
        "range_check": 1.0,
        "type_check": 0.5,
        "bounds_check": 1.0,
        "format_check": 2.0,
        "dependency_check": 3.0,
        "policy_check": 1.5,
    }

    # 1. Optimal ordering
    print("\n--- Optimal Ordering ---")
    orderer = OptimalOrderer(true_p, costs)
    opt_order = orderer.optimal_order()
    print(f"Optimal order: {opt_order}")
    print(f"Optimal cost:  {orderer.optimal_cost():.3f}")
    print(f"Worst cost:    {orderer.worst_cost():.3f}")
    print(f"Speedup:       {orderer.speedup_ratio():.2f}×")

    # 2. Pareto frontier
    print("\n--- Pareto Frontier ---")
    pareto = ParetoFrontier(true_p, costs)
    print(pareto.summary())

    # 3. Batch vs Streaming
    print("\n--- Batch vs Streaming ---")
    bvso = BatchVsStreamingOptimizer()
    rec = bvso.recommend(10_000, 6, list(true_p.values()), list(costs.values()))
    print(f"Recommended: {rec['recommended']}")
    print(f"Reason: {rec['reason']}")
    print(f"Speedup: {rec['speedup']:.2f}×")

    # 4. Adaptive learning (quick demo)
    print("\n--- Adaptive Learning (10K values) ---")
    check_fns = {
        "range_check": lambda v: v < -50 or v > 50,
        "type_check": lambda v: isinstance(v, str),
        "bounds_check": lambda v: abs(v) > 80,
        "format_check": lambda v: v > 30 or v < -30,
        "dependency_check": lambda v: abs(v) > 90,
        "policy_check": lambda v: v > 60,
    }
    result = run_adaptive_experiment(names, true_p, check_fns, n_values=10_000, costs=costs)
    print(f"Avg adaptive cost:  {result['avg_adaptive_cost']:.3f}")
    print(f"Avg static best:    {result['avg_static_best_cost']:.3f}")
    print(f"Avg static worst:   {result['avg_static_worst_cost']:.3f}")
    print(f"Convergence error:  {result['final_convergence_error']:.4f}")
    print(f"Rank correlation:   {result['final_rank_correlation']:.4f}")
    print(f"\nEstimated vs True probabilities:")
    for n in names:
        est = result['estimated_probabilities'][n]
        true = result['true_probabilities'][n]
        print(f"  {n:20s}: est={est:.3f}  true={true:.3f}")
