"""
Flux Immune — Affinity Maturation for Constraint Bounds

Borrowed from immunology: B cells mutate faster when affinity is LOW
(haven't found a good match yet), slower when affinity is HIGH (already close).
Plus a memory archive of elite solutions that persist across generations.

Key insight: Adaptive mutation rate is the KEY advantage over standard evolution.
- When far from optimal → large perturbations (exploration)
- When close to optimal → small perturbations (fine-tuning)
- Memory cells preserve elite solutions (long-lived B cells)
- Clonal expansion: the better the affinity, the more clones but smaller mutations

This is a DIFFERENT search strategy than flux_evolution.py:
- Evolution = fixed mutation, tournament selection
- Immune = adaptive mutation, memory archive, clonal expansion

Both produce sediment layers (corrected bounds). The fleet can use BOTH
strategies and keep whichever produces better tiles.

Part of the Constraint Theory Ecosystem.
"""

from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Core Data Structures
# ---------------------------------------------------------------------------

Bounds = List[Tuple[float, float]]  # [(lo, hi), ...] per dimension


@dataclass
class MemoryBCell:
    """An elite solution preserved across generations — a memory B cell.

    Just as the immune system keeps long-lived B cells that 'remember' past
    infections, we archive the best constraint bounds discovered so far.
    """
    bounds: Bounds
    affinity: float          # binding strength [0, 1]
    generation: int          # when this cell was created
    mutations: int = 0       # cumulative mutations to reach this state

    def age(self, current_gen: int) -> int:
        return current_gen - self.generation

    def clone(self) -> "MemoryBCell":
        return MemoryBCell(
            bounds=list(self.bounds),  # shallow copy of tuples is fine
            affinity=self.affinity,
            generation=self.generation,
            mutations=self.mutations,
        )


# ---------------------------------------------------------------------------
# Affinity Function
# ---------------------------------------------------------------------------

class AffinityFunction:
    """Measures how good constraint bounds are — the 'binding strength'.

    Affinity = 1 - (false_negative_rate + 0.1 * false_positive_rate)

    - False negatives (valid points rejected) are punished heavily
    - False positives (invalid points accepted) are punished lightly
    - Returns affinity in [0, 1]: 1 = perfect, 0 = terrible
    """

    def __init__(
        self,
        valid_points: np.ndarray,
        invalid_points: np.ndarray,
        fn_weight: float = 1.0,
        fp_weight: float = 0.1,
    ):
        """
        Args:
            valid_points: (N, D) array of points that SHOULD be inside bounds
            invalid_points: (M, D) array of points that SHOULD be outside bounds
            fn_weight: weight for false negatives (valid rejected)
            fp_weight: weight for false positives (invalid accepted)
        """
        self.valid = valid_points
        self.invalid = invalid_points
        self.fn_weight = fn_weight
        self.fp_weight = fp_weight

    def __call__(self, bounds: Bounds) -> float:
        return self.evaluate(bounds)

    def evaluate(self, bounds: Bounds) -> float:
        """Compute affinity for a set of bounds."""
        if len(self.valid) == 0 and len(self.invalid) == 0:
            return 0.5  # no data, neutral

        # False negative rate: valid points NOT inside bounds
        if len(self.valid) > 0:
            inside_valid = self._inside(self.valid, bounds)
            fn_rate = 1.0 - np.mean(inside_valid)
        else:
            fn_rate = 0.0

        # False positive rate: invalid points inside bounds
        if len(self.invalid) > 0:
            inside_invalid = self._inside(self.invalid, bounds)
            fp_rate = np.mean(inside_invalid)
        else:
            fp_rate = 0.0

        affinity = 1.0 - (self.fn_weight * fn_rate + self.fp_weight * fp_rate)
        return max(0.0, min(1.0, affinity))

    def _inside(self, points: np.ndarray, bounds: Bounds) -> np.ndarray:
        """Check which points are inside the bounds. Returns bool array."""
        D = points.shape[1]
        inside = np.ones(len(points), dtype=bool)
        for d in range(D):
            lo, hi = bounds[d]
            inside &= (points[:, d] >= lo) & (points[:, d] <= hi)
        return inside


