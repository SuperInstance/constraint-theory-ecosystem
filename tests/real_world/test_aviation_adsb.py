"""
Aviation: ADS-B Receiver Validation
Real system: dump1090 validates aircraft position data.
Tests FLUX constraint engine against aircraft telemetry constraints.
"""
import sys
import os
import random
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python'))
from flux_scaling import ScaledConstraint, run_benchmark, BenchmarkResult

# ADS-B constraints (real-world ranges)
ADS_B_CONSTRAINTS = [
    ("latitude", -90.0, 90.0),
    ("longitude", -180.0, 180.0),
    ("altitude_ft", -1000.0, 60000.0),
    ("ground_speed_kt", 0.0, 600.0),
    ("vertical_rate_fpm", -6400.0, 6400.0),
]

N_AIRCRAFT = 1000
ANOMALY_RATE = 0.05


def generate_aircraft_data(n: int) -> list:
    """Generate realistic aircraft position data with 5% anomalies."""
    records = []
    for _ in range(n):
        # Normal flight parameters (Gaussian around typical values)
        lat = random.gauss(40.0, 15.0)       # Most traffic in mid-latitudes
        lon = random.gauss(-90.0, 30.0)      # US/Europe centered
        alt = random.gauss(35000, 8000)      # Cruise altitude
        spd = random.gauss(450, 80)          # Typical jet speed
        vr = random.gauss(0, 500)            # Level flight usually

        # Inject anomalies
        if random.random() < ANOMALY_RATE:
            field = random.choice(["latitude", "longitude", "altitude_ft", "ground_speed_kt", "vertical_rate_fpm"])
            if field == "latitude":
                lat = random.choice([random.uniform(-200, -100), random.uniform(100, 200)])
            elif field == "longitude":
                lon = random.choice([random.uniform(-400, -200), random.uniform(200, 400)])
            elif field == "altitude_ft":
                alt = random.choice([random.uniform(-5000, -2000), random.uniform(70000, 100000)])
            elif field == "ground_speed_kt":
                spd = random.choice([random.uniform(-200, -50), random.uniform(800, 1200)])
            elif field == "vertical_rate_fpm":
                vr = random.choice([random.uniform(-10000, -7000), random.uniform(7000, 12000)])

        records.append({
            "latitude": lat,
            "longitude": lon,
            "altitude_ft": alt,
            "ground_speed_kt": spd,
            "vertical_rate_fpm": vr,
        })
    return records


def test_adsb_basic():
    """Test basic ADS-B constraint checking."""
    scaled = [ScaledConstraint(name=n, lo_real=lo, hi_real=hi) for n, lo, hi in ADS_B_CONSTRAINTS]

    # Valid aircraft
    valid = {"latitude": 40.7, "longitude": -74.0, "altitude_ft": 35000, "ground_speed_kt": 450, "vertical_rate_fpm": 100}
    for sc in scaled:
        flux_passed, naive = sc.check(valid[sc.name])
        assert naive, f"Valid value {valid[sc.name]} flagged by naive check for {sc.name}"
        # FLUX might have FP due to quantization — we track this in benchmark

    # Anomalous aircraft
    anomalous = {"latitude": 200.0, "longitude": -74.0, "altitude_ft": 35000, "ground_speed_kt": 450, "vertical_rate_fpm": 100}
    for sc in scaled:
        flux_passed, naive = sc.check(anomalous[sc.name])
        if sc.name == "latitude":
            assert not naive, "Lat=200 should fail naive check"
            assert not flux_passed, "Lat=200 should fail FLUX check"

    print("✓ ADS-B basic tests passed")


def test_adsb_benchmark():
    """Full benchmark: 1000 aircraft, 5% anomalies."""
    result = run_benchmark(
        domain="Aviation (ADS-B)",
        constraints=ADS_B_CONSTRAINTS,
        data_generator=generate_aircraft_data,
        required_rate=1_000_000,  # ~1M checks/sec needed for real-time ADS-B
        n_records=N_AIRCRAFT,
    )

    print(f"\n{'='*60}")
    print(f"Aviation ADS-B Benchmark — {N_AIRCRAFT} aircraft, {ANOMALY_RATE*100}% anomalies")
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
    print(f"  True violations:  {result.total_violations_true}")
    print(f"  Detected:         {result.total_violations_detected}")

    return result


if __name__ == "__main__":
    random.seed(42)
    test_adsb_basic()
    result = test_adsb_benchmark()
    print(f"\n✓ All ADS-B tests completed")
