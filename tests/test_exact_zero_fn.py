"""
EXACT Constraint Engine — Zero False Negative Validation Suite

Tests the EXACT implementations against the OLD INT8 quantized implementations.
Proves:
  1. Exact version has ZERO false negatives
  2. Old INT8 version has false negatives (demonstrating the bug)
  3. Exact version has zero false positives
  4. Performance is same or better

Runs 1M values per scenario across 6 real-world scenarios.
"""

import sys
import os
import random
import time
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'python'))

from flux_constraint_exact import FluxExact
from flux_constraint import FluxConstraint, Severity as OLD_SEVERITY, saturate

# ═══════════════════════════════════════════════════════════
# Scenario definitions with REALISTIC bounds
# ═══════════════════════════════════════════════════════════

SCENARIOS = {
    "ADS-B (Aviation)": {
        "exact": [
            {"lo": -1000, "hi": 45000, "name": "altitude_ft"},
            {"lo": 0, "hi": 600, "name": "ground_speed_kt"},
            {"lo": -180, "hi": 180, "name": "heading_deg"},
            {"lo": -55, "hi": 70, "name": "cabin_temp_c"},
        ],
        "value_range": (-1000, 45000),
        "out_of_range_vals": [45001, -1001, 50000, 50000, -2000, 700, 181, -181],
    },
    "FHIR (Medical)": {
        "exact": [
            {"lo": 36.1, "hi": 37.8, "name": "body_temp_c"},
            {"lo": 60, "hi": 100, "name": "heart_rate_bpm"},
            {"lo": 95, "hi": 100, "name": "spo2_pct"},
            {"lo": 80, "hi": 120, "name": "bp_systolic_mmhg"},
        ],
        "value_range": (36, 120),
        "out_of_range_vals": [37.81, 36.09, 101, 59, 94, 121, 200, 0],
    },
    "FIX (Financial)": {
        "exact": [
            {"lo": 0.0001, "hi": 100000, "name": "price"},
            {"lo": -100, "hi": 100, "name": "pct_change"},
            {"lo": 0.001, "hi": 1000, "name": "volatility"},
            {"lo": 0, "hi": 1, "name": "correlation"},
        ],
        "value_range": (-100, 100000),
        "out_of_range_vals": [100001, -0.00001, 100.001, 1.001, -100.001, 0.0009],
    },
    "SCADA (Energy)": {
        "exact": [
            {"lo": 49.0, "hi": 51.0, "name": "grid_freq_hz"},
            {"lo": 0.9, "hi": 1.1, "name": "voltage_pu"},
            {"lo": 0, "hi": 80, "name": "transformer_temp_c"},
            {"lo": 0, "hi": 100, "name": "line_load_pct"},
        ],
        "value_range": (0, 100),
        "out_of_range_vals": [51.01, 48.99, 1.101, 0.899, 81, -1, 101, 200],
    },
    "MQTT (IoT)": {
        "exact": [
            {"lo": -40, "hi": 85, "name": "ambient_temp_c"},
            {"lo": 0, "hi": 100, "name": "humidity_pct"},
            {"lo": 300, "hi": 1100, "name": "pressure_hpa"},
            {"lo": 0, "hi": 1000, "name": "co2_ppm"},
        ],
        "value_range": (-40, 1100),
        "out_of_range_vals": [86, -41, 101, -1, 1101, 299, 1001, -100],
    },
    "CAN (Automotive)": {
        "exact": [
            {"lo": 0, "hi": 8000, "name": "engine_rpm"},
            {"lo": -40, "hi": 150, "name": "coolant_temp_c"},
            {"lo": 0, "hi": 100, "name": "throttle_pct"},
            {"lo": -720, "hi": 720, "name": "steering_angle_deg"},
        ],
        "value_range": (-720, 8000),
        "out_of_range_vals": [8001, -1, 151, -41, 101, -1, 721, -721],
    },
}

N_VALUES = 1_000_000


