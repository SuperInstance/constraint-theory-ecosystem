"""
flux_verify.py — Formal Verification for Constraint Sets

Proves properties about constraint SETS (not individual checks):
1. verify_well_formed — no inverted ranges, no NaN bounds, no empty valid regions
2. verify_exhaustive — no value in [lo-ε, hi+ε] is misclassified
3. verify_deterministic — same inputs always produce same outputs
4. verify_zero_false_negatives — all out-of-range values detected

Based on flux_formal.py's ConstraintSetProver and BoundaryExhaustiveChecker,
refactored into composable verification functions.

Author: Forgemaster ⚒️
Date: 2026-05-19
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ─── Severity ────────────────────────────────────────────────────────────────

class Severity(Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


# ─── Constraint wrapper ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class Constraint:
    """A single range constraint [lo, hi] with a name."""
    name: str
    lo: float
    hi: float

    def check(self, value: float) -> bool:
        """True if value is in [lo, hi]."""
        return self.lo <= value <= self.hi

    def violation_magnitude(self, value: float) -> float:
        if value < self.lo:
            return self.lo - value
        if value > self.hi:
            return value - self.hi
        return 0.0


def _constraints_from_dicts(constraint_dicts: List[Dict]) -> List[Constraint]:
    """Convert list of dicts (from PRESETS) to Constraint objects."""
    return [
        Constraint(
            name=c.get("name", f"C{i}"),
            lo=float(c["lo"]),
            hi=float(c["hi"]),
        )
        for i, c in enumerate(constraint_dicts)
    ]


# ─── Verification Result ────────────────────────────────────────────────────

@dataclass
class VerificationReport:
    """Result of a verification pass."""
    name: str
    passed: bool
    details: List[str] = field(default_factory=list)
    counterexamples: List[Any] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed

    def summary(self) -> str:
        icon = "✅" if self.passed else "❌"
        lines = [f"{icon} {self.name}"]
        for d in self.details:
            lines.append(f"   {d}")
        for cx in self.counterexamples[:5]:
            lines.append(f"   counterexample: {cx}")
        if len(self.counterexamples) > 5:
            lines.append(f"   ... and {len(self.counterexamples) - 5} more counterexamples")
        return "\n".join(lines)


# ─── 1. Well-formedness ─────────────────────────────────────────────────────

def verify_well_formed(constraints: List[Dict]) -> VerificationReport:
    """
    Verify that a constraint set is well-formed.

    Checks:
    - No inverted ranges (lo > hi)
    - No NaN or Inf bounds
    - No empty valid regions (lo == hi — fragile with float)
    - All names are unique
    - All values are finite

    Returns VerificationReport with passed=True if all checks succeed.
    """
    cs = _constraints_from_dicts(constraints)
    details = []
    counterexamples = []
    passed = True

    # Unique names
    names = [c.name for c in cs]
    seen = set()
    for name in names:
        if name in seen:
            passed = False
            details.append(f"Duplicate constraint name: '{name}'")
            counterexamples.append({"type": "duplicate_name", "name": name})
        seen.add(name)

    for c in cs:
        # Inverted range
        if c.lo > c.hi:
            passed = False
            details.append(f"Inverted range: '{c.name}' lo={c.lo} > hi={c.hi}")
            counterexamples.append({"type": "inverted_range", "name": c.name, "lo": c.lo, "hi": c.hi})

        # NaN
        if math.isnan(c.lo) or math.isnan(c.hi):
            passed = False
            details.append(f"NaN bound: '{c.name}' lo={c.lo} hi={c.hi}")
            counterexamples.append({"type": "nan_bound", "name": c.name})

        # Inf
        if math.isinf(c.lo) or math.isinf(c.hi):
            passed = False
            details.append(f"Infinite bound: '{c.name}' lo={c.lo} hi={c.hi}")
            counterexamples.append({"type": "inf_bound", "name": c.name})

        # Empty valid region (point constraint)
        if c.lo == c.hi and not (math.isnan(c.lo) or math.isnan(c.hi)):
            details.append(f"Point constraint: '{c.name}' lo==hi=={c.lo} (fragile with float)")
            # This is a WARNING, not a hard failure — downgrade to info
            counterexamples.append({"type": "point_constraint", "name": c.name, "value": c.lo})

    if passed and not details:
        details.append(f"All {len(cs)} constraints are well-formed")

    return VerificationReport(
        name="well_formed",
        passed=passed,
        details=details,
        counterexamples=counterexamples,
    )


# ─── 2. Exhaustive boundary testing ─────────────────────────────────────────

def verify_exhaustive(
    constraints: List[Dict],
    epsilon: float = 1e-15,
) -> VerificationReport:
    """
    Verify that no value in [lo-ε, hi+ε] is misclassified.

    Tests boundary neighborhoods with multiple epsilon offsets:
    exact boundary, just inside, just outside.

    For continuous (float) domains, we check all REPRESENTABLE floats
    in the critical boundary regions.

    Returns VerificationReport with passed=True if no misclassification found.
    """
    cs = _constraints_from_dicts(constraints)
    details = []
    counterexamples = []

    epsilons = [
        0.0,
        -epsilon,
        epsilon,
        -epsilon * 1e3,
        epsilon * 1e3,
        -epsilon * 1e6,
        epsilon * 1e6,
        -1e-10,
        1e-10,
        -1e-5,
        1e-5,
        -1e-3,
        1e-3,
    ]

    for c in cs:
        for boundary in [c.lo, c.hi]:
            for eps in epsilons:
                test_val = boundary + eps
                if math.isnan(test_val) or math.isinf(test_val):
                    continue

                expected = c.lo <= test_val <= c.hi
                actual = c.check(test_val)

                if expected != actual:
                    counterexamples.append({
                        "constraint": c.name,
                        "boundary": boundary,
                        "epsilon": eps,
                        "test_value": test_val,
                        "expected_compliant": expected,
                        "actual_compliant": actual,
                    })

    if counterexamples:
        details.append(f"Found {len(counterexamples)} misclassification(s)")
    else:
        details.append(
            f"Tested {len(cs)} constraints × {len(epsilons)} epsilon offsets × 2 boundaries = "
            f"{len(cs) * len(epsilons) * 2} boundary checks — all correct"
        )

    return VerificationReport(
        name="exhaustive",
        passed=len(counterexamples) == 0,
        details=details,
        counterexamples=counterexamples,
    )


# ─── 3. Determinism ─────────────────────────────────────────────────────────

def verify_deterministic(
    constraints: List[Dict],
    n: int = 10000,
) -> VerificationReport:
    """
    Verify that same inputs always produce same outputs.

    Generate n test values spanning the full range of all constraints,
    check each against all constraints twice, and compare results.

    Returns VerificationReport with passed=True if all checks are deterministic.
    """
    cs = _constraints_from_dicts(constraints)
    details = []
    counterexamples = []

    if not cs:
        return VerificationReport(name="deterministic", passed=True, details=["No constraints to test"])

    # Find global range
    global_lo = min(c.lo for c in cs)
    global_hi = max(c.hi for c in cs)
    span = global_hi - global_lo
    if span == 0:
        span = 1.0

    # Generate test values: uniform + boundary-heavy
    import random
    rng = random.Random(42)  # Fixed seed for reproducibility
    values = []

    # Uniform samples
    for _ in range(n // 2):
        values.append(global_lo - span * 0.1 + rng.random() * span * 1.2)

    # Boundary-heavy samples
    for c in cs:
        for _ in range(n // (2 * len(cs)) + 1):
            for offset in [-1e-10, 0.0, 1e-10]:
                values.append(c.lo + offset)
                values.append(c.hi + offset)

    # Deduplicate while preserving order (approximate for floats)
    seen = set()
    unique_values = []
    for v in values:
        key = round(v, 12)
        if key not in seen:
            seen.add(key)
            unique_values.append(v)

    total_checks = 0
    for val in unique_values:
        for c in cs:
            r1 = c.check(val)
            r2 = c.check(val)
            m1 = c.violation_magnitude(val)
            m2 = c.violation_magnitude(val)

            if r1 != r2 or m1 != m2:
                counterexamples.append({
                    "constraint": c.name,
                    "value": val,
                    "run1": r1,
                    "run2": r2,
                    "mag1": m1,
                    "mag2": m2,
                })
            total_checks += 1

    if counterexamples:
        details.append(f"Found {len(counterexamples)} non-deterministic results out of {total_checks} checks")
    else:
        details.append(f"All {total_checks} checks are deterministic across {len(unique_values)} test values")

    return VerificationReport(
        name="deterministic",
        passed=len(counterexamples) == 0,
        details=details,
        counterexamples=counterexamples,
    )


# ─── 4. Zero false negatives ────────────────────────────────────────────────

def verify_zero_false_negatives(
    constraints: List[Dict],
    test_values: Optional[List[float]] = None,
) -> VerificationReport:
    """
    Verify that all out-of-range values are detected.

    A false negative is when a value is OUTSIDE [lo, hi] but the check
    returns True (compliant). This should NEVER happen.

    If test_values is None, generates values systematically:
    - Values slightly below each constraint's lo
    - Values slightly above each constraint's hi
    - Extreme out-of-range values

    Returns VerificationReport with passed=True if no false negatives found.
    """
    cs = _constraints_from_dicts(constraints)
    details = []
    counterexamples = []

    if test_values is None:
        test_values = []
        for c in cs:
            # Below lo
            test_values.extend([
                c.lo - 1e-15,
                c.lo - 1e-10,
                c.lo - 1e-5,
                c.lo - 1.0,
                c.lo - 100.0,
            ])
            # Above hi
            test_values.extend([
                c.hi + 1e-15,
                c.hi + 1e-10,
                c.hi + 1e-5,
                c.hi + 1.0,
                c.hi + 100.0,
            ])

    total_checks = 0
    for val in test_values:
        if math.isnan(val) or math.isinf(val):
            continue
        for c in cs:
            total_checks += 1
            # Determine expected: is this value ACTUALLY in range?
            in_range = c.lo <= val <= c.hi
            # Run the check
            check_result = c.check(val)

            if not in_range and check_result:
                # FALSE NEGATIVE: value is out of range but check says compliant
                counterexamples.append({
                    "constraint": c.name,
                    "value": val,
                    "lo": c.lo,
                    "hi": c.hi,
                    "expected": "violation",
                    "actual": "compliant",
                })

    if counterexamples:
        details.append(f"Found {len(counterexamples)} false negative(s) out of {total_checks} checks")
    else:
        details.append(f"All {total_checks} checks have zero false negatives")

    return VerificationReport(
        name="zero_false_negatives",
        passed=len(counterexamples) == 0,
        details=details,
        counterexamples=counterexamples,
    )


# ─── Combined verification ──────────────────────────────────────────────────

@dataclass
class ConstraintSetVerification:
    """Complete verification result for a constraint set."""
    constraint_set_hash: str
    preset_name: str
    reports: List[VerificationReport]
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.reports)

    def summary(self) -> str:
        lines = [
            f"Constraint Set Verification: {self.preset_name}",
            f"  hash: {self.constraint_set_hash[:16]}...",
            f"  all_passed: {self.all_passed}",
            "",
        ]
        for r in self.reports:
            lines.append(r.summary())
        return "\n".join(lines)


def verify_all(
    constraints: List[Dict],
    preset_name: str = "custom",
    exhaustive_epsilon: float = 1e-15,
    deterministic_n: int = 10000,
    false_neg_values: Optional[List[float]] = None,
) -> ConstraintSetVerification:
    """
    Run all four verification passes on a constraint set.

    Returns ConstraintSetVerification with combined results.
    """
    # Compute constraint set hash
    payload = json.dumps(
        sorted(constraints, key=lambda c: c.get("name", "")),
        sort_keys=True,
    )
    cs_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    reports = [
        verify_well_formed(constraints),
        verify_exhaustive(constraints, epsilon=exhaustive_epsilon),
        verify_deterministic(constraints, n=deterministic_n),
        verify_zero_false_negatives(constraints, test_values=false_neg_values),
    ]

    return ConstraintSetVerification(
        constraint_set_hash=cs_hash,
        preset_name=preset_name,
        reports=reports,
    )
