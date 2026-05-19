"""
Automotive: CAN Bus Signal Validation
Real system: CANedge / SavvyCAN validates CAN bus signals.
Tests FLUX constraint engine against automotive CAN bus constraints.
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

# CAN bus signal constraints
CAN_CONSTRAINTS = [
    ("engine_rpm", 0.0, 8000.0),
    ("vehicle_speed_kmh", 0.0, 300.0),
    ("coolant_temp_c", -40.0, 150.0),
    ("throttle_pct", 0.0, 100.0),
    ("brake_pressure_bar", 0.0, 200.0),
    ("steering_angle_deg", -720.0, 720.0),
    ("battery_voltage_v", 9.0, 16.0),
    ("fuel_level_pct", 0.0, 100.0),
]

N_VEHICLES = 100
CAN_HZ = 100  # 100 Hz per signal
SIGNALS = len(CAN_CONSTRAINTS)
TARGET_RATE = N_VEHICLES * SIGNALS * CAN_HZ  # 80,000/sec

# Simulate 10 seconds per vehicle for the benchmark
N_RECORDS = N_VEHICLES * 100  # 100 readings per vehicle


def generate_can_data(n: int) -> list:
    """Generate realistic CAN bus data with injected attack frames."""
    records = []
    for i in range(n):
        # Normal driving parameters
        rpm = max(0, random.gauss(2500, 800))
        speed = max(0, random.gauss(80, 30))
        coolant = random.gauss(90, 10)
        throttle = max(0, min(100, random.gauss(30, 15)))
        brake = max(0, random.gauss(10, 5))
        steering = random.gauss(0, 30)
        battery = random.gauss(13.5, 0.3)
        fuel = max(0, min(100, random.gauss(60, 15)))

        # CAN bus attack injection (0.3% of frames)
        if random.random() < 0.003:
            attack = random.choice(["rpm_spike", "speed_override", "brake_inject", "steering_hijack", "voltage_drop"])
            if attack == "rpm_spike":
                rpm = random.uniform(9000, 15000)  # Impossible RPM
            elif attack == "speed_override":
                speed = random.uniform(350, 500)    # Impossible speed
            elif attack == "brake_inject":
                brake = random.uniform(-50, -10)    # Negative pressure
            elif attack == "steering_hijack":
                steering = random.uniform(-900, -750)  # Beyond mechanical limit
            elif attack == "voltage_drop":
                battery = random.uniform(3, 7)      # Below minimum

        records.append({
            "engine_rpm": rpm,
            "vehicle_speed_kmh": speed,
            "coolant_temp_c": coolant,
            "throttle_pct": throttle,
            "brake_pressure_bar": brake,
            "steering_angle_deg": steering,
            "battery_voltage_v": battery,
            "fuel_level_pct": fuel,
        })
    return records


def test_can_basic():
    """Test basic CAN bus constraint checking."""
    scaled = [ScaledConstraint(name=n, lo_real=lo, hi_real=hi) for n, lo, hi in CAN_CONSTRAINTS]

    # Normal driving
    normal = {"engine_rpm": 2500, "vehicle_speed_kmh": 80, "coolant_temp_c": 90,
              "throttle_pct": 30, "brake_pressure_bar": 10, "steering_angle_deg": 0,
              "battery_voltage_v": 13.5, "fuel_level_pct": 60}
    for sc in scaled:
        flux_passed, naive = sc.check(normal[sc.name])
        assert naive, f"Normal CAN value flagged for {sc.name}"

    # Attack frame
    flux_passed, naive = scaled[0].check(12000.0)
    assert not naive, "RPM 12000 should fail"
    assert not flux_passed, "Attack RPM should fail FLUX"

    flux_passed, naive = scaled[6].check(5.0)
    assert not naive, "Battery 5V should fail"
    assert not flux_passed, "Voltage drop attack should fail FLUX"

    print("✓ CAN bus basic tests passed")


def test_can_benchmark():
    """Full benchmark: 100 vehicles × 8 signals × 100 Hz."""
    result = run_benchmark(
        domain="Automotive (CAN)",
        constraints=CAN_CONSTRAINTS,
        data_generator=generate_can_data,
        required_rate=float(TARGET_RATE),
        n_records=N_RECORDS,
    )

    print(f"\n{'='*60}")
    print(f"Automotive CAN Benchmark — {N_VEHICLES} vehicles × {SIGNALS} signals × {CAN_HZ}Hz")
    print(f"  Target: {TARGET_RATE:,} checks/sec sustained")
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
    test_can_basic()
    result = test_can_benchmark()
    print(f"\n✓ All CAN bus tests completed")
