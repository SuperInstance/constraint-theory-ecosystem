#!/usr/bin/env python3
"""Medical ICU Patient Monitoring benchmark.

50 patients × 8 vitals each at 100Hz = 40,000 checks/sec.
Measures latency distribution (p50/p95/p99/p99.9), alarm response time.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from benchmark_framework import (
    Constraint, run_benchmark, format_result, measure_memory_mb, compute_latency
)
import random
import time
import statistics


def icu_constraints() -> list:
    """8 vital sign constraints per patient."""
    return [
        Constraint(40, 200, "heart_rate_bpm"),       # HR
        Constraint(80, 100, "spo2_pct"),              # SpO2
        Constraint(60, 180, "bp_systolic_mmhg"),      # BP systolic
        Constraint(40, 100, "bp_diastolic_mmhg"),     # BP diastolic
        Constraint(34, 40, "temp_c"),                  # Core temp
        Constraint(8, 30, "resp_rate_bpm"),            # Respiratory rate
        Constraint(20, 50, "etco2_mmhg"),              # End-tidal CO2
        Constraint(3, 15, "glasgow_coma"),             # Consciousness (GCS)
    ]


def generate_vital(constraint, stable=True):
    """Generate a realistic vital sign reading.
    
    Args:
        stable: If True, generate within normal range with physiological noise.
                If False, generate potentially pathological values.
    """
    mid = (constraint.lo + constraint.hi) / 2
    spread = (constraint.hi - constraint.lo) * 0.2
    
    if stable:
        value = mid + random.gauss(0, spread * 0.3)
    else:
        # Occasional drift toward boundaries
        if random.random() < 0.7:
            value = mid + random.gauss(0, spread * 0.5)
        else:
            # Pathological: approach or exceed limits
            edge = constraint.lo if random.random() < 0.5 else constraint.hi
            value = edge + random.gauss(0, abs(constraint.hi - constraint.lo) * 0.1)
    
    return value


def main():
    print("=" * 70)
    print("MEDICAL ICU PATIENT MONITORING BENCHMARK")
    print("50 patients × 8 vitals × 100Hz = 40,000 checks/sec")
    print("=" * 70)

    n_patients = 50
    constraints = icu_constraints()
    required_rate = n_patients * 8 * 100  # 40,000/sec

    result = run_benchmark(
        scenario="ICU Monitoring",
        constraints=constraints,
        required_rate=required_rate,
        duration_sec=5.0,
        inject_rate=0.008,  # Higher injection rate (sicker patients)
        batch_size=1000,
    )

    print(format_result(result))
    print()

    # Detailed latency distribution
    print("--- Latency Distribution (50 patients, 3 seconds at 100Hz) ---")
    latencies = []
    total = 0
    violations = 0
    alarm_times = []  # time from violation injection to detection
    t_start = time.perf_counter()

    for sec in range(3):
        for cycle in range(100):  # 100Hz
            for patient in range(n_patients):
                for ci, c in enumerate(constraints):
                    stable = random.random() > 0.01  # 1% instability
                    value = generate_vital(c, stable=stable)
                    
                    t0 = time.perf_counter_ns()
                    passed = c.check(value)
                    t1 = time.perf_counter_ns()
                    latencies.append(t1 - t0)
                    
                    if not passed:
                        violations += 1
                        alarm_times.append(t1 - t0)  # ns from check to alarm
                    
                    total += 1

    elapsed = time.perf_counter() - t_start
    lat = compute_latency(latencies)
    
    print(f"Total checks: {total:,} in {elapsed:.2f}s")
    print(f"Throughput: {total/elapsed:,.0f}/sec (required: {required_rate:,}/sec)")
    print(f"Headroom: {(total/elapsed)/required_rate:.1f}x")
    print()
    print("Latency distribution:")
    print(f"  min:  {lat.min_us*1000:>8.1f} ns")
    print(f"  p50:  {lat.p50_us*1000:>8.1f} ns")
    print(f"  p95:  {lat.p95_us*1000:>8.1f} ns")
    print(f"  p99:  {lat.p99_us*1000:>8.1f} ns")
    print(f"  p99.9:{lat.p999_us*1000:>8.1f} ns")
    print(f"  max:  {lat.max_us*1000:>8.1f} ns")
    print(f"  std:  {lat.std_us*1000:>8.1f} ns")
    print()
    print(f"Violations detected: {violations}")
    
    if alarm_times:
        alarm_us = [ns / 1000.0 for ns in alarm_times]
        alarm_us.sort()
        print(f"Alarm response time: mean={statistics.mean(alarm_us):.1f}µs  p99={alarm_us[int(len(alarm_us)*0.99)]:.1f}µs")
    print()

    return result


if __name__ == "__main__":
    main()
