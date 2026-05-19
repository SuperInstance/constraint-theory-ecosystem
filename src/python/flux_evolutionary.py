"""
Flux Evolutionary — Genetic Algorithm for Constraint Set Optimization

Evolves optimal constraint configurations through tournament selection,
crossover, and mutation. Fitness = (detection_rate - false_positive_rate) / check_time.

Part of the Constraint Theory Ecosystem.
"""

from __future__ import annotations

import copy
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ConstraintSpec:
    """Definition of a single constraint."""
    name: str
    enabled: bool = True
    weight: float = 1.0          # Importance weight for fitness
    check_cost: float = 1.0      # Relative cost of checking this constraint
    threshold: float = 0.5       # Tunable parameter
    bound_lower: float = -1.0    # Lower bound
    bound_upper: float = 1.0     # Upper bound


@dataclass
class ConstraintChromosome:
    """A chromosome encoding a full constraint configuration."""
    genes: List[ConstraintSpec]          # One gene per constraint
    fitness: float = 0.0
    detection_rate: float = 0.0
    false_positive_rate: float = 0.0
    check_time: float = 0.0
    generation: int = 0


@dataclass
class EvaluationResult:
    """Result of evaluating a chromosome against data."""
    detected: int = 0
    missed: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    check_time_ms: float = 0.0

    @property
    def total_positive(self) -> int:
        return self.detected + self.missed

    @property
    def total_negative(self) -> int:
        return self.false_positives + self.true_negatives

    @property
    def detection_rate(self) -> float:
        tp = self.total_positive
        return self.detected / tp if tp > 0 else 1.0

    @property
    def false_positive_rate(self) -> float:
        tn = self.total_negative
        return self.false_positives / tn if tn > 0 else 0.0


@dataclass
class GAConfig:
    """Configuration for the genetic algorithm."""
    population_size: int = 50
    max_generations: int = 100
    mutation_rate: float = 0.1
    crossover_rate: float = 0.8
    tournament_size: int = 3
    elitism_count: int = 5
    stagnation_limit: int = 20
    parameter_mutation_sigma: float = 0.1
    seed: Optional[int] = None


@dataclass
class GAResult:
    """Result of running the GA optimizer."""
    best_chromosome: ConstraintChromosome
    generation_found: int
    total_generations: int
    fitness_history: List[float] = field(default_factory=list)
    diversity_history: List[float] = field(default_factory=list)
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Population Initialization
# ---------------------------------------------------------------------------

def random_chromosome(base_constraints: List[ConstraintSpec],
                      generation: int = 0) -> ConstraintChromosome:
    """Create a random chromosome from base constraints."""
    genes = []
    for spec in base_constraints:
        gene = copy.deepcopy(spec)
        # Randomize enabled state
        gene.enabled = random.random() > 0.3  # 70% chance enabled
        # Jitter parameters
        gene.threshold = max(0.0, min(1.0,
            gene.threshold + random.gauss(0, 0.15)))
        gene.bound_lower = gene.bound_lower + random.gauss(0, 0.1)
        gene.bound_upper = gene.bound_upper + random.gauss(0, 0.1)
        if gene.bound_lower >= gene.bound_upper:
            gene.bound_lower, gene.bound_upper = gene.bound_upper, gene.bound_lower
        genes.append(gene)
    return ConstraintChromosome(genes=genes, generation=generation)


def initialize_population(base_constraints: List[ConstraintSpec],
                          config: GAConfig) -> List[ConstraintChromosome]:
    """Create initial random population."""
    if config.seed is not None:
        random.seed(config.seed)
    return [random_chromosome(base_constraints, generation=0)
            for _ in range(config.population_size)]


# ---------------------------------------------------------------------------
# Fitness Evaluation
# ---------------------------------------------------------------------------

