"""
Flux Evolution — Evolutionary Accumulation of Correctness

Demonstrates that biological evolution and accumulated correctness share the
same mathematical structure: iterative refinement via selection pressure and
variation, with no designer needed. The process IS the intelligence.

Key insight: A population of constraint sets, evolved under fitness pressure,
accumulates edge-case knowledge just as biology accumulates adaptations.
The final population IS accumulated correctness — it embodies all edge cases
that evolution discovered, without any explicit "understanding."

Part of the Constraint Theory Ecosystem.
"""

from __future__ import annotations

import copy
import random
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Core Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ConstraintBound:
    """A single constraint dimension: name + [lower, upper] bounds."""
    name: str
    lower: float
    upper: float

    def contains(self, value: float) -> bool:
        return self.lower <= value <= self.upper

    @property
    def width(self) -> float:
        return self.upper - self.lower

    @property
    def midpoint(self) -> float:
        return (self.lower + self.upper) / 2.0

    def tighten(self, amount: float) -> "ConstraintBound":
        """Shrink bounds by amount on each side."""
        return ConstraintBound(
            self.name,
            self.lower + amount,
            self.upper - amount,
        )

    def relax(self, amount: float) -> "ConstraintBound":
        """Expand bounds by amount on each side."""
        return ConstraintBound(
            self.name,
            self.lower - amount,
            self.upper + amount,
        )

    def split(self) -> Tuple["ConstraintBound", "ConstraintBound"]:
        """Split into two tighter constraints at the midpoint."""
        mid = self.midpoint
        return (
            ConstraintBound(f"{self.name}_lo", self.lower, mid),
            ConstraintBound(f"{self.name}_hi", mid, self.upper),
        )

    def merge(self, other: "ConstraintBound") -> "ConstraintBound":
        """Merge two constraints (must be adjacent by name)."""
        return ConstraintBound(
            f"{self.name}|{other.name}",
            min(self.lower, other.lower),
            max(self.upper, other.upper),
        )


@dataclass
class TestCase:
    """A single test input with ground-truth label."""
    values: Dict[str, float]
    label: bool  # True = valid input, False = violation/anomaly
    name: str = ""
    category: str = "general"


@dataclass
class CheckResult:
    """Result of checking a test suite against a constraint set."""
    true_positives: int = 0    # correctly flagged violations
    false_negatives: int = 0   # missed violations (BAD)
    true_negatives: int = 0    # correctly passed valid inputs
    false_positives: int = 0   # valid inputs incorrectly flagged
    edge_cases_caught: set = field(default_factory=set)  # categories caught
    check_time_ms: float = 0.0

    @property
    def total(self) -> int:
        return self.true_positives + self.false_negatives + self.true_negatives + self.false_positives

    @property
    def correctness(self) -> float:
        """Fraction of correct decisions."""
        t = self.total
        return (self.true_positives + self.true_negatives) / t if t > 0 else 1.0

    @property
    def recall(self) -> float:
        """True positive rate — must be 1.0 (zero false negatives)."""
        pos = self.true_positives + self.false_negatives
        return self.true_positives / pos if pos > 0 else 1.0

    @property
    def precision(self) -> float:
        pos_pred = self.true_positives + self.false_positives
        return self.true_positives / pos_pred if pos_pred > 0 else 1.0

    @property
    def coverage(self) -> float:
        """Fraction of violation categories caught."""
        return len(self.edge_cases_caught)


@dataclass
class ConstraintSet:
    """Genotype: a set of constraint bounds defining accept/reject regions."""
    bounds: List[ConstraintBound]
    provenance: str = "unknown"
    generation: int = 0

    def accepts(self, values: Dict[str, float]) -> bool:
        """Check if all values fall within their bounds. True = accept."""
        for b in self.bounds:
            if b.name in values:
                if not b.contains(values[b.name]):
                    return False
        return True

    def evaluate(self, tests: List[TestCase]) -> CheckResult:
        """Run full test suite, return detailed results."""
        result = CheckResult()
        start = time.perf_counter()

        for tc in tests:
            accepted = self.accepts(tc.values)
            if tc.label:
                # Valid input
                if accepted:
                    result.true_negatives += 1
                else:
                    result.false_positives += 1
            else:
                # Violation
                if not accepted:
                    result.true_positives += 1
                    result.edge_cases_caught.add(tc.category)
                else:
                    result.false_negatives += 1

        result.check_time_ms = (time.perf_counter() - start) * 1000
        return result


