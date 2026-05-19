"""
flux_homeostasis.py — Homeostatic Feedback Loops, Adaptive Bounds, and Constraint Evolution

Two biology-inspired mechanisms for constraint systems:

1. HomeostaticController: Maintains constraint system stability through
   feedback loops. Monitors constraint health, adjusts bounds dynamically,
   supports "fever" (relaxed bounds) and "hypothermia" (tightened bounds) modes.

2. ConstraintEvolution: Sexual evolution of constraint configurations.
   Combines the best-performing configurations from different environments
   through crossover and mutation, selecting the fittest over generations.

Usage:
    from flux_homeostasis import HomeostaticController, ConstraintEvolution
"""

from __future__ import annotations
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable


# ===========================================================================
# 1. Homeostatic Controller
# ===========================================================================

class HomeostasisMode(Enum):
    """Operating modes for the homeostatic controller."""
    NORMAL = "normal"           # Setpoint active, negative feedback
    FEVER = "fever"             # Raised bounds (system under stress)
    HYPOTHERMIA = "hypothermia" # Lowered bounds (system conserving)


@dataclass
class ConstraintSetpoint:
    """Desired state for a constraint parameter.

    The setpoint defines the "body temperature" of a constraint —
    the value it should maintain. Like biological setpoints, these
    can shift in response to systemic conditions (fever raises
    temperature setpoint to fight infection).
    """
    name: str
    target: float              # Desired value
    lower_bound: float         # Minimum acceptable
    upper_bound: float         # Maximum acceptable
    tolerance: float = 0.1     # Allowed deviation from target
    priority: float = 1.0      # Higher = more critical

    @property
    def range(self) -> float:
        return self.upper_bound - self.lower_bound


@dataclass
class SensorReading:
    """A measurement from a constraint sensor."""
    constraint_name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    deviation: float = 0.0     # Distance from setpoint
    is_alert: bool = False     # Beyond tolerance


@dataclass
class EffectorAction:
    """An action taken to restore homeostatic balance."""
    constraint_name: str
    action_type: str           # "tighten", "relax", "escalate", "stabilize"
    magnitude: float           # How much to adjust
    reason: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class HomeostaticState:
    """Current state of the homeostatic controller."""
    mode: HomeostasisMode = HomeostasisMode.NORMAL
    total_deviation: float = 0.0
    max_deviation: float = 0.0
    alerts: int = 0
    actions_taken: int = 0
    last_adjustment: float = 0.0