# ---------------------------------------------------------------------------
# Clonal Expansion
# ---------------------------------------------------------------------------

class ClonalExpansion:
    """Expand elite solutions via clonal expansion.

    Take top-k memory cells, clone each N times with hypermutation.
    The better the affinity, the MORE clones but SMALLER mutations.
    This is the 'burst' part of clonal selection.
    """

    def __init__(
        self,
        n_clones: int = 10,
        clone_factor: float = 1.0,
        mutation_scale: float = 0.3,
        dims: int = 8,
    ):
        """
        Args:
            n_clones: base number of clones per elite
            clone_factor: scale factor (better affinity → more clones)
            mutation_scale: base mutation magnitude
            dims: number of constraint dimensions
        """
        self.n_clones = n_clones
        self.clone_factor = clone_factor
        self.mutation_scale = mutation_scale
        self.dims = dims

    def expand(self, elites: List[MemoryBCell], generation: int) -> List[Bounds]:
        """Clone elites with hypermutation. Better affinity → more clones, smaller mutations."""
        offspring: List[Bounds] = []

        for cell in elites:
            # Number of clones proportional to affinity
            n = max(1, int(self.n_clones * cell.affinity * self.clone_factor))

            # Mutation magnitude INVERSELY proportional to affinity
            # High affinity → small mutations (fine-tuning)
            # Low affinity → large mutations (exploration)
            scale = self.mutation_scale * (1.0 - cell.affinity + 0.1)

            for _ in range(n):
                new_bounds = self._mutate(cell.bounds, scale, cell.mutations + 1)
                offspring.append(new_bounds)

        return offspring

    def _mutate(self, bounds: Bounds, scale: float, mutations: int) -> Bounds:
        """Perturb bounds with Gaussian noise scaled by affinity."""
        new_bounds = []
        for lo, hi in bounds:
            width = hi - lo
            delta_lo = np.random.normal(0, scale * width * 0.3)
            delta_hi = np.random.normal(0, scale * width * 0.3)
            new_lo = lo + delta_lo
            new_hi = hi + delta_hi
            # Ensure lo <= hi
            if new_lo > new_hi:
                new_lo, new_hi = new_hi, new_lo
            new_bounds.append((new_lo, new_hi))
        return new_bounds


# ---------------------------------------------------------------------------
# Immune Optimizer
# ---------------------------------------------------------------------------

@dataclass
class ImmuneStats:
    """Statistics for one generation."""
    generation: int
    best_affinity: float
    mean_affinity: float
    worst_affinity: float
    memory_size: int
    mean_mutation_rate: float
    elapsed: float = 0.0


