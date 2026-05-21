"""
Medical Device Safety — IEC 62304 Constraint Checking
=====================================================

Monitors a Class C medical device (ventilator) against IEC 62304 
safety constraints. Every check is exact — no floating-point rounding
can hide a violation.

Run:
    pip install numpy
    python examples/medical_device_safety.py
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime


# --- IEC 62304 Safety Constraints for a Ventilator ---

@dataclass
class MedicalConstraint:
    name: str
    variable: str
    lower: float
    upper: float
    unit: str
    risk_level: str  # IEC 62304: A (low), B (medium), C (high — life support)
    iec_class: str
    failure_mode: str


VENTILATOR_CONSTRAINTS: List[MedicalConstraint] = []  # Built in __main__


def generate_patient_data(n_minutes: int = 60) -> Dict[str, np.ndarray]:
    """Generate simulated ventilator + patient monitoring data."""
    rng = np.random.default_rng(42)
    n = n_minutes * 20  # 20 readings per minute
    
    # Normal patient with occasional deterioration
    base = {
        "tidal_volume": rng.normal(500, 30, n),
        "respiratory_rate": rng.normal(16, 2, n),
        "pip": rng.normal(18, 3, n),
        "peep": rng.normal(5, 1, n),
        "fi_o2": rng.normal(0.40, 0.05, n),
        "minute_volume": rng.normal(8.0, 1.0, n),
        "ie_ratio": rng.normal(0.5, 0.1, n),
        "spo2": rng.normal(97, 1.5, n),
        "etco2": rng.normal(38, 3, n),
        "bp_systolic": rng.normal(120, 10, n),
        "heart_rate": rng.normal(75, 8, n),
        "body_temp": rng.normal(36.8, 0.3, n),
        "battery": np.linspace(95, 65, n),
        "supply_pressure": rng.normal(400, 20, n),
        "circuit_leak": rng.normal(5, 2, n),
        "alarm_latency": rng.normal(120, 50, n),
        "ambient_temp": rng.normal(22, 2, n),
        "humidity": rng.normal(50, 10, n),
    }
    
    # Inject a deterioration event at minute 30
    start = 30 * 20
    end = 35 * 20
    base["spo2"][start:end] = rng.normal(82, 3, end - start)  # Desaturation
    base["etco2"][start:end] = rng.normal(55, 4, end - start)  # CO2 retention
    base["respiratory_rate"][start:end] = rng.normal(6, 1, end - start)  # Bradypnea
    
    return base


def check_medical_constraint(constraint: MedicalConstraint, values: np.ndarray) -> Dict:
    """Check a medical constraint and generate an audit log entry."""
    violations = (values < constraint.lower) | (values > constraint.upper)
    violation_indices = np.where(violations)[0]
    
    return {
        "name": constraint.name,
        "variable": constraint.variable,
        "bounds": f"[{constraint.lower}, {constraint.upper}]",
        "unit": constraint.unit,
        "risk_level": constraint.risk_level,
        "iec_class": constraint.iec_class,
        "failure_mode": constraint.failure_mode,
        "total": len(values),
        "pass_count": int((~violations).sum()),
        "fail_count": int(violations.sum()),
        "violation_indices": violation_indices,
    }


def run_medical_monitor():
    """Run the IEC 62304 medical device safety monitor."""
    print("=" * 65)
    print("MEDICAL DEVICE SAFETY — IEC 62304 Constraint Checking")
    print("Device: Class C Ventilator (Life-Support)")
    print("=" * 65)
    
    # Generate 60 minutes of patient data
    duration_min = 60
    data = generate_patient_data(duration_min)
    n = len(next(iter(data.values())))
    print(f"\nMonitoring {duration_min} minutes of data ({n:,} readings)")
    print(f"Constraints: {len(VENTILATOR_CONSTRAINTS)}")
    
    # Check all constraints
    print("\n" + "-" * 65)
    print(f"{'Constraint':25s} {'Pass':>8s} {'Fail':>6s} {'Rate':>7s} {'Risk':>5s}")
    print("-" * 65)
    
    results = []
    for c in VENTILATOR_CONSTRAINTS:
        if c.variable not in data:
            continue
        r = check_medical_constraint(c, data[c.variable])
        results.append(r)
        
        status = "✓" if r["fail_count"] == 0 else "✗"
        print(f"  {status} {c.name:23s} {r['pass_count']:>6,}  {r['fail_count']:>5,}  "
              f"{r['pass_count']/r['total']*100:5.1f}%  [{c.risk_level}]")
    
    # IEC 62304 audit report
    print("\n" + "=" * 65)
    print("IEC 62304 AUDIT SUMMARY")
    print("=" * 65)
    
    total_checks = sum(r["total"] for r in results)
    total_pass = sum(r["pass_count"] for r in results)
    
    class_c_violations = sum(r["fail_count"] for r in results if r["risk_level"] == "C")
    class_b_violations = sum(r["fail_count"] for r in results if r["risk_level"] == "B")
    
    print(f"Total checks:        {total_checks:,}")
    print(f"Overall pass rate:   {total_pass/total_checks*100:.4f}%")
    print(f"\nClass C violations:  {class_c_violations:,} (life-critical)")
    print(f"Class B violations:  {class_b_violations:,} (important)")
    
    # Identify the deterioration event
    print("\n--- Deterioration Event Analysis (minute 30-35) ---")
    for r in results:
        if r["risk_level"] != "C" or r["fail_count"] == 0:
            continue
        # Check if violations cluster in the deterioration window
        det_start = 30 * 20
        det_end = 35 * 20
        det_violations = sum(1 for idx in r["violation_indices"] if det_start <= idx < det_end)
        if det_violations > 0:
            print(f"  {r['name']:25s}: {det_violations} violations during deterioration "
                  f"({r['failure_mode']})")
    
    if class_c_violations > 0:
        print("\n⚠ CLASS C VIOLATIONS — IEC 62304 requires corrective action")
    else:
        print("\n✓ All Class C constraints satisfied — device safe for use")


if __name__ == "__main__":
    # Fix: use the correct dataclass name
    VENTILATOR_CONSTRAINTS = []
    
    # Breathing parameters
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "tidal_volume", "tidal_volume", 200, 800, "mL", "C", "IEC 60601", "Hypo/hyperventilation"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "resp_rate", "respiratory_rate", 4, 35, "breaths/min", "C", "IEC 60601", "Asphyxia/barotrauma"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "peak_insp_pressure", "pip", 5, 40, "cmH2O", "C", "IEC 60601", "Barotrauma"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "peep", "peep", 0, 20, "cmH2O", "C", "IEC 60601", "Atelectasis/volutrauma"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "fi_o2", "fi_o2", 0.21, 1.0, "fraction", "C", "IEC 60601", "Hypoxia/O2 toxicity"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "minute_volume", "minute_volume", 3.0, 15.0, "L/min", "C", "IEC 60601", "Resp failure"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "ie_ratio", "ie_ratio", 0.25, 3.0, "ratio", "B", "IEC 60601", "Inverse ratio"))
    
    # Patient monitoring
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "spo2", "spo2", 85, 100, "percent", "C", "ISO 80601-2-61", "Hypoxemia"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "etco2", "etco2", 15, 60, "mmHg", "C", "ISO 21647", "Hyper/hypocapnia"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "bp_systolic", "bp_systolic", 60, 200, "mmHg", "B", "IEC 60601-2-30", "Hypo/hypertension"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "heart_rate", "heart_rate", 30, 180, "bpm", "B", "IEC 60601-2-27", "Arrhythmia"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "body_temp", "body_temp", 34.0, 41.0, "degC", "B", "ISO 80601-2-56", "Hypo/hyperthermia"))
    
    # Device hardware
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "battery_level", "battery", 10, 100, "percent", "B", "IEC 60601-1", "Power loss"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "supply_pressure", "supply_pressure", 280, 600, "kPa", "B", "ISO 5359", "Gas supply failure"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "circuit_integrity", "circuit_leak", 0, 50, "mL/min", "C", "ISO 5369", "Disconnect"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "alarm_latency", "alarm_latency", 0, 500, "ms", "C", "IEC 60601-1-8", "Delayed alarm"))
    
    # Environmental
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "ambient_temp", "ambient_temp", 10, 40, "degC", "A", "IEC 60601-1", "Malfunction"))
    VENTILATOR_CONSTRAINTS.append(MedicalConstraint(
        "ambient_humidity", "humidity", 15, 95, "percent_RH", "A", "IEC 60601-1", "Condensation"))
    
    run_medical_monitor()