class HomeostaticController:
    """Homeostatic feedback controller for constraint systems.

    Mirrors biological homeostasis:
    - Setpoints define desired constraint bounds (like body temperature)
    - Sensors measure current state
    - Comparator calculates deviation from setpoint
    - Effectors take corrective action
    - Feedback loops adjust bounds dynamically

    The controller supports three modes:
    - NORMAL: Setpoints active, negative feedback reduces deviation
    - FEVER: Bounds raised to allow adaptation under stress
    - HYPOTHERMIA: Bounds lowered during stable periods for precision

    Example:
        >>> controller = HomeostaticController()
        >>> controller.add_setpoint("response_time", target=100, lower=50, upper=200)
        >>> controller.sense("response_time", 150)
        >>> actions = controller.compare_and_act()
    """

    def __init__(
        self,
        fever_threshold: float = 0.8,      # Deviation fraction triggering fever
        hypothermia_threshold: float = 0.05, # Deviation fraction triggering hypothermia
        adaptation_rate: float = 0.1,        # How fast bounds adjust
        negative_feedback_gain: float = 0.5, # Strength of corrective action
        positive_feedback_gain: float = 0.2, # Strength of amplification
        history_size: int = 100,
    ):
        self.fever_threshold = fever_threshold
        self.hypothermia_threshold = hypothermia_threshold
        self.adaptation_rate = adaptation_rate
        self.negative_feedback_gain = negative_feedback_gain
        self.positive_feedback_gain = positive_feedback_gain
        self.history_size = history_size

        self.setpoints: dict[str, ConstraintSetpoint] = {}
        self.state = HomeostaticState()
        self.readings: dict[str, list[SensorReading]] = {}
        self.actions: list[EffectorAction] = []
        self._mode_history: list[tuple[float, HomeostasisMode]] = []

    def add_setpoint(
        self,
        name: str,
        target: float,
        lower: float,
        upper: float,
        tolerance: float = 0.1,
        priority: float = 1.0,
    ):
        """Add a constraint setpoint."""
        sp = ConstraintSetpoint(
            name=name,
            target=target,
            lower_bound=lower,
            upper_bound=upper,
            tolerance=tolerance,
            priority=priority,
        )
        self.setpoints[name] = sp
        self.readings[name] = []

    def sense(self, constraint_name: str, value: float) -> SensorReading:
        """Take a sensor reading for a constraint.

        Measures the current value and calculates deviation from setpoint.
        """
        sp = self.setpoints.get(constraint_name)
        if sp is None:
            raise ValueError(f"No setpoint for '{constraint_name}'")

        # Calculate deviation as fraction of range
        deviation = abs(value - sp.target) / max(sp.range, 1e-10)
        is_alert = deviation > sp.tolerance

        reading = SensorReading(
            constraint_name=constraint_name,
            value=value,
            deviation=deviation,
            is_alert=is_alert,
        )

        # Store reading
        history = self.readings[constraint_name]
        history.append(reading)
        if len(history) > self.history_size:
            history.pop(0)

        return reading

    def _avg_deviation(self) -> float:
        """Average deviation across all constraints."""
        deviations = []
        for name, readings in self.readings.items():
            if readings:
                deviations.append(readings[-1].deviation)
        return sum(deviations) / len(deviations) if deviations else 0.0

    def _max_deviation(self) -> float:
        """Maximum deviation across all constraints."""
        max_d = 0.0
        for name, readings in self.readings.items():
            if readings:
                max_d = max(max_d, readings[-1].deviation)
        return max_d

    def _detect_mode(self):
        """Detect whether the system should enter fever or hypothermia."""
        avg_dev = self._avg_deviation()
        max_dev = self._max_deviation()

        if max_dev >= self.fever_threshold:
            new_mode = HomeostasisMode.FEVER
        elif avg_dev <= self.hypothermia_threshold:
            new_mode = HomeostasisMode.HYPOTHERMIA
        else:
            new_mode = HomeostasisMode.NORMAL

        if new_mode != self.state.mode:
            self._mode_history.append((time.time(), new_mode))
            self.state.mode = new_mode

    def compare_and_act(self) -> list[EffectorAction]:
        """Compare current state to setpoints and take corrective action.

        This is the core homeostatic loop:
        1. Calculate deviations
        2. Detect operating mode
        3. Apply negative feedback (reduce deviation)
        4. Apply mode-specific adjustments
        """
        self._detect_mode()

        actions = []
        for name, sp in self.setpoints.items():
            readings = self.readings.get(name, [])
            if not readings:
                continue

            latest = readings[-1]
            if not latest.is_alert:
                continue

            # Negative feedback: correct toward setpoint
            if latest.deviation > sp.tolerance:
                magnitude = self.negative_feedback_gain * latest.deviation

                if self.state.mode == HomeostasisMode.FEVER:
                    # During fever: relax bounds (allow more deviation)
                    action_type = "relax"
                    magnitude *= 1.5
                    reason = "fever mode — relaxing bounds to reduce stress"
                elif self.state.mode == HomeostasisMode.HYPOTHERMIA:
                    # During hypothermia: tighten bounds (be more strict)
                    action_type = "tighten"
                    magnitude *= 2.0
                    reason = "hypothermia mode — tightening for precision"
                else:
                    action_type = "stabilize"
                    reason = "normal mode — applying negative feedback"

                # Adjust the setpoint bounds
                adjustment = self.adaptation_rate * magnitude * sp.range
                if latest.value > sp.target:
                    sp.upper_bound += adjustment if action_type == "relax" else -adjustment
                else:
                    sp.lower_bound -= adjustment if action_type == "relax" else -adjustment

                action = EffectorAction(
                    constraint_name=name,
                    action_type=action_type,
                    magnitude=magnitude,
                    reason=reason,
                )
                actions.append(action)
                self.state.actions_taken += 1

        # Update state
        self.state.total_deviation = self._avg_deviation()
        self.state.max_deviation = self._max_deviation()
        self.state.alerts = sum(
            1 for readings in self.readings.values()
            if readings and readings[-1].is_alert
        )
        self.actions.extend(actions)
        if len(self.actions) > self.history_size:
            self.actions = self.actions[-self.history_size:]

        return actions

    def check(self, constraint_name: str, value: float) -> tuple[bool, float, list[EffectorAction]]:
        """Convenience: sense + compare_and_act for a single constraint.

        Returns (in_bounds, deviation, actions).
        """
        reading = self.sense(constraint_name, value)
        sp = self.setpoints[constraint_name]
        in_bounds = sp.lower_bound <= value <= sp.upper_bound
        actions = self.compare_and_act()
        return in_bounds, reading.deviation, actions

    def statistics(self) -> dict:
        """Return controller statistics."""
        return {
            "mode": self.state.mode.value,
            "total_deviation": round(self.state.total_deviation, 4),
            "max_deviation": round(self.state.max_deviation, 4),
            "alerts": self.state.alerts,
            "actions_taken": self.state.actions_taken,
            "setpoints": len(self.setpoints),
            "mode_changes": len(self._mode_history),
        }