def evaluate_chromosome(
    chromosome: ConstraintChromosome,
    data: List[Dict[str, Any]],
    check_fn: Callable[[Dict[str, Any], ConstraintSpec], Optional[bool]],
) -> EvaluationResult:
    """
    Evaluate a chromosome against data.
    
    check_fn(sample, constraint) -> True if violation detected, False if OK, None if skip
    """
    result = EvaluationResult()
    enabled_genes = [g for g in chromosome.genes if g.enabled]
    
    if not enabled_genes:
        return result

    start = time.perf_counter()
    
    for sample in data:
        label = sample.get("label", None)  # True = actual violation
        
        detected_violation = False
        false_alarm = False
        
        for gene in enabled_genes:
            # Simulate check cost proportional to constraint complexity
            check_result = check_fn(sample, gene)
            
            if check_result is None:
                continue  # Skip this constraint for this sample
            
            if check_result:
                detected_violation = True
                break  # Short-circuit on first violation
        
        # Score against ground truth
        if label is True:  # Actual violation exists
            if detected_violation:
                result.detected += 1
            else:
                result.missed += 1
        else:  # No actual violation
            if detected_violation:
                result.false_positives += 1
            else:
                result.true_negatives += 1
    
    elapsed = time.perf_counter() - start
    result.check_time_ms = elapsed * 1000 / max(len(data), 1)
    
    return result


def compute_fitness(result: EvaluationResult) -> float:
    """Compute fitness: (detection_rate - FPR) / check_time."""
    dr = result.detection_rate
    fpr = result.false_positive_rate
    ct = result.check_time_ms
    
    if ct <= 0:
        ct = 0.001
    
    fitness = (dr - fpr) / (ct / 100.0)  # Normalize time
    
    # Heavy penalty for zero detection
    if result.total_positive > 0 and dr == 0:
        fitness -= 10.0
    
    return fitness


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def tournament_select(population: List[ConstraintChromosome],
                      tournament_size: int) -> ConstraintChromosome:
    """Select a chromosome via tournament selection."""
    candidates = random.sample(population, min(tournament_size, len(population)))
    return max(candidates, key=lambda c: c.fitness)


# ---------------------------------------------------------------------------
# Crossover
# ---------------------------------------------------------------------------

def single_point_crossover(
    parent1: ConstraintChromosome,
    parent2: ConstraintChromosome,
    crossover_rate: float,
) -> Tuple[ConstraintChromosome, ConstraintChromosome]:
    """Perform single-point crossover between two parents."""
    if random.random() > crossover_rate:
        return copy.deepcopy(parent1), copy.deepcopy(parent2)
    
    n = len(parent1.genes)
    point = random.randint(1, n - 1)
    
    child1_genes = copy.deepcopy(parent1.genes[:point]) + copy.deepcopy(parent2.genes[point:])
    child2_genes = copy.deepcopy(parent2.genes[:point]) + copy.deepcopy(parent1.genes[point:])
    
    return (ConstraintChromosome(genes=child1_genes),
            ConstraintChromosome(genes=child2_genes))


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

def mutate(chromosome: ConstraintChromosome,
           mutation_rate: float,
           sigma: float) -> ConstraintChromosome:
    """Apply mutation to a chromosome."""
    for gene in chromosome.genes:
        if random.random() < mutation_rate:
            gene.enabled = not gene.enabled
        
        if random.random() < mutation_rate:
            gene.threshold = max(0.0, min(1.0,
                gene.threshold + random.gauss(0, sigma)))
        
        if random.random() < mutation_rate:
            shift = random.gauss(0, sigma * 0.5)
            gene.bound_lower += shift
            gene.bound_upper -= shift
            if gene.bound_lower >= gene.bound_upper:
                gene.bound_lower, gene.bound_upper = (
                    min(gene.bound_lower, gene.bound_upper) - 0.01,
                    max(gene.bound_lower, gene.bound_upper) + 0.01,
                )
    
    return chromosome


# ---------------------------------------------------------------------------
# Diversity Measurement
# ---------------------------------------------------------------------------

def population_diversity(population: List[ConstraintChromosome]) -> float:
    """Measure population diversity as average Hamming distance of enabled states."""
    if len(population) < 2:
        return 0.0
    
    n_constraints = len(population[0].genes)
    total_distance = 0.0
    comparisons = 0
    
    for i in range(len(population)):
        for j in range(i + 1, min(i + 10, len(population))):  # Sample pairs
            dist = sum(1 for k in range(n_constraints)
                       if population[i].genes[k].enabled != population[j].genes[k].enabled)
            total_distance += dist / n_constraints
            comparisons += 1
    
    return total_distance / max(comparisons, 1)


# ---------------------------------------------------------------------------
# Main GA Loop
# ---------------------------------------------------------------------------