@dataclass
class FitnessScore:
    """Phenotype: fitness evaluation of a constraint set."""
    correctness: float      # Overall accuracy
    recall: float           # Must be 1.0 (zero false negatives)
    coverage: int           # Number of edge-case categories caught
    efficiency: int         # Number of constraints (fewer = better)
    surprise: int           # NEW edge cases this individual catches
    fitness: float = 0.0    # Composite score

    def compute_composite(self, alpha: float = 1.0, beta: float = 0.5,
                          gamma: float = 0.2) -> float:
        """
        Fitness = alpha * correctness + beta * coverage_norm - gamma * efficiency_norm
        With hard floor: recall must be 1.0, else fitness = 0.
        """
        if self.recall < 1.0:
            self.fitness = 0.0
            return 0.0
        cov = self.coverage
        eff = self.efficiency
        self.fitness = alpha * self.correctness + beta * cov - gamma * eff * 0.01
        return self.fitness


@dataclass
class Individual:
    """An individual in the population: genotype + phenotype."""
    constraint_set: ConstraintSet
    fitness_score: Optional[FitnessScore] = None
    check_result: Optional[CheckResult] = None


# ---------------------------------------------------------------------------
# Mutation Operators
# ---------------------------------------------------------------------------

def mutate_tighten(ind: Individual, sigma: float = 0.1) -> Individual:
    """Tighten a random constraint bound."""
    new_bounds = copy.deepcopy(ind.constraint_set.bounds)
    if not new_bounds:
        return copy.deepcopy(ind)
    idx = random.randrange(len(new_bounds))
    amount = abs(random.gauss(0, sigma)) * new_bounds[idx].width
    new_bounds[idx] = new_bounds[idx].tighten(amount)
    cs = ConstraintSet(
        bounds=new_bounds,
        provenance=f"tighten(g{ind.constraint_set.generation})",
        generation=ind.constraint_set.generation + 1,
    )
    return Individual(constraint_set=cs)


def mutate_relax(ind: Individual, sigma: float = 0.1) -> Individual:
    """Relax a random constraint bound."""
    new_bounds = copy.deepcopy(ind.constraint_set.bounds)
    if not new_bounds:
        return copy.deepcopy(ind)
    idx = random.randrange(len(new_bounds))
    amount = abs(random.gauss(0, sigma)) * new_bounds[idx].width
    new_bounds[idx] = new_bounds[idx].relax(amount)
    cs = ConstraintSet(
        bounds=new_bounds,
        provenance=f"relax(g{ind.constraint_set.generation})",
        generation=ind.constraint_set.generation + 1,
    )
    return Individual(constraint_set=cs)


def mutate_add_constraint(ind: Individual,
                          dimension_names: List[str],
                          value_range: Tuple[float, float] = (-5.0, 5.0)) -> Individual:
    """Add a new constraint dimension."""
    new_bounds = copy.deepcopy(ind.constraint_set.bounds)
    existing_names = {b.name for b in new_bounds}
    available = [n for n in dimension_names if n not in existing_names]
    if not available:
        return copy.deepcopy(ind)
    name = random.choice(available)
    lo = random.uniform(*value_range)
    hi = random.uniform(*value_range)
    if lo > hi:
        lo, hi = hi, lo
    new_bounds.append(ConstraintBound(name, lo, hi))
    cs = ConstraintSet(
        bounds=new_bounds,
        provenance=f"add({name},g{ind.constraint_set.generation})",
        generation=ind.constraint_set.generation + 1,
    )
    return Individual(constraint_set=cs)