# ===========================================================================
# 2. Constraint Evolution (Sexual Reproduction of Configurations)
# ===========================================================================

class GeneType(Enum):
    """Types of genes in a constraint chromosome."""
    BINARY = "binary"       # On/off for a constraint
    THRESHOLD = "threshold" # Numeric threshold value
    WEIGHT = "weight"       # Relative importance weight
    PRIORITY = "priority"   # Execution priority


@dataclass
class Gene:
    """A single gene in the constraint chromosome.

    Each gene controls one aspect of a constraint configuration:
    - Whether the constraint is enabled
    - Its threshold value
    - Its weight in the fitness function
    - Its execution priority
    """
    name: str
    gene_type: GeneType
    value: Any               # Current value (bool, float, etc.)
    min_value: float = 0.0   # For numeric genes
    max_value: float = 1.0   # For numeric genes

    def mutate(self, rate: float = 0.1, rng: random.Random | None = None) -> Gene:
        """Create a mutated copy of this gene."""
        rng = rng or random.Random()
        if rng.random() > rate:
            return Gene(name=self.name, gene_type=self.gene_type, value=self.value,
                       min_value=self.min_value, max_value=self.max_value)

        if self.gene_type == GeneType.BINARY:
            new_val = not self.value
        else:
            # Gaussian perturbation
            delta = rng.gauss(0, (self.max_value - self.min_value) * 0.1)
            new_val = max(self.min_value, min(self.max_value, float(self.value) + delta))

        return Gene(name=self.name, gene_type=self.gene_type, value=new_val,
                   min_value=self.min_value, max_value=self.max_value)


@dataclass
class Chromosome:
    """A complete constraint configuration encoded as a chromosome.

    Each chromosome represents one possible constraint configuration.
    Genes control individual constraint parameters.
    """
    genes: list[Gene]
    fitness: float = 0.0
    generation: int = 0
    origin: str = "random"   # "random", "crossover", "mutation"
    uid: str = ""

    def __post_init__(self):
        if not self.uid:
            raw = ",".join(f"{g.name}={g.value}" for g in self.genes)
            self.uid = hashlib.sha256(raw.encode()).hexdigest()[:12] if raw else ""

    @property
    def gene_dict(self) -> dict[str, Gene]:
        return {g.name: g for g in self.genes}

    def get_gene(self, name: str) -> Optional[Gene]:
        for g in self.genes:
            if g.name == name:
                return g
        return None


@dataclass
class EvolutionConfig:
    """Configuration for the evolutionary algorithm."""
    population_size: int = 50
    crossover_rate: float = 0.7
    mutation_rate: float = 0.1
    tournament_size: int = 3
    elite_count: int = 2
    max_generations: int = 100
    convergence_patience: int = 20
    niching_radius: float = 0.3    # For diversity maintenance


@dataclass
class EvolutionStats:
    """Statistics from an evolutionary run."""
    generation: int = 0
    best_fitness: float = 0.0
    avg_fitness: float = 0.0
    worst_fitness: float = 0.0
    diversity: float = 0.0  # Genetic diversity in population
    stagnation: int = 0     # Generations without improvement