class ImmuneOptimizer:
    """Affinity maturation for constraint bounds.

    The key difference from standard evolution: mutation rate ADAPTS to
    current fitness via the affinity-dependent mutation function:
        μ(a) = μ_max * (1 - a)

    High affinity (close to optimal) → low mutation (fine-tuning)
    Low affinity (far from optimal) → high mutation (exploration)

    Memory archive preserves top-k solutions across generations.
    """

    def __init__(
        self,
        dims: int = 8,
        population_size: int = 30,
        memory_size: int = 5,
        mu_max: float = 0.5,
        elite_fraction: float = 0.3,
        affinity_fn: Optional[AffinityFunction] = None,
        init_bounds: Optional[Bounds] = None,
        init_spread: float = 10.0,
    ):
        """
        Args:
            dims: number of constraint dimensions
            population_size: number of candidate bounds in population
            memory_size: how many elite solutions to archive
            mu_max: maximum mutation rate
            elite_fraction: fraction of population selected as elite
            affinity_fn: function to evaluate bounds quality
            init_bounds: initial guess for bounds center (optional)
            init_spread: initial spread around center
        """
        self.dims = dims
        self.pop_size = population_size
        self.memory_size = memory_size
        self.mu_max = mu_max
        self.elite_count = max(1, int(population_size * elite_fraction))
        self.affinity_fn = affinity_fn or AffinityFunction(
            np.array([]).reshape(0, dims),
            np.array([]).reshape(0, dims),
        )

        # Initialize population
        if init_bounds is not None:
            self.population = self._init_around(init_bounds, init_spread)
        else:
            self.population = self._init_random(init_spread)

        # Evaluate initial population
        self.affinities = [self.affinity_fn(b) for b in self.population]

        # Memory archive (starts empty)
        self.memory: List[MemoryBCell] = []

        # Clonal expansion
        self.clonal = ClonalExpansion(dims=dims)

        # History
        self.history: List[ImmuneStats] = []
        self.generation = 0

    def _init_random(self, spread: float) -> List[Bounds]:
        """Initialize population with random bounds."""
        pop = []
        for _ in range(self.pop_size):
            bounds = []
            for d in range(self.dims):
                lo = np.random.uniform(-spread, 0)
                hi = np.random.uniform(0, spread)
                bounds.append((lo, hi))
            pop.append(bounds)
        return pop

    def _init_around(self, center: Bounds, spread: float) -> List[Bounds]:
        """Initialize population around a center guess."""
        pop = []
        for _ in range(self.pop_size):
            bounds = []
            for lo, hi in center:
                delta_lo = np.random.uniform(-spread, spread)
                delta_hi = np.random.uniform(-spread, spread)
                new_lo = lo + delta_lo
                new_hi = hi + delta_hi
                if new_lo > new_hi:
                    new_lo, new_hi = new_hi, new_lo
                bounds.append((new_lo, new_hi))
            pop.append(bounds)
        return pop

    def mutation_rate(self, affinity: float) -> float:
        """Affinity-dependent mutation: μ(a) = μ_max * (1 - a)² + μ_floor.

        High affinity → low mutation (fine-tuning, but never zero)
        Low affinity → high mutation (exploration)
        Quadratic schedule: gentle near optimum, aggressive when far.
        """
        mu_floor = self.mu_max * 0.4  # never drop below 40% of max
        return self.mu_max * (1.0 - affinity) ** 2 + mu_floor

    def _mutate_bounds(self, bounds: Bounds, mu: float) -> Tuple[Bounds, int]:
        """Mutate bounds with rate mu. Returns (new_bounds, n_mutations).

        Three mutation types, equally likely:
        - SHIFT: translate both bounds by same amount (repositioning)
        - TIGHTEN: shrink bounds (reduce false positives)
        - WIDEN: expand bounds (reduce false negatives)
        """
        new_bounds = []
        n_mutations = 0
        for lo, hi in bounds:
            if np.random.random() < mu:
                width = hi - lo
                mut_type = np.random.random()
                if mut_type < 0.33:
                    # SHIFT: translate the interval
                    delta = np.random.normal(0, mu * width * 0.5)
                    new_lo = lo + delta
                    new_hi = hi + delta
                elif mut_type < 0.67:
                    # TIGHTEN: shrink both ends inward
                    shrink = abs(np.random.normal(0, mu * width * 0.3))
                    new_lo = lo + shrink
                    new_hi = hi - shrink
                else:
                    # WIDEN: expand both ends outward
                    expand = abs(np.random.normal(0, mu * width * 0.3))
                    new_lo = lo - expand
                    new_hi = hi + expand
                if new_lo > new_hi:
                    new_lo, new_hi = new_hi, new_lo
                n_mutations += 1
            else:
                new_lo, new_hi = lo, hi
            new_bounds.append((new_lo, new_hi))
        return new_bounds, n_mutations

    def step(self) -> ImmuneStats:
        """One generation of affinity maturation."""
        t0 = time.time()
        self.generation += 1

        # 1. Mutate each individual with ADAPTIVE mutation rate
        new_pop = []
        total_mutations = 0
        for i, bounds in enumerate(self.population):
            a = self.affinities[i]
            mu = self.mutation_rate(a)
            new_bounds, n_mut = self._mutate_bounds(bounds, mu)
            new_pop.append(new_bounds)
            total_mutations += n_mut

        # Also re-seed from memory with fresh mutations to avoid stagnation
        for cell in self.memory:
            mu = self.mutation_rate(cell.affinity) * 1.5  # slightly elevated
            new_bounds, _ = self._mutate_bounds(cell.bounds, mu)
            new_pop.append(new_bounds)

        # 2. Evaluate all candidates
        all_candidates = new_pop + [cell.bounds for cell in self.memory]
        all_affinities = [self.affinity_fn(b) for b in all_candidates]

        # 3. Select elite
        indexed = sorted(
            enumerate(all_candidates),
            key=lambda x: all_affinities[x[0]],
            reverse=True,
        )
        elite = [(all_candidates[i], all_affinities[i]) for i, _ in indexed[:self.pop_size]]

        # 4. Clonal expansion from top memory candidates
        top_elite = [
            MemoryBCell(b, a, self.generation, 0)
            for b, a in sorted(elite, key=lambda x: x[1], reverse=True)[:self.elite_count]
        ]
        clones = self.clonal.expand(top_elite, self.generation)

        # 5. Evaluate clones and merge
        clone_affinities = [self.affinity_fn(b) for b in clones]

        # 6. Build next generation: elites + clones, pick top pop_size
        combined = list(elite) + list(zip(clones, clone_affinities))
        combined.sort(key=lambda x: x[1], reverse=True)
        self.population = [b for b, _ in combined[:self.pop_size]]
        self.affinities = [a for _, a in combined[:self.pop_size]]

        # 7. Update memory archive
        for b, a in combined[:self.memory_size]:
            cell = MemoryBCell(b, a, self.generation, total_mutations)
            self._update_memory(cell)

        mean_mu = np.mean([self.mutation_rate(a) for a in self.affinities])

        stats = ImmuneStats(
            generation=self.generation,
            best_affinity=max(self.affinities),
            mean_affinity=float(np.mean(self.affinities)),
            worst_affinity=min(self.affinities),
            memory_size=len(self.memory),
            mean_mutation_rate=float(mean_mu),
            elapsed=time.time() - t0,
        )
        self.history.append(stats)
        return stats

    def _update_memory(self, candidate: MemoryBCell):
        """Add candidate to memory, replacing worst if full.

        Keep memory diverse: don't add if a very similar solution exists.
        """
        # Check for near-duplicate (within 5% per dimension)
        for existing in self.memory:
            if self._similar(candidate.bounds, existing.bounds):
                if candidate.affinity > existing.affinity:
                    self.memory.remove(existing)
                    self.memory.append(candidate)
                return

        self.memory.append(candidate)

        # Keep only top memory_size by affinity
        self.memory.sort(key=lambda c: c.affinity, reverse=True)
        if len(self.memory) > self.memory_size:
            self.memory = self.memory[:self.memory_size]

    def _similar(self, a: Bounds, b: Bounds, threshold: float = 0.05) -> bool:
        """Check if two bounds are similar (within threshold fraction per dim)."""
        for (lo_a, hi_a), (lo_b, hi_b) in zip(a, b):
            width = max(abs(hi_a - lo_a), abs(hi_b - lo_b), 0.01)
            if abs(lo_a - lo_b) / width > threshold or abs(hi_a - hi_b) / width > threshold:
                return False
        return True

    def run(self, generations: int = 100, verbose: bool = False) -> List[ImmuneStats]:
        """Run for N generations."""
        for g in range(generations):
            stats = self.step()
            if verbose and (g + 1) % 20 == 0:
                print(
                    f"Gen {stats.generation:3d} | "
                    f"best={stats.best_affinity:.4f} "
                    f"mean={stats.mean_affinity:.4f} "
                    f"μ={stats.mean_mutation_rate:.4f} "
                    f"mem={stats.memory_size}"
                )
        return self.history

    @property
    def best(self) -> Tuple[Bounds, float]:
        """Return best solution from memory or population."""
        if self.memory:
            best_cell = max(self.memory, key=lambda c: c.affinity)
            return best_cell.bounds, best_cell.affinity
        idx = int(np.argmax(self.affinities))
        return self.population[idx], self.affinities[idx]


