"""
flux_ecology.py — Ecological Succession, Stigmergic Communication, and Slime Mold Optimization

Three biology-inspired mechanisms for constraint systems:

1. ConstraintSuccession: Ecological succession after violation events.
   Pioneer → Intermediate → Climax constraint communities rebuild checking
   in stages after disturbance.

2. StigmergicField: Indirect communication through data markers.
   Constraint checkers leave pheromone-like trails on data, guiding
   future checking toward problematic regions.

3. PhysarumOptimizer: Slime-mold-inspired constraint ordering.
   Virtual tubes connect constraints; flow reinforces efficient orderings
   while underused tubes decay.

Usage:
    from flux_ecology import ConstraintSuccession, StigmergicField, PhysarumOptimizer
"""

from __future__ import annotations
import math
import random
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable


# ===========================================================================
# 1. Ecological Succession
# ===========================================================================

class SuccessionStage(Enum):
    """Stages of constraint community development after disturbance."""
    DISTURBED = "disturbed"       # After violation event, no checks active
    PIONEER = "pioneer"           # Simple bounds checks (fast, cheap)
    INTERMEDIATE = "intermediate"  # Relationship checks (medium cost)
    CLIMAX = "climax"             # Complex invariants (expensive, thorough)


@dataclass
class ConstraintOrganism:
    """A single constraint checker in the ecological community.

    Each "organism" is a constraint that checks a specific property.
    Organisms have a cost (resources to evaluate), coverage (what they check),
    and fitness (how many violations they catch).
    """
    name: str
    check_fn: Callable[[Any], tuple[bool, float]]  # (passed, severity)
    stage: SuccessionStage
    cost: float = 1.0                  # Computational cost to evaluate
    coverage: float = 1.0              # Fraction of space covered
    fitness: float = 0.0               # Violations caught / checks run
    checks_run: int = 0
    violations_caught: int = 0
    age: int = 0                       # Generations survived
    established: bool = False          # Fully integrated into community

    def check(self, value: Any) -> tuple[bool, float]:
        """Run this constraint check, update fitness."""
        self.checks_run += 1
        passed, severity = self.check_fn(value)
        if not passed:
            self.violations_caught += 1
        self.fitness = self.violations_caught / max(self.checks_run, 1)
        self.age += 1
        if self.checks_run >= 10 and self.fitness > 0.01:
            self.established = True
        return passed, severity


@dataclass
class SuccessionEvent:
    """Record of a succession transition."""
    from_stage: SuccessionStage
    to_stage: SuccessionStage
    trigger: str
    timestamp: float = field(default_factory=time.time)
    community_size: int = 0


