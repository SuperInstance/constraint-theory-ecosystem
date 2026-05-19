"""
flux_swiss_cheese.py — Swiss Cheese Safety Model for Constraint Systems

Cross-industry paradigm borrowing from aviation safety (James Reason, 1990):
aviation uses multiple independent defense layers (checklists, redundancies,
ATC procedures). A violation only causes harm if it passes through ALL layers.
Each sediment layer is a cheese slice with holes. The system is safe if the
holes don't align.

Core theorems:
  1. A violation escapes only if ALL layers miss it.
  2. Overall failure rate = product of individual failure rates (if independent).
  3. Alignment (shared blind spots) is the real enemy, not individual failure rates.
  4. Diversity optimization can drive alignment to zero.

Connection to fleet:
  - Each fleet agent is a safety layer with different blind spots
  - Fleet coordination = minimize hole alignment
  - The shadowgap IS the aligned holes
  - Accumulated correctness = adding layers until alignment = 0

Dependencies: numpy only.
Forgemaster ⚒️ — 2026-05-19
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

import numpy as np


# =============================================================================
# 1. SafetyLayer — Independent defense layer
# =============================================================================

@dataclass
class LayerResult:
    """Result from a single safety layer checking a value."""
    layer_name: str
    passed: bool                  # Did this layer pass the value?
    violations: np.ndarray        # shape (D,), bool — which dimensions flagged
    checked_dims: np.ndarray      # shape (D,), bool — which dimensions were covered
    confidence: float             # 0..1, how confident in the result


@dataclass
class SafetyLayer:
    """
    An independent defense layer in the Swiss Cheese model.

    Each layer has:
    - A checking function that evaluates inputs
    - An estimated failure probability (hole size)
    - Coverage: which constraint dimensions it checks
    - Blind spots: dimensions it does NOT check
    """
    name: str
    check_fn: Callable[[np.ndarray], Tuple[bool, np.ndarray, np.ndarray]]
    failure_prob: float            # estimated P(miss | violation exists)
    coverage: FrozenSet[int]       # dimensions this layer checks
    blind_spots: FrozenSet[int]    # dimensions this layer DOESN'T check

    @classmethod
    def create(
        cls,
        name: str,
        check_fn: Callable[[np.ndarray], Tuple[bool, np.ndarray, np.ndarray]],
        n_dims: int,
        blind_spots: Set[int],
        failure_prob: float = 0.1,
    ) -> "SafetyLayer":
        """Create a layer with explicit blind spots. Coverage = complement of blind_spots."""
        blind = frozenset(blind_spots)
        covered = frozenset(range(n_dims)) - blind
        return cls(
            name=name,
            check_fn=check_fn,
            failure_prob=failure_prob,
            coverage=covered,
            blind_spots=blind,
        )

    def check(self, value: np.ndarray) -> LayerResult:
        """Run this layer's check on a value. Returns LayerResult."""
        passed, violations, checked = self.check_fn(value)
        n_dims = len(self.coverage | self.blind_spots)
        full_checked = np.zeros(n_dims, dtype=bool)
        full_violations = np.zeros(n_dims, dtype=bool)
        for d in self.coverage:
            full_checked[d] = True
            full_violations[d] = violations[d] if d < len(violations) else False
        confidence = 1.0 - self.failure_prob if passed else self.failure_prob
        return LayerResult(
            layer_name=self.name,
            passed=passed,
            violations=full_violations,
            checked_dims=full_checked,
            confidence=confidence,
        )


# =============================================================================
# 2. SwissCheeseModel — Multiple independent layers
# =============================================================================

@dataclass
class CombinedResult:
    """Result from running all layers through the Swiss Cheese model."""
    passed: bool                   # Overall: passed if ANY layer caught it
    layer_results: List[LayerResult]
    n_layers: int
    n_caught_by: int               # How many layers caught the violation
    escape_probability: float      # Product of failure_probs for layers that missed
    overall_failure_rate: float    # Theoretical failure rate of the full stack


