#!/usr/bin/env python3
"""Maritime Fleet Tracking benchmark.

1000 vessels × 4 constraints each at 1Hz = 4,000 checks/sec.
Measures batch throughput and parallel scaling potential.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from benchmark_framework import (
    Constraint, run_benchmark, format_result, measure_memory_mb, compute_latency
)
import random
import time


def maritime_constraints() -> list:
    """4 constraints per vessel."""
    return [
        Constraint(-90, 90, "latitude"),       # position lat
        Constraint(-180, 180, "longitude"),     # position lon
        Constraint(0, 50, "speed_knots"),       # speed
        Constraint(0, 360, "heading_deg"),      # heading
    ]


def generate_vessel_state(constraints, inject=False):
    """Generate realistic AIS-like vessel data."""
    values = []
    for c in constraints:
        if inject and random.random() < 0.005:
            from benchmark_framework import inject_violation
            values.append(inject_violation(c))
        else:
            if c.tag == "latitude":
                v = random.gauss(35, 10)  # major shipping lanes
            elif c.tag == "longitude":
                v = random.gauss(-40, 30)
            elif c.tag == "speed_knots":
                v = abs(random.gauss(12, 5))  # typical vessel speed
            else:
                v = random.uniform(0, 360)
            values.append(max(c.lo, min(c.hi, v)))
    return values


def main():
    print("=" * 70)
    print("MARITIME FLEET TRACKING BENCHMARK")
    print("1000 vessels × 4 constraints × 1Hz = 4,000 checks/sec")
    print("=" * 70)

    n_vessels = 1000
    constraints = maritime_constraints()
    required_rate = n_vessels * 4 * 1  # 4,000/sec

    # Stress test
    result = run_benchmark(
        scenario="Maritime Fleet",
        constraints=constraints,
        required_rate=required_rate,
        duration_sec=5.0,
        inject_rate=0.005,
        batch_size=5000,
    )

    print(format_result(result))
    print()

    # Batch simulation: 1000 vessels, 10 update cycles
    print("--- Batch throughput (1000 vessels × 10 updates) ---")
    latencies = []
    total = 0
    violations = 0
    t_start = time.perf_counter()

    for update in range(10):
        for vessel in range(n_vessels):
            values = generate_vessel_state(constraints, inject=True)
            for ci, c in enumerate(constraints):
                t0 = time.perf_counter_ns()
                passed = c.check(values[ci])
                t1 = time.perf_counter_ns()
                latencies.append(t1 - t0)
                if not passed:
                    violations += 1
                total += 1

    elapsed = time.perf_counter() - t_start
    lat = compute_latency(latencies)
    print(f"Total checks: {total:,}")
    print(f"Elapsed: {elapsed:.3f}s")
    print(f"Throughput: {total/elapsed:,.0f}/sec")
    print(f"Latency: mean={lat.mean_us*1000:.1f}ns  p99={lat.p99_us*1000:.1f}ns  max={lat.max_us*1000:.1f}ns")
    print(f"Violations: {violations}")
    print()

    # Scaling test
    print("--- Scaling test (varying vessel counts) ---")
    for nv in [100, 500, 1000, 5000, 10000]:
        t0 = time.perf_counter()
        total = nv * 4 * 100  # 100 updates
        for _ in range(100):
            for ci in range(4):
                c = constraints[ci]
                for __ in range(nv):
                    c.check(random.uniform(c.lo, c.hi))
        elapsed = time.perf_counter() - t0
        rate = total / elapsed
        print(f"  {nv:>6} vessels: {rate:>12,.0f} checks/sec ({elapsed:.3f}s)")
    print()

    return result


if __name__ == "__main__":
    main()
