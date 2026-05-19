"""
FLUX Unified API v4 — The Single Entry Point
=============================================

`from flux import ConstraintEngine, Strategy`

Wraps all eight FLUX modules into one cohesive engine:
1. FluxExact (core exact checking — zero-alloc hot path)
2. flux_optimize (adaptive ordering)
3. flux_information (predictive checking, anomaly detection)
4. flux_signal (Kalman prediction, wavelet analysis)
5. flux_formal (setup-time proofs)
6. flux_algebra (error mask algebra, severity monoid)
7. flux_sediment (accumulated correctness as computational sediment)
8. flux_evolution (evolutionary optimization of constraint bounds)

Forgemaster ⚒️ — 2026-05-19
"""

from __future__ import annotations

import re
import time
from enum import Enum, auto
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

# ── Core engine ─────────────────────────────────────────────
from flux_constraint_exact import FluxExact, PRESETS, Severity, passed as _passed

# ── Research modules (lazy-loaded on .use()) ───────────────
from flux_optimize import ViolationProbabilityTracker, AdaptiveDecisionTree
from flux_information import PredictiveChecker, AnomalyDetector, ConstraintChannel
from flux_signal import KalmanPredictiveChecker, ViolationWavelet
from flux_formal import FormalConstraintSet, RangeConstraint, FormalProofCertificate
from flux_algebra import ErrorMask, SeverityMonoid

# ── Accumulated correctness modules (lazy-loaded on .use()) ──
from flux_sediment import (
    SedimentStack, SedimentAccumulator, ConstraintCorrection, SedimentExperiment,
)
from flux_evolution import (
    evolve as _evolve, TestCase as _EvoTestCase, ConstraintBound as _EvoBound,
    ConstraintSet as _EvoConstraintSet, EvolutionConfig as _EvolutionConfig,
    generate_test_suite as _generate_test_suite,
    create_hand_designed_baseline as _create_hand_designed_baseline,
    compare_evolved_vs_designed as _compare_evolved_vs_designed,
)

Number = Union[int, float]


# ── Strategy enum ───────────────────────────────────────────

class Strategy(Enum):
    ADAPTIVE_ORDERING = auto()      # flux_optimize
    PREDICTIVE = auto()             # flux_information
    KALMAN_PREDICTION = auto()      # flux_signal
    ANOMALY_DETECTION = auto()      # flux_information
    WAVELET_ANALYSIS = auto()       # flux_signal
    SEDIMENT = auto()               # flux_sediment — accumulated correctness layers
    EVOLUTION = auto()              # flux_evolution — evolutionary bound optimization


# ── Streaming helper ────────────────────────────────────────

class ConstraintStream:
    """Streaming interface — feed values one at a time."""

    __slots__ = ("_engine", "_history", "_max_history")

    def __init__(self, engine: "ConstraintEngine", max_history: int = 10_000):
        self._engine = engine
        self._history: List[int] = []
        self._max_history = max_history

    def feed(self, value: Number) -> int:
        """Feed a value, return error_mask (0 = pass)."""
        mask = self._engine.check(value)
        self._history.append(mask)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        return mask

    @property
    def history(self) -> List[int]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()


# ── Unified engine ──────────────────────────────────────────