class SwissCheeseModel:
    """
    Multiple independent defense layers. A violation passes through only
    if ALL layers miss it (all holes align).

    Overall failure rate = product of individual failure rates (independence assumption).
    """

    def __init__(self, name: str = "swiss_cheese"):
        self.name = name
        self.layers: List[SafetyLayer] = []

    def add_layer(self, layer: SafetyLayer) -> "SwissCheeseModel":
        self.layers.append(layer)
        return self

    @property
    def n_layers(self) -> int:
        return len(self.layers)

    @property
    def overall_failure_rate(self) -> float:
        """Product of individual failure rates. Only valid if layers are independent."""
        if not self.layers:
            return 1.0
        return float(np.prod([l.failure_prob for l in self.layers]))

    def check(self, value: np.ndarray) -> CombinedResult:
        """
        Run ALL layers against a value.

        A violation ESCAPES only if ALL layers miss it (pass=True).
        If any layer catches it (pass=False), the system catches it.
        """
        results = []
        n_caught = 0

        for layer in self.layers:
            r = layer.check(value)
            results.append(r)
            if not r.passed:
                n_caught += 1

        # System passes only if ALL layers pass (no layer caught anything)
        overall_passed = all(r.passed for r in results)

        # Escape probability: product of failure_probs of layers that passed
        # (these are the layers that didn't catch anything)
        miss_probs = [self.layers[i].failure_prob for i, r in enumerate(results) if r.passed]
        escape_prob = float(np.prod(miss_probs)) if miss_probs else 1.0

        return CombinedResult(
            passed=overall_passed,
            layer_results=results,
            n_layers=len(self.layers),
            n_caught_by=n_caught,
            escape_probability=escape_prob,
            overall_failure_rate=self.overall_failure_rate,
        )

    def batch_check(self, values: np.ndarray) -> List[CombinedResult]:
        """Check multiple values. values shape: (N, D)."""
        return [self.check(values[i]) for i in range(len(values))]


# =============================================================================
# 3. AlignmentDetector — Detect when holes align
# =============================================================================

@dataclass
class AlignmentReport:
    """Report on blind-spot alignment across layers."""
    n_layers: int
    n_dims: int
    dim_coverage: Dict[int, int]          # dim -> how many layers cover it
    aligned_dims: List[int]               # dims where ALL layers are blind
    alignment_fraction: float             # fraction of dims fully uncovered
    redundancy_per_dim: Dict[int, int]    # dim -> number of covering layers
    min_redundancy: int                   # minimum coverage across all dims
    safe: bool                            # True if no aligned dims


class AlignmentDetector:
    """
    Detect when holes (blind spots) align across layers.

    Alignment = fraction of dimensions where ALL layers have blind spots.
    High alignment = dangerous (holes line up, violations slip through).
    Low alignment = safe (diverse coverage, every dim checked by someone).
    """

    def __init__(self, n_dims: int):
        self.n_dims = n_dims

    def analyze(self, layers: List[SafetyLayer]) -> AlignmentReport:
        """Compute alignment across layers."""
        dim_coverage = {}
        for d in range(self.n_dims):
            count = sum(1 for l in layers if d in l.coverage)
            dim_coverage[d] = count

        aligned = [d for d in range(self.n_dims) if dim_coverage[d] == 0]
        alignment_frac = len(aligned) / self.n_dims if self.n_dims > 0 else 0.0
        min_red = min(dim_coverage.values()) if dim_coverage else 0

        return AlignmentReport(
            n_layers=len(layers),
            n_dims=self.n_dims,
            dim_coverage=dim_coverage,
            aligned_dims=aligned,
            alignment_fraction=alignment_frac,
            redundancy_per_dim=dim_coverage,
            min_redundancy=min_red,
            safe=len(aligned) == 0,
        )

    def pairwise_alignment(self, layers: List[SafetyLayer]) -> np.ndarray:
        """
        Compute pairwise alignment (shared blind spots) between all layer pairs.
        Returns matrix shape (n_layers, n_layers).
        Entry (i,j) = fraction of dims where both i and j are blind.
        """
        n = len(layers)
        mat = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                shared = layers[i].blind_spots & layers[j].blind_spots
                mat[i, j] = len(shared) / self.n_dims if self.n_dims > 0 else 0.0
        return mat


# =============================================================================
# 4. DiversityOptimizer — Optimize layer diversity
# =============================================================================

@dataclass
class OptimizationResult:
    """Result of diversity optimization."""
    selected_layers: List[SafetyLayer]
    alignment: AlignmentReport
    improvement: float   # reduction in alignment_fraction vs original set


