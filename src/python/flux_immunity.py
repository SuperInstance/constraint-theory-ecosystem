"""
flux_immunity.py — Immune System Negative Selection for Constraint Checking

Biology-inspired anomaly detection: instead of listing all invalid states
(combinatorially impossible), train on normal data and flag deviations.

How it works:
  1. Collect a "self set" of normal/valid values
  2. Generate random "detector" patterns
  3. Eliminate detectors that match any normal value (negative selection)
  4. Surviving detectors only match anomalous values
  5. When a value triggers a detector → anomaly detected

This mirrors T-cell maturation in the thymus:
  - Random T-cell receptors are generated
  - Those binding to self-proteins are eliminated (apoptosis)
  - Survivors circulate and trigger on non-self (pathogens)

Usage:
    immune = ImmuneConstraint(dimensions=3, detector_count=500)
    immune.train(normal_data)
    result = immune.check(novel_value)
    if result.is_anomalous:
        print(f"Anomaly score: {result.anomaly_score}")
"""

from __future__ import annotations
import math
import random
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

class DetectorType(Enum):
    EUCLIDEAN = "euclidean"     # Distance-based (continuous data)
    HYPERCUBE = "hypercube"     # Region-based (binned data)
    HAMMING = "hamming"         # Bit-difference (binary/categorical)


@dataclass
class Detector:
    """A single anomaly detector — the "T-cell" of the system.

    Each detector defines a region in feature space. If a value falls within
    that region, it's flagged as anomalous.
    """
    center: list[float]            # Center point in feature space
    radius: float                  # Detection radius
    detector_type: DetectorType = DetectorType.EUCLIDEAN
    activation_count: int = 0      # How many times this detector fired
    generation: int = 0            # Which generation of training produced this
    uid: str = ""

    def __post_init__(self):
        if not self.uid:
            raw = f"{self.center}:{self.radius}:{self.detector_type.value}"
            self.uid = hashlib.sha256(raw.encode()).hexdigest()[:12]

    def matches(self, value: list[float]) -> bool:
        """Check if value falls within this detector's detection region."""
        if self.detector_type == DetectorType.EUCLIDEAN:
            dist = self._euclidean_distance(value)
            return dist <= self.radius
        elif self.detector_type == DetectorType.HYPERCUBE:
            return self._hypercube_match(value)
        elif self.detector_type == DetectorType.HAMMING:
            return self._hamming_match(value)
        return False

    def distance_to(self, value: list[float]) -> float:
        """Raw distance from center to value."""
        return self._euclidean_distance(value)

    def _euclidean_distance(self, value: list[float]) -> float:
        if len(value) != len(self.center):
            return float('inf')
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(value, self.center)))

    def _hypercube_match(self, value: list[float]) -> bool:
        if len(value) != len(self.center):
            return False
        return all(abs(a - b) <= self.radius for a, b in zip(value, self.center))

    def _hamming_match(self, value: list[float]) -> bool:
        if len(value) != len(self.center):
            return False
        # Treat values as binary (>= 0.5 = 1, < 0.5 = 0)
        diff = sum(
            1 for a, b in zip(value, self.center)
            if (a >= 0.5) != (b >= 0.5)
        )
        return diff <= self.radius


@dataclass
class AnomalyResult:
    """Result of an immune constraint check."""
    value: list[float]
    is_anomalous: bool
    anomaly_score: float           # 0.0 = perfectly normal, 1.0 = max anomaly
    activated_detectors: list[Detector] = field(default_factory=list)
    total_detectors: int = 0
    coverage_fraction: float = 0.0  # fraction of non-self space covered

    @property
    def activation_count(self) -> int:
        return len(self.activated_detectors)

    @property
    def severity(self) -> str:
        if not self.is_anomalous:
            return "normal"
        if self.anomaly_score < 0.3:
            return "low"
        if self.anomaly_score < 0.7:
            return "medium"
        return "high"


@dataclass
class TrainingReport:
    """Summary of the negative selection training process."""
    total_candidates: int
    eliminated: int              # Detectors that matched self (eliminated)
    surviving: int               # Detectors that only match non-self
    elimination_rate: float      # fraction eliminated
    self_set_size: int
    generations: int = 1


# ---------------------------------------------------------------------------
# Negative Selection Algorithm
# ---------------------------------------------------------------------------

