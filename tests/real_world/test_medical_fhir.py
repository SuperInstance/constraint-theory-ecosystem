"""
Medical: HL7/FHIR Vital Signs Validation
Real system: OpenMRS / Mirth Connect validates FHIR Observation resources.
Tests FLUX constraint engine against patient vital signs constraints.
"""
import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python'))
from flux_scaling import ScaledConstraint, run_benchmark, BenchmarkResult

# FHIR vital signs constraints
FHIR_CONSTRAINTS = [
    ("heart_rate_bpm", 30.0, 220.0),
    ("spo2_pct", 70.0, 100.0),
    ("systolic_bp_mmhg", 60.0, 250.0),
    ("diastolic_bp_mmhg", 30.0, 150.0),
    ("temperature_c", 30.0, 45.0),
    ("respiratory_rate", 4.0, 60.0),
    ("ph", 6.8, 8.0),
    ("glucose_mgdl", 20.0, 600.0),
]

N_PATIENTS = 10000
OUTLIER_RATE = 0.01

# Realistic vital signs distributions (mean, stddev)
VITAL_DISTRIBUTIONS = {
    "heart_rate_bpm": (72, 12),
    "spo2_pct": (97, 2),
    "systolic_bp_mmhg": (120, 15),
    "diastolic_bp_mmhg": (80, 10),
    "temperature_c": (36.6, 0.4),
    "respiratory_rate": (16, 3),
    "ph": (7.4, 0.05),
    "glucose_mgdl": (100, 25),
}


def generate_patient_data(n: int) -> list:
    """Generate realistic patient vital signs with 1% outliers."""
    records = []
    for _ in range(n):
        record = {}
        for name, (mean, std) in VITAL_DISTRIBUTIONS.items():
            record[name] = random.gauss(mean, std)

        # Inject outlier in 1% of records
        if random.random() < OUTLIER_RATE:
            field = random.choice(list(VITAL_DISTRIBUTIONS.keys()))
            lo, hi = None, None
            for cname, clo, chi in FHIR_CONSTRAINTS:
                if cname == field:
                    lo, hi = clo, chi
                    break
            # Push outside bounds
            margin = (hi - lo) * 0.3
            if random.random() < 0.5:
                record[field] = lo - margin * random.uniform(0.5, 2.0)
            else:
                record[field] = hi + margin * random.uniform(0.5, 2.0)

        records.append(record)
    return records


def test_fhir_basic():
    """Test basic vital signs constraint checking."""
    scaled = [ScaledConstraint(name=n, lo_real=lo, hi_real=hi) for n, lo, hi in FHIR_CONSTRAINTS]

    # Normal patient
    normal = {
        "heart_rate_bpm": 72, "spo2_pct": 98, "systolic_bp_mmhg": 120,
        "diastolic_bp_mmhg": 80, "temperature_c": 36.6, "respiratory_rate": 16,
        "ph": 7.4, "glucose_mgdl": 100
    }
    for sc in scaled:
        flux_passed, naive = sc.check(normal[sc.name])
        assert naive, f"Normal value {normal[sc.name]} flagged for {sc.name}"

    # Critical patient
    critical = {
        "heart_rate_bpm": 250, "spo2_pct": 98, "systolic_bp_mmhg": 120,
        "diastolic_bp_mmhg": 80, "temperature_c": 36.6, "respiratory_rate": 16,
        "ph": 7.4, "glucose_mgdl": 100
    }
    flux_passed, naive = scaled[0].check(critical["heart_rate_bpm"])
    assert not naive, "HR=250 should fail"
    assert not flux_passed, "HR=250 should fail FLUX"

    print("✓ FHIR basic tests passed")


def test_fhir_benchmark():
    """Full benchmark: 10,000 patients, 1% outliers."""
    result = run_benchmark(
        domain="Medical (FHIR)",
        constraints=FHIR_CONSTRAINTS,
        data_generator=generate_patient_data,
        required_rate=500_000,  # Large hospital system
        n_records=N_PATIENTS,
    )

    print(f"\n{'='*60}")
    print(f"Medical FHIR Benchmark — {N_PATIENTS:,} patients, {OUTLIER_RATE*100}% outliers")
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
    test_fhir_basic()
    result = test_fhir_benchmark()
    print(f"\n✓ All FHIR tests completed")