def mutate_split(ind: Individual) -> Individual:
    """Split a random constraint into two tighter ones."""
    new_bounds = copy.deepcopy(ind.constraint_set.bounds)
    if not new_bounds:
        return copy.deepcopy(ind)
    idx = random.randrange(len(new_bounds))
    lo, hi = new_bounds[idx].split()
    new_bounds = new_bounds[:idx] + [lo, hi] + new_bounds[idx + 1:]
    cs = ConstraintSet(
        bounds=new_bounds,
        provenance=f"split(g{ind.constraint_set.generation})",
        generation=ind.constraint_set.generation + 1,
    )
    return Individual(constraint_set=cs)


def mutate_merge(ind: Individual) -> Individual:
    """Merge two adjacent constraints into one."""
    new_bounds = copy.deepcopy(ind.constraint_set.bounds)
    if len(new_bounds) < 2:
        return copy.deepcopy(ind)
    idx = random.randrange(len(new_bounds) - 1)
    merged = new_bounds[idx].merge(new_bounds[idx + 1])
    new_bounds = new_bounds[:idx] + [merged] + new_bounds[idx + 2:]
    cs = ConstraintSet(
        bounds=new_bounds,
        provenance=f"merge(g{ind.constraint_set.generation})",
        generation=ind.constraint_set.generation + 1,
    )
    return Individual(constraint_set=cs)


MUTATION_OPERATORS = [
    mutate_tighten,
    mutate_relax,
    mutate_add_constraint,
    mutate_split,
    mutate_merge,
]


def apply_random_mutation(ind: Individual,
                          dimension_names: List[str],
                          sigma: float = 0.1) -> Individual:
    """Apply a randomly chosen mutation operator."""
    # Filter out add_constraint if we need dimension names
    ops = [mutate_tighten, mutate_relax, mutate_split, mutate_merge]
    if dimension_names:
        ops.append(mutate_add_constraint)
    op = random.choice(ops)
    if op == mutate_add_constraint:
        return op(ind, dimension_names)
    elif op in (mutate_tighten, mutate_relax):
        return op(ind, sigma)
    else:
        return op(ind)


# ---------------------------------------------------------------------------
# Selection & Crossover
# ---------------------------------------------------------------------------

def tournament_select(population: List[Individual],
                      fitnesses: List[float],
                      k: int = 3) -> Individual:
    """Tournament selection: pick k random, return the fittest."""
    contenders = random.sample(range(len(population)),
                               min(k, len(population)))
    best_idx = max(contenders, key=lambda i: fitnesses[i])
    return population[best_idx]


def crossover(parent_a: Individual, parent_b: Individual) -> Individual:
    """Uniform crossover: for each dimension, randomly pick from a parent."""
    bounds_a = {b.name: b for b in parent_a.constraint_set.bounds}
    bounds_b = {b.name: b for b in parent_b.constraint_set.bounds}
    all_names = list(set(bounds_a.keys()) | set(bounds_b.keys()))

    child_bounds = []
    gen = max(parent_a.constraint_set.generation,
              parent_b.constraint_set.generation) + 1
    for name in all_names:
        if name in bounds_a and name in bounds_b:
            child_bounds.append(copy.deepcopy(
                random.choice([bounds_a[name], bounds_b[name]])))
        elif name in bounds_a:
            child_bounds.append(copy.deepcopy(bounds_a[name]))
        else:
            child_bounds.append(copy.deepcopy(bounds_b[name]))

    cs = ConstraintSet(
        bounds=child_bounds,
        provenance=f"crossover(g{gen})",
        generation=gen,
    )
    return Individual(constraint_set=cs)


# ---------------------------------------------------------------------------
# Fitness Evaluation
# ---------------------------------------------------------------------------

def evaluate_fitness(ind: Individual,
                     tests: List[TestCase],
                     prev_caught: Optional[set] = None) -> FitnessScore:
    """
    Evaluate an individual against the test suite.
    prev_caught: edge-case categories caught by the PREVIOUS generation
                 (for computing surprise).
    """
    result = ind.constraint_set.evaluate(tests) if ind.check_result is None else ind.check_result
    ind.check_result = result

    surprise = 0
    if prev_caught is not None:
        new_categories = result.edge_cases_caught - prev_caught
        surprise = len(new_categories)

    score = FitnessScore(
        correctness=result.correctness,
        recall=result.recall,
        coverage=result.coverage,
        efficiency=len(ind.constraint_set.bounds),
        surprise=surprise,
    )
    score.compute_composite()
    ind.fitness_score = score
    return score


