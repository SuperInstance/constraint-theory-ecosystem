#!/usr/bin/env python3
"""Nuclear Reactor Safety System benchmark.

200 sensors × 8 constraints each at 1000Hz = 1,600,000 checks/sec.
Measures WCET, determinism, proof certificate overhead.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from benchmark_framework import (
    Constraint, run_benchmark, format_result, measure_memory_mb, compute_latency
)
import random
import time


def reactor_constraints() -> list:
    """200 reactor sensors, 8 constraints each (value + severity levels)."""
    sensor_defs = [
        # Primary loop (50 sensors)
        ("neutron_flux_%", 0, 120),         # % of rated power
        ("neutron_rate_%s", -10, 10),        # %/sec rate of change
        ("coolant_temp_inlet_C", 270, 295),  # pressurized water reactor
        ("coolant_temp_outlet_C", 290, 330),
        ("coolant_pressure_MPa", 14.5, 16.5),
        ("coolant_flow_kg_s", 4000, 18000),
        ("pressurizer_level_pct", 20, 80),
        ("pressurizer_pressure_MPa", 14.5, 16.5),
        # Steam system (50 sensors)
        ("steam_pressure_MPa", 5.0, 7.5),
        ("steam_flow_kg_s", 500, 3000),
        ("steam_temp_C", 250, 290),
        ("feedwater_temp_C", 200, 240),
        ("feedwater_flow_kg_s", 500, 3000),
        ("condenser_pressure_kPa", 3, 15),
        ("condenser_temp_C", 30, 55),
        # Safety systems (50 sensors)
        ("safety_injection_pressure_MPa", 0, 16),
        ("safety_injection_flow_kg_s", 0, 500),
        ("containment_pressure_kPa", 100, 500),
        ("containment_temp_C", 20, 120),
        ("containment_h2_pct", 0, 4),
        ("rcs_leak_rate_kg_s", 0, 50),
        # Turbine (50 sensors)
        ("turbine_rpm", 1400, 1900),
        ("turbine_vibration_mm_s", 0, 12),
        ("turbine_bearing_temp_C", 40, 120),
        ("generator_mw", 0, 1200),
        ("generator_voltage_kv", 20, 28),
        ("generator_freq_hz", 49, 51),
        ("transformer_temp_C", 30, 90),
    ]
    
    constraints = []
    for i in range(200):
        base = sensor_defs[i % len(sensor_defs)]
        name = f"{base[0]}_{i}"
        lo, hi = base[1], base[2]
        
        # 8 constraint levels per sensor (escalating severity)
        range_size = hi - lo
        # Normal operating (green)
        constraints.append(Constraint(lo, hi, f"{name}_green"))
        # Warning (yellow) - 10% wider
        margin = range_size * 0.1
        constraints.append(Constraint(lo - margin, hi + margin, f"{name}_yellow"))
        # Alert (orange) - 20% wider
        margin = range_size * 0.2
        constraints.append(Constraint(lo - margin, hi + margin, f"{name}_orange"))
        # Critical (red) - 30% wider
        margin = range_size * 0.3
        constraints.append(Constraint(lo - margin, hi + margin, f"{name}_red"))
        # Rate of change (normal)
        rate = range_size * 0.02
        constraints.append(Constraint(-rate, rate, f"{name}_rate_normal"))
        # Rate of change (emergency)
        rate = range_size * 0.1
        constraints.append(Constraint(-rate, rate, f"{name}_rate_emergency"))
        # Deadband check
        constraints.append(Constraint(lo, hi, f"{name}_deadband"))
        # Out-of-range hard limit
        constraints.append(Constraint(lo - range_size, hi + range_size, f"{name}_hard_limit"))
    
    return constraints


def main():
    print("=" * 70)
    print("NUCLEAR REACTOR SAFETY SYSTEM BENCHMARK")
    print("200 sensors × 8 constraints × 1000Hz = 1,600,000 checks/sec")
    print("=" * 70)

    constraints = reactor_constraints()
    print(f"Total constraints: {len(constraints)}")

    required_rate = 200 * 8 * 1000  # 1.6M/sec

    result = run_benchmark(
        scenario="Nuclear Reactor Safety",
        constraints=constraints,
        required_rate=required_rate,
        duration_sec=5.0,
        inject_rate=0.002,
        batch_size=5000,
    )

    print(format_result(result))
    print()

    # WCET measurement — worst-case single check
    print("--- WCET (Worst-Case Execution Time) measurement ---")
    worst_ns = 0
    best_ns = float('inf')
    latencies = []
    
    for _ in range(1_000_000):
        c = constraints[random.randint(0, len(constraints) - 1)]
        mid = (c.lo + c.hi) / 2
        spread = (c.hi - c.lo) * 0.3
        value = mid + random.gauss(0, spread)
        
        t0 = time.perf_counter_ns()
        passed = c.check(value)
        t1 = time.perf_counter_ns()
        dt = t1 - t0
        latencies.append(dt)
        if dt > worst_ns:
            worst_ns = dt
        if dt < best_ns:
            best_ns = dt
    
    lat = compute_latency(latencies)
    print(f"WCET: {worst_ns} ns")
    print(f"Best: {best_ns} ns")
    print(f"Mean: {lat.mean_us*1000:.1f} ns  p99: {lat.p99_us*1000:.1f} ns")
    print(f"Determinism ratio (WCET/mean): {worst_ns / (lat.mean_us*1000):.1f}x")
    print()

    # Proof overhead estimation (hashing simulation)
    print("--- Proof Certificate Overhead ---")
    import hashlib
    t_start = time.perf_counter()
    proofs = 0
    for _ in range(100_000):
        c = constraints[random.randint(0, len(constraints) - 1)]
        mid = (c.lo + c.hi) / 2
        value = mid + random.gauss(0, (c.hi - c.lo) * 0.3)
        passed = c.check(value)
        # Simulate proof: hash(value || lo || hi || result)
        data = f"{value}:{c.lo}:{c.hi}:{passed}".encode()
        hashlib.sha256(data).digest()
        proofs += 1
    elapsed_proof = time.perf_counter() - t_start
    
    # Same without proof
    t_start = time.perf_counter()
    for _ in range(100_000):
        c = constraints[random.randint(0, len(constraints) - 1)]
        mid = (c.lo + c.hi) / 2
        value = mid + random.gauss(0, (c.hi - c.lo) * 0.3)
        c.check(value)
    elapsed_noproof = time.perf_counter() - t_start
    
    overhead_pct = ((elapsed_proof - elapsed_noproof) / elapsed_noproof) * 100
    print(f"With proof:    {elapsed_proof:.3f}s ({proofs/elapsed_proof:.0f}/sec)")
    print(f"Without proof: {elapsed_noproof:.3f}s ({100000/elapsed_noproof:.0f}/sec)")
    print(f"Overhead: {overhead_pct:.1f}%")
    print()

    result.proof_overhead_pct = overhead_pct
    return result


if __name__ == "__main__":
    main()
