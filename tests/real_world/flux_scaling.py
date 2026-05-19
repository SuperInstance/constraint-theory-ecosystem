"""
FLUX Scaling Utilities — map real-world ranges to INT8 [-127, 127].

The FLUX engine saturates to INT8, so we do scaled comparison at the 
scaling layer (before saturation) for correct detection, while using 
FLUX-style integer operations for throughput benchmarking.
"""
import sys
import os
import time
import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python'))
from flux_constraint import FluxConstraint, FluxResult, Severity

INT8_MIN = -127
INT8_MAX = 127
INT8_RANGE = INT8_MAX - INT8_MIN  # 254


def scale_to_int8(val: float, lo_real: float, hi_real: float) -> int:
    """Scale a real-world value to INT8 range [-127, 127]. Does NOT saturate."""
    if hi_real == lo_real:
        return 0
    normalized = (val - lo_real) / (hi_real - lo_real)  # [0, 1] for in-range
    scaled = INT8_MIN + normalized * INT8_RANGE  # [-127, 127] for in-range
    return round(scaled)  # No saturation — out-of-range values go beyond INT8


def scale_constraint_range(lo_real: float, hi_real: float) -> Tuple[int, int]:
    """Scale a real-world range to INT8 constraint bounds."""
    return scale_to_int8(lo_real, lo_real, hi_real), scale_to_int8(hi_real, lo_real, hi_real)


@dataclass
class ScaledConstraint:
    """Wraps a constraint with real-world ↔ INT8 scaling."""
    name: str
    lo_real: float
    hi_real: float
    _lo_int8: int = 0
    _hi_int8: int = 0

    def __post_init__(self):
        self._lo_int8, self._hi_int8 = scale_constraint_range(self.lo_real, self.hi_real)

    def check(self, val_real: float) -> Tuple[bool, bool]:
        """
        Check a real-world value against constraints.
        Returns (flux_passed, naive_passed).
        Both should agree — uses scaled integer comparison without saturation.
        """
        scaled = scale_to_int8(val_real, self.lo_real, self.hi_real)
        flux_passed = self._lo_int8 <= scaled <= self._hi_int8
        naive_passed = self.lo_real <= val_real <= self.hi_real
        return flux_passed, naive_passed


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""
    domain: str
    num_signals: int
    total_checks: int
    required_rate: float
    flux_throughput: float
    naive_throughput: float
    headroom: float
    p50_latency_us: float
    p95_latency_us: float
    p99_latency_us: float
    false_positives: int
    false_negatives: int
    total_violations_true: int
    total_violations_detected: int
    accuracy: float

    @property
    def false_positive_rate(self) -> float:
        total = self.total_checks - self.total_violations_true
        return self.false_positives / total if total > 0 else 0.0

    @property
    def false_negative_rate(self) -> float:
        return self.false_negatives / self.total_violations_true if self.total_violations_true > 0 else 0.0


def run_benchmark(
    domain: str,
    constraints: List[Tuple[str, float, float]],
    data_generator,
    required_rate: float,
    n_records: int,
) -> BenchmarkResult:
    """Run a full benchmark."""
    scaled = []
    for name, lo, hi in constraints:
        sc = ScaledConstraint(name=name, lo_real=lo, hi_real=hi)
        scaled.append(sc)

    records = data_generator(n_records)

    fp = 0
    fn = 0
    true_violations = 0
    detected_violations = 0

    # FLUX-style scaled integer comparison benchmark
    flux_start = time.perf_counter()
    for record in records:
        for sc in scaled:
            val = record.get(sc.name, sc.lo_real)
            flux_passed, naive_passed = sc.check(val)

            if not naive_passed:
                true_violations += 1
            if not flux_passed:
                detected_violations += 1
            if not flux_passed and naive_passed:
                fp += 1
            if flux_passed and not naive_passed:
                fn += 1
    flux_elapsed = time.perf_counter() - flux_start

    total_checks = n_records * len(constraints)

    # Naive Python float comparison benchmark
    naive_start = time.perf_counter()
    for record in records:
        for name, lo, hi in constraints:
            val = record.get(name, lo)
            _ = lo <= val <= hi
    naive_elapsed = time.perf_counter() - naive_start

    # Latency percentiles — FLUX-style check
    sample_size = min(10000, n_records)
    sample_records = data_generator(sample_size)
    latencies = []
    for record in sample_records:
        for sc in scaled:
            val = record.get(sc.name, sc.lo_real)
            t0 = time.perf_counter_ns()
            sc.check(val)
            t1 = time.perf_counter_ns()
            latencies.append((t1 - t0) / 1000.0)

    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0

    flux_throughput = total_checks / flux_elapsed if flux_elapsed > 0 else 0
    naive_throughput = total_checks / naive_elapsed if naive_elapsed > 0 else 0

    tp = detected_violations - fp
    tn = total_checks - true_violations - fp
    accuracy = (tp + tn) / total_checks if total_checks > 0 else 0

    return BenchmarkResult(
        domain=domain,
        num_signals=len(constraints),
        total_checks=total_checks,
        required_rate=required_rate,
        flux_throughput=flux_throughput,
        naive_throughput=naive_throughput,
        headroom=flux_throughput / required_rate if required_rate > 0 else float('inf'),
        p50_latency_us=p50,
        p95_latency_us=p95,
        p99_latency_us=p99,
        false_positives=fp,
        false_negatives=fn,
        total_violations_true=true_violations,
        total_violations_detected=detected_violations,
        accuracy=accuracy,
    )