# ---------------------------------------------------------------------------
# Evolution Engine
# ---------------------------------------------------------------------------

@dataclass
class EvolutionConfig:
    """Configuration for the evolutionary process."""
    population_size: int = 40
    generations: int = 60
    mutation_rate: float = 0.4
    crossover_rate: float = 0.5
    tournament_k: int = 3
    elitism: int = 2
    mutation_sigma: float = 0.15
    seed: Optional[int] = None


@dataclass
class GenerationStats:
    """Statistics for a single generation."""
    generation: int
    best_fitness: float
    avg_fitness: float
    best_correctness: float
    best_recall: float
    best_coverage: int
    total_edge_cases: int
    diversity: float  # number of unique constraint configurations
    pareto_size: int


@dataclass
class EvolutionResult:
    """Result of running the full evolutionary process."""
    config: EvolutionConfig
    generations: List[GenerationStats] = field(default_factory=list)
    final_population: List[Individual] = field(default_factory=list)
    pareto_front: List[Individual] = field(default_factory=list)
    best_individual: Optional[Individual] = None
    elapsed_seconds: float = 0.0
    correctness_monotonic: bool = True
    coverage_monotonic: bool = True


def create_random_individual(dimension_names: List[str],
                             gen: int = 0,
                             value_range: Tuple[float, float] = (-5.0, 5.0)) -> Individual:
    """Create a random individual with constraints on given dimensions."""
    bounds = []
    for name in dimension_names:
        lo = random.uniform(*value_range)
        hi = random.uniform(*value_range)
        if lo > hi:
            lo, hi = hi, lo
        bounds.append(ConstraintBound(name, lo, hi))
    cs = ConstraintSet(bounds=bounds, provenance="random_init", generation=gen)
    return Individual(constraint_set=cs)


def compute_pareto_front(population: List[Individual],
                         fitnesses: List[float]) -> List[Individual]:
    """
    Compute Pareto front: individuals not dominated on (correctness, -efficiency).
    Dominated = exists another individual with >= correctness AND <= efficiency
                with at least one strict inequality.
    """
    if not population:
        return []

    scored = []
    for ind, fit_val in zip(population, fitnesses):
        if ind.fitness_score is None:
            continue
        scored.append((ind, ind.fitness_score.correctness, ind.fitness_score.efficiency))

    if not scored:
        return []

    pareto = []
    for i, (ind_i, corr_i, eff_i) in enumerate(scored):
        dominated = False
        for j, (ind_j, corr_j, eff_j) in enumerate(scored):
            if i == j:
                continue
            if corr_j >= corr_i and eff_j <= eff_i:
                if corr_j > corr_i or eff_j < eff_i:
                    dominated = True
                    break
        if not dominated:
            pareto.append(ind_i)
    return pareto


