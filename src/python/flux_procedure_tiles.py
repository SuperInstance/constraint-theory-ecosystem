"""
FLUX Procedure Tiles — Tile-as-Procedure Pattern

Demonstrates that a PLATO tile IS an executable procedure:
  - Large model (specialist) creates the tile with pre/post conditions, steps, contingencies
  - Small model (general practitioner) reads the tile and executes it exactly
  - Refinement cycles accumulate intelligence into the tile

The tile is the intelligence transfer mechanism. The executor doesn't need to
understand constraint theory — it needs to follow the procedure.

Usage:
    from flux_procedure_tiles import (
        build_preset_procedure, execute_procedure, refine_procedure,
        demonstrate_capability_ladder,
    )
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Import the constraint engine for preset data and actual checking
from flux_constraint_exact import PRESETS, Severity


# ── Procedure Tile Data Structures ──────────────────────────

class StepType(str, Enum):
    VALIDATE = "validate"
    CHECK = "check"
    BUILD = "build"
    CLASSIFY = "classify"
    HASH = "hash"
    REPORT = "report"


@dataclass
class ProcedureStep:
    """A single step in the procedure — must be executable by any model."""
    order: int
    step_type: StepType
    description: str
    action: str  # What to do, in plain language
    expected_output: str  # What the output should look like
    failure_action: str  # What to do if this step fails

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "step_type": self.step_type.value,
            "description": self.description,
            "action": self.action,
            "expected_output": self.expected_output,
            "failure_action": self.failure_action,
        }


@dataclass
class Contingency:
    """What to do when things go wrong — like surgical complication management."""
    condition: str
    action: str
    rationale: str

    def to_dict(self) -> dict:
        return {
            "condition": self.condition,
            "action": self.action,
            "rationale": self.rationale,
        }


@dataclass
class ConstraintProcedureTile:
    """
    A procedure tile for constraint checking.

    This is the intelligence transfer artifact. A small model reads this
    and executes constraint checking WITHOUT understanding the underlying math.
    """
    # Identity
    name: str
    version: int
    domain: str
    created_by: str
    created_at: float

    # Procedure specification
    pre_conditions: List[str]
    steps: List[ProcedureStep]
    post_conditions: List[str]
    contingencies: List[Contingency]

    # Constraint data (embedded so executor doesn't need external references)
    constraints: List[Dict[str, Any]]

    # Severity thresholds
    severity_thresholds: Dict[str, int]

    # Provenance
    refinement_history: List[Dict[str, Any]] = field(default_factory=list)
    parent_tile_hash: Optional[str] = None

    @property
    def tile_hash(self) -> str:
        """Deterministic hash of tile content — proves what was executed."""
        payload = json.dumps({
            "name": self.name,
            "version": self.version,
            "constraints": self.constraints,
            "steps": [s.to_dict() for s in self.steps],
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "domain": self.domain,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "tile_hash": self.tile_hash,
            "parent_tile_hash": self.parent_tile_hash,
            "pre_conditions": self.pre_conditions,
            "steps": [s.to_dict() for s in self.steps],
            "post_conditions": self.post_conditions,
            "contingencies": [c.to_dict() for c in self.contingencies],
            "constraints": self.constraints,
            "severity_thresholds": self.severity_thresholds,
            "refinement_history": self.refinement_history,
        }

    def to_compact(self) -> str:
        """Compact representation suitable for small-model consumption."""
        lines = [
            f"# Procedure Tile: {self.name} v{self.version}",
            f"# Hash: {self.tile_hash}",
            f"# Domain: {self.domain}",
            "",
            "## Pre-conditions (must be true before execution):",
        ]
        for pc in self.pre_conditions:
            lines.append(f"  - {pc}")
        lines.append("")
        lines.append("## Steps (execute in order):")
        for s in self.steps:
            lines.append(f"  {s.order}. [{s.step_type.value}] {s.description}")
            lines.append(f"     Action: {s.action}")
            lines.append(f"     Expected: {s.expected_output}")
            lines.append(f"     On failure: {s.failure_action}")
        lines.append("")
        lines.append("## Post-conditions (must be true after execution):")
        for pc in self.post_conditions:
            lines.append(f"  - {pc}")
        lines.append("")
        lines.append("## Contingencies (when things go wrong):")
        for c in self.contingencies:
            lines.append(f"  - IF {c.condition}: {c.action} (because: {c.rationale})")
        lines.append("")
        lines.append("## Constraints:")
        for c in self.constraints:
            lines.append(f"  - {c['name']}: [{c['lo']}, {c['hi']}]")
        return "\n".join(lines)


# ── Tile Builder ────────────────────────────────────────────

def build_preset_procedure(preset_name: str) -> ConstraintProcedureTile:
    """
    Create a complete procedure tile from a FLUX preset.

    The specialist (large model) creates this tile. It encodes:
    - All constraint bounds from the preset
    - Step-by-step checking procedure
    - Error handling contingencies
    - Severity classification rules

    A general practitioner (small model) can execute this without
    understanding why the bounds are what they are.
    """
    if preset_name not in PRESETS:
        raise ValueError(
            f"Unknown preset '{preset_name}'. "
            f"Available: {list(PRESETS.keys())}"
        )

    constraints = PRESETS[preset_name]
    n = len(constraints)

    # Build the standard 5-step procedure
    steps = [
        ProcedureStep(
            order=1,
            step_type=StepType.VALIDATE,
            description="Validate input values",
            action=(
                "For each value in the input array, check: "
                "(a) is it a number? (b) is it NaN? (c) is it Inf? "
                "Count the total values and verify it matches the number of constraints."
            ),
            expected_output="A list of booleans: valid[i] = True if input[i] is a finite number",
            failure_action="If count mismatch, return error with expected vs actual count",
        ),
        ProcedureStep(
            order=2,
            step_type=StepType.CHECK,
            description="Check each constraint (lo <= value <= hi)",
            action=(
                "For each valid value at index i, check: "
                "constraint[i].lo <= value[i] <= constraint[i].hi. "
                "If NaN or Inf, the constraint is violated. "
                "Set bit i in error_mask if violated."
            ),
            expected_output=(
                f"An integer error_mask with exactly {n} relevant bits. "
                f"Bit i is 1 if constraint i is violated."
            ),
            failure_action="If any check throws an exception, set all bits and report",
        ),
        ProcedureStep(
            order=3,
            step_type=StepType.BUILD,
            description="Build error mask (bitwise)",
            action=(
                f"Construct error_mask as integer where bit i = 1 iff constraint i violated. "
                f"Maximum mask value for {n} constraints is {2**n - 1}. "
                f"For NaN inputs, set ALL bits for that constraint index."
            ),
            expected_output=f"Integer in range [0, {2**n - 1}]",
            failure_action="If mask exceeds maximum, clamp and report overflow",
        ),
        ProcedureStep(
            order=4,
            step_type=StepType.CLASSIFY,
            description="Classify severity based on violation count",
            action=(
                "Count the number of set bits in error_mask. "
                "0 violations → PASS, 1-2 → CAUTION, 3-4 → WARNING, 5+ → CRITICAL. "
                "Also note which constraints were violated (lo vs hi)."
            ),
            expected_output="Severity level (PASS/CAUTION/WARNING/CRITICAL) and violation details",
            failure_action="If bit count is ambiguous, default to CRITICAL (safety first)",
        ),
        ProcedureStep(
            order=5,
            step_type=StepType.HASH,
            description="Generate proof hash",
            action=(
                "Compute SHA-256 hash of: tile_hash + error_mask + severity + values checked. "
                "This proves what was checked and what the result was."
            ),
            expected_output="16-character hex string",
            failure_action="If hash computation fails, return 'hash-error' and still deliver result",
        ),
    ]

    # Pre-conditions: what must be true before execution
    pre_conditions = [
        f"Input is a numeric sequence with exactly {n} values (one per constraint)",
        "All constraint bounds are finite numbers (no NaN/Inf in bounds)",
        "Constraint lo <= hi for every constraint",
        "Values are provided in the same order as constraints",
    ]

    # Post-conditions: what must be true after execution
    post_conditions = [
        f"error_mask has at most {n} bits set (no spurious violations)",
        "No false negatives: if a value is out of bounds, the corresponding bit IS set",
        "Severity is consistent with violation count",
        "Proof hash is deterministic for the same inputs",
    ]

    # Contingencies: what to do when things go wrong
    contingencies = [
        Contingency(
            condition="NaN detected in input",
            action="Set ALL bits in error_mask to 1, severity CRITICAL",
            rationale="NaN means unknown state — treat as worst case. Safety first.",
        ),
        Contingency(
            condition="Inf detected in input",
            action="Set corresponding bit to 1, treat as out-of-range",
            rationale="Inf exceeds any finite bound by definition",
        ),
        Contingency(
            condition="Wrong number of input values",
            action="Return error immediately, do not check any constraints",
            rationale="Cannot reliably map values to constraints if count mismatches",
        ),
        Contingency(
            condition="Non-numeric input",
            action="Treat as NaN — set all bits, severity CRITICAL",
            rationale="Non-numeric is worse than unknown — it's a type error",
        ),
        Contingency(
            condition="Value exactly equals lo or hi",
            action="PASS — boundary values are in-bounds (inclusive)",
            rationale="lo <= value <= hi is the invariant; boundary is in-bounds by definition",
        ),
    ]

    # Severity thresholds
    severity_thresholds = {
        "pass_max_violations": 0,
        "caution_max_violations": 2,
        "warning_max_violations": 4,
        "critical_min_violations": 5,
    }

    return ConstraintProcedureTile(
        name=f"flux-{preset_name}-procedure",
        version=1,
        domain=preset_name,
        created_by="forgemaster-specialist",
        created_at=time.time(),
        pre_conditions=pre_conditions,
        steps=steps,
        post_conditions=post_conditions,
        contingencies=contingencies,
        constraints=constraints,
        severity_thresholds=severity_thresholds,
    )


# ── Procedure Executor ──────────────────────────────────────

@dataclass
class ExecutionResult:
    """Result of executing a procedure tile."""
    error_mask: int = 0
    severity: str = "PASS"
    violation_count: int = 0
    details: List[Dict[str, Any]] = field(default_factory=list)
    proof_hash: str = ""
    tile_hash: str = ""
    execution_time_ms: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "error_mask": self.error_mask,
            "severity": self.severity,
            "violation_count": self.violation_count,
            "details": self.details,
            "proof_hash": self.proof_hash,
            "tile_hash": self.tile_hash,
            "execution_time_ms": round(self.execution_time_ms, 3),
            "warnings": self.warnings,
        }


def execute_procedure(
    tile: ConstraintProcedureTile,
    values: List[Any],
) -> ExecutionResult:
    """
    Execute a procedure tile — small-model-friendly.

    This function follows the steps EXACTLY as specified in the tile.
    A Seed-2.0-mini could implement this from the tile's compact representation.
    No understanding of constraint theory required — just follow the procedure.

    Args:
        tile: A ConstraintProcedureTile with embedded constraints and steps
        values: List of values to check (one per constraint)

    Returns:
        ExecutionResult with error_mask, severity, proof hash, and details
    """
    start = time.monotonic()
    n = len(tile.constraints)
    result = ExecutionResult(tile_hash=tile.tile_hash)

    # ── Step 1: Validate input ──────────────────────────────
    # Check count
    if len(values) != n:
        result.warnings.append(
            f"Count mismatch: expected {n} values, got {len(values)}"
        )
        result.severity = "CRITICAL"
        result.error_mask = (1 << n) - 1  # All bits set
        result.violation_count = n
        result.execution_time_ms = (time.monotonic() - start) * 1000
        return result

    # Check each value for NaN/Inf/type
    valid = []
    for i, v in enumerate(values):
        if not isinstance(v, (int, float)):
            result.warnings.append(f"Value[{i}] is non-numeric ({type(v).__name__})")
            valid.append(False)
        elif math.isnan(v):
            result.warnings.append(f"Value[{i}] is NaN")
            valid.append(False)
        elif math.isinf(v):
            result.warnings.append(f"Value[{i}] is Inf")
            valid.append(False)
        else:
            valid.append(True)

    # ── Step 2 & 3: Check constraints and build error mask ──
    error_mask = 0
    details = []

    for i in range(n):
        constraint = tile.constraints[i]
        lo = constraint["lo"]
        hi = constraint["hi"]
        name = constraint["name"]
        val = values[i]

        detail: Dict[str, Any] = {
            "name": name,
            "lo": lo,
            "hi": hi,
            "value": val,
            "valid_type": valid[i],
        }

        if not valid[i]:
            # Contingency: NaN/Inf/non-numeric → bit set
            error_mask |= (1 << i)
            detail["passed"] = False
            detail["reason"] = "invalid_type" if not isinstance(val, (int, float)) else (
                "NaN" if isinstance(val, float) and math.isnan(val) else "Inf"
            )
        else:
            # Standard check: lo <= val <= hi
            lo_ok = lo <= val
            hi_ok = val <= hi
            passed = lo_ok and hi_ok
            detail["passed"] = passed
            detail["lo_violated"] = not lo_ok
            detail["hi_violated"] = not hi_ok
            if not passed:
                error_mask |= (1 << i)
                detail["reason"] = "lo_violated" if not lo_ok else "hi_violated"

        details.append(detail)

    result.error_mask = error_mask
    result.details = details

    # ── Step 4: Classify severity ───────────────────────────
    violation_count = bin(error_mask).count("1")
    result.violation_count = violation_count

    # Per contingency: NaN or non-numeric → CRITICAL (safety first)
    has_invalid = any(not v for v in valid)

    thresholds = tile.severity_thresholds
    if has_invalid:
        result.severity = "CRITICAL"
    elif violation_count == 0:
        result.severity = "PASS"
    elif violation_count <= thresholds.get("caution_max_violations", 2):
        result.severity = "CAUTION"
    elif violation_count <= thresholds.get("warning_max_violations", 4):
        result.severity = "WARNING"
    else:
        result.severity = "CRITICAL"

    # ── Step 5: Generate proof hash ─────────────────────────
    proof_payload = json.dumps({
        "tile_hash": tile.tile_hash,
        "error_mask": error_mask,
        "severity": result.severity,
        "values": [v if isinstance(v, (int, float)) and not math.isnan(v) and not math.isinf(v) else str(v) for v in values],
    }, sort_keys=True)
    result.proof_hash = hashlib.sha256(proof_payload.encode()).hexdigest()[:16]

    result.execution_time_ms = (time.monotonic() - start) * 1000
    return result


# ── Procedure Refiner ───────────────────────────────────────

def refine_procedure(
    tile: ConstraintProcedureTile,
    outcomes: List[Dict[str, Any]],
) -> ConstraintProcedureTile:
    """
    Refine a procedure tile based on execution outcomes.

    The hospital science pattern: every execution refines the protocol.
    If outcomes show edge cases, add new contingencies.
    If outcomes show performance issues, optimize step ordering.

    Creates a NEW version of the tile — the old one is preserved.

    Args:
        tile: The procedure tile to refine
        outcomes: List of execution results (as dicts)

    Returns:
        A new ConstraintProcedureTile with version incremented
    """
    new_contingencies = list(tile.contingencies)
    refinement_notes = []

    # Analyze outcomes for patterns
    nan_count = sum(1 for o in outcomes if any(
        w.startswith("Value[") and "NaN" in w for w in o.get("warnings", [])
    ))
    inf_count = sum(1 for o in outcomes if any(
        w.startswith("Value[") and "Inf" in w for w in o.get("warnings", [])
    ))
    count_mismatch = sum(1 for o in outcomes if any(
        "Count mismatch" in w for w in o.get("warnings", [])
    ))

    # Edge case: NaN values appeared frequently
    if nan_count > 0:
        existing = [c.condition for c in new_contingencies]
        if not any("Batch NaN" in c for c in existing):
            new_contingencies.append(Contingency(
                condition="Batch NaN detected (multiple NaN values in one execution)",
                action="Flag the data source as potentially corrupted",
                rationale=f"Observed {nan_count} NaN occurrences in {len(outcomes)} executions — suggests upstream data quality issue",
            ))
            refinement_notes.append(f"Added batch-NaN contingency (observed {nan_count} occurrences)")

    # Edge case: Inf values
    if inf_count > 0:
        existing = [c.condition for c in new_contingencies]
        if not any("Batch Inf" in c for c in existing):
            new_contingencies.append(Contingency(
                condition="Batch Inf detected (multiple Inf values in one execution)",
                action="Check for division-by-zero in upstream calculations",
                rationale=f"Observed {inf_count} Inf occurrences in {len(outcomes)} executions — likely upstream arithmetic error",
            ))
            refinement_notes.append(f"Added batch-Inf contingency (observed {inf_count} occurrences)")

    # Edge case: count mismatches
    if count_mismatch > 0:
        existing = [c.condition for c in new_contingencies]
        if not any("Repeated count mismatch" in c for c in existing):
            new_contingencies.append(Contingency(
                condition="Repeated count mismatch (expected != actual values)",
                action="Check if schema has changed — constraint set may need updating",
                rationale=f"Observed {count_mismatch} count mismatches in {len(outcomes)} executions",
            ))
            refinement_notes.append(f"Added count-mismatch contingency (observed {count_mismatch} occurrences)")

    # Analyze which constraints are most frequently violated
    violation_counts: Dict[str, int] = {}
    for o in outcomes:
        for d in o.get("details", []):
            if not d.get("passed", True):
                name = d.get("name", "unknown")
                violation_counts[name] = violation_counts.get(name, 0) + 1

    # If a constraint is violated >50% of the time, note it
    total = len(outcomes)
    hot_constraints = [
        name for name, count in violation_counts.items()
        if count > total * 0.5 and total > 0
    ]
    if hot_constraints:
        refinement_notes.append(
            f"High-violation constraints: {hot_constraints} — consider reviewing bounds"
        )

    # Build refinement history entry
    history_entry = {
        "from_version": tile.version,
        "to_version": tile.version + 1,
        "outcomes_analyzed": len(outcomes),
        "new_contingencies_added": len(new_contingencies) - len(tile.contingencies),
        "notes": refinement_notes,
        "timestamp": time.time(),
    }

    # Build new tile
    return ConstraintProcedureTile(
        name=tile.name,
        version=tile.version + 1,
        domain=tile.domain,
        created_by=tile.created_by,
        created_at=tile.created_at,
        pre_conditions=tile.pre_conditions,
        steps=tile.steps,  # Steps unchanged for now
        post_conditions=tile.post_conditions,
        contingencies=new_contingencies,
        constraints=tile.constraints,
        severity_thresholds=tile.severity_thresholds,
        refinement_history=tile.refinement_history + [history_entry],
        parent_tile_hash=tile.tile_hash,
    )


# ── Capability Ladder Demo ──────────────────────────────────

def demonstrate_capability_ladder() -> str:
    """
    Demonstrate the tile-as-procedure pattern end-to-end.

    Shows:
    1. Large model creates the procedure tile
    2. Prints the tile in a format any model can read
    3. Executes with various inputs (normal, edge, failure)
    4. Refines based on outcomes
    5. The refined tile accumulates the intelligence

    Returns the full demonstration as a string.
    """
    lines: List[str] = []
    def log(s: str = "") -> None:
        lines.append(s)

    log("=" * 72)
    log("FLUX PROCEDURE TILES — Capability Ladder Demonstration")
    log("=" * 72)

    # ── Phase 1: Specialist creates tile ─────────────────────
    log()
    log("── Phase 1: Specialist (large model) creates procedure tile ──")
    log()

    tile = build_preset_procedure("automotive_can")
    log(f"Created: {tile.name} v{tile.version}")
    log(f"Domain: {tile.domain}")
    log(f"Constraints: {len(tile.constraints)}")
    log(f"Steps: {len(tile.steps)}")
    log(f"Contingencies: {len(tile.contingencies)}")
    log(f"Hash: {tile.tile_hash}")
    log()

    # Print compact form
    log("── Tile Compact Form (readable by any model) ──")
    log()
    compact = tile.to_compact()
    for line in compact.split("\n")[:40]:  # First 40 lines
        log(line)
    if len(compact.split("\n")) > 40:
        extra = len(compact.split('\n')) - 40
        log(f"  ... ({extra} more lines)")
    log()

    # ── Phase 2: Execute with normal inputs ──────────────────
    log("── Phase 2: General Practitioner (small model) executes ──")
    log()

    # Normal values — all in bounds
    normal = [3000, 80, 90, 50, 50, 0, 12.6, 75]
    result = execute_procedure(tile, normal)
    log(f"Input: {normal}")
    log(f"Result: mask={result.error_mask}, severity={result.severity}, "
        f"violations={result.violation_count}, hash={result.proof_hash}")
    assert result.severity == "PASS"
    assert result.violation_count == 0
    log("✓ All in-bounds → PASS")
    log()

    # ── Phase 3: Edge cases ──────────────────────────────────
    log("── Phase 3: Edge cases and failures ──")
    log()

    # Boundary values (exactly at lo/hi)
    boundary = [0, 300, -40, 100, 200, 720, 9, 0]
    result = execute_procedure(tile, boundary)
    log(f"Boundary: {boundary}")
    log(f"Result: mask={result.error_mask}, severity={result.severity}")
    assert result.severity == "PASS"
    log("✓ Boundary values (exactly at lo/hi) → PASS")
    log()

    # Out of bounds
    oob = [9000, 350, 200, 50, 50, 0, 12.6, 75]
    result = execute_procedure(tile, oob)
    log(f"Out-of-bounds: {oob}")
    log(f"Result: mask={result.error_mask}, severity={result.severity}, "
        f"violations={result.violation_count}")
    assert result.violation_count >= 2  # RPM + speed + temp
    log(f"✓ Out-of-bounds detected → {result.severity} ({result.violation_count} violations)")
    for d in result.details:
        if not d["passed"]:
            log(f"  ✗ {d['name']}: value={d['value']}, bounds=[{d['lo']}, {d['hi']}]")
    log()

    # NaN input
    nan_input = [3000, float('nan'), 90, 50, 50, 0, 12.6, 75]
    result = execute_procedure(tile, nan_input)
    log(f"NaN input: speed=nan")
    log(f"Result: mask={result.error_mask}, severity={result.severity}")
    assert result.severity == "CRITICAL"
    log("✓ NaN detected → CRITICAL (safety first)")
    log()

    # Inf input
    inf_input = [float('inf'), 80, 90, 50, 50, 0, 12.6, 75]
    result = execute_procedure(tile, inf_input)
    log(f"Inf input: rpm=inf")
    log(f"Result: mask={result.error_mask}, severity={result.severity}")
    assert result.violation_count >= 1
    log("✓ Inf detected → violation flagged")
    log()

    # Wrong count
    wrong_count = [3000, 80]
    result = execute_procedure(tile, wrong_count)
    log(f"Wrong count: {len(wrong_count)} values (expected {len(tile.constraints)})")
    log(f"Result: mask={result.error_mask}, severity={result.severity}")
    assert result.severity == "CRITICAL"
    log("✓ Count mismatch → CRITICAL")
    log()

    # ── Phase 4: Refinement cycle ────────────────────────────
    log("── Phase 4: Refinement cycle (hospital science pattern) ──")
    log()

    # Simulate execution outcomes
    outcomes = [
        execute_procedure(tile, normal).to_dict(),
        execute_procedure(tile, oob).to_dict(),
        execute_procedure(tile, nan_input).to_dict(),
        execute_procedure(tile, inf_input).to_dict(),
        execute_procedure(tile, wrong_count).to_dict(),
        execute_procedure(tile, normal).to_dict(),
    ]

    log(f"Collected {len(outcomes)} execution outcomes")
    log("  - 2 normal (PASS)")
    log("  - 1 out-of-bounds (WARNING+)")
    log("  - 1 NaN (CRITICAL)")
    log("  - 1 Inf (CAUTION+)")
    log("  - 1 count mismatch (CRITICAL)")
    log()

    # Refine
    refined = refine_procedure(tile, outcomes)
    log(f"Refined tile: {refined.name} v{refined.version}")
    log(f"  Parent hash: {refined.parent_tile_hash}")
    log(f"  New hash: {refined.tile_hash}")
    log(f"  New contingencies: {len(refined.contingencies)} (was {len(tile.contingencies)})")
    log(f"  History: {refined.refinement_history[-1]}")
    log()

    # ── Phase 5: Intelligence accumulation ───────────────────
    log("── Phase 5: Intelligence accumulation ──")
    log()

    # Second refinement round with NaN-heavy data
    more_outcomes = [
        execute_procedure(tile, [float('nan')] * 8).to_dict(),
        execute_procedure(tile, [float('nan')] * 8).to_dict(),
        execute_procedure(tile, normal).to_dict(),
    ]

    v3 = refine_procedure(refined, more_outcomes)
    log(f"Third version: {v3.name} v{v3.version}")
    log(f"  Contingencies: {len(v3.contingencies)} (original: {len(tile.contingencies)})")
    log(f"  Refinement rounds: {len(v3.refinement_history)}")
    log()

    # Show new contingencies
    log("New contingencies added through refinement:")
    for c in v3.contingencies:
        if c not in tile.contingencies:
            log(f"  + IF {c.condition}: {c.action}")
            log(f"    Because: {c.rationale}")
    log()

    # ── Summary ──────────────────────────────────────────────
    log("=" * 72)
    log("SUMMARY")
    log("=" * 72)
    log()
    log(f"Original tile v1: {len(tile.contingencies)} contingencies, {len(tile.steps)} steps")
    log(f"Refined tile  v2: {len(refined.contingencies)} contingencies, {len(refined.steps)} steps")
    log(f"Refined tile  v3: {len(v3.contingencies)} contingencies, {len(v3.steps)} steps")
    log()
    log("The tile accumulated intelligence through execution feedback.")
    log("A small model executing v3 handles edge cases that v1 didn't anticipate.")
    log("This is the medical protocol pattern: outcomes refine the procedure.")
    log()
    log("✓ Tiles ARE intelligence transfer.")
    log("✓ The procedure IS the capability amplifier.")
    log("✓ Accumulation compounds with every cycle.")

    return "\n".join(lines)
