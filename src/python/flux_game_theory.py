"""
FLUX Game Theory — Nash equilibria, Shapley values, Vickrey mechanisms for constraint systems.

Insights from game theory applied to constraint checking:
1. Nash equilibrium: constraint bounds where no single change improves utility
2. Shapley value: fair credit distribution when multiple constraints detect violations
3. Vickrey mechanism: truthful bound reporting as dominant strategy

Forgemaster ⚒️ — 2026-05-19
"""

import math
import hashlib
from typing import List, Dict, Tuple, Optional, Callable
from itertools import combinations


# ── Data Types ──

class Constraint:
    """A single constraint with bounds and metadata."""
    def __init__(self, lo: float, hi: float, name: str = "", weight: float = 1.0):
        self.lo = lo
        self.hi = hi
        self.name = name
        self.weight = weight
    
    def check(self, value: float) -> bool:
        """Returns True if value is within bounds."""
        if value != value:  # NaN
            return False
        return self.lo <= value <= self.hi
    
    def __repr__(self):
        return f"Constraint({self.lo}, {self.hi}, '{self.name}')"


class ViolationEvent:
    """A violation detected by the system."""
    def __init__(self, value: float, constraints: List[Constraint],
                 violators: List[int], timestamp: float = 0.0):
        self.value = value
        self.constraints = constraints
        self.violators = violators  # indices of constraints that caught it
        self.timestamp = timestamp
    
    @property
    def n_total(self) -> int:
        return len(self.constraints)
    
    @property
    def n_violators(self) -> int:
        return len(self.violators)


# ── 1. Nash Equilibrium Finder ──

class NashConstraintFinder:
    """
    Find Nash equilibria for constraint systems.
    
    Each constraint is a 'player' that can adjust its bounds.
    Utility = weighted(detection_rate - false_positive_rate).
    Nash equilibrium: no player can improve utility by unilaterally changing bounds.
    
    For box constraints with exact checking:
    - Detection rate = P(value outside bounds | value is anomalous)
    - False positive rate = P(value outside bounds | value is normal)
    
    For normal-distributed values, the optimal bound that maximizes 
    (detection - false_positive) is the Neyman-Pearson threshold.
    """

    def __init__(self, constraints: List[Constraint],
                 normal_mean: float = 0.0, normal_std: float = 1.0,
                 anomaly_mean: float = 0.0, anomaly_std: float = 3.0):
        self.constraints = constraints
        self.normal_mean = normal_mean
        self.normal_std = normal_std
        self.anomaly_mean = anomaly_mean
        self.anomaly_std = anomaly_std

    def utility(self, lo: float, hi: float) -> float:
        """
        Utility of a single constraint with given bounds.
        detection_rate = P(outside bounds | anomaly distribution)
        false_positive_rate = P(outside bounds | normal distribution)
        utility = detection_rate - false_positive_rate
        """
        from math import erf, sqrt
        
        def normal_cdf(x, mu, sigma):
            return 0.5 * (1 + erf((x - mu) / (sigma * sqrt(2))))
        
        # Detection rate: probability anomaly falls outside bounds
        p_anomaly_in = normal_cdf(hi, self.anomaly_mean, self.anomaly_std) - \
                       normal_cdf(lo, self.anomaly_mean, self.anomaly_std)
        detection_rate = 1.0 - p_anomaly_in
        
        # False positive rate: probability normal falls outside bounds
        p_normal_in = normal_cdf(hi, self.normal_mean, self.normal_std) - \
                      normal_cdf(lo, self.normal_mean, self.normal_std)
        false_positive_rate = 1.0 - p_normal_in
        
        return detection_rate - false_positive_rate

    def find_equilibrium(self, iterations: int = 100, lr: float = 0.01) -> List[Tuple[float, float]]:
        """
        Find Nash equilibrium via iterated best response.
        Each player adjusts bounds to maximize utility given others' bounds.
        
        Returns list of (lo, hi) for each constraint at equilibrium.
        """
        n = len(self.constraints)
        bounds = [(c.lo, c.hi) for c in self.constraints]
        
        for _ in range(iterations):
            for i in range(n):
                best_utility = float('-inf')
                best_bounds = bounds[i]
                
                # Grid search over possible bounds for player i
                center = (bounds[i][0] + bounds[i][1]) / 2
                width = bounds[i][1] - bounds[i][0]
                
                for dlo in [-lr * width, 0, lr * width]:
                    for dhi in [-lr * width, 0, lr * width]:
                        new_lo = bounds[i][0] + dlo
                        new_hi = bounds[i][1] + dhi
                        if new_lo >= new_hi:
                            continue
                        
                        u = self.utility(new_lo, new_hi)
                        if u > best_utility:
                            best_utility = u
                            best_bounds = (new_lo, new_hi)
                
                bounds[i] = best_bounds
        
        return bounds

    def is_nash_equilibrium(self, bounds: List[Tuple[float, float]],
                            epsilon: float = 1e-6) -> bool:
        """Check if no player can improve by more than epsilon."""
        for i in range(len(bounds)):
            current_u = self.utility(bounds[i][0], bounds[i][1])
            # Try perturbations
            for dlo in [-epsilon, epsilon]:
                for dhi in [-epsilon, epsilon]:
                    if bounds[i][0] + dlo >= bounds[i][1] + dhi:
                        continue
                    if self.utility(bounds[i][0] + dlo, bounds[i][1] + dhi) > current_u + epsilon:
                        return False
        return True


