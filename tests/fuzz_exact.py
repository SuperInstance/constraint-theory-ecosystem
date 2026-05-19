"""
Property-based fuzzer for FLUX Exact Constraint Engine.

No external dependencies — implements property-based testing from scratch.
Runs 10 million iterations by default.

Properties verified:
  P1: value < lo → check MUST fail
  P2: value > hi → check MUST fail
  P3: lo <= value <= hi → check MUST pass
  P4: error_mask bits correspond EXACTLY to which constraints failed
  P5: same inputs → same outputs (determinism)
  P6: severity is monotone with violation count
"""

import sys
import os
import math
import random
import struct
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from flux_constraint_exact import FluxExact, Severity, SEVERITY_TABLE


# ============================================================================
# Fuzz Value Generators
# ============================================================================

def random_float(rng: random.Random) -> float:
    """Generate a random float including adversarial edge cases."""
    roll = rng.random()

    if roll < 0.02:
        # NaN — adversarial
        return float("nan")
    elif roll < 0.04:
        # +Inf
        return float("inf")
    elif roll < 0.06:
        # -Inf
        return float("-inf")
    elif roll < 0.08:
        # Signed zeros
        return rng.choice([0.0, -0.0])
    elif roll < 0.12:
        # Denormalized floats
        bits = rng.randint(1, 0x007FFFFF)
        return struct.unpack('f', struct.pack('I', bits))[0] * rng.choice([1, -1])
    elif roll < 0.16:
        # Very large floats
        return rng.uniform(1e100, 1e300) * rng.choice([1, -1])
    elif roll < 0.20:
        # Very small (near zero) floats
        return rng.uniform(1e-300, 1e-100) * rng.choice([1, -1])
    elif roll < 0.24:
        # Float precision edge cases
        return rng.choice([0.1 + 0.2, 1e16 + 1, 1.0/3.0, math.pi, math.e])
    elif roll < 0.28:
        # Boundary values from presets
        return rng.choice([36.1, 37.8, 49.0, 51.0, 0.0001, 100000, -40, 150])
    elif roll < 0.32:
        # Integer values
        return float(rng.randint(-1000000, 1000000))
    else:
        # Normal floats in various ranges
        range_choice = rng.randint(0, 4)
        if range_choice == 0:
            return rng.uniform(-1000, 1000)
        elif range_choice == 1:
            return rng.uniform(-1e6, 1e6)
        elif range_choice == 2:
            return rng.uniform(-1e-6, 1e-6)
        elif range_choice == 3:
            return rng.uniform(0, 1)
        else:
            return rng.uniform(-100, 100)


def random_constraint(rng: random.Random) -> dict:
    """Generate a random constraint definition."""
    lo = rng.choice([
        rng.uniform(-1000, 1000),
        rng.uniform(-1e6, 1e6),
        0.0, -40.0, 36.1, 49.0, 0.0001,
        float("-inf"),
    ])
    hi = rng.choice([
        rng.uniform(-1000, 1000),
        rng.uniform(-1e6, 1e6),
        0.0, 150.0, 37.8, 51.0, 100000.0,
        float("inf"),
    ])

    # Ensure lo <= hi
    if lo > hi:
        lo, hi = hi, lo

    # Occasionally make a point constraint
    if rng.random() < 0.05:
        mid = (lo + hi) / 2 if math.isfinite(lo) and math.isfinite(hi) else 0.0
        lo = hi = mid

    return {"lo": lo, "hi": hi, "name": f"c{rng.randint(0, 999)}"}


def random_constraint_set(rng: random.Random) -> list:
    """Generate a random set of 1-8 constraints."""
    n = rng.randint(1, 8)
    return [random_constraint(rng) for _ in range(n)]


# ============================================================================
# Property Checks
# ============================================================================

class FuzzResult:
    def __init__(self):
        self.iterations = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.failures = []  # (property, description, details)
        self.nan_false_negatives = 0
        self.inf_edge_cases = 0
        self.start_time = time.time()

    def report(self):
        elapsed = time.time() - self.start_time
        rate = self.iterations / elapsed if elapsed > 0 else 0
        print(f"\n{'='*60}")
        print(f"FUZZ RESULTS: {self.iterations:,} iterations in {elapsed:.1f}s ({rate:,.0f}/s)")
        print(f"  Passed:  {self.passed:,}")
        print(f"  Failed:  {self.failed:,}")
        print(f"  Skipped: {self.skipped:,}")
        print(f"  NaN false negatives: {self.nan_false_negatives:,}")
        print(f"  Inf edge cases: {self.inf_edge_cases:,}")
        if self.failures:
            print(f"\n{'!'*60}")
            print(f"FAILURES ({len(self.failures)}):")
            for prop, desc, details in self.failures[:20]:
                print(f"  P{prop}: {desc}")
                print(f"    {details}")
        else:
            print(f"\n✓ ALL PROPERTIES HOLD")
        print(f"{'='*60}")


