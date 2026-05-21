# Tutorial 3: Use the 248-Constraint Industry Library

**Time:** 5 minutes  
**What you'll learn:** Load and use pre-built constraint sets for real industries.

---

## What's in the Library

The `constraints/` directory contains 248 verified constraints across 10 industries:

| Industry | File | Constraints | Standard |
|----------|------|------------|----------|
| Aerospace | `constraints/aviation.md` | 25 | DO-254 |
| Automotive | `constraints/automotive.md` | 28 | ISO 26262 |
| Medical | `constraints/medical.md` | 22 | IEC 62304 |
| Nuclear | `constraints/nuclear.md` | 30 | IEC 61508 |
| Railway | `constraints/railway.md` | 18 | EN 50128 |
| Maritime | `constraints/maritime.md` | 24 | IACS |
| Energy | `constraints/energy.md` | 35 | IEEE 1547 |
| Robotics | `constraints/robotics.md` | 25 | ISO 10218 |
| Space | `constraints/space.md` | 28 | ECSS-E-ST-10C |
| AUV | `constraints/autonomous-underwater.md` | 13 | IMCA |

## Step 1: Load an industry constraint set

```python
from constraint_theory import IndustryLibrary, FluxChecker

# Load aerospace constraints
aero = IndustryLibrary("aviation")
print(f"Loaded {aero.constraint_count} constraints")  # 25

# List all constraints
for name, spec in aero.constraints.items():
    print(f"  {name}: {spec.variable} in {spec.bounds} {spec.unit}")
```

## Step 2: Check aircraft sensor readings

```python
# Simulated sensor data from a commercial aircraft
flight_data = {
    "cabin_pressure": 1.013,      # atm (cruise altitude)
    "cabin_altitude": 2438,        # m (8000 ft)
    "fuel_flow_rate": 0.85,        # kg/s
    "engine egt": 625,             # degC
    "hydraulic_pressure": 20.7,    # MPa (3000 psi)
    "wing_angle_attack": 3.2,      # degrees
    "airspeed": 230,               # m/s (Mach 0.78)
    "vertical_speed": 0.5,         # m/s
}

# Check all 25 aerospace constraints against this data
report = aero.check_all(flight_data)
print(report.summary())
# ✓ 25/25 constraints satisfied
# All systems nominal
```

## Step 3: Handle violations

```python
# Simulate a pressure anomaly
flight_data_anomaly = {
    "cabin_pressure": 0.68,        # BELOW safe range [0.75, 1.05]
    "cabin_altitude": 2438,
    "fuel_flow_rate": 0.85,
    "engine_egt": 625,
    "hydraulic_pressure": 20.7,
    "wing_angle_attack": 3.2,
    "airspeed": 230,
    "vertical_speed": 0.5,
}

report = aero.check_all(flight_data_anomaly)
print(report.summary())
# ✗ 24/25 constraints satisfied
# VIOLATION: cabin_pressure = 0.68 atm ∉ [0.75, 1.05] atm
#   Priority: CRITICAL
#   Category: SAFETY
#   Action: Cabin pressure outside safe range — deploy emergency oxygen

# Get just the violations
for v in report.violations:
    print(f"[{v.priority}] {v.variable} = {v.value} {v.unit} (limit: {v.bounds})")
```

## Step 4: Batch check — monitor a full flight

```python
import numpy as np
from constraint_theory import IndustryLibrary

aero = IndustryLibrary("aviation")

# Generate 10,000 simulated flight sensor readings (1 hour at ~0.36s intervals)
n_readings = 10_000
flight_telemetry = {
    "cabin_pressure": np.random.normal(1.013, 0.05, n_readings),
    "airspeed": np.random.normal(230, 15, n_readings),
    "engine_egt": np.random.normal(625, 50, n_readings),
    "hydraulic_pressure": np.random.normal(20.7, 1.0, n_readings),
}

# Batch check all readings
results = aero.check_batch(flight_telemetry, device="cuda")
print(f"Total checks: {results.total:,}")
print(f"Pass rate: {results.pass_rate * 100:.4f}%")
print(f"Violations: {results.violation_count}")
print(f"Throughput: {results.throughput_bps:.1f}B c/s")
```

## Step 5: Multi-industry monitoring

```python
from constraint_theory import IndustryLibrary

# Load multiple industries for a vehicle that spans domains
libraries = {
    "automotive": IndustryLibrary("automotive"),  # ISO 26262
    "energy": IndustryLibrary("energy"),           # IEEE 1547
    "robotics": IndustryLibrary("robotics"),       # ISO 10218
}

# Autonomous vehicle sensor data
av_data = {
    # Automotive
    "brake_pressure": 12.5,    # MPa
    "steering_angle": 2.3,     # degrees
    "vehicle_speed": 28.0,     # m/s
    
    # Energy (battery pack)
    "cell_voltage": 3.85,      # V
    "pack_temp": 32.0,         # degC
    "charge_current": 45.0,    # A
    
    # Robotics (LiDAR/sensors)
    "lidar_rpm": 600,          # rev/min
    "camera_temp": 42.0,       # degC
}

# Check against all applicable standards
for name, lib in libraries.items():
    report = lib.check_all(av_data)
    status = "✓" if report.all_pass else "✗"
    print(f"{status} {name}: {report.pass_count}/{report.total} constraints passed")
```

## INT8 Compatibility

85% of the 248 constraints are INT8-compatible via Pythagorean48 encoding, enabling GPU throughput of 62.2B checks/sec:

```python
lib = IndustryLibrary("aviation")
int8_count = sum(1 for c in lib.constraints.values() if c.int8_compatible)
print(f"INT8 compatible: {int8_count}/{lib.constraint_count}")
# INT8 compatible: 21/25
```

**Next:** [Tutorial 4 — Understand FLUX-C Bytecode →](04-flux-bytecode.md)
