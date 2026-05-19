"""Shared benchmark framework for FLUX real-world scenarios."""
import time
import random
import math
import statistics
import os
import json
import resource
from dataclasses import dataclass, field
from typing import List, Tuple, Callable, Optional


@dataclass
class Constraint:
    """Range constraint: value must be in [lo, hi]."""
    lo: float
    hi: float
    tag: str

    def check(self, value: float) -> bool:
        return self.lo <= value <= self.hi


@dataclass
class LatencyStats:
    min_us: float
    max_us: float
    mean_us: float
    p50_us: float
    p95_us: float
    p99_us: float
    p999_us: float
    std_us: float

    def to_dict(self):
        return {k: round(v, 3) for k, v in self.__dict__.items()}


@dataclass
class BenchResult:
    scenario: str
    total_checks: int
    elapsed_sec: float
    throughput: float  # checks/sec
    headroom: float    # throughput / required_rate
    latency: LatencyStats
    memory_mb: float
    violations_injected: int
    violations_detected: int
    false_positives: int
    proof_overhead_pct: float = 0.0

    def to_dict(self):
        d = self.__dict__.copy()
        d['latency'] = self.latency.to_dict()
        return d


def measure_memory_mb() -> float:
    """Get current RSS in MB."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def compute_latency(latencies_ns: List[float]) -> LatencyStats:
    """Compute latency statistics from nanosecond samples."""
    if not latencies_ns:
        return LatencyStats(0, 0, 0, 0, 0, 0, 0, 0)
    us = [ns / 1000.0 for ns in latencies_ns]
    s = sorted(us)
    n = len(s)
    return LatencyStats(
        min_us=s[0],
        max_us=s[-1],
        mean_us=statistics.mean(us),
        p50_us=s[int(n * 0.50)],
        p95_us=s[int(n * 0.95)],
        p99_us=s[int(n * 0.99)],
        p999_us=s[min(int(n * 0.999), n - 1)],
        std_us=statistics.stdev(us) if n > 1 else 0.0,
    )


def generate_sensor_value(center: float, spread: float, noise_std: float = 0.0) -> float:
    """Generate a sensor reading with Gaussian noise."""
    base = center + random.gauss(0, noise_std) if noise_std > 0 else center
    return base + random.uniform(-spread, spread)


def inject_violation(constraint: Constraint, magnitude: float = 1.5) -> float:
    """Generate a value guaranteed to violate the constraint."""
    range_size = constraint.hi - constraint.lo
    if random.random() < 0.5:
        return constraint.lo - abs(range_size * magnitude * random.uniform(0.1, 0.5))
    else:
        return constraint.hi + abs(range_size * magnitude * random.uniform(0.1, 0.5))


def run_benchmark(
    scenario: str,
    constraints: List[Constraint],
    required_rate: float,
    duration_sec: float = 5.0,
    inject_rate: float = 0.01,
    batch_size: int = 1000,
) -> BenchResult:
    """Run a constraint checking benchmark.
    
    Args:
        scenario: Name of the benchmark scenario
        constraints: List of constraints to check
        required_rate: Required checks/sec
        duration_sec: How long to run the benchmark
        inject_rate: Fraction of values that are injected violations
        batch_size: Values per batch
    """
    mem_before = measure_memory_mb()
    
    total_checks = 0
    violations_injected = 0
    violations_detected = 0
    false_positives = 0
    latencies_ns = []
    
    n_constraints = len(constraints)
    checks_per_batch = batch_size * n_constraints
    
    start = time.perf_counter()
    batch_count = 0
    
    while True:
        elapsed = time.perf_counter() - start
        if elapsed >= duration_sec:
            break
        
        # Generate batch of values
        batch_start = time.perf_counter_ns()
        for _ in range(batch_size):
            for ci, constraint in enumerate(constraints):
                # Decide if this is a violation injection
                if random.random() < inject_rate:
                    value = inject_violation(constraint)
                    violations_injected += 1
                    should_fail = True
                else:
                    # Normal value within range
                    mid = (constraint.lo + constraint.hi) / 2
                    spread = (constraint.hi - constraint.lo) * 0.4
                    value = generate_sensor_value(mid, spread, noise_std=spread * 0.05)
                    should_fail = False
                
                t0 = time.perf_counter_ns()
                passed = constraint.check(value)
                t1 = time.perf_counter_ns()
                latencies_ns.append(t1 - t0)
                
                if not passed:
                    violations_detected += 1
                    if not should_fail:
                        false_positives += 1
                
                total_checks += 1
        
        batch_count += 1
    
    elapsed = time.perf_counter() - start
    mem_after = measure_memory_mb()
    
    # Downsample latencies if too many (keep 100k)
    if len(latencies_ns) > 100_000:
        step = len(latencies_ns) // 100_000
        latencies_ns = latencies_ns[::step]
    
    latency = compute_latency(latencies_ns)
    throughput = total_checks / elapsed if elapsed > 0 else 0
    headroom = throughput / required_rate if required_rate > 0 else float('inf')
    
    return BenchResult(
        scenario=scenario,
        total_checks=total_checks,
        elapsed_sec=elapsed,
        throughput=throughput,
        headroom=headroom,
        latency=latency,
        memory_mb=mem_after - mem_before,
        violations_injected=violations_injected,
        violations_detected=violations_detected,
        false_positives=false_positives,
    )


def format_result(r: BenchResult) -> str:
    lines = [
        f"## {r.scenario}",
        f"- Total checks: {r.total_checks:,}",
        f"- Elapsed: {r.elapsed_sec:.2f}s",
        f"- Throughput: {r.throughput:,.0f} checks/sec",
        f"- Headroom: {r.headroom:.1f}x",
        f"- Latency (ns): min={r.latency.min_us*1000:.1f}  mean={r.latency.mean_us*1000:.1f}  p99={r.latency.p99_us*1000:.1f}",
        f"- Memory delta: {r.memory_mb:.1f} MB",
        f"- Violations: injected={r.violations_injected}  detected={r.violations_detected}  false_pos={r.false_positives}",
    ]
    return "\n".join(lines)
