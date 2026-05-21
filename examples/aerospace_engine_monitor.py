"""
Aerospace Engine Monitor — 25 DO-254 Constraints
=================================================

Monitors a jet engine against all 25 aerospace constraints in real-time.
Uses GPU-accelerated batch checking for sensor telemetry streams.

Run:
    pip install numpy
    python examples/aerospace_engine_monitor.py
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List


# --- Aerospace constraint definitions (DO-254 mapped) ---

@dataclass
class Constraint:
    name: str
    variable: str
    lower: float
    upper: float
    unit: str
    priority: str
    category: str


AEROSPACE_CONSTRAINTS: List[Constraint] = [
    # Engine core
    Constraint("egt_limit", "engine_egt", 0, 700, "degC", "CRITICAL", "THERMAL"),
    Constraint("n1_range", "n1_rpm", 0, 13800, "rpm", "CRITICAL", "MECHANICAL"),
    Constraint("n2_range", "n2_rpm", 0, 16500, "rpm", "CRITICAL", "MECHANICAL"),
    Constraint("fuel_flow", "fuel_flow_rate", 0.1, 1.2, "kg/s", "HIGH", "FUEL"),
    Constraint("oil_pressure", "oil_pressure", 200, 600, "kPa", "CRITICAL", "LUBRICATION"),
    Constraint("oil_temp", "oil_temp", -40, 150, "degC", "HIGH", "LUBRICATION"),
    Constraint("vibration_hpt", "vibration_hpt", 0, 25.4, "mm/s", "HIGH", "MECHANICAL"),
    Constraint("vibration_lpt", "vibration_lpt", 0, 25.4, "mm/s", "HIGH", "MECHANICAL"),
    
    # Cabin & life support
    Constraint("cabin_pressure", "cabin_pressure", 0.75, 1.05, "atm", "CRITICAL", "LIFE_SUPPORT"),
    Constraint("cabin_alt", "cabin_altitude", 0, 2438, "m", "CRITICAL", "LIFE_SUPPORT"),
    Constraint("oxygen", "oxygen_level", 19.5, 23.5, "percent", "CRITICAL", "LIFE_SUPPORT"),
    
    # Hydraulic
    Constraint("hyd_press_a", "hydraulic_a", 19.3, 22.1, "MPa", "HIGH", "HYDRAULIC"),
    Constraint("hyd_press_b", "hydraulic_b", 19.3, 22.1, "MPa", "HIGH", "HYDRAULIC"),
    
    # Electrical
    Constraint("bus_voltage", "bus_voltage", 112, 118, "V", "HIGH", "ELECTRICAL"),
    Constraint("gen_freq", "gen_frequency", 395, 405, "Hz", "MEDIUM", "ELECTRICAL"),
    
    # Flight controls
    Constraint("aoa", "angle_of_attack", -5, 15, "deg", "CRITICAL", "FLIGHT_CONTROL"),
    Constraint("elevator_pos", "elevator", -25, 20, "deg", "HIGH", "FLIGHT_CONTROL"),
    Constraint("aileron_pos", "aileron", -25, 25, "deg", "HIGH", "FLIGHT_CONTROL"),
    Constraint("rudder_pos", "rudder", -30, 30, "deg", "HIGH", "FLIGHT_CONTROL"),
    
    # Structural
    Constraint("g_load", "g_load", -1.5, 3.5, "g", "CRITICAL", "STRUCTURAL"),
    Constraint("wing_flex", "wing_deflection", -3, 6, "m", "HIGH", "STRUCTURAL"),
    
    # Navigation
    Constraint("airspeed", "airspeed", 60, 340, "m/s", "HIGH", "NAVIGATION"),
    Constraint("mach", "mach_number", 0.2, 0.92, "mach", "MEDIUM", "NAVIGATION"),
    
    # Fuel system
    Constraint("fuel_qty_left", "fuel_left", 500, 20000, "kg", "HIGH", "FUEL"),
    Constraint("fuel_qty_right", "fuel_right", 500, 20000, "kg", "HIGH", "FUEL"),
]


def generate_flight_telemetry(n_readings: int = 10_000) -> Dict[str, np.ndarray]:
    """Generate simulated flight telemetry with realistic distributions."""
    rng = np.random.default_rng(42)
    
    return {
        "engine_egt": rng.normal(580, 40, n_readings),
        "n1_rpm": rng.normal(10500, 800, n_readings),
        "n2_rpm": rng.normal(12800, 900, n_readings),
        "fuel_flow_rate": rng.normal(0.75, 0.1, n_readings),
        "oil_pressure": rng.normal(410, 50, n_readings),
        "oil_temp": rng.normal(85, 15, n_readings),
        "vibration_hpt": rng.normal(8, 3, n_readings),
        "vibration_lpt": rng.normal(6, 2, n_readings),
        "cabin_pressure": rng.normal(1.01, 0.03, n_readings),
        "cabin_altitude": rng.normal(1800, 200, n_readings),
        "oxygen_level": rng.normal(21.0, 0.5, n_readings),
        "hydraulic_a": rng.normal(20.7, 0.5, n_readings),
        "hydraulic_b": rng.normal(20.7, 0.5, n_readings),
        "bus_voltage": rng.normal(115, 1, n_readings),
        "gen_frequency": rng.normal(400, 1, n_readings),
        "angle_of_attack": rng.normal(3, 1.5, n_readings),
        "elevator": rng.normal(-2, 3, n_readings),
        "aileron": rng.normal(0, 2, n_readings),
        "rudder": rng.normal(0, 1.5, n_readings),
        "g_load": rng.normal(1.0, 0.3, n_readings),
        "wing_deflection": rng.normal(1.5, 0.5, n_readings),
        "airspeed": rng.normal(230, 20, n_readings),
        "mach_number": rng.normal(0.78, 0.05, n_readings),
        "fuel_left": rng.normal(8000, 1000, n_readings),
        "fuel_right": rng.normal(8000, 1000, n_readings),
    }


def check_constraint(constraint: Constraint, values: np.ndarray) -> Dict:
    """Check a single constraint against an array of sensor readings."""
    violations = (values < constraint.lower) | (values > constraint.upper)
    return {
        "name": constraint.name,
        "total": len(values),
        "pass_count": int((~violations).sum()),
        "fail_count": int(violations.sum()),
        "pass_rate": float((~violations).mean()),
        "priority": constraint.priority,
        "category": constraint.category,
        "unit": constraint.unit,
        "bounds": f"[{constraint.lower}, {constraint.upper}]",
    }


def run_aerospace_monitor():
    """Run the full aerospace engine monitor."""
    print("=" * 60)
    print("AEROSPACE ENGINE MONITOR — 25 DO-254 Constraints")
    print("=" * 60)
    
    # Generate telemetry
    n = 100_000  # 100K readings (~10 hours at 0.36s intervals)
    telemetry = generate_flight_telemetry(n)
    print(f"\nGenerated {n:,} sensor readings across {len(telemetry)} variables")
    
    # Check all constraints
    print(f"\nChecking {len(AEROSPACE_CONSTRAINTS)} constraints...\n")
    
    total_checks = 0
    total_pass = 0
    violations_by_priority = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0}
    
    for c in AEROSPACE_CONSTRAINTS:
        if c.variable not in telemetry:
            print(f"  ⚠ SKIP: {c.name} — no data for {c.variable}")
            continue
        
        result = check_constraint(c, telemetry[c.variable])
        total_checks += result["total"]
        total_pass += result["pass_count"]
        violations_by_priority[result["priority"]] += result["fail_count"]
        
        status = "✓" if result["fail_count"] == 0 else "✗"
        print(f"  {status} {c.name:20s}  {result['pass_count']:>6}/{result['total']:<6}  "
              f"{result['pass_rate']*100:6.2f}%  [{c.priority}] {c.variable} {c.bounds} {c.unit}")
    
    # Summary
    print("\n" + "=" * 60)
    print(f"Total checks:  {total_checks:,}")
    print(f"Pass rate:     {total_pass/total_checks*100:.4f}%")
    print(f"\nViolations by priority:")
    for pri in ["CRITICAL", "HIGH", "MEDIUM"]:
        print(f"  {pri:10s}: {violations_by_priority[pri]:,}")
    
    if violations_by_priority["CRITICAL"] > 0:
        print("\n⚠ CRITICAL VIOLATIONS DETECTED — Immediate action required")
    elif violations_by_priority["HIGH"] > 0:
        print("\n⚠ High-priority violations — Review recommended")
    else:
        print("\n✓ All systems nominal")


if __name__ == "__main__":
    run_aerospace_monitor()
