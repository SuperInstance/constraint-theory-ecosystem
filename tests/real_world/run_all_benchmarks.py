#!/usr/bin/env python3
"""
Run all 6 real-world FLUX constraint engine benchmarks.
"""
import sys
import os
import time
import random

base = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.join(base, 'src', 'python'))
sys.path.insert(0, base)

from tests.real_world.flux_scaling import BenchmarkResult

# Import all test modules
from tests.real_world.test_aviation_adsb import test_adsb_basic, test_adsb_benchmark
from tests.real_world.test_medical_fhir import test_fhir_basic, test_fhir_benchmark
from tests.real_world.test_financial_fix import test_fix_basic, test_fix_benchmark
from tests.real_world.test_energy_scada import test_scada_basic, test_scada_benchmark
from tests.real_world.test_iot_mqtt import test_iot_basic, test_iot_benchmark
from tests.real_world.test_automotive_can import test_can_basic, test_can_benchmark


def main():
    random.seed(42)

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  FLUX Constraint Engine — Real-World Application Benchmarks ║")
    print("╚══════════════════════════════════════════════════════════════╝\n")

    results = []

    suites = [
        ("Aviation (ADS-B)", test_adsb_basic, test_adsb_benchmark),
        ("Medical (FHIR)", test_fhir_basic, test_fhir_benchmark),
        ("Financial (FIX)", test_fix_basic, test_fix_benchmark),
        ("Energy (SCADA)", test_scada_basic, test_scada_benchmark),
        ("IoT (MQTT)", test_iot_basic, test_iot_benchmark),
        ("Automotive (CAN)", test_can_basic, test_can_benchmark),
    ]

    for name, basic_fn, bench_fn in suites:
        print(f"\n{'#'*60}")
        print(f"# {name}")
        print(f"{'#'*60}")
        try:
            basic_fn()
            result = bench_fn()
            results.append(result)
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            import traceback
            traceback.print_exc()

    # Summary
    print(f"\n\n{'='*80}")
    print(f"  SUMMARY — FLUX Real-World Benchmark Results")
    print(f"{'='*80}\n")

    if not results:
        print("  No results to report.")
        return

    # Table header
    print(f"  {'Domain':<20} {'Signals':>7} {'Required':>14} {'Throughput':>14} {'Headroom':>9} {'p99(μs)':>9} {'FP Rate':>9} {'FN Rate':>9}")
    print(f"  {'-'*20} {'-'*7} {'-'*14} {'-'*14} {'-'*9} {'-'*9} {'-'*9} {'-'*9}")

    for r in results:
        req_str = f"{r.required_rate:,.0f}" if r.required_rate < 1e9 else f"{r.required_rate/1e6:.0f}M"
        thru_str = f"{r.flux_throughput:,.0f}" if r.flux_throughput < 1e9 else f"{r.flux_throughput/1e6:.1f}M"
        print(f"  {r.domain:<20} {r.num_signals:>7} {req_str:>14} {thru_str:>14} {r.headroom:>8.1f}x {r.p99_latency_us:>8.2f} {r.false_positive_rate:>8.4%} {r.false_negative_rate:>8.4%}")

    # Write markdown report
    md_path = os.path.join(os.path.dirname(__file__), '..', '..', 'benchmarks', 'REAL_WORLD_RESULTS.md')
    os.makedirs(os.path.dirname(md_path), exist_ok=True)

    with open(md_path, 'w') as f:
        f.write("# FLUX Constraint Engine — Real-World Application Benchmarks\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Test Environments\n\n")
        f.write("Each test ports a real-world constraint checking pattern to the FLUX polylanguage system.\n")
        f.write("FLUX uses INT8 saturated arithmetic [-127, 127] with automatic scaling from real-world ranges.\n\n")

        f.write("## Summary Table\n\n")
        f.write("| Domain | Signals | Required Rate | FLUX Throughput | Headroom | p99 Latency | False Positive Rate | False Negative Rate |\n")
        f.write("|--------|---------|---------------|-----------------|----------|-------------|--------------------|--------------------|\n")
        for r in results:
            f.write(f"| {r.domain} | {r.num_signals} | {r.required_rate:,.0f}/s | {r.flux_throughput:,.0f}/s | {r.headroom:.1f}x | {r.p99_latency_us:.2f} μs | {r.false_positive_rate:.4%} | {r.false_negative_rate:.4%} |\n")

        f.write("\n## Detailed Results\n\n")
        for r in results:
            f.write(f"### {r.domain}\n\n")
            f.write(f"- **Total checks:** {r.total_checks:,}\n")
            f.write(f"- **FLUX throughput:** {r.flux_throughput:,.0f} checks/sec\n")
            f.write(f"- **Naive throughput:** {r.naive_throughput:,.0f} checks/sec\n")
            f.write(f"- **Headroom:** {r.headroom:.1f}x required rate\n")
            f.write(f"- **p50 latency:** {r.p50_latency_us:.2f} μs\n")
            f.write(f"- **p95 latency:** {r.p95_latency_us:.2f} μs\n")
            f.write(f"- **p99 latency:** {r.p99_latency_us:.2f} μs\n")
            f.write(f"- **False positives:** {r.false_positives} ({r.false_positive_rate:.4%})\n")
            f.write(f"- **False negatives:** {r.false_negatives} ({r.false_negative_rate:.4%})\n")
            f.write(f"- **Accuracy:** {r.accuracy:.4%}\n")
            f.write(f"- **True violations:** {r.total_violations_true}\n")
            f.write(f"- **Detected violations:** {r.total_violations_detected}\n\n")

        f.write("## Methodology\n\n")
        f.write("1. **Scaling:** Real-world ranges mapped to INT8 [-127, 127] via linear interpolation\n")
        f.write("2. **Data generation:** Gaussian distributions centered on typical operating points\n")
        f.write("3. **Anomaly injection:** Percentage-based injection of out-of-range values\n")
        f.write("4. **Comparison:** FLUX results compared against naive `lo <= val <= hi` Python checks\n")
        f.write("5. **Latency:** Measured via `perf_counter_ns()` with percentile reporting\n")
        f.write("6. **Throughput:** Total checks / wall-clock time for the full batch\n")
        f.write("7. **Accuracy:** (TP + TN) / total, where ground truth is naive Python range check\n\n")

        f.write("## Notes\n\n")
        f.write("- FLUX INT8 quantization introduces quantization error near constraint boundaries\n")
        f.write("- False positives occur when a real value barely passes but quantizes to a failing INT8 value\n")
        f.write("- False negatives occur when a real value barely fails but quantizes to a passing INT8 value\n")
        f.write("- The SCADA frequency constraint (59.95-60.05 Hz) is the most challenging for INT8 quantization\n")
        f.write("- Throughput numbers are single-threaded Python; production Rust/C implementations would be 10-100x faster\n")

    print(f"\n  Results written to: {md_path}")
    print(f"\n{'='*80}")
    print(f"  All benchmarks complete. {len(results)}/{len(suites)} suites passed.")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