class ConstraintSuccession:
    """Ecological succession for constraint checking.

    After a disturbance (major violation event), the constraint community
    rebuilds in stages:

    1. PIONEER: Fast, cheap checks colonize first (bounds, null, type)
    2. INTERMEDIATE: Medium checks establish (relationships, consistency)
    3. CLIMAX: Complex invariants form stable community (global constraints)

    Transitions happen when the current community's fitness stabilizes
    (organisms are established with consistent detection rates).

    Example:
        >>> def check_range(v):
        ...     return (0 <= v <= 100, 0.5)
        >>> succession = ConstraintSuccession()
        >>> pioneer = ConstraintOrganism("range", check_range, SuccessionStage.PIONEER)
        >>> succession.add_organism(pioneer)
        >>> succession.disturb("system crash")
        >>> results = succession.check(50)
    """

    def __init__(
        self,
        pioneer_threshold: float = 0.8,    # % of pioneer organisms established
        intermediate_threshold: float = 0.7, # % of intermediate established
        stability_window: int = 10,          # Checks for stability
    ):
        self.stage = SuccessionStage.DISTURBED
        self.organisms: dict[SuccessionStage, list[ConstraintOrganism]] = {
            stage: [] for stage in SuccessionStage
        }
        self.pioneer_threshold = pioneer_threshold
        self.intermediate_threshold = intermediate_threshold
        self.stability_window = stability_window
        self.events: list[SuccessionEvent] = []
        self._check_count = 0
        self._disturbance_count = 0

    @property
    def community_size(self) -> int:
        return sum(len(orgs) for orgs in self.organisms.values())

    @property
    def active_organisms(self) -> list[ConstraintOrganism]:
        """Return organisms active in the current stage."""
        active = []
        stage_order = list(SuccessionStage)
        current_idx = stage_order.index(self.stage)
        for i in range(current_idx + 1):
            stage = stage_order[i]
            if stage != SuccessionStage.DISTURBED:
                active.extend(self.organisms[stage])
        return active

    def add_organism(self, organism: ConstraintOrganism):
        """Add a constraint organism to the community."""
        self.organisms[organism.stage].append(organism)

    def disturb(self, reason: str = "violation event"):
        """Trigger a disturbance — resets community to disturbed state.

        Like a forest fire: clears the active community but keeps
        the species pool (organisms) available for recolonization.
        """
        old_stage = self.stage
        self.stage = SuccessionStage.DISTURBED
        self._disturbance_count += 1
        self._check_count = 0

        # Reset organism fitness but keep them in the pool
        for stage_orgs in self.organisms.values():
            for org in stage_orgs:
                org.established = False
                org.checks_run = 0
                org.violations_caught = 0
                org.fitness = 0.0
                org.age = 0

        self.events.append(SuccessionEvent(
            from_stage=old_stage,
            to_stage=SuccessionStage.DISTURBED,
            trigger=reason,
            community_size=self.community_size,
        ))

    def _check_stage_transition(self) -> bool:
        """Check if current stage is ready to advance."""
        if self.stage == SuccessionStage.DISTURBED:
            # Pioneers can colonize immediately if any exist
            return len(self.organisms[SuccessionStage.PIONEER]) > 0

        if self.stage == SuccessionStage.PIONEER:
            pioneers = self.organisms[SuccessionStage.PIONEER]
            if not pioneers:
                return False
            established_frac = sum(1 for p in pioneers if p.established) / len(pioneers)
            return (established_frac >= self.pioneer_threshold
                    and self._check_count >= self.stability_window)

        if self.stage == SuccessionStage.INTERMEDIATE:
            intermediates = self.organisms[SuccessionStage.INTERMEDIATE]
            if not intermediates:
                return False
            established_frac = sum(1 for i in intermediates if i.established) / len(intermediates)
            return (established_frac >= self.intermediate_threshold
                    and self._check_count >= self.stability_window)

        return False  # CLIMAX is terminal

    def _advance_stage(self):
        """Advance to the next succession stage."""
        transitions = {
            SuccessionStage.DISTURBED: SuccessionStage.PIONEER,
            SuccessionStage.PIONEER: SuccessionStage.INTERMEDIATE,
            SuccessionStage.INTERMEDIATE: SuccessionStage.CLIMAX,
        }
        next_stage = transitions.get(self.stage)
        if next_stage:
            old = self.stage
            self.stage = next_stage
            self._check_count = 0  # Reset for next stability window
            self.events.append(SuccessionEvent(
                from_stage=old,
                to_stage=next_stage,
                trigger="stage transition",
                community_size=self.community_size,
            ))

    def check(self, value: Any) -> list[tuple[str, bool, float]]:
        """Check a value against active constraint community.

        Only organisms from established stages are active.
        Returns list of (organism_name, passed, severity) tuples.
        """
        results = []
        active = self.active_organisms

        for organism in active:
            passed, severity = organism.check(value)
            results.append((organism.name, passed, severity))

        self._check_count += 1

        # Check for stage transition
        if self._check_stage_transition():
            self._advance_stage()

        return results

    def statistics(self) -> dict:
        """Return succession statistics."""
        return {
            "stage": self.stage.value,
            "community_size": self.community_size,
            "active_organisms": len(self.active_organisms),
            "disturbances": self._disturbance_count,
            "checks_since_disturbance": self._check_count,
            "pioneers": len(self.organisms[SuccessionStage.PIONEER]),
            "intermediates": len(self.organisms[SuccessionStage.INTERMEDIATE]),
            "climax": len(self.organisms[SuccessionStage.CLIMAX]),
            "transitions": len(self.events),
        }


# ===========================================================================
# 2. Stigmergic Field — Indirect Communication Through Data Markers
# ===========================================================================

@dataclass
class PheromoneMarker:
    """A pheromone-like marker left on data by a constraint checker.

    Like ant pheromone trails, markers have intensity (decays over time)
    and type (which checker left it).
    """
    checker_name: str
    intensity: float       # 0.0 to 1.0
    timestamp: float       # When placed
    severity: float = 0.0  # Original violation severity
    uid: str = ""

    def __post_init__(self):
        if not self.uid:
            raw = f"{self.checker_name}:{self.intensity}:{self.timestamp}"
            self.uid = hashlib.sha256(raw.encode()).hexdigest()[:10]