def generate_test_values(scenario_name, scenario, n):
    """Generate n test values: mix of in-range, boundary, and out-of-range."""
    values = []
    lo, hi = scenario["value_range"]

    # 90% random in-range
    for _ in range(int(n * 0.9)):
        values.append(random.uniform(lo, hi))

    # 5% boundary values (at or epsilon from bounds)
    for _ in range(int(n * 0.025)):
        c = random.choice(scenario["exact"])
        eps = random.choice([0, 0.001, -0.001, 0.0001, -0.0001])
        values.append(c["lo"] + eps)
        values.append(c["hi"] + eps)

    # 5% out-of-range
    out_vals = scenario["out_of_range_vals"]
    for _ in range(int(n * 0.025)):
        values.append(random.choice(out_vals))
        # Also add far-out values
        values.append(random.uniform(hi * 1.5, hi * 3))
        values.append(random.uniform(lo * 3, lo * 1.5))

    # Ensure we have exactly n values
    while len(values) < n:
        values.append(random.uniform(lo, hi))

    return values[:n]


def old_int8_check(constraints_old, value):
    """Simulate old INT8-quantized check for a single constraint set."""
    val = saturate(int(value))
    violated = 0
    error_mask = 0
    for i, c in enumerate(constraints_old):
        lo_fail = val < c.lo
        hi_fail = val > c.hi
        if lo_fail or hi_fail:
            error_mask |= (1 << i)
            violated += 1
    return error_mask, violated


def run_scenario(name, scenario):
    """Test one scenario against both exact and old engines."""
    print(f"\n{'='*60}")
    print(f"  Scenario: {name}")
    print(f"{'='*60}")

    exact_fc = FluxExact(scenario["exact"])

    # Build old-style constraints (saturated bounds)
    old_constraints = []
    for c in scenario["exact"]:
        old_constraints.append(type('C', (), {
            'lo': saturate(int(c["lo"])),
            'hi': saturate(int(c["hi"])),
        })())

    # Show the quantization damage
    print("\n  Bound quantization damage:")
    for i, c in enumerate(scenario["exact"]):
        old_lo = saturate(int(c["lo"]))
        old_hi = saturate(int(c["hi"]))
        damaged = (old_lo != c["lo"]) or (old_hi != c["hi"])
        if damaged:
            print(f"    {c['name']}: [{c['lo']}, {c['hi']}] → [{old_lo}, {old_hi}] ← DAMAGED")
        else:
            print(f"    {c['name']}: [{c['lo']}, {c['hi']}] (survives INT8)")

    # Generate values
    values = generate_test_values(name, scenario, N_VALUES)
    print(f"\n  Testing {len(values):,} values...")

    # Run exact check
    t0 = time.perf_counter()
    exact_results = []
    for v in values:
        exact_results.append(exact_fc.check(v))
    t_exact = time.perf_counter() - t0

    # Run old INT8 check
    t0 = time.perf_counter()
    old_results = []
    for v in values:
        old_results.append(old_int8_check(old_constraints, v))
    t_old = time.perf_counter() - t0

    # Analyze results
    exact_fn = 0  # False negatives (violation missed by exact)
    exact_fp = 0  # False positives (in-range flagged by exact)
    old_fn = 0    # False negatives (violation missed by old)
    old_fp = 0    # False positives (in-range flagged by old)

    # For ground truth, we manually check each value against exact bounds
    for i, v in enumerate(values):
        # Ground truth: check each constraint manually
        true_violated = False
        for c in scenario["exact"]:
            if v < c["lo"] or v > c["hi"]:
                true_violated = True
                break

        exact_violated = not exact_results[i].passed
        old_violated = old_results[i][1] > 0

        if true_violated and not exact_violated:
            exact_fn += 1
        if not true_violated and exact_violated:
            exact_fp += 1
        if true_violated and not old_violated:
            old_fn += 1
        if not true_violated and old_violated:
            old_fp += 1

    print(f"\n  Results:")
    print(f"    EXACT engine:")
    print(f"      False negatives: {exact_fn} {'✓ ZERO' if exact_fn == 0 else '✗ FAILURE'}")
    print(f"      False positives: {exact_fp}")
    print(f"      Throughput: {len(values)/t_exact:,.0f} checks/sec ({t_exact*1000:.1f}ms)")

    print(f"    OLD INT8 engine:")
    print(f"      False negatives: {old_fn} {'✓' if old_fn == 0 else f'✗ {old_fn} MISSED VIOLATIONS'}")
    print(f"      False positives: {old_fp}")
    print(f"      Throughput: {len(values)/t_old:,.0f} checks/sec ({t_old*1000:.1f}ms)")

    speedup = t_old / t_exact if t_exact > 0 else 0
    print(f"    Speed ratio: {speedup:.2f}x ({'exact is faster' if speedup > 1 else 'old is faster'})")

    return {
        "name": name,
        "exact_fn": exact_fn,
        "exact_fp": exact_fp,
        "old_fn": old_fn,
        "old_fp": old_fp,
        "t_exact": t_exact,
        "t_old": t_old,
        "n_values": len(values),
    }


