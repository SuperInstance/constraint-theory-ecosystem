"""
FLUX Constraint Engine — Pure Python
INT8 saturated constraint checking. Zero dependencies.

Usage:
    from flux_constraint import FluxConstraint, Severity
    
    fc = FluxConstraint([
        {"lo": 15, "hi": 55, "name": "battery_temp"},
        {"lo": 0, "hi": 100, "name": "charge_rate"},
    ])
    
    result = fc.check(60)
    print(result.severity)      # Severity.CAUTION
    print(result.error_mask)    # 0x01
    print(result.passed)        # False
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Dict, Optional, Tuple


INT8_MIN = -127
INT8_MAX = 127


def saturate(val: int) -> int:
    """Clamp to saturated INT8 [-127, 127]"""
    return max(INT8_MIN, min(INT8_MAX, int(val)))


class Severity(IntEnum):
    """Constraint violation severity levels."""
    PASS = 0
    CAUTION = 1
    WARNING = 2
    CRITICAL = 3


@dataclass
class ConstraintDef:
    """A single constraint definition."""
    lo: int
    hi: int
    name: str

    def __post_init__(self):
        self.lo = saturate(self.lo)
        self.hi = saturate(self.hi)


@dataclass
class ConstraintDetail:
    """Result for a single constraint check."""
    name: str
    lo: int
    hi: int
    value: int
    passed: bool
    lo_violated: bool
    hi_violated: bool


@dataclass
class FluxResult:
    """Result of a constraint check."""
    error_mask: int = 0
    severity: Severity = Severity.PASS
    violated_lo: int = 0
    violated_hi: int = 0
    violated_count: int = 0
    details: List[ConstraintDetail] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.severity == Severity.PASS

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


# Industry presets
PRESETS: Dict[str, List[Dict]] = {
    "aviation": [
        {"lo": -55, "hi": 70, "name": "cabin_temp_C"},
        {"lo": 75, "hi": 101, "name": "cabin_pressure_kPa"},
        {"lo": 0, "hi": 100, "name": "fuel_flow_pct"},
        {"lo": 60, "hi": 100, "name": "hydraulic_pct"},
    ],
    "automotive": [
        {"lo": -40, "hi": 60, "name": "battery_temp_C"},
        {"lo": 0, "hi": 100, "name": "soc_pct"},
        {"lo": 0, "hi": 100, "name": "charge_rate_pct"},
        {"lo": 20, "hi": 80, "name": "cabin_temp_C"},
    ],
    "maritime": [
        {"lo": -2, "hi": 35, "name": "sea_temp_C"},
        {"lo": 50, "hi": 100, "name": "hull_integrity_pct"},
        {"lo": 0, "hi": 50, "name": "wave_height_m"},
        {"lo": 0, "hi": 80, "name": "wind_speed_kn"},
    ],
    "medical": [
        {"lo": 36, "hi": 38, "name": "body_temp_C"},
        {"lo": 60, "hi": 100, "name": "heart_rate_bpm"},
        {"lo": 95, "hi": 100, "name": "spo2_pct"},
        {"lo": 80, "hi": 120, "name": "bp_systolic_mmHg"},
    ],
    "energy": [
        {"lo": 49, "hi": 51, "name": "grid_freq_Hz_x10"},
        {"lo": 95, "hi": 105, "name": "voltage_pct"},
        {"lo": 0, "hi": 80, "name": "transformer_temp_C"},
        {"lo": 0, "hi": 100, "name": "line_load_pct"},
    ],
    "nuclear": [
        {"lo": 0, "hi": 110, "name": "neutron_flux_pct"},
        {"lo": 0, "hi": 65, "name": "core_temp_C_x10"},
        {"lo": 72, "hi": 100, "name": "pressurizer_pct"},
        {"lo": 0, "hi": 100, "name": "coolant_flow_pct"},
    ],
    "railway": [
        {"lo": 0, "hi": 100, "name": "speed_pct"},
        {"lo": 0, "hi": 100, "name": "brake_pressure_pct"},
        {"lo": 0, "hi": 1, "name": "door_interlock"},
        {"lo": 0, "hi": 80, "name": "track_temp_C"},
    ],
    "robotics": [
        {"lo": -100, "hi": 100, "name": "joint_torque_pct"},
        {"lo": 0, "hi": 100, "name": "speed_pct"},
        {"lo": 0, "hi": 100, "name": "force_pct"},
        {"lo": -127, "hi": 127, "name": "position_mm"},
    ],
    "space": [
        {"lo": -40, "hi": 50, "name": "temp_C"},
        {"lo": 0, "hi": 100, "name": "solar_panel_pct"},
        {"lo": 0, "hi": 100, "name": "propellant_pct"},
        {"lo": 0, "hi": 100, "name": "battery_pct"},
    ],
    "underwater": [
        {"lo": 0, "hi": 100, "name": "depth_pct"},
        {"lo": 0, "hi": 100, "name": "battery_pct"},
        {"lo": -5, "hi": 35, "name": "water_temp_C"},
        {"lo": 0, "hi": 100, "name": "thruster_pct"},
    ],
}


class FluxConstraint:
    """
    FLUX INT8 saturated constraint checker.
    
    Up to 8 constraints per sensor. All values clamped to [-127, 127].
    """

    def __init__(self, constraints: List[Dict]):
        if not constraints or len(constraints) == 0:
            raise ValueError("FluxConstraint requires non-empty constraints list")
        if len(constraints) > 8:
            raise ValueError("Maximum 8 constraints (INT8 x8 flat bounds)")
        
        self.constraints = [
            ConstraintDef(
                lo=c["lo"], hi=c["hi"],
                name=c.get("name", f"C{i}")
            )
            for i, c in enumerate(constraints)
        ]

    def check(self, value: int) -> FluxResult:
        """Check a single value against all constraints."""
        val = saturate(value)
        result = FluxResult()
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

            result.details.append(ConstraintDetail(
                name=c.name, lo=c.lo, hi=c.hi, value=val,
                passed=passed, lo_violated=lo_fail, hi_violated=hi_fail
            ))

        nc = len(self.constraints)
        if violated == 0:
            result.severity = Severity.PASS
        elif violated <= nc // 4:
            result.severity = Severity.CAUTION
        elif violated <= nc // 2:
            result.severity = Severity.WARNING
        else:
            result.severity = Severity.CRITICAL
        result.violated_count = violated

        return result

    def check_batch(self, values: List[int]) -> Tuple[List[FluxResult], Dict[str, int]]:
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
        import time
        t0 = time.perf_counter()
        for i in range(iterations):
            self.check((i % 254) - 127)
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
    def from_preset(cls, name: str) -> "FluxConstraint":
        """Load an industry preset."""
        if name not in PRESETS:
            raise ValueError(f"Unknown preset: {name}. Available: {', '.join(PRESETS.keys())}")
        return cls(PRESETS[name])

    @classmethod
    def available_presets(cls) -> List[str]:
        """List available industry presets."""
        return list(PRESETS.keys())


if __name__ == "__main__":
    import json

    print("╔══════════════════════════════════════════════════════╗")
    print("║  FLUX Constraint Engine — Python                    ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    # Aviation example
    fc = FluxConstraint.from_preset("aviation")
    print(f"Loaded aviation preset: {len(fc.constraints)} constraints")
    for c in fc.constraints:
        print(f"  {c.name}: [{c.lo}, {c.hi}]")

    # Check some values
    print("\nExamples:")
    for val in [-60, 0, 25, 70, 90, 127]:
        r = fc.check(val)
        status = "✓" if r.passed else f"✗ sev={r.severity.name}"
        print(f"  val={val:>4}: {status} mask=0x{r.error_mask:02X}")

    # Benchmark
    print("\nBenchmark:")
    bench = fc.benchmark()
    print(f"  {bench['rate_M']:.1f}M checks/sec ({bench['iterations']:,} iterations in {bench['total_ms']:.1f}ms)")

    # All presets
    print("\nAvailable presets:", ", ".join(FluxConstraint.available_presets()))