# ── 2. Shapley Value for Detection Credit ──

class ShapleyCredit:
    """
    Distribute detection credit using Shapley values.
    
    When K constraints detect a violation out of N total,
    the Shapley value fairly distributes credit based on
    marginal contribution of each constraint across all
    possible orderings.
    
    φ_i = Σ_{S⊆N\{i}} (|S|! * (N-|S|-1)! / N!) * (v(S∪{i}) - v(S))
    
    For binary detection (each constraint either catches or doesn't):
    - If constraint i caught the violation: φ_i = 1/K
    - If constraint i missed: φ_i = 0
    
    This is because all detectors are symmetric — any K-subset 
    with equal size gets equal Shapley value.
    """

    def __init__(self, constraints: List[Constraint]):
        self.constraints = constraints
        self.n = len(constraints)

    def characteristic_function(self, coalition: set, value: float) -> float:
        """Value of a coalition: 1 if any member detects the violation, 0 otherwise."""
        for i in coalition:
            if not self.constraints[i].check(value):
                return 1.0
        return 0.0

    def shapley_values(self, value: float) -> List[float]:
        """Compute Shapley values for each constraint given a test value."""
        if self.n == 0:
            return []
        
        n = self.n
        values = [0.0] * n
        
        # For each constraint, sum over all subsets
        for i in range(n):
            others = [j for j in range(n) if j != i]
            
            for size in range(len(others) + 1):
                for subset in combinations(others, size):
                    s = set(subset)
                    weight = math.factorial(size) * math.factorial(n - size - 1) / math.factorial(n)
                    marginal = (self.characteristic_function(s | {i}, value) - 
                               self.characteristic_function(s, value))
                    values[i] += weight * marginal
        
        return values

    def shapley_batch(self, values: List[float]) -> List[List[float]]:
        """Compute Shapley values for a batch of test values."""
        return [self.shapley_values(v) for v in values]

    @staticmethod
    def shapley_symmetric(k: int, n: int) -> Tuple[float, float]:
        """
        Analytic Shapley value for symmetric binary detectors.
        K detectors caught, N total.
        
        Each catcher gets 1/K, each non-catcher gets 0.
        """
        if k == 0:
            return (0.0, 0.0)
        return (1.0 / k, 0.0)


# ── 3. Vickrey Constraint Mechanism ──

class VickreyMechanism:
    """
    Truthful mechanism for constraint bound reporting.
    
    Each constraint 'reports' its bounds. The mechanism uses
    the SECOND-BEST bounds (not the reporter's own) to evaluate
    that constraint, making truthful reporting dominant.
    
    Payment to constraint i:
        payment_i = utility(second-best bounds for i) - utility(reported bounds for i)
    
    This is incentive-compatible: reporting true bounds maximizes expected payment.
    """

    def __init__(self, constraints: List[Constraint],
                 penalty_per_missed: float = 10.0,
                 penalty_per_false_positive: float = 1.0):
        self.constraints = constraints
        self.penalty_missed = penalty_per_missed
        self.penalty_fp = penalty_per_false_positive

    def evaluate(self, reported_bounds: List[Tuple[float, float]],
                 test_values: List[Tuple[float, bool]]) -> Dict:
        """
        Evaluate reported bounds against labeled test data.
        test_values: list of (value, is_anomaly) pairs.
        
        Returns detection metrics and payments.
        """
        n = len(self.constraints)
        
        # Compute utility for each constraint's reported bounds
        utilities = []
        for i in range(n):
            lo, hi = reported_bounds[i]
            detections = 0
            false_positives = 0
            missed = 0
            
            for value, is_anomaly in test_values:
                violates = not (lo <= value <= hi) or value != value
                if violates and is_anomaly:
                    detections += 1
                elif violates and not is_anomaly:
                    false_positives += 1
                elif not violates and is_anomaly:
                    missed += 1
            
            utility = detections - self.penalty_fp * false_positives - self.penalty_missed * missed
            utilities.append(utility)
        
        # Vickrey payment: utility at second-best bounds minus utility at reported
        payments = []
        for i in range(n):
            # Second-best: use bounds from the nearest other constraint
            best_other_utility = float('-inf')
            for j in range(n):
                if j == i:
                    continue
                if utilities[j] > best_other_utility:
                    best_other_utility = utilities[j]
            
            payment = max(0, best_other_utility - utilities[i])
            payments.append(payment)
        
        return {
            "utilities": utilities,
            "payments": payments,
            "total_utility": sum(utilities),
            "total_payment": sum(payments),
        }

    def is_truthful(self, reported_bounds: List[Tuple[float, float]],
                    true_bounds: List[Tuple[float, float]],
                    test_values: List[Tuple[float, bool]]) -> bool:
        """
        Check if truthful reporting gives equal or better utility
        than the reported bounds (dominant strategy verification).
        """
        true_result = self.evaluate(true_bounds, test_values)
        reported_result = self.evaluate(reported_bounds, test_values)
        
        return true_result["total_utility"] >= reported_result["total_utility"]


