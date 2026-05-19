#!/usr/bin/env python3
"""Aviation TCAS benchmark — 100 aircraft, 8 constraints each, 1Hz for 10s.

Simulates realistic traffic collision avoidance with altitude, speed, heading,
vertical rate, distance, closure rate, bearing, and intent constraints.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from benchmark_framework import (
    Constraint, run_benchmark, format_result, generate_sensor_value, inject_violation,
    measure_memory_mb, compute_latency
)
import random
import time


def aviation_constraints() -> list:
    """8 constraints per aircraft for TCAS."""
    return [
        Constraint(0, 45000, "altitude_ft"),        # altitude in feet
        Constraint(100, 600, "airspeed_kts"),         # airspeed in knots
        Constraint(0, 360, "heading_deg"),            # heading 0-360
        Constraint(-6000, 6000, "vert_rate_fpm"),     # vertical rate ft/min
        Constraint(0, 300, "distance_nm"),            # distance to nearest nmi
        Constraint(0, 1200, "closure_rate_kts"),      # closure rate knots
        Constraint(0, 360, "bearing_deg"),            # bearing to traffic
        Constraint(-1, 1, "intent_score"),            # intent classification (-1 hostile, +1 benign)
    ]


def generate_aircraft_state(constraints, inject=False):
    """Generate realistic aircraft sensor readings."""
    values = []
    for c in constraints:
        if inject and random.random() < 0.01:
            values.append(inject_violation(c))
        else:
            if c.tag == "altitude_ft":
                v = random.gauss(35000, 5000)  # cruise altitude
            elif c.tag == "airspeed_kts":
                v = random.gauss(450, 30)
            elif c.tag == "heading_deg":
                v = random.uniform(0, 360)
            elif c.tag == "vert_rate_fpm":
                v = random.gauss(0, 500)
            elif c.tag == "distance_nm":
                v = abs(random.gauss(40, 20))
            elif c.tag == "closure_rate_kts":
                v = abs(random.gauss(100, 80))
            elif c.tag == "bearing_deg":
                v = random.uniform(0, 360)
            else:
                v = random.gauss(0, 0.3)
            values.append(max(c.lo, min(c.hi, v)))
    return values


def main():
    print("=" * 70)
    print("AVIATION TCAS BENCHMARK")
    print("100 aircraft × 8 constraints × 10 updates (1Hz)")
    print("Required: 8,000 checks over 10 seconds")
    print("=" * 70)

    n_aircraft = 100
    n_constraints = 8
    updates = 10
    required_rate = n_aircraft * n_constraints * 1  # 800/sec sustained (but we stress test)

    constraints = aviation_constraints()

    # Stress test: run at much higher rate to find throughput ceiling
    result = run_benchmark(
        scenario="Aviation TCAS",
        constraints=constraints,
        required_rate=required_rate,
        duration_sec=5.0,
        inject_rate=0.01,
        batch_size=500,
    )

    print(format_result(result))
    print()

    # Realistic simulation: 100 aircraft × 8 constraints × 10 updates
    print("--- Realistic TCAS simulation (10 seconds at 1Hz) ---")
    latencies = []
    violations = 0
    total = 0
    t_start = time.perf_counter()

    for update in range(updates):
        for ac in range(n_aircraft):
            values = generate_aircraft_state(constraints, inject=True)
            for ci, c in enumerate(constraints):
                t0 = time.perf_counter_ns()
                passed = c.check(values[ci])
                t1 = time.perf_counter_ns()
                latencies.append(t1 - t0)
                if not passed:
                    violations += 1
                total += 1

    elapsed = time.perf_counter() - start if 'start' in dir() else time.perf_counter() - t_start
    lat = compute_latency(latencies)
    print(f"Total checks: {total}")
    print(f"Violations detected: {violations}")
    print(f"Latency per check: mean={lat.mean_us*1000:.1f}ns  p99={lat.p99_us*1000:.1f}ns  max={lat.max_us*1000:.1f}ns")
    print()

    return result


if __name__ == "__main__":
    main()