class DiversityOptimizer:
    """
    Optimize layer selection to MINIMIZE blind-spot alignment.

    This is a set cover problem: we want to choose layers such that every
    dimension is covered by at least one layer (ideally multiple).

    The optimal fleet has ZERO alignment: every dimension covered by at
    least one layer. Better yet: every dimension covered by >= 2 layers.
    """

    def __init__(self, n_dims: int):
        self.n_dims = n_dims
        self.detector = AlignmentDetector(n_dims)

    def greedy_cover(self, layers: List[SafetyLayer], min_redundancy: int = 1) -> List[SafetyLayer]:
        """
        Greedy set cover: pick layers that cover the most uncovered dimensions.
        Continue until all dims have >= min_redundancy coverage.
        """
        selected: List[SafetyLayer] = []
        remaining = list(layers)
        coverage_count = np.zeros(self.n_dims, dtype=int)

        while np.min(coverage_count) < min_redundancy and remaining:
            best_layer = None
            best_score = -1
            for layer in remaining:
                # How many dims does this layer cover that are still under min_redundancy?
                undercovered = sum(
                    1 for d in layer.coverage
                    if coverage_count[d] < min_redundancy
                )
                if undercovered > best_score:
                    best_score = undercovered
                    best_layer = layer

            if best_layer is None or best_score == 0:
                break

            selected.append(best_layer)
            remaining.remove(best_layer)
            for d in best_layer.coverage:
                coverage_count[d] += 1

        return selected

    def optimize(
        self,
        layers: List[SafetyLayer],
        min_redundancy: int = 1,
    ) -> OptimizationResult:
        """
        Find the optimal subset of layers that minimizes alignment.
        Returns the best subset with its alignment report.
        """
        original_report = self.detector.analyze(layers)

        # Try greedy cover first
        greedy = self.greedy_cover(layers, min_redundancy)
        greedy_report = self.detector.analyze(greedy)

        # If greedy achieves zero alignment, that's optimal
        if greedy_report.alignment_fraction == 0.0:
            improvement = original_report.alignment_fraction - greedy_report.alignment_fraction
            return OptimizationResult(
                selected_layers=greedy,
                alignment=greedy_report,
                improvement=improvement,
            )

        # Otherwise try brute-force for small layer counts
        if len(layers) <= 15:
            best = self._brute_force(layers, min_redundancy)
            if best is not None:
                return best

        # Fall back to greedy result
        improvement = original_report.alignment_fraction - greedy_report.alignment_fraction
        return OptimizationResult(
            selected_layers=greedy,
            alignment=greedy_report,
            improvement=improvement,
        )

    def _brute_force(
        self, layers: List[SafetyLayer], min_redundancy: int
    ) -> Optional[OptimizationResult]:
        """Brute-force search for small layer counts. Finds minimum set with zero alignment."""
        original_report = self.detector.analyze(layers)
        n = len(layers)

        # Try increasing subset sizes
        for size in range(1, n + 1):
            best_for_size = None
            best_align = 1.0
            for combo in itertools.combinations(layers, size):
                report = self.detector.analyze(list(combo))
                if report.min_redundancy >= min_redundancy and report.alignment_fraction < best_align:
                    best_align = report.alignment_fraction
                    best_for_size = (list(combo), report)
                if best_align == 0.0:
                    break
            if best_for_size is not None:
                combo_layers, report = best_for_size
                improvement = original_report.alignment_fraction - report.alignment_fraction
                return OptimizationResult(
                    selected_layers=combo_layers,
                    alignment=report,
                    improvement=improvement,
                )
        return None

    def design_blind_spots(
        self,
        n_layers: int,
        n_dims: int,
        blind_per_layer: int,
        min_coverage: int = 2,
    ) -> List[Set[int]]:
        """
        Design blind spots such that every dimension is covered by >= min_coverage layers.
        This is the OPTIMAL assignment: minimize alignment by construction.

        Returns list of blind_spots sets (one per layer).
        """
        assert n_layers * blind_per_layer <= n_layers * (n_dims - min_coverage), \
            f"Can't guarantee min_coverage={min_coverage} with {n_layers} layers and {blind_per_layer} blinds each"

        # Strategy: distribute blind spots round-robin, ensuring no dim gets too many
        max_blinds_per_dim = n_layers - min_coverage

        blind_spots: List[Set[int]] = [set() for _ in range(n_layers)]
        dim_blind_count = np.zeros(n_dims, dtype=int)

        # Assign blind spots to layers, spreading evenly across dimensions
        dim_idx = 0
        for layer_idx in range(n_layers):
            assigned = 0
            attempts = 0
            while assigned < blind_per_layer and attempts < n_dims * 2:
                if dim_blind_count[dim_idx] < max_blinds_per_dim and dim_idx not in blind_spots[layer_idx]:
                    blind_spots[layer_idx].add(dim_idx)
                    dim_blind_count[dim_idx] += 1
                    assigned += 1
                dim_idx = (dim_idx + 1) % n_dims
                attempts += 1

        return blind_spots