def evolve(tests: List[TestCase],
           dimension_names: List[str],
           config: EvolutionConfig,
           hand_designed: Optional[ConstraintSet] = None) -> EvolutionResult:
    """
    Run the full evolutionary process.

    Args:
        tests: Test suite with ground-truth labels
        dimension_names: Names of constraint dimensions
        config: Evolution parameters
        hand_designed: Optional hand-designed constraint set for comparison

    Returns:
        EvolutionResult with full statistics
    """
    if config.seed is not None:
        random.seed(config.seed)

    start_time = time.perf_counter()

    # Initialize population
    population = [
        create_random_individual(dimension_names, gen=0)
        for _ in range(config.population_size)
    ]

    all_caught_categories: set = set()
    prev_best_correctness = 0.0
    prev_total_coverage = 0
    result = EvolutionResult(config=config)

    for gen in range(config.generations):
        # Evaluate all individuals
        fitnesses: List[float] = []
        gen_caught: set = set()

        for ind in population:
            score = evaluate_fitness(ind, tests, prev_caught=all_caught_categories)
            fitnesses.append(score.fitness)
            if ind.check_result:
                gen_caught |= ind.check_result.edge_cases_caught

        all_caught_categories |= gen_caught

        # Sort by fitness for statistics
        sorted_pairs = sorted(zip(fitnesses, population),
                              key=lambda p: p[0], reverse=True)
        best_ind = sorted_pairs[0][1]
        best_score = best_ind.fitness_score

        # Track monotonicity
        if best_score.correctness < prev_best_correctness - 1e-9:
            result.correctness_monotonic = False
        prev_best_correctness = best_score.correctness

        current_coverage = len(all_caught_categories)
        if current_coverage < prev_total_coverage:
            result.coverage_monotonic = False
        prev_total_coverage = current_coverage

        # Compute Pareto front
        pareto = compute_pareto_front(population, fitnesses)

        # Diversity: count unique bound configurations
        configs_seen = set()
        for ind in population:
            key = tuple(sorted(
                (b.name, round(b.lower, 3), round(b.upper, 3))
                for b in ind.constraint_set.bounds
            ))
            configs_seen.add(key)

        # Record stats
        avg_fit = sum(fitnesses) / len(fitnesses) if fitnesses else 0
        stats = GenerationStats(
            generation=gen,
            best_fitness=max(fitnesses) if fitnesses else 0,
            avg_fitness=avg_fit,
            best_correctness=best_score.correctness,
            best_recall=best_score.recall,
            best_coverage=best_score.coverage,
            total_edge_cases=current_coverage,
            diversity=len(configs_seen),
            pareto_size=len(pareto),
        )
        result.generations.append(stats)

        # Selection + reproduction
        new_population: List[Individual] = []

        # Elitism: keep top performers
        for i in range(min(config.elitism, len(sorted_pairs))):
            elite = copy.deepcopy(sorted_pairs[i][1])
            elite.constraint_set.generation = gen + 1
            new_population.append(elite)

        # Fill rest with crossover + mutation
        while len(new_population) < config.population_size:
            if random.random() < config.crossover_rate and len(population) > 1:
                parent_a = tournament_select(population, fitnesses, config.tournament_k)
                parent_b = tournament_select(population, fitnesses, config.tournament_k)
                child = crossover(parent_a, parent_b)
            else:
                parent = tournament_select(population, fitnesses, config.tournament_k)
                child = copy.deepcopy(parent)
                child.constraint_set.generation = gen + 1

            if random.random() < config.mutation_rate:
                child = apply_random_mutation(child, dimension_names, config.mutation_sigma)

            new_population.append(child)

        population = new_population

    # Final evaluation
    fitnesses = []
    for ind in population:
        score = evaluate_fitness(ind, tests)
        fitnesses.append(score.fitness)

    sorted_pairs = sorted(zip(fitnesses, population),
                          key=lambda p: p[0], reverse=True)
    result.final_population = population
    result.best_individual = sorted_pairs[0][1]
    result.pareto_front = compute_pareto_front(population, fitnesses)
    result.elapsed_seconds = time.perf_counter() - start_time

    return result


# ---------------------------------------------------------------------------
# Hand-Designed Baselines (for comparison)
# ---------------------------------------------------------------------------

def create_hand_designed_baseline(dimension_names: List[str],
                                  value_range: Tuple[float, float] = (-5.0, 5.0),
                                  tolerance: float = 0.3) -> ConstraintSet:
    """
    Create a simple hand-designed baseline: tight bounds around zero
    with fixed tolerance. This is what a human designer might write.
    """
    bounds = []
    for name in dimension_names:
        bounds.append(ConstraintBound(
            name,
            -tolerance,
            tolerance,
        ))
    return ConstraintSet(bounds=bounds, provenance="hand_designed")