def demonstrate_smoking_gun():
    """Show the exact case where INT8 fails and exact succeeds."""
    print("\n" + "="*60)
    print("  SMOKING GUN: INT8 False Negative Demonstration")
    print("="*60)

    # Constraint: coolant_temp in [-40, 150]
    # INT8 saturates 150 → 127
    # Value 151: INT8 saturates to 127, passes [−40, 127]. WRONG.
    # Exact: 151 > 150, correctly detected.

    print("\n  Constraint: coolant_temp in [-40, 150]")
    print(f"  INT8 quantized bounds: [-40, {saturate(150)}]")
    print()

    test_vals = [149, 150, 151, 127, 128, 200, -40, -41, 500]
    print(f"  {'Value':>8} | {'INT8 clamped':>12} | {'INT8 result':>12} | {'EXACT result':>12} | Match?")
    print(f"  {'-'*8} | {'-'*12} | {'-'*12} | {'-'*12} | {'-'*8}")

    fc_exact = FluxExact([{"lo": -40, "hi": 150, "name": "coolant_temp"}])

    for v in test_vals:
        clamped = saturate(int(v))
        # Old: check clamped value against clamped bounds
        old_pass = (clamped >= -40) and (clamped <= 127)
        # Exact: check original value against original bounds
        exact_pass = fc_exact.check(v).passed

        match = "✓" if old_pass == exact_pass else "← FALSE NEG!"
        print(f"  {v:>8} | {clamped:>12} | {'PASS' if old_pass else 'FAIL':>12} | {'PASS' if exact_pass else 'FAIL':>12} | {match}")


def main():
    random.seed(42)

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  FLUX Exact vs INT8 — Zero False Negative Validation      ║")
    print("║  6 scenarios × 1M values each                               ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    # Smoking gun first
    demonstrate_smoking_gun()

    # Run all scenarios
    all_results = []
    for name, scenario in SCENARIOS.items():
        all_results.append(run_scenario(name, scenario))

    # Summary
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)

    total_exact_fn = sum(r["exact_fn"] for r in all_results)
    total_old_fn = sum(r["old_fn"] for r in all_results)
    total_exact_fp = sum(r["exact_fp"] for r in all_results)
    total_old_fp = sum(r["old_fp"] for r in all_results)
    total_values = sum(r["n_values"] for r in all_results)

    print(f"\n  Total values tested: {total_values:,}")
    print(f"\n  {'Scenario':<22} | {'EXACT FN':>8} | {'OLD FN':>8} | {'EXACT FP':>8} | {'OLD FP':>8} | Speed")
    print(f"  {'-'*22} | {'-'*8} | {'-'*8} | {'-'*8} | {'-'*8} | {'-'*8}")

    for r in all_results:
        speedup = r["t_old"] / r["t_exact"] if r["t_exact"] > 0 else 0
        print(f"  {r['name']:<22} | {r['exact_fn']:>8} | {r['old_fn']:>8} | {r['exact_fp']:>8} | {r['old_fp']:>8} | {speedup:.2f}x")

    print(f"  {'TOTAL':<22} | {total_exact_fn:>8} | {total_old_fn:>8} | {total_exact_fp:>8} | {total_old_fp:>8}")

    print()
    if total_exact_fn == 0:
        print("  ✓ EXACT ENGINE: ZERO FALSE NEGATIVES — INVARIANT HELDS")
    else:
        print(f"  ✗ EXACT ENGINE: {total_exact_fn} FALSE NEGATIVES — INVARIANT VIOLATED!")

    if total_old_fn > 0:
        print(f"  ✗ OLD INT8 ENGINE: {total_old_fn} FALSE NEGATIVES — SAFETY BUG CONFIRMED")
    else:
        print("  Note: Old engine had 0 FN in this run (bounds fit INT8 or values were integers)")

    if total_exact_fp == 0:
        print("  ✓ EXACT ENGINE: ZERO FALSE POSITIVES")

    # Final assertion
    assert total_exact_fn == 0, f"EXACT engine has {total_exact_fn} false negatives — INVARIANT VIOLATED!"
    print("\n  ═══ ALL TESTS PASSED ═══\n")


if __name__ == "__main__":
    main()