# ---------------------------------------------------------------------------
# Standard Evolution (Baseline for Comparison)
# ---------------------------------------------------------------------------

class StandardEvolution:
    """Fixed-mutation-rate evolution for comparison.

    Same population size, same affinity function, but WITHOUT:
    - Adaptive mutation rate
    - Memory archive
    - Clonal expansion
    """

    def __init__(
        self,
        dims: int = 8,
        population_size: int = 30,
        fixed_mutation_rate: float = 0.25,
        elite_fraction: float = 0.3,
        affinity_fn: Optional[AffinityFunction] = None,
        init_bounds: Optional[Bounds] = None,
        init_spread: float = 10.0,
    ):
        self.dims = dims
        self.pop_size = population_size
        self.fixed_mu = fixed_mutation_rate
        self.elite_count = max(1, int(population_size * elite_fraction))
        self.affinity_fn = affinity_fn or AffinityFunction(
            np.array([]).reshape(0, dims),
            np.array([]).reshape(0, dims),
        )

        # Same initialization as ImmuneOptimizer
        if init_bounds is not None:
            self.population = []
            for _ in range(self.pop_size):
                bounds = []
                for lo, hi in init_bounds:
                    delta_lo = np.random.uniform(-init_spread, init_spread)
                    delta_hi = np.random.uniform(-init_spread, init_spread)
                    new_lo = lo + delta_lo
                    new_hi = hi + delta_hi
                    if new_lo > new_hi:
                        new_lo, new_hi = new_hi, new_lo
                    bounds.append((new_lo, new_hi))
                self.population.append(bounds)
        else:
            self.population = []
            for _ in range(self.pop_size):
                bounds = []
                for d in range(self.dims):
                    lo = np.random.uniform(-init_spread, 0)
                    hi = np.random.uniform(0, init_spread)
                    bounds.append((lo, hi))
                self.population.append(bounds)

        self.affinities = [self.affinity_fn(b) for b in self.population]
        self.history: List[ImmuneStats] = []
        self.generation = 0

    def _mutate_fixed(self, bounds: Bounds) -> Bounds:
        """Fixed-rate mutation with shift/tighten/widen."""
        new_bounds = []
        for lo, hi in bounds:
            if np.random.random() < self.fixed_mu:
                width = hi - lo
                mut_type = np.random.random()
                if mut_type < 0.33:
                    delta = np.random.normal(0, self.fixed_mu * width * 0.5)
                    new_lo, new_hi = lo + delta, hi + delta
                elif mut_type < 0.67:
                    shrink = abs(np.random.normal(0, self.fixed_mu * width * 0.3))
                    new_lo, new_hi = lo + shrink, hi - shrink
                else:
                    expand = abs(np.random.normal(0, self.fixed_mu * width * 0.3))
                    new_lo, new_hi = lo - expand, hi + expand
                if new_lo > new_hi:
                    new_lo, new_hi = new_hi, new_lo
            else:
                new_lo, new_hi = lo, hi
            new_bounds.append((new_lo, new_hi))
        return new_bounds

    def step(self) -> ImmuneStats:
        """One generation of standard evolution."""
        t0 = time.time()
        self.generation += 1

        # Mutate all with fixed rate
        new_pop = [self._mutate_fixed(b) for b in self.population]
        new_aff = [self.affinity_fn(b) for b in new_pop]

        # Select top (truncation selection)
        combined = list(zip(new_pop, new_aff)) + list(zip(self.population, self.affinities))
        combined.sort(key=lambda x: x[1], reverse=True)
        self.population = [b for b, _ in combined[:self.pop_size]]
        self.affinities = [a for _, a in combined[:self.pop_size]]

        stats = ImmuneStats(
            generation=self.generation,
            best_affinity=max(self.affinities),
            mean_affinity=float(np.mean(self.affinities)),
            worst_affinity=min(self.affinities),
            memory_size=0,
            mean_mutation_rate=self.fixed_mu,
            elapsed=time.time() - t0,
        )
        self.history.append(stats)
        return stats

    def run(self, generations: int = 100, verbose: bool = False) -> List[ImmuneStats]:
        for g in range(generations):
            stats = self.step()
            if verbose and (g + 1) % 20 == 0:
                print(
                    f"Gen {stats.generation:3d} | "
                    f"best={stats.best_affinity:.4f} "
                    f"mean={stats.mean_affinity:.4f}"
                )
        return self.history

    @property
    def best(self) -> Tuple[Bounds, float]:
        idx = int(np.argmax(self.affinities))
        return self.population[idx], self.affinities[idx]


