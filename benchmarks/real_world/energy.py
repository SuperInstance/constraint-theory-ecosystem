#!/usr/bin/env python3
"""Energy Grid Real-Time Monitoring benchmark.

10,000 grid points × 4 constraints each at 50Hz = 2,000,000 checks/sec sustained.
Measures sustained throughput, memory usage, cache behavior.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from benchmark_framework import (
    Constraint, run_benchmark, format_result, measure_memory_mb, compute_latency
)
import random
import time


def grid_constraints() -> list:
    """4 constraints per grid point."""
    return [
        Constraint(0.95, 1.05, "voltage_pu"),       # per-unit voltage
        Constraint(49.0, 51.0, "frequency_hz"),      # frequency
        Constraint(0, 500, "load_mw"),                # MW load
        Constraint(-0.95, 0.95, "phase_angle_rad"),   # power factor angle
    ]


def main():
    print("=" * 70)
    print("ENERGY GRID REAL-TIME MONITORING BENCHMARK")
    print("10,000 grid points × 4 constraints × 50Hz = 2,000,000 checks/sec")
    print("=" * 70)

    n_points = 10000
    constraints = grid_constraints()
    required_rate = n_points * 4 * 50  # 2M/sec

    result = run_benchmark(
        scenario="Energy Grid",
        constraints=constraints,
        required_rate=required_rate,
        duration_sec=5.0,
        inject_rate=0.003,
        batch_size=10000,
    )

    print(format_result(result))
    print()

    # Sustained throughput at scale
    print("--- Sustained throughput (10K points, 5 seconds) ---")
    latencies = []
    total = 0
    violations = 0
    memory_samples = []

    t_start = time.perf_counter()
    for sec in range(5):
        sec_start = time.perf_counter()
        for cycle in range(50):  # 50Hz
            for point in range(n_points):
                for ci, c in enumerate(constraints):
                    # Realistic grid values
                    if c.tag == "voltage_pu":
                        v = random.gauss(1.0, 0.01)
                    elif c.tag == "frequency_hz":
                        v = random.gauss(50.0, 0.05)
                    elif c.tag == "load_mw":
                        v = abs(random.gauss(200, 80))
                    else:
                        v = random.gauss(0, 0.3)
                    
                    t0 = time.perf_counter_ns()
                    passed = c.check(v)
                    t1 = time.perf_counter_ns()
                    latencies.append(t1 - t0)
                    if not passed:
                        violations += 1
                    total += 1
        
        memory_samples.append(measure_memory_mb())
        sec_elapsed = time.perf_counter() - sec_start
        print(f"  Second {sec+1}: {total:,} checks, {total/(time.perf_counter()-t_start):,.0f}/sec, RSS: {memory_samples[-1]:.1f}MB")

    elapsed = time.perf_counter() - t_start
    lat = compute_latency(latencies[-100000:])  # last 100k samples
    
    print(f"\nTotal: {total:,} checks in {elapsed:.2f}s")
    print(f"Throughput: {total/elapsed:,.0f}/sec (required: {required_rate:,}/sec)")
    print(f"Headroom: {(total/elapsed)/required_rate:.2f}x")
    print(f"Latency: mean={lat.mean_us*1000:.1f}ns  p99={lat.p99_us*1000:.1f}ns  max={lat.max_us*1000:.1f}ns")
    print(f"Violations: {violations}")
    print(f"Memory growth: {memory_samples[-1] - memory_samples[0]:.1f}MB over 5 seconds")
    print()

    return result


if __name__ == "__main__":
    main()