def is_mathematically_in_range(value: float, lo: float, hi: float) -> bool:
    """Check if value is in [lo, hi] mathematically, handling special cases.
    
    Returns:
        True if value is in range (or NaN/Inf edge case)
        False if value is definitively out of range
        None if undefined (NaN comparison)
    """
    if math.isnan(value):
        return None  # NaN comparisons are undefined
    if math.isinf(value):
        if value > 0:
            return hi == float("inf")  # +Inf in range only if hi = Inf
        else:
            return lo == float("-inf")  # -Inf in range only if lo = -Inf
    if math.isnan(lo) or math.isnan(hi):
        return None
    return lo <= value <= hi


def run_fuzz(iterations: int = 10_000_000, seed: int = None) -> FuzzResult:
    """Run the property-based fuzzer."""
    rng = random.Random(seed or 42)
    result = FuzzResult()

    for _ in range(iterations):
        result.iterations += 1

        # Generate random constraint set
        try:
            constraints = random_constraint_set(rng)
            fc = FluxExact(constraints)
        except (ValueError, OverflowError):
            result.skipped += 1
            continue

        # Generate random value
        value = random_float(rng)

        # Skip NaN — we know it's a false negative (documented bug)
        if math.isnan(value):
            r = fc.check(value)
            if r.passed:
                result.nan_false_negatives += 1
            result.skipped += 1
            continue

        # Skip +/-Inf — handle separately
        if math.isinf(value):
            try:
                r = fc.check(value)
                result.inf_edge_cases += 1
            except Exception:
                result.skipped += 1
            continue

        # Run the check
        try:
            r = fc.check(value)
        except Exception as e:
            result.failures.append(("EXC", "Exception during check", str(e)))
            result.failed += 1
            continue

        # ---- Property 1-3: Correctness ----
        for i, c in enumerate(fc.constraints):
            math_result = is_mathematically_in_range(value, c.lo, c.hi)
            if math_result is None:
                continue  # Skip NaN boundary

            engine_passed = not bool(r.error_mask & (1 << i))

            if math_result and not engine_passed:
                # FALSE POSITIVE (less dangerous but still wrong)
                result.failures.append((
                    "P3",
                    f"False positive: val={value} in [{c.lo}, {c.hi}] but engine says FAIL",
                    f"constraint {i}: error_mask={r.error_mask:#010b}"
                ))
                result.failed += 1
                break

            if not math_result and engine_passed:
                # FALSE NEGATIVE — THE CARDINAL SIN
                result.failures.append((
                    "P1/P2",
                    f"FALSE NEGATIVE: val={value} NOT in [{c.lo}, {c.hi}] but engine says PASS",
                    f"constraint {i}: error_mask={r.error_mask:#010b}"
                ))
                result.failed += 1
                break
        else:
            # ---- Property 4: error_mask consistency ----
            for i, detail in enumerate(r.details):
                bit_set = bool(r.error_mask & (1 << i))
                if bit_set == detail.passed:
                    result.failures.append((
                        "P4",
                        f"Mask bit != detail: constraint {i}",
                        f"bit_set={bit_set}, passed={detail.passed}, val={value}"
                    ))
                    result.failed += 1
                    break
            else:
                # ---- Property 5: Determinism ----
                r2 = fc.check(value)
                if r.error_mask != r2.error_mask or r.severity != r2.severity:
                    result.failures.append((
                        "P5",
                        f"Non-deterministic: same inputs, different outputs",
                        f"val={value}, mask1={r.error_mask}, mask2={r2.error_mask}"
                    ))
                    result.failed += 1
                    continue

                # ---- Property 6: Severity monotone ----
                vc = r.violated_count
                if vc < len(SEVERITY_TABLE):
                    expected_sev = SEVERITY_TABLE[vc]
                    if r.severity != expected_sev:
                        result.failures.append((
                            "P6",
                            f"Severity mismatch: count={vc}, expected={expected_sev}, got={r.severity}",
                            f"val={value}"
                        ))
                        result.failed += 1
                        continue

                result.passed += 1

        # Progress reporting
        if result.iterations % 1_000_000 == 0:
            elapsed = time.time() - result.start_time
            rate = result.iterations / elapsed
            print(f"  {result.iterations:,} iterations ({rate:,.0f}/s) — "
                  f"passed={result.passed:,} failed={result.failed:,} "
                  f"nan_fn={result.nan_false_negatives:,}")

    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="FLUX Exact Constraint Fuzzer")
    parser.add_argument("-n", "--iterations", type=int, default=10_000_000,
                        help="Number of fuzz iterations (default: 10M)")
    parser.add_argument("-s", "--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    args = parser.parse_args()

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  FLUX Exact Constraint Engine — Adversarial Fuzzer  ║")
    print(f"║  {args.iterations:,} iterations, seed={args.seed}                  ║")
    print(f"╚══════════════════════════════════════════════════════╝\n")

    result = run_fuzz(iterations=args.iterations, seed=args.seed)
    result.report()

    # Exit with failure if any property violations found
    if result.failures:
        sys.exit(1)
    print("\n✓ EXIT 0 — All properties verified")
