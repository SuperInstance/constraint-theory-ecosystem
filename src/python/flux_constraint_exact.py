"""
FLUX Exact Constraint Engine — Zero False Negatives
Exact numeric comparison. No INT8 quantization on bounds or values.

INVARIANT: A value outside bounds is ALWAYS detected. No exceptions.

Usage:
    from flux_constraint_exact import FluxExact, Severity
    
    fc = FluxExact([
        {"lo": -40, "hi": 150, "name": "coolant_temp"},
        {"lo": 0, "hi": 8000, "name": "engine_rpm"},
    ])
    
    result = fc.check(151)
    assert not result.passed  # 151 > 150, correctly detected
    
    result = fc.check(150)
    assert result.passed  # exactly at boundary, in range
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Dict, Optional, Tuple, Union
import time

Number = Union[int, float]


class Severity(IntEnum):
    """Constraint violation severity levels."""
    PASS = 0
    CAUTION = 1
    WARNING = 2
    CRITICAL = 3


# Severity lookup from violation count (0-8)
SEVERITY_TABLE = [
    Severity.PASS,       # 0 violations
    Severity.CAUTION,    # 1
    Severity.CAUTION,    # 2
    Severity.WARNING,    # 3
    Severity.WARNING,    # 4
    Severity.CRITICAL,   # 5
    Severity.CRITICAL,   # 6
    Severity.CRITICAL,   # 7
    Severity.CRITICAL,   # 8
]


@dataclass
class ExactConstraintDef:
    """A single constraint definition — bounds stored as original values."""
    lo: float
    hi: float
    name: str

    def __post_init__(self):
        self.lo = float(self.lo)
        self.hi = float(self.hi)
        if self.lo > self.hi:
            raise ValueError(f"Constraint '{self.name}': lo ({self.lo}) > hi ({self.hi})")


@dataclass
class ExactDetail:
    """Result for a single constraint check."""
    name: str
    lo: float
    hi: float
    value: float
    passed: bool
    lo_violated: bool
    hi_violated: bool


@dataclass
class ExactResult:
    """Result of an exact constraint check. Zero false negatives guaranteed."""
    error_mask: int = 0
    severity: Severity = Severity.PASS
    violated_lo: int = 0
    violated_hi: int = 0
    violated_count: int = 0
    details: List[ExactDetail] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.error_mask == 0

    def to_dict(self) -> dict:
        return {
            "error_mask": self.error_mask,
            "severity": int(self.severity),
            "severity_name": self.severity.name,
            "violated_lo": self.violated_lo,
            "violated_hi": self.violated_hi,
            "violated_count": self.violated_count,
            "passed": self.passed,
            "details": [
                {
                    "name": d.name,
                    "lo": d.lo,
                    "hi": d.hi,
                    "value": d.value,
                    "passed": d.passed,
                }
                for d in self.details
            ],
        }


# Industry presets with REALISTIC bounds (not INT8-limited)
PRESETS: Dict[str, List[Dict]] = {
    "automotive_can": [
        {"lo": 0, "hi": 8000, "name": "engine_rpm"},
        {"lo": 0, "hi": 300, "name": "vehicle_speed_kmh"},
        {"lo": -40, "hi": 150, "name": "coolant_temp_c"},
        {"lo": 0, "hi": 100, "name": "throttle_pct"},
        {"lo": 0, "hi": 200, "name": "brake_pressure_bar"},
        {"lo": -720, "hi": 720, "name": "steering_angle_deg"},
        {"lo": 9, "hi": 16, "name": "battery_voltage_v"},
        {"lo": 0, "hi": 100, "name": "fuel_level_pct"},
    ],
    "aviation_adsb": [
        {"lo": -1000, "hi": 45000, "name": "altitude_ft"},
        {"lo": 0, "hi": 600, "name": "ground_speed_kt"},
        {"lo": -180, "hi": 180, "name": "heading_deg"},
        {"lo": -55, "hi": 70, "name": "cabin_temp_c"},
        {"lo": 75, "hi": 101, "name": "cabin_pressure_kpa"},
        {"lo": 0, "hi": 100, "name": "fuel_flow_pct"},
        {"lo": 60, "hi": 100, "name": "hydraulic_pct"},
        {"lo": -90, "hi": 90, "name": "pitch_deg"},
    ],
    "medical_fhir": [
        {"lo": 36.1, "hi": 37.8, "name": "body_temp_c"},
        {"lo": 60, "hi": 100, "name": "heart_rate_bpm"},
        {"lo": 95, "hi": 100, "name": "spo2_pct"},
        {"lo": 80, "hi": 120, "name": "bp_systolic_mmhg"},
        {"lo": 60, "hi": 100, "name": "bp_diastolic_mmhg"},
        {"lo": 12, "hi": 20, "name": "respiratory_rate"},
        {"lo": 7.35, "hi": 7.45, "name": "ph"},
        {"lo": 0, "hi": 300, "name": "glucose_mg_dl"},
    ],
    "energy_scada": [
        {"lo": 49.0, "hi": 51.0, "name": "grid_freq_hz"},
        {"lo": 0.9, "hi": 1.1, "name": "voltage_pu"},
        {"lo": 0, "hi": 80, "name": "transformer_temp_c"},
        {"lo": 0, "hi": 100, "name": "line_load_pct"},
        {"lo": 0, "hi": 500, "name": "current_a"},
        {"lo": -100, "hi": 100, "name": "power_factor_pct_offset"},
        {"lo": 0, "hi": 360, "name": "phase_angle_deg"},
        {"lo": 0, "hi": 50, "name": "thd_pct"},
    ],
    "iot_mqtt": [
        {"lo": -40, "hi": 85, "name": "ambient_temp_c"},
        {"lo": 0, "hi": 100, "name": "humidity_pct"},
        {"lo": 300, "hi": 1100, "name": "pressure_hpa"},
        {"lo": 0, "hi": 1000, "name": "co2_ppm"},
        {"lo": 0, "hi": 500, "name": "pm25_ug_m3"},
        {"lo": 0, "hi": 5000, "name": "light_lux"},
        {"lo": 0, "hi": 100, "name": "battery_pct"},
        {"lo": -120, "hi": -20, "name": "wifi_rssi_dbm"},
    ],
    "financial_fix": [
        {"lo": 0.0001, "hi": 100000, "name": "price"},
        {"lo": 1, "hi": 10000000, "name": "volume"},
        {"lo": -100, "hi": 100, "name": "pct_change"},
        {"lo": 0.001, "hi": 1000, "name": "volatility"},
        {"lo": 0, "hi": 1, "name": "correlation"},
        {"lo": -100000, "hi": 100000, "name": "spread_bps"},
        {"lo": 0, "hi": 86400, "name": "time_offset_s"},
        {"lo": 0.01, "hi": 100, "name": "duration_years"},
    ],
}


class FluxExact:
    """
    FLUX Exact Constraint Engine — Zero False Negatives.
    
    Bounds and values are compared in ORIGINAL numeric space.
    No INT8 quantization of bounds or values.
    INT8 saturation is ONLY for the error mask accumulator (which naturally fits in 8 bits).
    
    Up to 8 constraints per sensor.
    """

    def __init__(self, constraints: List[Dict]):
        if not constraints:
            raise ValueError("FluxExact requires non-empty constraints list")
        if len(constraints) > 8:
            raise ValueError("Maximum 8 constraints (error_mask is uint8)")
        
        self.constraints = [
            ExactConstraintDef(
                lo=c["lo"], hi=c["hi"],
                name=c.get("name", f"C{i}")
            )
            for i, c in enumerate(constraints)
        ]

    def check(self, value: Number) -> ExactResult:
        """
        Check a single value against all constraints.
        
        INVARIANT: value is compared in ORIGINAL numeric space.
        No quantization. No saturation. Exact comparison.
        ZERO false negatives guaranteed.
        """
        val = float(value)
        result = ExactResult()
        violated = 0

        for i, c in enumerate(self.constraints):
            lo_fail = val < c.lo
            hi_fail = val > c.hi
            passed = not lo_fail and not hi_fail

            if not passed:
                result.error_mask |= (1 << i)
                violated += 1
            if lo_fail:
                result.violated_lo |= (1 << i)
            if hi_fail:
                result.violated_hi |= (1 << i)

            result.details.append(ExactDetail(
                name=c.name, lo=c.lo, hi=c.hi, value=val,
                passed=passed, lo_violated=lo_fail, hi_violated=hi_fail
            ))

        result.violated_count = violated
        result.severity = SEVERITY_TABLE[violated] if violated < len(SEVERITY_TABLE) else Severity.CRITICAL

        return result

    def check_batch(self, values: List[Number]) -> Tuple[List[ExactResult], Dict[str, int]]:
        """Check multiple values. Returns (results, stats)."""
        results = []
        stats = {"pass": 0, "caution": 0, "warning": 0, "critical": 0}

        for v in values:
            r = self.check(v)
            results.append(r)
            stats[r.severity.name.lower()] += 1

        return results, stats

    def benchmark(self, iterations: int = 1_000_000) -> Dict:
        """Benchmark check rate."""
        t0 = time.perf_counter()
        for i in range(iterations):
            self.check((i % 1000) - 500)
        t1 = time.perf_counter()
        total_ms = (t1 - t0) * 1000
        rate = (iterations * len(self.constraints)) / (t1 - t0)
        return {
            "rate": rate,
            "rate_M": rate / 1e6,
            "total_ms": total_ms,
            "iterations": iterations,
            "constraints": len(self.constraints),
        }

    @classmethod
    def from_preset(cls, name: str) -> "FluxExact":
        """Load an industry preset."""
        if name not in PRESETS:
            raise ValueError(f"Unknown preset: {name}. Available: {', '.join(PRESETS.keys())}")
        return cls(PRESETS[name])

    @classmethod
    def available_presets(cls) -> List[str]:
        """List available industry presets."""
        return list(PRESETS.keys())


# Backward-compatible alias for the exact check
flux_check_exact = FluxExact


if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════╗")
    print("║  FLUX Exact Constraint Engine — Python              ║")
    print("║  ZERO FALSE NEGATIVES GUARANTEED                    ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    # Demonstrate the fix
    fc = FluxExact([{"lo": -40, "hi": 150, "name": "coolant_temp"}])
    
    print("Demonstrating exact check vs INT8 quantized:")
    print(f"  Constraint: [-40, 150]")
    
    test_vals = [150, 151, 127, 128, -40, -41, 200, 500]
    for val in test_vals:
        r = fc.check(val)
        # What old INT8 would do:
        old_clamped = max(-127, min(127, val))
        old_hi = 127  # saturate(150) = 127
        old_pass = -127 <= old_clamped <= old_hi
        status = "✓ PASS" if r.passed else f"✗ {r.severity.name}"
        old_status = "✓ PASS" if old_pass else "✗ FAIL"
        mismatch = " ← FALSE NEG!" if old_pass and not r.passed else ""
        print(f"  val={val:>5}: exact={status} | old_INT8={old_status}{mismatch}")

    # Automotive CAN preset
    print("\nAutomotive CAN preset:")
    fc_can = FluxExact.from_preset("automotive_can")
    for c in fc_can.constraints:
        print(f"  {c.name}: [{c.lo}, {c.hi}]")

    # Benchmark
    print("\nBenchmark:")
    bench = fc_can.benchmark()
    print(f"  {bench['rate_M']:.1f}M checks/sec ({bench['iterations']:,} iterations in {bench['total_ms']:.1f}ms)")

    print("\nAvailable presets:", ", ".join(FluxExact.available_presets()))