# =============================================================================
# 5. Experiments and Adversarial Testing
# =============================================================================

def make_layer_check_fn(
    lo: np.ndarray, hi: np.ndarray, blind_spots: Set[int]
) -> Callable[[np.ndarray], Tuple[bool, np.ndarray, np.ndarray]]:
    """Create a check function for a layer with given bounds and blind spots."""
    n_dims = len(lo)

    def check(value: np.ndarray) -> Tuple[bool, np.ndarray, np.ndarray]:
        violations = np.zeros(n_dims, dtype=bool)
        checked = np.ones(n_dims, dtype=bool)
        for d in blind_spots:
            checked[d] = False
        for d in range(n_dims):
            if d not in blind_spots:
                violations[d] = value[d] < lo[d] or value[d] > hi[d]
        has_violation = bool(np.any(violations))
        return (not has_violation, violations, checked)

    return check


def run_experiment(
    n_dims: int = 8,
    n_layers: int = 5,
    blind_per_layer: int = 2,   # 25% blind per layer (2 of 8)
    n_tests: int = 10_000,
    seed: int = 42,
) -> Dict:
    """
    Run the Swiss Cheese experiment:
    - Random blind spots: alignment ~ (2/8)^5 ≈ ~0.1% per-dim fully uncovered
      but across 8 dims, ~some dims will have holes aligned
    - Optimized blind spots: alignment = 0% (every dimension covered by >= 2 layers)
    - Show that optimized catches more violations than random.
    """
    rng = np.random.RandomState(seed)
    lo = np.zeros(n_dims)
    hi = np.ones(n_dims)

    # --- Random blind spots ---
    random_layers = []
    for i in range(n_layers):
        blinds = set(rng.choice(n_dims, size=blind_per_layer, replace=False))
        check_fn = make_layer_check_fn(lo, hi, blinds)
        layer = SafetyLayer.create(
            name=f"random_layer_{i}",
            check_fn=check_fn,
            n_dims=n_dims,
            blind_spots=blinds,
            failure_prob=0.1,
        )
        random_layers.append(layer)

    # --- Optimized blind spots ---
    optimizer = DiversityOptimizer(n_dims)
    optimized_blinds = optimizer.design_blind_spots(n_layers, n_dims, blind_per_layer, min_coverage=2)

    optimized_layers = []
    for i, blinds in enumerate(optimized_blinds):
        check_fn = make_layer_check_fn(lo, hi, blinds)
        layer = SafetyLayer.create(
            name=f"optimized_layer_{i}",
            check_fn=check_fn,
            n_dims=n_dims,
            blind_spots=blinds,
            failure_prob=0.1,
        )
        optimized_layers.append(layer)

    # --- Alignment analysis ---
    detector = AlignmentDetector(n_dims)
    random_report = detector.analyze(random_layers)
    optimized_report = detector.analyze(optimized_layers)

    # --- Build models ---
    random_model = SwissCheeseModel("random")
    for l in random_layers:
        random_model.add_layer(l)

    optimized_model = SwissCheeseModel("optimized")
    for l in optimized_layers:
        optimized_model.add_layer(l)

    # --- Generate adversarial test values ---
    # Mix of violations: some violate only specific dimensions
    test_values = rng.uniform(-0.5, 1.5, size=(n_tests, n_dims))  # Some will be out of [0,1]

    # Run through both models
    random_results = random_model.batch_check(test_values)
    optimized_results = optimized_model.batch_check(test_values)

    # Count ground truth violations
    gt_violated = np.any(
        (test_values < lo[np.newaxis, :]) | (test_values > hi[np.newaxis, :]),
        axis=1,
    )
    n_violated = int(np.sum(gt_violated))

    # Count misses (violation exists but model passed it)
    random_misses = sum(
        1 for i, r in enumerate(random_results)
        if gt_violated[i] and r.passed
    )
    optimized_misses = sum(
        1 for i, r in enumerate(optimized_results)
        if gt_violated[i] and r.passed
    )

    random_catch_rate = 1.0 - (random_misses / n_violated) if n_violated > 0 else 1.0
    optimized_catch_rate = 1.0 - (optimized_misses / n_violated) if n_violated > 0 else 1.0

    # Also compute: violations that hit ONLY aligned dims (the escape route)
    aligned_random = set(random_report.aligned_dims)
    aligned_optimized = set(optimized_report.aligned_dims)

    # Count violations that only touch aligned dims
    escape_via_alignment_random = 0
    escape_via_alignment_optimized = 0
    for i in range(n_tests):
        if gt_violated[i]:
            violated_dims = set(
                d for d in range(n_dims)
                if test_values[i, d] < lo[d] or test_values[i, d] > hi[d]
            )
            if violated_dims.issubset(aligned_random):
                escape_via_alignment_random += 1
            if violated_dims.issubset(aligned_optimized):
                escape_via_alignment_optimized += 1

    return {
        "n_dims": n_dims,
        "n_layers": n_layers,
        "blind_per_layer": blind_per_layer,
        "n_tests": n_tests,
        "n_violated": n_violated,
        "random_alignment": random_report.alignment_fraction,
        "optimized_alignment": optimized_report.alignment_fraction,
        "random_aligned_dims": random_report.aligned_dims,
        "optimized_aligned_dims": optimized_report.aligned_dims,
        "random_misses": random_misses,
        "optimized_misses": optimized_misses,
        "random_catch_rate": random_catch_rate,
        "optimized_catch_rate": optimized_catch_rate,
        "random_redundancy": random_report.min_redundancy,
        "optimized_redundancy": optimized_report.min_redundancy,
        "escape_via_alignment_random": escape_via_alignment_random,
        "escape_via_alignment_optimized": escape_via_alignment_optimized,
        "random_dim_coverage": random_report.dim_coverage,
        "optimized_dim_coverage": optimized_report.dim_coverage,
        "random_blinds": [l.blind_spots for l in random_layers],
        "optimized_blinds": [frozenset(b) for b in optimized_blinds],
    }


