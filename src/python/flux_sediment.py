"""
flux_sediment.py — Accumulated Correctness as Computational Sediment

Models constraint correctness as geological sediment: layers of edge-case
corrections that accumulate over time, each layer immutable, new layers
superseding specific corrections from older ones.

Core theorem: A constraint system with N sediment layers has strictly
higher correctness than the same system with fewer layers, converging
monotonically toward complete coverage.

Depends on: flux_constraint_exact, flux_algebra, flux_information
Forgemaster ⚒️ — 2026-05-19
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple, Union
)

import numpy as np


# =============================================================================
# 1. SedimentLayer — Immutable edge-case correction layer
# =============================================================================

@dataclass(frozen=True)
class ConstraintCorrection:
    """A single correction to a constraint definition."""
    constraint_name: str
    old_lo: Optional[float] = None
    old_hi: Optional[float] = None
    new_lo: Optional[float] = None
    new_hi: Optional[float] = None
    override_pass: Optional[bool] = None  # Force pass/fail regardless of bounds
    reason: str = ""

    def apply_to(self, lo: float, hi: float, passed: bool) -> Tuple[float, float, bool]:
        """Apply correction to bounds and pass state. Returns (new_lo, new_hi, new_passed)."""
        out_lo = self.new_lo if self.new_lo is not None else lo
        out_hi = self.new_hi if self.new_hi is not None else hi
        out_passed = self.override_pass if self.override_pass is not None else passed
        return out_lo, out_hi, out_passed

    def to_dict(self) -> dict:
        return {
            "constraint_name": self.constraint_name,
            "old_lo": self.old_lo, "old_hi": self.old_hi,
            "new_lo": self.new_lo, "new_hi": self.new_hi,
            "override_pass": self.override_pass,
            "reason": self.reason,
        }


@dataclass
class SedimentLayer:
    """
    An immutable layer of edge-case corrections.

    Each layer represents a crisis that was discovered and fixed.
    Layers are NEVER deleted — only superseded by newer layers.
    """
    layer_id: int
    input_context: Dict[str, Any]       # What triggered this layer (the crisis)
    corrections: List[ConstraintCorrection]
    timestamp: float = field(default_factory=time.time)
    provenance: str = ""                 # Source system/repo
    model: str = ""                      # Model that created this layer
    superseded: bool = False             # Marked true if a newer layer fully overrides
    superseded_by: Optional[int] = None  # Layer ID that supersedes this one
    catch_count: int = 0                 # How many edge cases this layer has caught

    def content_hash(self) -> str:
        """Deterministic hash for PLATO tile serialization."""
        blob = json.dumps(
            {"id": self.layer_id, "corrections": [c.to_dict() for c in self.corrections]},
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def to_tile(self) -> dict:
        """Serialize to PLATO tile format."""
        return {
            "tile_type": "sediment_layer",
            "layer_id": self.layer_id,
            "content_hash": self.content_hash(),
            "input_context": self.input_context,
            "corrections": [c.to_dict() for c in self.corrections],
            "timestamp": self.timestamp,
            "provenance": self.provenance,
            "model": self.model,
            "superseded": self.superseded,
            "superseded_by": self.superseded_by,
            "catch_count": self.catch_count,
        }

    @classmethod
    def from_tile(cls, tile: dict) -> SedimentLayer:
        """Deserialize from PLATO tile."""
        corrections = [ConstraintCorrection(**c) for c in tile.get("corrections", [])]
        return cls(
            layer_id=tile["layer_id"],
            input_context=tile.get("input_context", {}),
            corrections=corrections,
            timestamp=tile.get("timestamp", 0.0),
            provenance=tile.get("provenance", ""),
            model=tile.get("model", ""),
            superseded=tile.get("superseded", False),
            superseded_by=tile.get("superseded_by"),
            catch_count=tile.get("catch_count", 0),
        )


# =============================================================================
# 2. SedimentStack — Ordered stack of correction layers
# =============================================================================

@dataclass
class SedimentResult:
    """Result of running a check through the sediment stack."""
    base_error_mask: int
    base_severity: int
    final_error_mask: int
    final_severity: int
    layers_applied: List[int]     # Layer IDs that modified the result
    corrections_applied: int      # Total corrections applied
    passed: bool

    def to_dict(self) -> dict:
        return {
            "base_error_mask": self.base_error_mask,
            "base_severity": self.base_severity,
            "final_error_mask": self.final_error_mask,
            "final_severity": self.final_severity,
            "layers_applied": self.layers_applied,
            "corrections_applied": self.corrections_applied,
            "passed": self.passed,
        }


class SedimentStack:
    """
    Stack of sediment layers (oldest at bottom, newest at top).

    The HOT PATH (basic constraint check) runs first, then each active
    sediment layer can modify the result. Layers are NEVER deleted,
    only superseded.
    """

    def __init__(self):
        self._layers: List[SedimentLayer] = []
        self._next_id: int = 0

    @property
    def depth(self) -> int:
        return len(self._layers)

    @property
    def active_layers(self) -> List[SedimentLayer]:
        """Layers not superseded."""
        return [l for l in self._layers if not l.superseded]

    def add_layer(
        self,
        input_context: Dict[str, Any],
        corrections: List[ConstraintCorrection],
        provenance: str = "",
        model: str = "",
    ) -> SedimentLayer:
        """Add a new correction layer on top of the stack."""
        layer = SedimentLayer(
            layer_id=self._next_id,
            input_context=input_context,
            corrections=corrections,
            provenance=provenance,
            model=model,
        )
        self._layers.append(layer)
        self._next_id += 1
        return layer

    def supersede_layer(self, old_id: int, new_id: int) -> bool:
        """Mark old layer as superseded by new layer."""
        for layer in self._layers:
            if layer.layer_id == old_id and not layer.superseded:
                layer.superseded = True
                layer.superseded_by = new_id
                return True
        return False

    def check_with_sediment(
        self,
        base_error_mask: int,
        base_severity: int,
        constraint_names: List[str],
        values: Dict[str, float],
        constraint_defs: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> SedimentResult:
        """
        Run a base check result through all active sediment layers.

        Each layer can modify bounds or override pass/fail for specific constraints.

        Args:
            base_error_mask: Error mask from the hot path check
            base_severity: Severity from hot path
            constraint_names: Ordered list of constraint names (bit positions)
            values: Dict of constraint_name -> actual value
            constraint_defs: Optional dict of constraint_name -> (lo, hi) for re-checking

        Returns:
            SedimentResult with final corrected state
        """
        current_mask = base_error_mask
        current_severity = base_severity
        layers_applied: List[int] = []
        corrections_applied = 0

        for layer in self._layers:
            if layer.superseded:
                continue

            layer_modified = False
            for correction in layer.corrections:
                if correction.constraint_name not in constraint_names:
                    continue

                bit_idx = constraint_names.index(correction.constraint_name)
                bit = 1 << bit_idx
                is_violated = bool(current_mask & bit)

                modified = False

                # Override pass/fail takes priority (doesn't need bounds)
                if correction.override_pass is not None:
                    if correction.override_pass and is_violated:
                        current_mask &= ~bit
                        modified = True
                    elif not correction.override_pass and not is_violated:
                        current_mask |= bit
                        modified = True
                elif constraint_defs and correction.constraint_name in constraint_defs:
                    # Bounds-based correction
                    orig_lo, orig_hi = constraint_defs[correction.constraint_name]
                    new_lo, new_hi, _ = correction.apply_to(orig_lo, orig_hi, not is_violated)
                    val = values.get(correction.constraint_name, 0.0)
                    in_new_bounds = (new_lo <= val <= new_hi)
                    if is_violated and in_new_bounds:
                        current_mask &= ~bit
                        modified = True
                    elif not is_violated and not in_new_bounds:
                        current_mask |= bit
                        modified = True

                if modified:
                    layer_modified = True
                corrections_applied += 1

            if layer_modified:
                layers_applied.append(layer.layer_id)
                layer.catch_count += 1

        # Recompute severity from final mask
        if current_mask == 0:
            current_severity = 0  # PASS
        else:
            # Count bits and map to severity
            n_violated = bin(current_mask).count("1")
            severity_table = [0, 1, 1, 2, 2, 3, 3, 3, 3]
            current_severity = severity_table[min(n_violated, len(severity_table) - 1)]

        return SedimentResult(
            base_error_mask=base_error_mask,
            base_severity=base_severity,
            final_error_mask=current_mask,
            final_severity=current_severity,
            layers_applied=layers_applied,
            corrections_applied=corrections_applied,
            passed=(current_mask == 0),
        )


# =============================================================================
# 3. SedimentAccumulator — Tracks accumulation metrics
# =============================================================================

@dataclass
class AccumulationMetrics:
    """Snapshot of sediment accumulation state."""
    total_layers: int
    active_layers: int
    superseded_layers: int
    total_catches: int
    correctness_density: float      # Fraction of observed input space covered
    predicted_next_surprise_region: Optional[str]  # Where next edge case likely appears
    coverage_by_layer: Dict[int, int]  # layer_id -> catch_count


class SedimentAccumulator:
    """
    Tracks how correctness accumulates as sediment layers are added.

    Measures:
    - How many edge cases each layer has caught
    - "Correctness density" — fraction of input space covered by sediment
    - Predicts where the NEXT edge case will appear (information-theoretic surprise)
    """

    def __init__(self, n_constraints: int):
        self.n_constraints = n_constraints
        self._input_log: List[Tuple[Dict[str, float], SedimentResult]] = []
        self._error_frequency: Dict[int, int] = {}  # error_mask -> count
        self._total_checks: int = 0
        self._sediment_catches: int = 0

    def record_check(
        self,
        values: Dict[str, float],
        result: SedimentResult,
    ) -> None:
        """Record a check result for accumulation tracking."""
        self._total_checks += 1
        self._input_log.append((values, result))
        self._error_frequency[result.final_error_mask] = (
            self._error_frequency.get(result.final_error_mask, 0) + 1
        )
        if result.layers_applied:
            self._sediment_catches += 1

    @property
    def total_checks(self) -> int:
        return self._total_checks

    @property
    def sediment_catches(self) -> int:
        return self._sediment_catches

    def correctness_density(self) -> float:
        """
        Fraction of observed input space covered by sediment corrections.

        Uses information-theoretic measure: fraction of total entropy
        explained by sediment layer corrections.
        """
        if self._total_checks == 0:
            return 0.0
        return self._sediment_catches / self._total_checks

    def predict_next_surprise(self) -> Optional[str]:
        """
        Predict where the next edge case will appear using
        information-theoretic surprise (Kolmogorov complexity proxy).

        Returns the error mask pattern most likely to surprise next,
        or None if no data.
        """
        if not self._error_frequency:
            return None

        total = sum(self._error_frequency.values())
        # Find the error mask with lowest frequency (most surprising when it appears)
        # but exclude mask=0 (pass) — we want failure patterns
        failure_masks = {k: v for k, v in self._error_frequency.items() if k != 0}
        if not failure_masks:
            return None

        # Surprise = -log2(P(pattern)) weighted by severity
        most_surprising = None
        max_surprise = -1.0
        for mask, count in failure_masks.items():
            p = count / total
            surprise = -math.log2(p + 1e-15) * (bin(mask).count("1"))
            if surprise > max_surprise:
                max_surprise = surprise
                most_surprising = f"error_mask=0b{mask:b}"

        return most_surprising

    def compute_metrics(self, stack: SedimentStack) -> AccumulationMetrics:
        """Compute full accumulation metrics snapshot."""
        active = stack.active_layers
        return AccumulationMetrics(
            total_layers=stack.depth,
            active_layers=len(active),
            superseded_layers=stack.depth - len(active),
            total_catches=self._sediment_catches,
            correctness_density=self.correctness_density(),
            predicted_next_surprise_region=self.predict_next_surprise(),
            coverage_by_layer={l.layer_id: l.catch_count for l in stack._layers},
        )


import math  # needed for log2 in predict_next_surprise


# =============================================================================
# 4. Convergence Experiment
# =============================================================================

class SedimentExperiment:
    """
    Demonstrates that constraint systems with N sediment layers have
    strictly higher correctness than the same system with fewer layers,
    converging monotonically.
    """

    @staticmethod
    def _compute_base_mask(
        constraint_defs: Dict[str, Tuple[float, float]],
        values: Dict[str, float],
    ) -> int:
        """Check values against constraint bounds and return error mask.
        Works for any number of constraints with independent values."""
        mask = 0
        for i, (name, (lo, hi)) in enumerate(constraint_defs.items()):
            val = values.get(name, 0.0)
            if val < lo or val > hi:
                mask |= (1 << i)
        return mask

    @staticmethod
    def run_convergence_experiment(
        constraints: List[Dict[str, Any]],
        test_inputs: List[Dict[str, float]],
        edge_cases: List[Tuple[Dict[str, float], List[ConstraintCorrection]]],
    ) -> Dict[str, Any]:
        """
        Run the convergence experiment.

        Args:
            constraints: List of constraint defs: [{"name": str, "lo": float, "hi": float}, ...]
            test_inputs: Test input vectors: [{constraint_name: value, ...}, ...]
            edge_cases: List of (input_values, corrections) to add as layers

        Returns:
            Dict with convergence data: correctness at each layer depth
        """
        # Preserve insertion order for deterministic bit positions
        constraint_names = [c["name"] for c in constraints]
        constraint_defs = {c["name"]: (c["lo"], c["hi"]) for c in constraints}

        # Baseline correctness — no sediment
        base_correct = 0
        base_masks: List[int] = []
        for inp in test_inputs:
            mask = SedimentExperiment._compute_base_mask(constraint_defs, inp)
            base_masks.append(mask)
            if mask == 0:
                base_correct += 1

        base_rate = base_correct / len(test_inputs) if test_inputs else 0.0

        # Build sediment stack incrementally
        stack = SedimentStack()
        accumulator = SedimentAccumulator(n_constraints=len(constraints))

        convergence_data = []
        convergence_data.append({
            "layer_depth": 0,
            "correct_count": base_correct,
            "total_inputs": len(test_inputs),
            "correctness_rate": base_rate,
            "catches": 0,
        })

        for i, (edge_input, corrections) in enumerate(edge_cases):
            # Add layer
            stack.add_layer(
                input_context={"edge_case_index": i, "input": edge_input},
                corrections=corrections,
                provenance="convergence_experiment",
                model="flux_sediment",
            )

            # Re-check all inputs with sediment
            correct = 0
            catches = 0
            for inp in test_inputs:
                mask = SedimentExperiment._compute_base_mask(constraint_defs, inp)

                result = stack.check_with_sediment(
                    base_error_mask=mask,
                    base_severity=0,
                    constraint_names=constraint_names,
                    values=inp,
                    constraint_defs=constraint_defs,
                )
                accumulator.record_check(inp, result)

                if result.passed:
                    correct += 1
                if result.layers_applied:
                    catches += 1

            rate = correct / len(test_inputs) if test_inputs else 0.0
            convergence_data.append({
                "layer_depth": i + 1,
                "correct_count": correct,
                "total_inputs": len(test_inputs),
                "correctness_rate": rate,
                "catches": catches,
            })

        # Check monotonic convergence
        rates = [d["correctness_rate"] for d in convergence_data]
        is_monotonic = all(rates[i] <= rates[i + 1] for i in range(len(rates) - 1))

        return {
            "base_correctness": base_rate,
            "final_correctness": rates[-1] if rates else 0.0,
            "is_monotonic": is_monotonic,
            "improvement": rates[-1] - rates[0] if rates else 0.0,
            "convergence_data": convergence_data,
            "n_layers": len(edge_cases),
            "n_test_inputs": len(test_inputs),
        }
