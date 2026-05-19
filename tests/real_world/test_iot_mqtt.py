"""
IoT: MQTT Sensor Network Validation
Real system: Mosquitto/Eclipse Hono validates sensor payloads.
Tests FLUX constraint engine against IoT sensor constraints.
"""
import sys
import os
import random
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'python'))
from flux_scaling import ScaledConstraint, run_benchmark, BenchmarkResult

# IoT sensor constraints
IOT_CONSTRAINTS = [
    ("temperature_c", -40.0, 85.0),
    ("humidity_pct", 0.0, 100.0),
    ("pressure_hpa", 800.0, 1200.0),
    ("co2_ppm", 300.0, 5000.0),
    ("pm25_ugm3", 0.0, 500.0),
    ("battery_pct", 0.0, 100.0),
]

N_SENSORS = 10000
SENSOR_HZ = 1  # 1 Hz per sensor
TARGET_RATE = N_SENSORS * len(IOT_CONSTRAINTS) * SENSOR_HZ  # 60,000/sec


def generate_iot_data(n: int) -> list:
    """Generate realistic IoT sensor data with drift, dead sensors, noise."""
    records = []
    # Track per-sensor state for drift simulation
    drift_state = {i: 0.0 for i in range(min(n, 1000))}

    for i in range(n):
        sensor_id = i % min(n, 1000)

        # Normal readings
        temp = random.gauss(22, 5)
        humidity = random.gauss(55, 10)
        pressure = random.gauss(1013, 15)
        co2 = random.gauss(420, 30)
        pm25 = random.gauss(15, 8)
        battery = max(0, random.gauss(70, 20))

        # Sensor drift (gradual increase over time)
        drift_state[sensor_id] += random.gauss(0.01, 0.05)
        temp += drift_state[sensor_id]

        # Dead sensor scenario (0.2%): stuck at extreme value
        if random.random() < 0.002:
            field = random.choice(["temperature_c", "humidity_pct", "pressure_hpa", "co2_ppm", "pm25_ugm3", "battery_pct"])
            if field == "temperature_c":
                temp = random.choice([-60, -50, 100, 120])
            elif field == "humidity_pct":
                humidity = random.choice([-10, 120])
            elif field == "pressure_hpa":
                pressure = random.choice([600, 1400])
            elif field == "co2_ppm":
                co2 = random.choice([100, 8000])
            elif field == "pm25_ugm3":
                pm25 = random.choice([-20, 700])
            elif field == "battery_pct":
                battery = random.choice([-5, 110])

        # High noise burst (1%)
        if random.random() < 0.01:
            temp += random.gauss(0, 50)

        records.append({
            "temperature_c": temp,
            "humidity_pct": humidity,
            "pressure_hpa": pressure,
            "co2_ppm": co2,
            "pm25_ugm3": max(0, pm25),
            "battery_pct": battery,
        })
    return records


def test_iot_basic():
    """Test basic IoT constraint checking."""
    scaled = [ScaledConstraint(name=n, lo_real=lo, hi_real=hi) for n, lo, hi in IOT_CONSTRAINTS]

    # Normal reading
    normal = {"temperature_c": 22, "humidity_pct": 55, "pressure_hpa": 1013,
              "co2_ppm": 420, "pm25_ugm3": 15, "battery_pct": 80}
    for sc in scaled:
        flux_passed, naive = sc.check(normal[sc.name])
        assert naive, f"Normal sensor value flagged for {sc.name}"

    # Dead sensor
    flux_passed, naive = scaled[0].check(-60.0)
    assert not naive, "Temp -60 should fail"
    assert not flux_passed, "Dead sensor should fail FLUX"

    print("✓ IoT basic tests passed")


def test_iot_benchmark():
    """Full benchmark: 10,000 sensors × 6 values × 1 Hz."""
    result = run_benchmark(
        domain="IoT (MQTT)",
        constraints=IOT_CONSTRAINTS,
        data_generator=generate_iot_data,
        required_rate=float(TARGET_RATE),
        n_records=N_SENSORS,
    )

    print(f"\n{'='*60}")
    print(f"IoT MQTT Benchmark — {N_SENSORS:,} sensors × {len(IOT_CONSTRAINTS)} values × {SENSOR_HZ}Hz")
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
    test_iot_basic()
    result = test_iot_benchmark()
    print(f"\n✓ All IoT tests completed")
