"""
FLUX Unified API v4 — The Single Entry Point
=============================================

`from flux import ConstraintEngine, Strategy`

Wraps all six FLUX modules into one cohesive engine:
1. FluxExact (core exact checking — zero-alloc hot path)
2. flux_optimize (adaptive ordering)
3. flux_information (predictive checking, anomaly detection)
4. flux_signal (Kalman prediction, wavelet analysis)
5. flux_formal (setup-time proofs)
6. flux_algebra (error mask algebra, severity monoid)

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

Number = Union[int, float]


# ── Strategy enum ───────────────────────────────────────────

class Strategy(Enum):
    ADAPTIVE_ORDERING = auto()      # flux_optimize
    PREDICTIVE = auto()             # flux_information
    KALMAN_PREDICTION = auto()      # flux_signal
    ANOMALY_DETECTION = auto()      # flux_information
    WAVELET_ANALYSIS = auto()       # flux_signal


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