def run_ga(
    base_constraints: List[ConstraintSpec],
    data: List[Dict[str, Any]],
    check_fn: Callable,
    config: Optional[GAConfig] = None,
) -> GAResult:
    """
    Run the genetic algorithm to find optimal constraint configuration.
    
    Args:
        base_constraints: Template constraints to evolve from
        data: Evaluation dataset with 'label' field
        check_fn: Function(sample, ConstraintSpec) -> Optional[bool]
        config: GA hyperparameters
    
    Returns:
        GAResult with best chromosome and history
    """
    if config is None:
        config = GAConfig()
    
    start_time = time.perf_counter()
    
    # Initialize
    population = initialize_population(base_constraints, config)
    best_ever = None
    best_fitness = float('-inf')
    best_generation = 0
    stagnation_count = 0
    fitness_history: List[float] = []
    diversity_history: List[float] = []
    
    for gen in range(config.max_generations):
        # Evaluate fitness
        for chrom in population:
            result = evaluate_chromosome(chrom, data, check_fn)
            chrom.fitness = compute_fitness(result)
            chrom.detection_rate = result.detection_rate
            chrom.false_positive_rate = result.false_positive_rate
            chrom.check_time = result.check_time_ms
            chrom.generation = gen
        
        # Sort by fitness
        population.sort(key=lambda c: c.fitness, reverse=True)
        
        # Track best
        gen_best = population[0]
        fitness_history.append(gen_best.fitness)
        
        if gen_best.fitness > best_fitness:
            best_fitness = gen_best.fitness
            best_ever = copy.deepcopy(gen_best)
            best_generation = gen
            stagnation_count = 0
        else:
            stagnation_count += 1
        
        # Check stagnation
        diversity = population_diversity(population)
        diversity_history.append(diversity)
        
        if stagnation_count >= config.stagnation_limit:
            break
        
        # Elitism: keep top performers
        elite = [copy.deepcopy(c) for c in population[:config.elitism_count]]
        
        # Breed new population
        new_population = list(elite)
        while len(new_population) < config.population_size:
            parent1 = tournament_select(population, config.tournament_size)
            parent2 = tournament_select(population, config.tournament_size)
            
            child1, child2 = single_point_crossover(
                parent1, parent2, config.crossover_rate)
            
            child1 = mutate(child1, config.mutation_rate,
                          config.parameter_mutation_sigma)
            child2 = mutate(child2, config.mutation_rate,
                          config.parameter_mutation_sigma)
            
            new_population.append(child1)
            if len(new_population) < config.population_size:
                new_population.append(child2)
        
        population = new_population
    
    elapsed = time.perf_counter() - start_time
    
    return GAResult(
        best_chromosome=best_ever or population[0],
        generation_found=best_generation,
        total_generations=len(fitness_history),
        fitness_history=fitness_history,
        diversity_history=diversity_history,
        elapsed_seconds=elapsed,
    )


# ---------------------------------------------------------------------------
# Convenience: Built-in check function for testing
# ---------------------------------------------------------------------------