# =============================================================================
# 6. Convenience: run experiment and print results
# =============================================================================

def print_experiment(results: Dict) -> None:
    """Pretty-print experiment results."""
    print("=" * 70)
    print("SWISS CHEESE SAFETY MODEL — EXPERIMENT RESULTS")
    print("=" * 70)
    print(f"  Dimensions: {results['n_dims']}")
    print(f"  Layers:     {results['n_layers']}")
    print(f"  Blind/layer: {results['blind_per_layer']} ({100*results['blind_per_layer']/results['n_dims']:.0f}% blind)")
    print(f"  Tests:      {results['n_tests']:,}")
    print(f"  Violations: {results['n_violated']:,}")
    print()

    print("RANDOM BLIND SPOTS:")
    for i, b in enumerate(results['random_blinds']):
        print(f"  Layer {i}: blind = {{{', '.join(str(x) for x in sorted(b))}}}")
    print(f"  Alignment: {results['random_alignment']*100:.1f}% of dims fully uncovered")
    print(f"  Aligned dims: {results['random_aligned_dims']}")
    print(f"  Min redundancy: {results['random_redundancy']}")
    print(f"  Dim coverage: {results['random_dim_coverage']}")
    print(f"  Misses: {results['random_misses']} / {results['n_violated']}")
    print(f"  Catch rate: {results['random_catch_rate']*100:.2f}%")
    print(f"  Escapes via aligned holes: {results['escape_via_alignment_random']}")
    print()

    print("OPTIMIZED BLIND SPOTS:")
    for i, b in enumerate(results['optimized_blinds']):
        print(f"  Layer {i}: blind = {{{', '.join(str(x) for x in sorted(b))}}}")
    print(f"  Alignment: {results['optimized_alignment']*100:.1f}% of dims fully uncovered")
    print(f"  Aligned dims: {results['optimized_aligned_dims']}")
    print(f"  Min redundancy: {results['optimized_redundancy']}")
    print(f"  Dim coverage: {results['optimized_dim_coverage']}")
    print(f"  Misses: {results['optimized_misses']} / {results['n_violated']}")
    print(f"  Catch rate: {results['optimized_catch_rate']*100:.2f}%")
    print(f"  Escapes via aligned holes: {results['escape_via_alignment_optimized']}")
    print()

    print("CONCLUSION:")
    if results['optimized_catch_rate'] > results['random_catch_rate']:
        diff = (results['optimized_catch_rate'] - results['random_catch_rate']) * 100
        print(f"  ✅ Optimized catches {diff:.2f}% MORE violations")
    elif results['optimized_catch_rate'] == 1.0 and results['random_catch_rate'] == 1.0:
        print("  ✅ Both catch 100% — alignment gap only shows under targeted attacks")
    else:
        print(f"  ⚠️  Results need investigation")

    print(f"  Alignment reduction: {results['random_alignment']*100:.1f}% → {results['optimized_alignment']*100:.1f}%")
    print(f"  Theorem: DIVERSE sediment layers > homogeneous sediment layers")
    print("=" * 70)