class NegativeSelection:
    """Core negative selection algorithm.

    Generates candidate detectors, then eliminates any that match the self set.
    The surviving population only activates on anomalous (non-self) inputs.
    """

    def __init__(
        self,
        dimensions: int,
        detector_type: DetectorType = DetectorType.EUCLIDEAN,
        radius_range: tuple[float, float] = (0.05, 0.3),
        self_tolerance: float = 0.01,
        seed: int | None = None,
    ):
        self.dimensions = dimensions
        self.detector_type = detector_type
        self.radius_range = radius_range
        self.self_tolerance = self_tolerance  # margin around self samples
        self._rng = random.Random(seed)

    def generate_candidates(self, count: int) -> list[Detector]:
        """Generate random candidate detectors (immature T-cells)."""
        candidates = []
        for _ in range(count):
            center = [self._rng.uniform(0, 1) for _ in range(self.dimensions)]
            radius = self._rng.uniform(*self.radius_range)
            candidates.append(Detector(
                center=center,
                radius=radius,
                detector_type=self.detector_type,
            ))
        return candidates

    def eliminate_self_reactive(
        self,
        candidates: list[Detector],
        self_set: list[list[float]],
    ) -> list[Detector]:
        """Negative selection: remove detectors that match any self sample.

        This is the thymic selection step. Detectors that react to self are
        eliminated (apoptosis), just like self-reactive T-cells.
        """
        surviving = []
        for detector in candidates:
            is_self_reactive = False
            for self_sample in self_set:
                # Use a slightly tighter radius for self-matching
                # (self_tolerance adds a buffer to avoid false positives)
                if detector.matches(self_sample):
                    is_self_reactive = True
                    break
            if not is_self_reactive:
                surviving.append(detector)
        return surviving

    def train(
        self,
        self_set: list[list[float]],
        target_count: int = 200,
        max_generations: int = 5,
        batch_size: int = 500,
    ) -> tuple[list[Detector], TrainingReport]:
        """Run multi-generation negative selection training.

        Args:
            self_set: Normal/valid samples (the "self" the system should tolerate)
            target_count: Desired number of surviving detectors
            max_generations: Max training rounds
            batch_size: Candidates per generation

        Returns:
            Tuple of (surviving detectors, training report)
        """
        all_surviving: list[Detector] = []
        total_candidates = 0

        for gen in range(max_generations):
            candidates = self.generate_candidates(batch_size)
            total_candidates += len(candidates)
            surviving = self.eliminate_self_reactive(candidates, self_set)

            # Tag with generation
            for d in surviving:
                d.generation = gen

            all_surviving.extend(surviving)

            if len(all_surviving) >= target_count:
                break

        # Trim to target if oversubscribed
        if len(all_surviving) > target_count:
            # Keep detectors with maximal coverage (spread them out)
            all_surviving = self._select_diverse(all_surviving, target_count)

        eliminated = total_candidates - len(all_surviving)
        report = TrainingReport(
            total_candidates=total_candidates,
            eliminated=eliminated,
            surviving=len(all_surviving),
            elimination_rate=eliminated / total_candidates if total_candidates > 0 else 0,
            self_set_size=len(self_set),
            generations=gen + 1,
        )
        return all_surviving, report

    def _select_diverse(self, detectors: list[Detector], count: int) -> list[Detector]:
        """Select a diverse subset of detectors for maximum coverage."""
        if len(detectors) <= count:
            return detectors

        selected = [detectors[0]]
        remaining = list(detectors[1:])

        while len(selected) < count and remaining:
            # Pick the detector farthest from already-selected
            best_idx = 0
            best_min_dist = -1
            for i, d in enumerate(remaining):
                min_dist = min(d.distance_to(s.center) for s in selected)
                if min_dist > best_min_dist:
                    best_min_dist = min_dist
                    best_idx = i
            selected.append(remaining.pop(best_idx))

        return selected


# ---------------------------------------------------------------------------
# Immune Constraint System
# ---------------------------------------------------------------------------