# ---------------------------------------------------------------------------
# Experiment: Immune vs Standard
# ---------------------------------------------------------------------------

def run_experiment(
    dims: int = 8,
    generations: int = 100,
    n_valid: int = 200,
    n_invalid: int = 100,
    seed: int = 42,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Compare immune optimizer vs standard evolution.

    Creates a target region in 8D space, generates valid/invalid test points,
    then runs both optimizers starting from poor initial bounds.
    """
    np.random.seed(seed)
    random.seed(seed)

    # Target bounds to discover
    target = [(np.random.uniform(-5, 5), np.random.uniform(-5, 5)) for _ in range(dims)]
    for i in range(dims):
        lo, hi = target[i]
        if lo > hi:
            target[i] = (hi, lo)

    # Generate test points
    valid_points = np.array([
        [np.random.uniform(lo, hi) for lo, hi in target]
        for _ in range(n_valid)
    ])
    # Invalid points: outside at least one dimension
    invalid_points = []
    for _ in range(n_invalid):
        pt = [np.random.uniform(lo, hi) for lo, hi in target]
        # Push one dimension outside
        d = np.random.randint(dims)
        lo, hi = target[d]
        pt[d] = hi + np.random.uniform(0.5, 5.0)
        invalid_points.append(pt)
    invalid_points = np.array(invalid_points)

    # Affinity function
    aff = AffinityFunction(valid_points, invalid_points)

    # Poor initial bounds (wide, off-center — affinity ~0.3)
    init_bounds = [(-15.0, 15.0) for _ in range(dims)]

    # Run immune optimizer
    immune = ImmuneOptimizer(
        dims=dims,
        population_size=30,
        memory_size=5,
        mu_max=0.5,
        elite_fraction=0.3,
        affinity_fn=aff,
        init_bounds=init_bounds,
        init_spread=3.0,
    )
    if verbose:
        print("=== Immune Optimizer (adaptive mutation) ===")
    immune_history = immune.run(generations=generations, verbose=verbose)

    # Run standard evolution
    std = StandardEvolution(
        dims=dims,
        population_size=30,
        fixed_mutation_rate=0.25,
        elite_fraction=0.3,
        affinity_fn=aff,
        init_bounds=init_bounds,
        init_spread=3.0,
    )
    if verbose:
        print("\n=== Standard Evolution (fixed mutation) ===")
    std_history = std.run(generations=generations, verbose=verbose)

    # Compare results
    immune_best_bounds, immune_best_aff = immune.best
    std_best_bounds, std_best_aff = std.best

    results = {
        "target": target,
        "immune_best": immune_best_bounds,
        "immune_best_affinity": immune_best_aff,
        "immune_history": immune_history,
        "std_best": std_best_bounds,
        "std_best_affinity": std_best_aff,
        "std_history": std_history,
        "immune_convergence_gen": _convergence_gen(immune_history, threshold=0.9),
        "std_convergence_gen": _convergence_gen(std_history, threshold=0.9),
        "advantage": immune_best_aff - std_best_aff,
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"Immune best affinity:  {immune_best_aff:.4f}")
        print(f"Standard best affinity: {std_best_aff:.4f}")
        print(f"Advantage:              {results['advantage']:+.4f}")
        print(f"Immune converged at gen: {results['immune_convergence_gen']}")
        print(f"Standard converged at gen: {results['std_convergence_gen']}")
        print(f"\nBoth strategies are complementary — the fleet uses whichever")
        print(f"produces better tiles for a given problem instance.")
        if immune_best_aff > std_best_aff:
            print(f"→ Immune optimizer wins this instance")
        elif std_best_aff > immune_best_aff:
            print(f"→ Standard evolution wins this instance")
        else:
            print(f"→ Tie")

    return results


def _convergence_gen(history: List[ImmuneStats], threshold: float = 0.9) -> int:
    """Find first generation where best affinity >= threshold."""
    for s in history:
        if s.best_affinity >= threshold:
            return s.generation
    return -1  # never converged


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    results = run_experiment(generations=100, verbose=True)