# ── 4. Evolutionary Constraint Game ──

class EvolutionaryConstraintGame:
    """
    Constraint systems evolve through selection pressure.
    
    Population of constraint configurations, evaluated on data.
    Fitness = (detection_rate * weight_detect) - (false_positive_rate * weight_fp).
    Selection + mutation + crossover across generations.
    """

    def __init__(self, n_constraints: int = 4,
                 population_size: int = 20,
                 mutation_rate: float = 0.1,
                 crossover_rate: float = 0.5):
        self.n_constraints = n_constraints
        self.pop_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate

    def random_individual(self, lo_range: Tuple[float, float],
                          hi_range: Tuple[float, float]) -> List[Tuple[float, float]]:
        """Generate a random constraint configuration."""
        import random
        individual = []
        for _ in range(self.n_constraints):
            lo = random.uniform(*lo_range)
            hi = random.uniform(max(lo, lo_range[0]), hi_range[1])
            individual.append((lo, hi))
        return individual

    def fitness(self, individual: List[Tuple[float, float]],
                test_values: List[Tuple[float, bool]]) -> float:
        """Evaluate fitness against labeled data."""
        detections = 0
        false_positives = 0
        total_anomalies = sum(1 for _, a in test_values if a)
        total_normals = sum(1 for _, a in test_values if not a)
        
        for value, is_anomaly in test_values:
            # Any constraint violation counts as detection
            violates = any(not (lo <= value <= hi) or value != value
                         for lo, hi in individual)
            if violates and is_anomaly:
                detections += 1
            elif violates and not is_anomaly:
                false_positives += 1
        
        detection_rate = detections / max(1, total_anomalies)
        fp_rate = false_positives / max(1, total_normals)
        
        return detection_rate - fp_rate

    def evolve(self, test_values: List[Tuple[float, bool]],
               generations: int = 50,
               lo_range: Tuple[float, float] = (-10, -1),
               hi_range: Tuple[float, float] = (1, 10)) -> Tuple[List[Tuple[float, float]], List[float]]:
        """
        Run evolutionary optimization.
        Returns (best_individual, fitness_history).
        """
        import random
        
        # Initialize population
        population = [self.random_individual(lo_range, hi_range) 
                      for _ in range(self.pop_size)]
        
        history = []
        
        for gen in range(generations):
            # Evaluate fitness
            fitnesses = [(ind, self.fitness(ind, test_values)) 
                        for ind in population]
            fitnesses.sort(key=lambda x: x[1], reverse=True)
            
            best_fitness = fitnesses[0][1]
            history.append(best_fitness)
            
            # Selection: top 50%
            survivors = [ind for ind, _ in fitnesses[:self.pop_size // 2]]
            
            # Create next generation
            new_population = list(survivors)
            
            while len(new_population) < self.pop_size:
                # Tournament selection for parents
                p1 = random.choice(survivors)
                p2 = random.choice(survivors)
                
                # Crossover
                if random.random() < self.crossover_rate:
                    point = random.randint(1, self.n_constraints - 1)
                    child = p1[:point] + p2[point:]
                else:
                    child = list(p1)
                
                # Mutation
                if random.random() < self.mutation_rate:
                    idx = random.randint(0, self.n_constraints - 1)
                    lo, hi = child[idx]
                    delta = random.gauss(0, 0.5)
                    child[idx] = (lo + delta, hi + delta)
                    # Ensure lo < hi
                    child[idx] = (min(child[idx]), max(child[idx]))
                
                new_population.append(child)
            
            population = new_population[:self.pop_size]
        
        # Return best individual
        final_fitnesses = [(ind, self.fitness(ind, test_values)) 
                          for ind in population]
        final_fitnesses.sort(key=lambda x: x[1], reverse=True)
        
        return final_fitnesses[0][0], history