class ConstraintEvolution:
    """Sexual evolution of constraint configurations.

    Combines the best-performing constraint configurations through
    crossover and mutation, selecting the fittest over generations.

    Inspired by biological sexual reproduction:
    - Chromosomes encode complete constraint configurations
    - Crossover combines genes from two parents
    - Mutation adds random variation
    - Selection picks the fittest for reproduction
    - Niching prevents premature convergence

    Example:
        >>> gene_specs = [
        ...     Gene("range_enabled", GeneType.BINARY, True),
        ...     Gene("range_threshold", GeneType.THRESHOLD, 0.5, 0.0, 1.0),
        ...     Gene("type_enabled", GeneType.BINARY, True),
        ... ]
        >>> def fitness(chromosome):
        ...     return sum(1.0 for g in chromosome.genes if g.value is True or g.value > 0.5)
        >>> evo = ConstraintEvolution(gene_specs, fitness)
        >>> best = evo.run()
        >>> print(best.fitness)
    """

    def __init__(
        self,
        gene_specs: list[Gene],
        fitness_fn: Callable[[Chromosome], float],
        config: EvolutionConfig | None = None,
        seed: int | None = None,
    ):
        self.gene_specs = gene_specs
        self.fitness_fn = fitness_fn
        self.config = config or EvolutionConfig()
        self._rng = random.Random(seed)

        self.population: list[Chromosome] = []
        self.best: Optional[Chromosome] = None
        self.history: list[EvolutionStats] = []
        self._generation = 0
        self._best_fitness_history: list[float] = []

    def _random_chromosome(self) -> Chromosome:
        """Generate a random chromosome from gene specs."""
        genes = []
        for spec in self.gene_specs:
            if spec.gene_type == GeneType.BINARY:
                value = self._rng.choice([True, False])
            elif spec.gene_type == GeneType.THRESHOLD:
                value = self._rng.uniform(spec.min_value, spec.max_value)
            elif spec.gene_type == GeneType.WEIGHT:
                value = self._rng.uniform(0.0, 1.0)
            elif spec.gene_type == GeneType.PRIORITY:
                value = self._rng.randint(int(spec.min_value), int(spec.max_value))
            else:
                value = self._rng.uniform(spec.min_value, spec.max_value)

            genes.append(Gene(
                name=spec.name,
                gene_type=spec.gene_type,
                value=value,
                min_value=spec.min_value,
                max_value=spec.max_value,
            ))
        return Chromosome(genes=genes, origin="random")

    def _initialize_population(self):
        """Create initial random population."""
        self.population = [
            self._random_chromosome()
            for _ in range(self.config.population_size)
        ]
        self._evaluate_population()

    def _evaluate_population(self):
        """Evaluate fitness for entire population."""
        for chrom in self.population:
            chrom.fitness = self.fitness_fn(chrom)
            chrom.generation = self._generation

        # Update best
        current_best = max(self.population, key=lambda c: c.fitness)
        if self.best is None or current_best.fitness > self.best.fitness:
            self.best = Chromosome(
                genes=list(current_best.genes),
                fitness=current_best.fitness,
                generation=self._generation,
                origin=current_best.origin,
            )

    def _tournament_select(self) -> Chromosome:
        """Select a chromosome using tournament selection."""
        candidates = self._rng.sample(
            self.population,
            min(self.config.tournament_size, len(self.population))
        )
        return max(candidates, key=lambda c: c.fitness)

    def _crossover(self, parent1: Chromosome, parent2: Chromosome) -> Chromosome:
        """Uniform crossover: each gene comes from either parent.

        This is the "sexual reproduction" step — genes from two
        successful parents combine to create offspring that may
        inherit the best traits of both.
        """
        child_genes = []
        for g1, g2 in zip(parent1.genes, parent2.genes):
            if self._rng.random() < 0.5:
                child_genes.append(Gene(
                    name=g1.name, gene_type=g1.gene_type, value=g1.value,
                    min_value=g1.min_value, max_value=g1.max_value,
                ))
            else:
                child_genes.append(Gene(
                    name=g2.name, gene_type=g2.gene_type, value=g2.value,
                    min_value=g2.min_value, max_value=g2.max_value,
                ))
        return Chromosome(genes=child_genes, generation=self._generation, origin="crossover")

    def _mutate(self, chromosome: Chromosome) -> Chromosome:
        """Mutate a chromosome's genes."""
        mutated_genes = [g.mutate(self.config.mutation_rate, self._rng) for g in chromosome.genes]
        return Chromosome(
            genes=mutated_genes,
            generation=self._generation,
            origin="mutation",
        )

    def _genetic_diversity(self) -> float:
        """Measure genetic diversity in population.

        Uses average pairwise Hamming distance between chromosomes.
        """
        if len(self.population) < 2:
            return 0.0

        sample_size = min(10, len(self.population))
        sample = self._rng.sample(self.population, sample_size)

        distances = []
        for i in range(len(sample)):
            for j in range(i + 1, len(sample)):
                dist = 0
                for g1, g2 in zip(sample[i].genes, sample[j].genes):
                    if g1.value != g2.value:
                        dist += 1
                    elif isinstance(g1.value, (int, float)):
                        dist += abs(float(g1.value) - float(g2.value))
                distances.append(dist / max(len(sample[0].genes), 1))

        return sum(distances) / len(distances) if distances else 0.0

    def _niching(self):
        """Apply niching (fitness sharing) to prevent premature convergence.

        Chromosomes that are too similar share fitness, reducing the
        advantage of clustering around one solution.
        """
        for i, chrom in enumerate(self.population):
            sharing = 0.0
            for j, other in enumerate(self.population):
                if i == j:
                    continue
                dist = sum(
                    1 for g1, g2 in zip(chrom.genes, other.genes)
                    if g1.value != g2.value
                ) / max(len(chrom.genes), 1)
                if dist < self.config.niching_radius:
                    sharing += 1 - (dist / self.config.niching_radius)
            if sharing > 0:
                chrom.fitness /= (1 + sharing)

    def step(self) -> EvolutionStats:
        """Run one generation of evolution.

        1. Select parents (tournament)
        2. Crossover (sexual reproduction)
        3. Mutate (random variation)
        4. Evaluate fitness
        5. Select survivors (elitism + fitness)
        """
        if not self.population:
            self._initialize_population()

        # Elitism: keep top performers
        sorted_pop = sorted(self.population, key=lambda c: c.fitness, reverse=True)
        elites = sorted_pop[:self.config.elite_count]

        # Create offspring
        offspring = []
        while len(offspring) < self.config.population_size - self.config.elite_count:
            p1 = self._tournament_select()
            p2 = self._tournament_select()

            if self._rng.random() < self.config.crossover_rate:
                child = self._crossover(p1, p2)
            else:
                child = Chromosome(
                    genes=[Gene(name=g.name, gene_type=g.gene_type, value=g.value,
                               min_value=g.min_value, max_value=g.max_value)
                          for g in p1.genes],
                    generation=self._generation,
                )

            child = self._mutate(child)
            offspring.append(child)

        # New population = elites + offspring
        self.population = elites + offspring
        self._evaluate_population()
        self._niching()

        # Stats
        fitnesses = [c.fitness for c in self.population]
        diversity = self._genetic_diversity()
        self._best_fitness_history.append(max(fitnesses))

        # Check stagnation
        stagnation = 0
        if len(self._best_fitness_history) >= 2:
            recent = self._best_fitness_history[-self.config.convergence_patience:]
            if len(recent) >= self.config.convergence_patience:
                if abs(recent[-1] - recent[0]) < 1e-6:
                    stagnation = self.config.convergence_patience

        stats = EvolutionStats(
            generation=self._generation,
            best_fitness=max(fitnesses),
            avg_fitness=sum(fitnesses) / len(fitnesses),
            worst_fitness=min(fitnesses),
            diversity=diversity,
            stagnation=stagnation,
        )
        self.history.append(stats)
        self._generation += 1
        return stats

    def run(self, max_generations: int | None = None) -> Chromosome:
        """Run evolution until convergence or max generations.

        Returns the best chromosome found.
        """
        max_gen = max_generations or self.config.max_generations
        self._initialize_population()

        for _ in range(max_gen):
            stats = self.step()
            if stats.stagnation >= self.config.convergence_patience:
                break

        return self.best

    def statistics(self) -> dict:
        """Return evolution statistics."""
        return {
            "generation": self._generation,
            "population_size": len(self.population),
            "best_fitness": self.best.fitness if self.best else None,
            "best_genes": {g.name: g.value for g in self.best.genes} if self.best else {},
            "diversity": self.history[-1].diversity if self.history else 0,
        }


# Need hashlib import at top level
import hashlib