class ConstraintEngine:
    """
    FLUX Unified Constraint Engine.

    Single entry point that merges all FLUX research modules.
    Core path is zero-alloc. Strategies plug in on demand.
    """

    def __init__(self, constraints: List[Dict]):
        self._raw = constraints
        self._exact = FluxExact(constraints)
        self._strategies: Dict[Strategy, object] = {}
        self._provenance: List[Dict] = []

    # ── Construction helpers ────────────────────────────────

    @classmethod
    def from_guard(cls, guard_text: str) -> "ConstraintEngine":
        """
        Parse a GUARD DSL string into a ConstraintEngine.

        Format:
            GUARD <name> in [<lo>, <hi>] with priority <LEVEL>
        """
        constraints = []
        pattern = re.compile(
            r"GUARD\s+(\w+)\s+in\s+\[\s*([+-]?\d*\.?\d+)\s*,\s*([+-]?\d*\.?\d+)\s*\]"
            r"(?:\s+with\s+priority\s+(\w+))?",
            re.IGNORECASE,
        )
        for m in pattern.finditer(guard_text):
            lo, hi = float(m.group(2)), float(m.group(3))
            constraints.append({"lo": lo, "hi": hi, "name": m.group(1)})
        if not constraints:
            raise ValueError("No valid GUARD statements found")
        return cls(constraints)

    @classmethod
    def from_preset(cls, name: str) -> "ConstraintEngine":
        """Create from a named preset (automotive_can, aviation_adsb, etc.)."""
        if name not in PRESETS:
            avail = ", ".join(PRESETS.keys())
            raise ValueError(f"Unknown preset '{name}'. Available: {avail}")
        return cls(PRESETS[name])

    @classmethod
    def available_presets(cls) -> List[str]:
        return list(PRESETS.keys())

    # ── Zero-alloc hot path ─────────────────────────────────

    def check(self, value: Number) -> int:
        """Check value. Returns error_mask (0 = all pass). Zero allocations."""
        mask = self._exact.check_mask(value)
        # Feed strategies if active
        if Strategy.ADAPTIVE_ORDERING in self._strategies and mask != 0:
            self._feed_adaptive(value, mask)
        if Strategy.PREDICTIVE in self._strategies:
            self._feed_predictive(value, mask)
        if Strategy.KALMAN_PREDICTION in self._strategies:
            self._feed_kalman(value, mask)
        if Strategy.ANOMALY_DETECTION in self._strategies:
            self._feed_anomaly(mask)
        # Sediment post-processing
        if Strategy.SEDIMENT in self._strategies:
            mask = self._feed_sediment(value, mask)
        return mask

    def passed(self, value: Number) -> bool:
        """Check if value passes all constraints."""
        return self.check(value) == 0

    # ── SIMD batch ──────────────────────────────────────────

    def check_batch(self, values) -> np.ndarray:
        """Vectorized batch check. Returns np.ndarray of uint8 error_masks."""
        return self._exact.check_batch_numpy(values)

    # ── Detail (allocates) ──────────────────────────────────

    def check_detail(self, value: Number) -> dict:
        """Full result as dict. Allocates — not for hot path."""
        return self._exact.check_detail(value)

    # ── Strategy management ─────────────────────────────────

    def use(self, strategy: Strategy) -> "ConstraintEngine":
        """Activate a strategy. Returns self for chaining."""
        if strategy in self._strategies:
            return self  # already active

        if strategy == Strategy.ADAPTIVE_ORDERING:
            names = [c.get("name", f"C{i}") for i, c in enumerate(self._raw)]
            tracker = ViolationProbabilityTracker(names)
            self._strategies[strategy] = tracker

        elif strategy == Strategy.PREDICTIVE:
            # PredictiveChecker expects (constraint_fn, n_constraints)
            n = self._exact.n
            exact = self._exact

            def _check_fn(value: float) -> int:
                return exact.check_mask(value)

            checker = PredictiveChecker(_check_fn, n)
            lo_bounds = [float(c["lo"]) for c in self._raw]
            hi_bounds = [float(c["hi"]) for c in self._raw]
            checker.learn_bounds(lo_bounds, hi_bounds)
            self._strategies[strategy] = checker

        elif strategy == Strategy.KALMAN_PREDICTION:
            # Create a Kalman checker for each constraint; store as list
            kalmans = []
            for c in self._raw:
                lo, hi = float(c["lo"]), float(c["hi"])
                k = KalmanPredictiveChecker(lo, hi)
                k._initialized = False
                kalmans.append(k)
            self._strategies[strategy] = kalmans

        elif strategy == Strategy.ANOMALY_DETECTION:
            n = len(self._raw)
            detector = AnomalyDetector(n_constraints=n)
            self._strategies[strategy] = detector

        elif strategy == Strategy.WAVELET_ANALYSIS:
            self._strategies[strategy] = ViolationWavelet()

        elif strategy == Strategy.SEDIMENT:
            stack = SedimentStack()
            accumulator = SedimentAccumulator(n_constraints=self._exact.n)
            self._strategies[strategy] = {"stack": stack, "accumulator": accumulator}

        elif strategy == Strategy.EVOLUTION:
            self._strategies[strategy] = {"result": None, "best_bounds": None}

        self._provenance.append({
            "event": "strategy_enabled",
            "strategy": strategy.name,
            "timestamp": time.time(),
        })
        return self

    def active_strategies(self) -> List[Strategy]:
        """List currently active strategies."""
        return list(self._strategies.keys())

    def get_strategy(self, strategy: Strategy):
        """Get the raw strategy object, or None."""
        return self._strategies.get(strategy)

    # ── Strategy feeds (internal) ───────────────────────────

    def _feed_adaptive(self, value: Number, mask: int):
        tracker = self._strategies[Strategy.ADAPTIVE_ORDERING]
        for i in range(self._exact.n):
            name = self._exact._names[i]
            violated = bool(mask & (1 << i))
            tracker.observe(name, violated)

    def _feed_predictive(self, value: Number, mask: int):
        checker = self._strategies[Strategy.PREDICTIVE]
        # PredictiveChecker.check returns (error_mask, was_exact_fallback)
        try:
            checker.check(float(value))
        except Exception:
            pass

    def _feed_kalman(self, value: Number, mask: int):
        kalmans = self._strategies[Strategy.KALMAN_PREDICTION]
        v = float(value)
        for k in kalmans:
            try:
                if not getattr(k, '_initialized', False):
                    k._initialize(v)
                    k._initialized = True
                k.update(v)
            except Exception:
                pass

    def _feed_anomaly(self, mask: int):
        detector = self._strategies[Strategy.ANOMALY_DETECTION]
        try:
            detector.observe(mask)
        except Exception:
            pass

    def _feed_sediment(self, value: Number, mask: int) -> int:
        """Run sediment post-processing. Returns potentially corrected error mask."""
        data = self._strategies[Strategy.SEDIMENT]
        stack = data["stack"]
        accumulator = data["accumulator"]
        constraint_names = list(self._exact._names)
        constraint_defs = {c.get("name", f"C{i}"): (float(c["lo"]), float(c["hi"])) for i, c in enumerate(self._raw)}
        values = {c.get("name", f"C{i}"): float(value) for i, c in enumerate(self._raw)}

        severity = 0
        if mask != 0:
            n_violated = bin(mask).count("1")
            sev_table = [0, 1, 1, 2, 2, 3, 3, 3, 3]
            severity = sev_table[min(n_violated, len(sev_table) - 1)]

        result = stack.check_with_sediment(
            base_error_mask=mask,
            base_severity=severity,
            constraint_names=constraint_names,
            values=values,
            constraint_defs=constraint_defs,
        )
        accumulator.record_check(values, result)
        return result.final_error_mask

    # ── Streaming ───────────────────────────────────────────

    def stream(self, max_history: int = 10_000) -> ConstraintStream:
        """Create a streaming interface."""
        return ConstraintStream(self, max_history=max_history)

    # ── Proofs and provenance ───────────────────────────────

    def proof_certificate(self) -> Optional[FormalProofCertificate]:
        """
        Compile-time proof of constraint set well-formedness.
        Proves: no inverted ranges, no overlapping severities,
        no empty valid regions, no boundary misclassifications.
        """
        constraints = [
            RangeConstraint(
                lo=float(c["lo"]),
                hi=float(c["hi"]),
                name=c.get("name", f"C{i}"),
            )
            for i, c in enumerate(self._raw)
        ]
        fcs = FormalConstraintSet(constraints)
        return fcs.prove()

    def provenance_log(self) -> List[Dict]:
        """Runtime audit trail of strategy activations and events."""
        return list(self._provenance)

    # ── Benchmark ───────────────────────────────────────────

    def benchmark(self, iterations: int = 1_000_000) -> float:
        """Returns checks/sec for the hot path."""
        return self._exact.benchmark(iterations)

    # ── Properties ──────────────────────────────────────────

    @property
    def n_constraints(self) -> int:
        return self._exact.n

    @property
    def constraints(self) -> list:
        return list(self._exact.constraints)

    @property
    def names(self) -> Tuple[str, ...]:
        return self._exact._names

    # ── Sediment strategy interface ────────────────────────

    def add_sediment_layer(
        self,
        corrections: List[ConstraintCorrection],
        context: Optional[Dict] = None,
    ) -> "ConstraintEngine":
        """
        Manually add a sediment correction layer.

        Requires Strategy.SEDIMENT to be active (call .use(Strategy.SEDIMENT) first).

        Args:
            corrections: List of ConstraintCorrection objects
            context: Optional dict describing what triggered this layer

        Returns:
            self for chaining
        """
        if Strategy.SEDIMENT not in self._strategies:
            raise RuntimeError("SEDIMENT strategy not active. Call engine.use(Strategy.SEDIMENT) first.")
        stack = self._strategies[Strategy.SEDIMENT]["stack"]
        stack.add_layer(
            input_context=context or {},
            corrections=corrections,
            provenance="manual",
            model="flux_api",
        )
        return self

    def sediment_stats(self) -> Dict:
        """
        Get sediment accumulation statistics.

        Returns dict with: depth, active_layers, correctness_density,
        predicted_surprise, coverage_by_layer.

        Requires Strategy.SEDIMENT.
        """
        if Strategy.SEDIMENT not in self._strategies:
            raise RuntimeError("SEDIMENT strategy not active.")
        data = self._strategies[Strategy.SEDIMENT]
        stack = data["stack"]
        accumulator = data["accumulator"]
        metrics = accumulator.compute_metrics(stack)
        return {
            "depth": stack.depth,
            "active_layers": metrics.active_layers,
            "superseded_layers": metrics.superseded_layers,
            "total_catches": metrics.total_catches,
            "correctness_density": metrics.correctness_density,
            "predicted_surprise": metrics.predicted_next_surprise_region,
            "coverage_by_layer": metrics.coverage_by_layer,
        }

    # ── Evolution strategy interface ────────────────────────

    def evolve(
        self,
        tests: Optional[List[Dict]] = None,
        generations: int = 50,
        population_size: int = 40,
        seed: Optional[int] = None,
    ) -> Dict:
        """
        Run evolutionary optimization on constraint bounds.

        Requires Strategy.EVOLUTION to be active.

        Args:
            tests: Optional list of test case dicts with 'values', 'label', 'category'.
                   If None, generates a synthetic test suite.
            generations: Number of evolution generations
            population_size: Population size per generation
            seed: Random seed for reproducibility

        Returns:
            Dict with best_correctness, best_recall, best_coverage, elapsed_seconds,
            generations_run, best_bounds.
        """
        if Strategy.EVOLUTION not in self._strategies:
            raise RuntimeError("EVOLUTION strategy not active. Call engine.use(Strategy.EVOLUTION) first.")

        # Derive dimension names from engine constraints
        dimension_names = list(self._exact._names)

        # Convert engine constraints to test suite if not provided
        if tests is None:
            # Use engine bounds as valid range hints
            lo_bounds = [float(c["lo"]) for c in self._raw]
            hi_bounds = [float(c["hi"]) for c in self._raw]
            valid_lo = max(-1.0, min(lo_bounds))
            valid_hi = min(1.0, max(hi_bounds))
            evo_tests = _generate_test_suite(
                dimension_names,
                n_valid=200, n_violation=100,
                valid_range=(valid_lo, valid_hi),
                edge_categories=5,
                seed=seed or 42,
            )
        else:
            # Convert dicts to TestCase objects
            evo_tests = [
                _EvoTestCase(
                    values=t["values"],
                    label=t["label"],
                    name=t.get("name", ""),
                    category=t.get("category", "general"),
                )
                for t in tests
            ]

        config = _EvolutionConfig(
            population_size=population_size,
            generations=generations,
            seed=seed,
        )

        result = _evolve(evo_tests, dimension_names, config)

        # Store result
        best = result.best_individual
        best_bounds = None
        if best and best.fitness_score:
            best_bounds = {
                b.name: (b.lower, b.upper)
                for b in best.constraint_set.bounds
            }

        self._strategies[Strategy.EVOLUTION]["result"] = result
        self._strategies[Strategy.EVOLUTION]["best_bounds"] = best_bounds

        self._provenance.append({
            "event": "evolution_complete",
            "generations": generations,
            "best_fitness": best.fitness_score.fitness if best and best.fitness_score else None,
            "timestamp": time.time(),
        })

        return {
            "best_correctness": best.fitness_score.correctness if best and best.fitness_score else None,
            "best_recall": best.fitness_score.recall if best and best.fitness_score else None,
            "best_coverage": best.fitness_score.coverage if best and best.fitness_score else None,
            "best_fitness": best.fitness_score.fitness if best and best.fitness_score else None,
            "best_bounds": best_bounds,
            "generations_run": len(result.generations),
            "elapsed_seconds": result.elapsed_seconds,
            "correctness_monotonic": result.correctness_monotonic,
            "pareto_front_size": len(result.pareto_front),
        }

    def thermo_stats(self) -> Dict:
        """
        Get thermodynamic-style stats for the evolution strategy.

        Returns entropy, temperature, and phase transition information
        derived from the final population distribution.

        Requires Strategy.EVOLUTION with a completed evolution run.
        """
        if Strategy.EVOLUTION not in self._strategies:
            raise RuntimeError("EVOLUTION strategy not active.")
        result = self._strategies[Strategy.EVOLUTION]["result"]
        if result is None:
            return {
                "entropy": None,
                "temperature": None,
                "free_energy": None,
                "phase": "pre_evolution",
                "message": "Call engine.evolve() first.",
            }

        # Compute entropy from fitness distribution of final population
        fitnesses = []
        for ind in result.final_population:
            if ind.fitness_score and ind.fitness_score.fitness > 0:
                fitnesses.append(ind.fitness_score.fitness)

        if not fitnesses:
            return {"entropy": 0.0, "temperature": 0.0, "free_energy": 0.0, "phase": "converged"}

        import math
        total_fit = sum(fitnesses)
        probs = [f / total_fit for f in fitnesses]
        entropy = -sum(p * math.log2(p + 1e-15) for p in probs)
        temperature = entropy  # Boltzmann analogy
        avg_fitness = total_fit / len(fitnesses)
        free_energy = avg_fitness - temperature * 0.1  # F = E - T*S

        # Phase detection
        if entropy < 0.5:
            phase = "crystalized"  # Low entropy = converged
        elif entropy < 3.0:
            phase = "liquid"       # Medium entropy = exploring
        else:
            phase = "gas"          # High entropy = diverse

        # Check for phase transitions across generations
        transitions = []
        prev_phase = None
        for gs in result.generations:
            if gs.diversity < result.config.population_size * 0.2:
                cur_phase = "crystalized"
            elif gs.diversity < result.config.population_size * 0.6:
                cur_phase = "liquid"
            else:
                cur_phase = "gas"
            if prev_phase and cur_phase != prev_phase:
                transitions.append({"generation": gs.generation, "from": prev_phase, "to": cur_phase})
            prev_phase = cur_phase

        return {
            "entropy": round(entropy, 4),
            "temperature": round(temperature, 4),
            "free_energy": round(free_energy, 4),
            "phase": phase,
            "phase_transitions": transitions,
            "population_size": len(fitnesses),
        }

    def __repr__(self) -> str:
        presets_inv = {tuple(tuple(c.items()) for c in v): k for k, v in PRESETS.items()}
        raw_key = tuple(tuple(sorted(c.items())) for c in self._raw)
        # Try to match a preset by checking each one
        preset_name = None
        for pname, pconstraints in PRESETS.items():
            if len(pconstraints) == len(self._raw):
                match = all(
                    abs(float(pc.get("lo", 0)) - float(self._raw[i].get("lo", 0))) < 1e-12
                    and abs(float(pc.get("hi", 0)) - float(self._raw[i].get("hi", 0))) < 1e-12
                    and pc.get("name") == self._raw[i].get("name")
                    for i, pc in enumerate(pconstraints)
                )
                if match:
                    preset_name = pname
                    break

        strategies = [s.name for s in self._strategies]
        parts = [f"ConstraintEngine(n={self._exact.n}"]
        if preset_name:
            parts.append(f"preset={preset_name!r}")
        if strategies:
            parts.append(f"strategies={strategies}")
        parts.append(")")
        return " ".join(parts)