class ImmuneConstraintSystem:
    """Full immune-inspired constraint checking system.

    Combines negative selection training with real-time anomaly detection.
    Includes memory cells (frequently activated detectors get "promoted") and
    tolerance adjustment based on false positive rates.

    Args:
        dimensions: Number of features in each data point
        detector_count: Target number of anomaly detectors
        detector_type: Detection algorithm (euclidean, hypercube, hamming)

    Example:
        >>> immune = ImmuneConstraintSystem(dimensions=3, detector_count=100)
        >>> # Train on normal data
        >>> normal_data = [[0.5, 0.5, 0.5], [0.4, 0.6, 0.5], ...]
        >>> immune.train(normal_data)
        >>> # Check a new value
        >>> result = immune.check([0.5, 0.5, 0.5])
        >>> result.is_anomalous
        False
        >>> result = immune.check([0.99, 0.01, 0.99])
        >>> result.is_anomalous
        True
    """

    def __init__(
        self,
        dimensions: int,
        detector_count: int = 200,
        detector_type: DetectorType = DetectorType.EUCLIDEAN,
        anomaly_threshold: float = 1,
        seed: int | None = None,
    ):
        self.dimensions = dimensions
        self.detector_count = detector_count
        self.detector_type = detector_type
        self.anomaly_threshold = anomaly_threshold  # min activations to flag
        self._seed = seed
        self.detectors: list[Detector] = []
        self.memory_cells: list[Detector] = []  # Frequently activated
        self._trained = False
        self._self_set: list[list[float]] = []
        self._check_history: list[AnomalyResult] = []
        self._false_positive_buffer: list[AnomalyResult] = []

    @property
    def is_trained(self) -> bool:
        return self._trained

    @property
    def detector_population(self) -> int:
        return len(self.detectors)

    @property
    def memory_cell_count(self) -> int:
        return len(self.memory_cells)

    def train(
        self,
        self_set: list[list[float]],
        max_generations: int = 5,
    ) -> TrainingReport:
        """Train the immune system on normal data.

        Args:
            self_set: Collection of normal/valid data points.
                     Each point is a list of floats in [0, 1] range.
                     Normalize your data before passing it!
            max_generations: Max training rounds.

        Returns:
            TrainingReport with training statistics.
        """
        # Validate dimensions
        for s in self_set:
            if len(s) != self.dimensions:
                raise ValueError(
                    f"Self sample has {len(s)} dimensions, expected {self.dimensions}"
                )

        self._self_set = [list(s) for s in self_set]
        nsa = NegativeSelection(
            dimensions=self.dimensions,
            detector_type=self.detector_type,
            seed=self._seed,
        )
        self.detectors, report = nsa.train(
            self_set=self_set,
            target_count=self.detector_count,
            max_generations=max_generations,
        )
        self._trained = True
        return report

    def check(self, value: list[float]) -> AnomalyResult:
        """Check a value against the trained immune system.

        Any detector that matches the value indicates potential anomaly.
        More activations = higher anomaly score.

        Args:
            value: Data point to check (same dimensions as training data).

        Returns:
            AnomalyResult with anomaly score and activated detectors.
        """
        if not self._trained:
            raise RuntimeError("System not trained. Call train() first.")
        if len(value) != self.dimensions:
            raise ValueError(
                f"Value has {len(value)} dimensions, expected {self.dimensions}"
            )

        activated = []
        # Check against both regular detectors and memory cells
        all_detectors = self.detectors + self.memory_cells
        for detector in all_detectors:
            if detector.matches(value):
                detector.activation_count += 1
                activated.append(detector)

        # Anomaly score: fraction of detectors that activated
        total = len(all_detectors)
        score = len(activated) / total if total > 0 else 0.0
        is_anomalous = len(activated) >= self.anomaly_threshold

        result = AnomalyResult(
            value=value,
            is_anomalous=is_anomalous,
            anomaly_score=round(score, 6),
            activated_detectors=activated,
            total_detectors=total,
            coverage_fraction=round(len(self.detectors) / max(total, 1), 4),
        )

        # Promote frequently activated detectors to memory cells
        for d in activated:
            if d.activation_count >= 5 and d not in self.memory_cells:
                self.memory_cells.append(d)

        self._check_history.append(result)
        return result

    def report_false_positive(self, result: AnomalyResult):
        """Report a false positive to help calibrate the system.

        The system will attempt to eliminate detectors that cause false positives.
        """
        for d in result.activated_detectors:
            if d in self.detectors:
                self.detectors.remove(d)
                # Demote from memory cells too
                if d in self.memory_cells:
                    self.memory_cells.remove(d)

    def retrain_with_feedback(self):
        """Retrain using accumulated false positive data.

        Adds false positive values to the self set and re-trains.
        """
        fp_values = [r.value for r in self._false_positive_buffer]
        if fp_values:
            self._self_set.extend(fp_values)
            self._false_positive_buffer.clear()
            self.train(self._self_set)

    def statistics(self) -> dict:
        """Return system statistics."""
        total_checks = len(self._check_history)
        anomalies = sum(1 for r in self._check_history if r.is_anomalous)
        return {
            "total_checks": total_checks,
            "anomalies_detected": anomalies,
            "anomaly_rate": round(anomalies / total_checks, 4) if total_checks > 0 else 0,
            "detector_population": len(self.detectors),
            "memory_cells": len(self.memory_cells),
            "self_set_size": len(self._self_set),
            "dimensions": self.dimensions,
        }


# ---------------------------------------------------------------------------
# Helper: Data normalization
# ---------------------------------------------------------------------------

class Normalizer:
    """Min-max normalizer for preparing data for the immune system.

    Transforms data to [0, 1] range per dimension.
    """

    def __init__(self):
        self.mins: list[float] = []
        self.maxs: list[float] = []
        self._fitted = False

    def fit(self, data: list[list[float]]) -> Normalizer:
        """Compute min/max for each dimension."""
        if not data:
            return self
        dims = len(data[0])
        self.mins = [min(row[d] for row in data) for d in range(dims)]
        self.maxs = [max(row[d] for row in data) for d in range(dims)]
        self._fitted = True
        return self

    def transform(self, data: list[list[float]]) -> list[list[float]]:
        """Normalize data to [0, 1] range."""
        if not self._fitted:
            raise RuntimeError("Normalizer not fitted. Call fit() first.")
        result = []
        for row in data:
            normalized = []
            for d, val in enumerate(row):
                span = self.maxs[d] - self.mins[d]
                if span == 0:
                    normalized.append(0.5)
                else:
                    normalized.append((val - self.mins[d]) / span)
            result.append(normalized)
        return result

    def inverse_transform(self, data: list[list[float]]) -> list[list[float]]:
        """Denormalize data back to original range."""
        if not self._fitted:
            raise RuntimeError("Normalizer not fitted.")
        result = []
        for row in data:
            denorm = []
            for d, val in enumerate(row):
                span = self.maxs[d] - self.mins[d]
                denorm.append(val * span + self.mins[d])
            result.append(denorm)
        return result