def compare_evolved_vs_designed(evolved: Individual,
                                designed: ConstraintSet,
                                tests: List[TestCase]) -> Dict[str, Any]:
    """Compare an evolved individual against a hand-designed baseline."""
    evolved_result = evolved.constraint_set.evaluate(tests)
    designed_result = designed.evaluate(tests)

    return {
        "evolved_correctness": evolved_result.correctness,
        "designed_correctness": designed_result.correctness,
        "evolved_recall": evolved_result.recall,
        "designed_recall": designed_result.recall,
        "evolved_coverage": evolved_result.coverage,
        "designed_coverage": designed_result.coverage,
        "evolved_efficiency": len(evolved.constraint_set.bounds),
        "designed_efficiency": len(designed.bounds),
        "evolved_edge_cases": evolved_result.edge_cases_caught,
        "designed_edge_cases": designed_result.edge_cases_caught,
        "evolved_misses": evolved_result.false_negatives,
        "designed_misses": designed_result.false_negatives,
        "evolution_wins": evolved_result.correctness > designed_result.correctness,
    }


# ---------------------------------------------------------------------------
# Test Suite Generators
# ---------------------------------------------------------------------------

def generate_test_suite(dimension_names: List[str],
                        n_valid: int = 200,
                        n_violation: int = 100,
                        valid_range: Tuple[float, float] = (-1.0, 1.0),
                        violation_range: Tuple[float, float] = (-5.0, 5.0),
                        edge_categories: int = 5,
                        seed: Optional[int] = None) -> List[TestCase]:
    """
    Generate a test suite with:
    - Valid inputs (within valid_range)
    - Violations (outside valid_range on at least one dimension)
    - Edge cases in named categories (boundary, extreme, corner, drift, spike)
    """
    if seed is not None:
        random.seed(seed)

    tests: List[TestCase] = []

    # Valid inputs
    for i in range(n_valid):
        values = {name: random.uniform(*valid_range) for name in dimension_names}
        tests.append(TestCase(values=values, label=True,
                              name=f"valid_{i}", category="valid"))

    # General violations
    for i in range(n_violation):
        values = {name: random.uniform(*valid_range) for name in dimension_names}
        # Corrupt one dimension
        dim = random.choice(dimension_names)
        if random.random() < 0.5:
            values[dim] = random.uniform(violation_range[0], valid_range[0])
        else:
            values[dim] = random.uniform(valid_range[1], violation_range[1])
        tests.append(TestCase(values=values, label=False,
                              name=f"violation_{i}", category="general_violation"))

    # Edge case categories
    category_defs = {
        "boundary": lambda: {
            name: random.choice([
                valid_range[0] + random.gauss(0, 0.02),
                valid_range[1] + random.gauss(0, 0.02),
            ])
            for name in dimension_names
        },
        "extreme": lambda: {
            name: random.uniform(*violation_range) for name in dimension_names
        },
        "corner": lambda: {
            name: random.choice([violation_range[0], violation_range[1]])
            for name in dimension_names
        },
        "drift": lambda: {
            name: valid_range[1] + abs(random.gauss(0, 0.5))
            for name in dimension_names
        },
        "spike": lambda: _spike_values(dimension_names, valid_range, violation_range),
    }

    for cat_name, gen_fn in list(category_defs.items())[:edge_categories]:
        for i in range(20):
            values = gen_fn()
            # Boundary cases are mixed: some valid, some not
            if cat_name == "boundary":
                is_violation = any(
                    v < valid_range[0] or v > valid_range[1]
                    for v in values.values()
                )
                tests.append(TestCase(values=values, label=not is_violation,
                                      name=f"{cat_name}_{i}", category=cat_name))
            else:
                tests.append(TestCase(values=values, label=False,
                                      name=f"{cat_name}_{i}", category=cat_name))

    return tests


def _spike_values(dims: List[str],
                  valid: Tuple[float, float],
                  viol: Tuple[float, float]) -> Dict[str, float]:
    """One dimension spikes to extreme, rest are normal."""
    values = {d: random.uniform(*valid) for d in dims}
    spike_dim = random.choice(dims)
    values[spike_dim] = random.choice([viol[0], viol[1]])
    return values