@dataclass
class StigmergicDataItem:
    """A data item that carries pheromone markers.

    Checkers read and write markers on this item, communicating
    indirectly through the shared data surface.
    """
    key: str
    value: Any
    markers: list[PheromoneMarker] = field(default_factory=list)

    @property
    def total_intensity(self) -> float:
        """Sum of all marker intensities (after decay)."""
        return sum(m.intensity for m in self.markers)

    def strongest_marker(self) -> Optional[PheromoneMarker]:
        """Return the marker with highest intensity."""
        if not self.markers:
            return None
        return max(self.markers, key=lambda m: m.intensity)


class StigmergicField:
    """Stigmergic communication system for constraint checkers.

    Checkers communicate indirectly by leaving pheromone-like markers
    on data items. The field manages marker lifecycle:

    1. Placement: Checkers add markers when they find violations
    2. Evaporation: Markers decay over time (exponential decay)
    3. Reinforcement: Repeated violations strengthen existing markers
    4. Selection: Future checking is guided toward high-marker regions

    Example:
        >>> field = StigmergicField(evaporation_rate=0.1)
        >>> field.add_item("x", 42)
        >>> field.place_marker("x", "range_check", severity=0.8)
        >>> items = field.select_for_checking(count=5)
    """

    def __init__(
        self,
        evaporation_rate: float = 0.05,    # Per-tick decay rate
        min_intensity: float = 0.01,        # Below this, marker removed
        reinforcement_boost: float = 0.2,   # Added when same checker re-marks
        max_markers_per_item: int = 50,
    ):
        self.evaporation_rate = evaporation_rate
        self.min_intensity = min_intensity
        self.reinforcement_boost = reinforcement_boost
        self.max_markers_per_item = max_markers_per_item
        self.items: dict[str, StigmergicDataItem] = {}
        self._tick = 0

    def add_item(self, key: str, value: Any):
        """Add a data item to the field."""
        self.items[key] = StigmergicDataItem(key=key, value=value)

    def get_item(self, key: str) -> Optional[StigmergicDataItem]:
        """Get a data item by key."""
        return self.items.get(key)

    def place_marker(
        self,
        item_key: str,
        checker_name: str,
        severity: float = 1.0,
        timestamp: float | None = None,
    ):
        """Place a pheromone marker on a data item.

        If the same checker already has a marker on this item,
        reinforce it instead of adding a new one.
        """
        item = self.items.get(item_key)
        if item is None:
            return

        ts = timestamp or time.time()

        # Check for existing marker from same checker
        for marker in item.markers:
            if marker.checker_name == checker_name:
                # Reinforce existing marker
                marker.intensity = min(1.0, marker.intensity + self.reinforcement_boost)
                marker.severity = max(marker.severity, severity)
                marker.timestamp = ts
                return

        # New marker
        marker = PheromoneMarker(
            checker_name=checker_name,
            intensity=severity,
            timestamp=ts,
            severity=severity,
        )
        item.markers.append(marker)

        # Trim if too many markers
        if len(item.markers) > self.max_markers_per_item:
            # Remove weakest markers
            item.markers.sort(key=lambda m: m.intensity, reverse=True)
            item.markers = item.markers[:self.max_markers_per_item]

    def evaporate(self, ticks: int = 1):
        """Evaporate (decay) all markers.

        Intensity decays exponentially: I(t+1) = I(t) * (1 - rate)^ticks
        Markers below minimum intensity are removed.
        """
        decay = (1 - self.evaporation_rate) ** ticks
        for item in self.items.values():
            surviving = []
            for marker in item.markers:
                marker.intensity *= decay
                if marker.intensity >= self.min_intensity:
                    surviving.append(marker)
            item.markers = surviving

        self._tick += ticks

    def select_for_checking(self, count: int = 10) -> list[StigmergicDataItem]:
        """Select data items for checking, biased toward high-marker regions.

        Uses weighted random selection: items with more intense markers
        are more likely to be selected. This concentrates checking effort
        where violations are most common.
        """
        items = list(self.items.values())
        if not items:
            return []

        # Weight by total marker intensity (with small base weight)
        weights = []
        for item in items:
            w = item.total_intensity + 0.01  # Small base weight for unmarked items
            weights.append(w)

        total = sum(weights)
        if total == 0:
            return random.sample(items, min(count, len(items)))

        # Weighted selection without replacement
        selected = []
        remaining = list(zip(items, weights))
        for _ in range(min(count, len(remaining))):
            items_r, weights_r = zip(*remaining) if remaining else ([], [])
            total_r = sum(weights_r)
            if total_r == 0:
                break
            # Pick weighted random
            r = random.uniform(0, total_r)
            cumulative = 0
            picked_idx = 0
            for i, w in enumerate(weights_r):
                cumulative += w
                if r <= cumulative:
                    picked_idx = i
                    break
            selected.append(items_r[picked_idx])
            remaining.pop(picked_idx)

        return selected

    def field_intensity(self) -> dict[str, float]:
        """Return total marker intensity per item."""
        return {key: item.total_intensity for key, item in self.items.items()}

    def statistics(self) -> dict:
        """Return field statistics."""
        all_markers = [m for item in self.items.values() for m in item.markers]
        intensities = [m.intensity for m in all_markers]
        return {
            "items": len(self.items),
            "total_markers": len(all_markers),
            "total_intensity": sum(intensities) if intensities else 0,
            "avg_intensity": sum(intensities) / len(intensities) if intensities else 0,
            "max_intensity": max(intensities) if intensities else 0,
            "ticks": self._tick,
        }