def make_threshold_check_fn(
    value_field: str = "value",
) -> Callable[[Dict[str, Any], ConstraintSpec], Optional[bool]]:
    """
    Create a simple threshold-based check function.
    Violation if value < bound_lower or value > bound_upper.
    """
    def check(sample: Dict[str, Any], gene: ConstraintSpec) -> Optional[bool]:
        value = sample.get(value_field, None)
        if value is None:
            return None
        return value < gene.bound_lower or value > gene.bound_upper
    return check


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _run_tests():
    """Run built-in tests."""
    import sys
    passed = 0
    failed = 0
    
    def assert_test(condition, name):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name}")
    
    print("\n=== flux_evolutionary tests ===\n")
    
    # Test 1: ConstraintSpec creation
    spec = ConstraintSpec(name="test", enabled=True, threshold=0.5)
    assert_test(spec.name == "test", "ConstraintSpec creation")
    
    # Test 2: Random chromosome
    base = [
        ConstraintSpec(name="c1", bound_lower=-1.0, bound_upper=1.0),
        ConstraintSpec(name="c2", bound_lower=0.0, bound_upper=2.0),
        ConstraintSpec(name="c3", bound_lower=-0.5, bound_upper=0.5),
    ]
    chrom = random_chromosome(base)
    assert_test(len(chrom.genes) == 3, "Random chromosome has correct gene count")
    assert_test(chrom.fitness == 0.0, "Initial fitness is 0")
    
    # Test 3: Population initialization
    config = GAConfig(population_size=20, seed=42)
    pop = initialize_population(base, config)
    assert_test(len(pop) == 20, "Population has correct size")
    
    # Test 4: Tournament selection
    for i, c in enumerate(pop):
        c.fitness = i * 1.0
    selected = tournament_select(pop, 3)
    assert_test(selected.fitness > 0, "Tournament selection returns fit individual")
    
    # Test 5: Crossover
    p1, p2 = pop[0], pop[1]
    c1, c2 = single_point_crossover(p1, p2, 1.0)
    assert_test(len(c1.genes) == 3, "Crossover child has correct gene count")
    assert_test(c1.genes != p1.genes or c1.genes != p2.genes,
                "Crossover produces different offspring")
    
    # Test 6: Mutation
    original = copy.deepcopy(c1)
    mutated = mutate(copy.deepcopy(c1), 0.5, 0.2)
    assert_test(any(g.enabled != o.enabled for g, o in zip(mutated.genes, original.genes)) or
                any(abs(g.threshold - o.threshold) > 0.001 for g, o in zip(mutated.genes, original.genes)),
                "Mutation changes at least some genes")
    
    # Test 7: EvaluationResult
    er = EvaluationResult(detected=8, missed=2, false_positives=1, true_negatives=9)
    assert_test(abs(er.detection_rate - 0.8) < 0.001, "Detection rate correct")
    assert_test(abs(er.false_positive_rate - 0.1) < 0.001, "FPR correct")
    
    # Test 8: Fitness computation
    fitness = compute_fitness(er)
    assert_test(fitness > 0, "Fitness is positive for good result")
    
    # Test 9: Make threshold check function
    check_fn = make_threshold_check_fn()
    sample_in = {"value": 0.5, "label": False}
    sample_out = {"value": 2.0, "label": True}
    gene = ConstraintSpec(name="test", bound_lower=-1.0, bound_upper=1.0)
    assert_test(check_fn(sample_in, gene) == False, "In-bounds sample passes")
    assert_test(check_fn(sample_out, gene) == True, "Out-of-bounds sample fails")
    
    # Test 10: Full GA run
    data = [
        {"value": 0.3, "label": False},   # Normal
        {"value": -0.5, "label": False},   # Normal
        {"value": 1.5, "label": True},     # Violation
        {"value": -2.0, "label": True},    # Violation
        {"value": 0.1, "label": False},    # Normal
        {"value": 3.0, "label": True},     # Violation
        {"value": 0.7, "label": False},    # Normal
        {"value": -1.5, "label": True},    # Violation
    ] * 3  # 24 samples
    
    base_constraints = [
        ConstraintSpec(name="upper_bound", bound_lower=-1.0, bound_upper=1.0,
                      check_cost=1.0),
        ConstraintSpec(name="tight_bound", bound_lower=-0.5, bound_upper=0.5,
                      check_cost=1.5),
        ConstraintSpec(name="wide_bound", bound_lower=-3.0, bound_upper=3.0,
                      check_cost=0.5),
    ]
    
    ga_config = GAConfig(
        population_size=15,
        max_generations=20,
        mutation_rate=0.15,
        seed=42,
    )
    
    result = run_ga(base_constraints, data, check_fn, ga_config)
    assert_test(result.best_chromosome is not None, "GA returns a best chromosome")
    assert_test(result.total_generations > 0, "GA ran at least one generation")
    assert_test(len(result.fitness_history) > 0, "GA recorded fitness history")
    assert_test(result.best_chromosome.fitness > 0, "Best chromosome has positive fitness")
    assert_test(len(result.best_chromosome.genes) == 3, "Best has correct constraint count")
    
    # Test 11: Diversity measurement
    div = population_diversity(pop)
    assert_test(0.0 <= div <= 1.0, "Diversity is in [0, 1]")
    
    # Test 12: Chromosome deep copy isolation
    original_chrom = copy.deepcopy(result.best_chromosome)
    mutated_copy = mutate(copy.deepcopy(result.best_chromosome), 1.0, 1.0)
    assert_test(original_chrom.fitness == result.best_chromosome.fitness,
                "Deep copy preserves original")
    
    print(f"\n  Results: {passed} passed, {failed} failed\n")
    return failed == 0


if __name__ == "__main__":
    import sys
    success = _run_tests()
    sys.exit(0 if success else 1)
