#!/usr/bin/env python3
"""Autonomous Vehicle Sensor Fusion benchmark.

50 sensors × 4 constraints each at 100Hz = 20,000 checks/sec sustained.
Sensors: LIDAR, radar, camera, GPS, IMU, wheel speed, brake pressure,
steering angle, battery, motor temp, etc.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from benchmark_framework import (
    Constraint, run_benchmark, format_result, measure_memory_mb, compute_latency
)
import random
import time


def automotive_sensors() -> list:
    """50 sensor types, each with 4 constraints (value range, rate-of-change, noise-floor, cross-check)."""
    sensor_defs = [
        ("lidar_range_m", 0.1, 200),
        ("lidar_intensity", 0, 255),
        ("lidar_return_count", 1, 1000),
        ("lidar_angular_rate_dps", -180, 180),
        ("radar_range_m", 0.5, 250),
        ("radar_velocity_ms", -80, 80),
        ("radar_azimuth_deg", -60, 60),
        ("radar_elevation_deg", -30, 30),
        ("camera_brightness", 0, 255),
        ("camera_contrast", 0, 100),
        ("camera_saturation", 0, 100),
        ("camera_framerate_fps", 10, 60),
        ("gps_lat_deg", -90, 90),
        ("gps_lon_deg", -180, 180),
        ("gps_alt_m", -100, 5000),
        ("gps_hdop", 0, 50),
        ("imu_accel_x_g", -4, 4),
        ("imu_accel_y_g", -4, 4),
        ("imu_accel_z_g", -4, 4),
        ("imu_gyro_x_dps", -500, 500),
        ("wheel_speed_fl_kph", 0, 200),
        ("wheel_speed_fr_kph", 0, 200),
        ("wheel_speed_rl_kph", 0, 200),
        ("wheel_speed_rr_kph", 0, 200),
        ("brake_pressure_bar", 0, 200),
        ("brake_temp_c", -20, 800),
        ("steering_angle_deg", -540, 540),
        ("steering_rate_dps", -360, 360),
        ("battery_voltage", 300, 420),
        ("battery_current_a", -200, 200),
        ("battery_temp_c", -20, 60),
        ("battery_soc_pct", 0, 100),
        ("motor_temp_c", -20, 180),
        ("motor_rpm", -15000, 15000),
        ("motor_torque_nm", -400, 400),
        ("inverter_temp_c", -20, 120),
        ("cabin_temp_c", 15, 35),
        ("ext_temp_c", -40, 55),
        ("tire_pressure_psi", 25, 45),
        ("suspension_travel_mm", -150, 150),
        ("ultrasonic_front_m", 0.1, 5),
        ("ultrasonic_rear_m", 0.1, 5),
        ("v2x_signal_dbm", -120, -20),
        ("v2x_latency_ms", 0, 100),
        ("can_bus_load_pct", 0, 100),
        ("compute_gpu_temp_c", 20, 95),
        ("compute_cpu_load_pct", 0, 100),
        ("compute_mem_load_pct", 0, 100),
        ("odometer_km", 0, 500000),
        ("fuel_cell_output_kw", 0, 120),
    ]
    
    constraints = []
    for name, lo, hi in sensor_defs:
        # Primary range constraint
        constraints.append(Constraint(lo, hi, f"{name}"))
        # Rate of change constraint (10% of range per cycle)
        rate = abs(hi - lo) * 0.1
        constraints.append(Constraint(-rate, rate, f"{name}_rate"))
        # Noise floor constraint (5% of range)
        noise = abs(hi - lo) * 0.05
        constraints.append(Constraint(-noise, noise, f"{name}_noise"))
        # Cross-check: value must be within 90% of range from center
        mid = (lo + hi) / 2
        half_range = abs(hi - lo) * 0.45
        constraints.append(Constraint(mid - half_range, mid + half_range, f"{name}_cross"))
    
    return constraints


def main():
    print("=" * 70)
    print("AUTONOMIVE VEHICLE SENSOR FUSION BENCHMARK")
    print("50 sensors × 4 constraints × 100Hz = 20,000 checks/sec")
    print("=" * 70)

    constraints = automotive_sensors()
    print(f"Total constraints: {len(constraints)}")

    required_rate = 50 * 4 * 100  # 20,000 checks/sec

    result = run_benchmark(
        scenario="AV Sensor Fusion",
        constraints=constraints,
        required_rate=required_rate,
        duration_sec=5.0,
        inject_rate=0.005,
        batch_size=200,
    )

    print(format_result(result))
    print()

    # Sustained throughput test
    print("--- Sustained throughput test (20,000 checks/sec target) ---")
    latencies = []
    total = 0
    violations = 0
    t_start = time.perf_counter()
    
    # Run for 3 seconds, checking at 100Hz rate
    cycles_per_sec = 100
    checks_per_cycle = 50 * 4  # 200
    
    for sec in range(3):
        for cycle in range(cycles_per_sec):
            for ci in range(checks_per_cycle):
                c = constraints[ci % len(constraints)]
                mid = (c.lo + c.hi) / 2
                spread = (c.hi - c.lo) * 0.3
                value = mid + random.gauss(0, spread)
                
                t0 = time.perf_counter_ns()
                passed = c.check(value)
                t1 = time.perf_counter_ns()
                latencies.append(t1 - t0)
                if not passed:
                    violations += 1
                total += 1
    
    elapsed = time.perf_counter() - t_start
    lat = compute_latency(latencies)
    actual_rate = total / elapsed
    print(f"Checks: {total:,} in {elapsed:.2f}s = {actual_rate:,.0f}/sec")
    print(f"Required: 20,000/sec  Headroom: {actual_rate/20000:.1f}x")
    print(f"Latency: mean={lat.mean_us*1000:.1f}ns  p99={lat.p99_us*1000:.1f}ns  max={lat.max_us*1000:.1f}ns")
    print(f"Violations: {violations}")
    print()

    return result


if __name__ == "__main__":
    main()
