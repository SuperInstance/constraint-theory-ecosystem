"""
Energy: SCADA System Validation
Real system: OpenPDC / PI System validates power grid measurements.
Tests FLUX constraint engine against power grid telemetry.
"""
import sys
import os
import sys
import random
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python'))
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flux_scaling import ScaledConstraint, run_benchmark, BenchmarkResult

# SCADA constraints (tight tolerances!)
SCADA_CONSTRAINTS = [
    ("voltage_pu", 0.95, 1.05),       # Per unit — very tight range!
    ("frequency_hz", 59.95, 60.05),    # ±0.05 Hz — extremely tight
    ("active_power_mw", 0.0, 1000.0),
    ("reactive_power_mvar", -500.0, 500.0),
    ("current_a", 0.0, 5000.0),
    ("temperature_c", -40.0, 150.0),
]

N_GRID_POINTS = 50000
SIM_HZ = 60  # 60 Hz sampling
TARGET_RATE = 50_000 * 6 * 60  # 18M checks/sec


def generate_scada_data(n: int) -> list:
    """Generate realistic power grid data at 60Hz."""
    records = []
    for _ in range(n):
        # Nominal values with small noise (power grid is very stable)
        voltage = random.gauss(1.0, 0.005)    # ±0.5% noise
        freq = random.gauss(60.0, 0.003)      # ±0.003 Hz noise
        active = random.gauss(500, 100)        # Load varies
        reactive = random.gauss(0, 50)         # Near unity PF
        current = random.gauss(2500, 300)
        temp = random.gauss(45, 10)

        # Occasional grid events (0.5%)
        if random.random() < 0.005:
            event = random.choice(["voltage_sag", "frequency_excursion", "overload", "fault"])
            if event == "voltage_sag":
                voltage = random.uniform(0.8, 0.94)
            elif event == "frequency_excursion":
                freq = random.choice([59.80, 60.20, 59.85, 60.15])
            elif event == "overload":
                active = random.uniform(1100, 1500)
            elif event == "fault":
                current = random.uniform(6000, 10000)

        records.append({
            "voltage_pu": voltage,
            "frequency_hz": freq,
            "active_power_mw": active,
            "reactive_power_mvar": reactive,
            "current_a": current,
            "temperature_c": temp,
        })
    return records


def test_scada_basic():
    """Test basic SCADA constraint checking."""
    scaled = [ScaledConstraint(name=n, lo_real=lo, hi_real=hi) for n, lo, hi in SCADA_CONSTRAINTS]

    # Normal grid state
    normal = {"voltage_pu": 1.0, "frequency_hz": 60.0, "active_power_mw": 500,
              "reactive_power_mvar": 0, "current_a": 2500, "temperature_c": 45}
    for sc in scaled:
        flux_passed, naive = sc.check(normal[sc.name])
        assert naive, f"Normal grid value flagged for {sc.name}"

    # Voltage sag
    flux_passed, naive = scaled[0].check(0.85)
    assert not naive, "Voltage 0.85 pu should fail"
    assert not flux_passed, "Voltage sag should fail FLUX"

    # Frequency excursion
    flux_passed, naive = scaled[1].check(59.80)
    assert not naive, "Freq 59.80 should fail"
    assert not flux_passed, "Freq excursion should fail FLUX"

    print("✓ SCADA basic tests passed")


def test_scada_benchmark():
    """Full benchmark: 50,000 grid points × 6 measurements × 60 Hz."""
    result = run_benchmark(
        domain="Energy (SCADA)",
        constraints=SCADA_CONSTRAINTS,
        data_generator=generate_scada_data,
        required_rate=float(TARGET_RATE),
        n_records=N_GRID_POINTS,
    )

    print(f"\n{'='*60}")
    print(f"Energy SCADA Benchmark — {N_GRID_POINTS:,} grid points")
    print(f"  Target: {N_GRID_POINTS} × 6 × {SIM_HZ}Hz = {TARGET_RATE/1e6:.0f}M checks/sec")
    print(f"{'='*60}")
    print(f"  Total checks:    {result.total_checks:,}")
    print(f"  FLUX throughput:  {result.flux_throughput:,.0f} checks/sec")
    print(f"  Naive throughput: {result.naive_throughput:,.0f} checks/sec")
    print(f"  Headroom:         {result.headroom:.1f}x required rate")
    print(f"  p50 latency:      {result.p50_latency_us:.2f} μs")
    print(f"  p95 latency:      {result.p95_latency_us:.2f} μs")
    print(f"  p99 latency:      {result.p99_latency_us:.2f} μs")
    print(f"  False positives:  {result.false_positives} ({result.false_positive_rate:.4%})")
    print(f"  False negatives:  {result.false_negatives} ({result.false_negative_rate:.4%})")
    print(f"  Accuracy:         {result.accuracy:.4%}")

    return result


if __name__ == "__main__":
    random.seed(42)
    test_scada_basic()
    result = test_scada_benchmark()
    print(f"\n✓ All SCADA tests completed")