# ===========================================================================
# 3. Physarum (Slime Mold) Constraint Ordering Optimizer
# ===========================================================================

@dataclass
class PhysarumTube:
    """A tube connecting two constraints in the Physarum network.

    Tube thickness represents ordering quality between two constraints.
    Thicker tubes = better ordering (constraints that should be adjacent).
    """
    from_constraint: str
    to_constraint: str
    thickness: float = 0.1       # Initial thickness
    flow: float = 0.0            # Current flow through tube
    quality: float = 0.0         # Last measured ordering quality
    evaluations: int = 0

    @property
    def uid(self) -> str:
        return f"{self.from_constraint}->{self.to_constraint}"


@dataclass
class OrderingResult:
    """Result of evaluating a constraint ordering."""
    ordering: list[str]
    quality: float                # Higher = better
    violations_detected: int = 0
    false_positives: int = 0
    evaluation_time: float = 0.0


class PhysarumOptimizer:
    """Slime-mold-inspired constraint ordering optimizer.

    Inspired by Physarum polycephalum, which finds shortest paths by
    growing tubes along all routes simultaneously. Tubes carrying useful
    flow thicken; underused tubes wither.

    Applied to constraint ordering:
    - Each constraint is a node
    - Tubes connect nodes (possible orderings)
    - Tube thickness = how good the ordering is
    - Flow = exploration rate
    - The system converges on the most efficient checking sequence

    Key equations:
        Flow:    f_ij = k * t_ij
        Update:  t_ij(t+1) = t_ij(t) + α * (Q - Q_best)  [reinforce]
                 t_ij(t+1) = t_ij(t) - β * t_ij(t)       [decay]
        Clamp:   t_ij = max(0, t_ij)

    Example:
        >>> constraints = ["range", "type", "consistency", "invariant"]
        >>> def evaluate(ordering):
        ...     # Return quality score for this ordering
        ...     return sum(1.0 / (i + 1) for i in range(len(ordering)))
        >>> optimizer = PhysarumOptimizer(constraints, evaluate)
        >>> best = optimizer.run(iterations=100)
        >>> print(best.ordering)
    """

    def __init__(
        self,
        constraints: list[str],
        evaluate_fn: Callable[[list[str]], float],
        initial_thickness: float = 0.1,
        flow_constant: float = 1.0,
        learning_rate: float = 0.1,
        decay_rate: float = 0.05,
        exploration_prob: float = 0.2,
        seed: int | None = None,
    ):
        self.constraints = constraints
        self.evaluate_fn = evaluate_fn
        self.flow_constant = flow_constant
        self.learning_rate = learning_rate
        self.decay_rate = decay_rate
        self.exploration_prob = exploration_prob
        self._rng = random.Random(seed)

        # Build tube network: all ordered pairs
        self.tubes: dict[str, PhysarumTube] = {}
        for i, c1 in enumerate(constraints):
            for j, c2 in enumerate(constraints):
                if i != j:
                    tube = PhysarumTube(
                        from_constraint=c1,
                        to_constraint=c2,
                        thickness=initial_thickness,
                    )
                    self.tubes[tube.uid] = tube

        self.best_result: Optional[OrderingResult] = None
        self.history: list[OrderingResult] = []
        self._iteration = 0

    def _extract_ordering(self) -> list[str]:
        """Extract constraint ordering from tube thicknesses.

        Uses a greedy walk: start from the constraint with highest
        outgoing thickness, then follow the thickest tube to the next.
        With probability `exploration_prob`, uses random selection instead.
        """
        if self._rng.random() < self.exploration_prob:
            # Random exploration
            ordering = list(self.constraints)
            self._rng.shuffle(ordering)
            return ordering

        # Greedy walk following thickest tubes
        remaining = list(self.constraints)
        ordering = []

        # Start from constraint with highest outgoing thickness
        if remaining:
            best_start = max(remaining, key=lambda c: self._outgoing_thickness(c, remaining))
            ordering.append(best_start)
            remaining.remove(best_start)

        while remaining:
            current = ordering[-1]
            # Find thickest tube from current to any remaining
            candidates = []
            for c in remaining:
                uid = f"{current}->{c}"
                tube = self.tubes.get(uid)
                if tube:
                    candidates.append((c, tube.thickness))
                else:
                    candidates.append((c, 0.01))

            if not candidates:
                # Shouldn't happen, but safety
                ordering.extend(remaining)
                break

            # Weighted random selection from candidates
            total = sum(t for _, t in candidates)
            if total <= 0:
                next_c = self._rng.choice(remaining)
            else:
                r = self._rng.uniform(0, total)
                cumulative = 0
                next_c = candidates[-1][0]
                for c, t in candidates:
                    cumulative += t
                    if r <= cumulative:
                        next_c = c
                        break

            ordering.append(next_c)
            remaining.remove(next_c)

        return ordering

    def _outgoing_thickness(self, constraint: str, targets: list[str]) -> float:
        """Total outgoing tube thickness from a constraint to targets."""
        total = 0.0
        for t in targets:
            uid = f"{constraint}->{t}"
            tube = self.tubes.get(uid)
            if tube:
                total += tube.thickness
        return total

    def _update_tubes(self, ordering: list[str], quality: float):
        """Update tube thicknesses based on ordering quality.

        Reinforces tubes in the ordering, decays all tubes.
        """
        best_q = self.best_result.quality if self.best_result else 0.0

        # Reinforce tubes in the current ordering
        for i in range(len(ordering) - 1):
            uid = f"{ordering[i]}->{ordering[i + 1]}"
            tube = self.tubes.get(uid)
            if tube:
                improvement = max(0, quality - best_q)
                tube.thickness += self.learning_rate * (1.0 + improvement)
                tube.quality = quality
                tube.evaluations += 1

        # Decay all tubes
        for tube in self.tubes.values():
            tube.thickness *= (1 - self.decay_rate)
            tube.thickness = max(0, tube.thickness)

    def step(self) -> OrderingResult:
        """Run one iteration of the Physarum optimization.

        1. Extract ordering from tube network
        2. Evaluate ordering quality
        3. Update tube thicknesses
        """
        ordering = self._extract_ordering()
        quality = self.evaluate_fn(ordering)

        result = OrderingResult(ordering=ordering, quality=quality)
        self.history.append(result)

        # Update best
        if self.best_result is None or quality > self.best_result.quality:
            self.best_result = result

        # Update tubes
        self._update_tubes(ordering, quality)

        # Update flow
        for tube in self.tubes.values():
            tube.flow = self.flow_constant * tube.thickness

        self._iteration += 1
        return result

    def run(self, iterations: int = 100) -> OrderingResult:
        """Run optimization for N iterations.

        Returns the best ordering found.
        """
        for _ in range(iterations):
            self.step()
        return self.best_result

    def get_tube_matrix(self) -> dict[str, dict[str, float]]:
        """Get tube thicknesses as a matrix dict."""
        matrix: dict[str, dict[str, float]] = {}
        for c in self.constraints:
            matrix[c] = {}
            for c2 in self.constraints:
                if c != c2:
                    uid = f"{c}->{c2}"
                    tube = self.tubes.get(uid)
                    matrix[c][c2] = tube.thickness if tube else 0.0
        return matrix

    def statistics(self) -> dict:
        """Return optimizer statistics."""
        thicknesses = [t.thickness for t in self.tubes.values()]
        return {
            "iterations": self._iteration,
            "constraints": len(self.constraints),
            "tubes": len(self.tubes),
            "best_quality": self.best_result.quality if self.best_result else None,
            "best_ordering": self.best_result.ordering if self.best_result else None,
            "avg_thickness": sum(thicknesses) / len(thicknesses) if thicknesses else 0,
            "max_thickness": max(thicknesses) if thicknesses else 0,
            "active_tubes": sum(1 for t in thicknesses if t > 0.01),
        }
