"""
FLUX Exact Constraint Engine — Zero False Negatives
Production-grade. Zero-alloc hot path. Numpy vectorized batch.

INVARIANT: A value outside bounds is ALWAYS detected. No exceptions.
NaN always violates all constraints. No opt-in required.

Usage:
    from flux_constraint_exact import FluxExact

    fc = FluxExact([{"lo": -40, "hi": 150, "name": "coolant_temp"}])

    # Zero-alloc hot path
    mask = fc.check_mask(151)     # → int (0 = pass)

    # Legacy path (backward compat — returns ExactResult)
    result = fc.check(151)        # → ExactResult with .passed, .severity, etc.

    # Batch: numpy vectorized
    masks = fc.check_batch(arr)   # → np.ndarray of uint8 masks

    # Details only when needed
    detail = fc.check_detail(151) # → dict
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Tuple, Union

import numpy as np

Number = Union[int, float]

# ── Severity ────────────────────────────────────────────────

class Severity(IntEnum):
    PASS = 0
    CAUTION = 1
    WARNING = 2
    CRITICAL = 3

_SEVERITY_TABLE = [
    Severity.PASS, Severity.CAUTION, Severity.CAUTION,
    Severity.WARNING, Severity.WARNING,
    Severity.CRITICAL, Severity.CRITICAL, Severity.CRITICAL, Severity.CRITICAL,
]

SEVERITY_TABLE = _SEVERITY_TABLE


# ── Data classes (backward compat) ─────────────────────────

@dataclass
class ExactConstraintDef:
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
    name: str
    lo: float
    hi: float
    value: float
    passed: bool
    lo_violated: bool
    hi_violated: bool

@dataclass
class ExactResult:
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
                {"name": d.name, "lo": d.lo, "hi": d.hi, "value": d.value, "passed": d.passed}
                for d in self.details
            ],
        }


# ── Presets (module-level constants) ────────────────────────

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


# ── Module-level helpers ────────────────────────────────────

def severity(mask: int) -> Severity:
    n = bin(mask).count("1")
    return _SEVERITY_TABLE[n] if n < len(_SEVERITY_TABLE) else Severity.CRITICAL

def passed(mask: int) -> bool:
    return mask == 0


# ── FluxExact ───────────────────────────────────────────────

class FluxExact:
    """
    FLUX Exact Constraint Engine — Zero False Negatives.

    check_mask()  → int error_mask    (zero-alloc hot path)
    check()       → ExactResult       (backward compat, allocates)
    check_batch() → np.ndarray uint8  (numpy vectorized)
    check_detail() → dict             (allocates, full info)
    """

    __slots__ = ("_lo", "_hi", "_names", "n", "constraints")

    def __init__(self, constraints: List[Dict]):
        if not constraints:
            raise ValueError("FluxExact requires non-empty constraints list")
        if len(constraints) > 8:
            raise ValueError("Maximum 8 constraints (error_mask is uint8)")

        self._lo = tuple(float(c["lo"]) for c in constraints)
        self._hi = tuple(float(c["hi"]) for c in constraints)
        self._names = tuple(c.get("name", f"C{i}") for i, c in enumerate(constraints))
        self.n = len(constraints)

        for i in range(self.n):
            if self._lo[i] > self._hi[i]:
                raise ValueError(
                    f"Constraint '{self._names[i]}': lo ({self._lo[i]}) > hi ({self._hi[i]})"
                )

        self.constraints = [
            ExactConstraintDef(lo=self._lo[i], hi=self._hi[i], name=self._names[i])
            for i in range(self.n)
        ]

    # ── Zero-alloc hot path ─────────────────────────────────

    def check_mask(self, value: Number) -> int:
        """Check value. Returns error_mask (0 = all pass). Zero allocations."""
        v = float(value)
        if v != v:
            return (1 << self.n) - 1
        mask = 0
        for i in range(self.n):
            if v < self._lo[i] or v > self._hi[i]:
                mask |= (1 << i)
        return mask

    # ── Backward-compat check (returns ExactResult) ─────────

    def check(self, value: Number) -> ExactResult:
        """Check value. Returns ExactResult with .passed, .severity, .details."""
        v = float(value)
        is_nan = v != v
        mask = 0
        lo_mask = 0
        hi_mask = 0
        details = []

        for i in range(self.n):
            if is_nan:
                lo_f = hi_f = True
            else:
                lo_f = v < self._lo[i]
                hi_f = v > self._hi[i]
            p = not lo_f and not hi_f
            if not p:
                mask |= (1 << i)
            if lo_f:
                lo_mask |= (1 << i)
            if hi_f:
                hi_mask |= (1 << i)
            details.append(ExactDetail(
                name=self._names[i], lo=self._lo[i], hi=self._hi[i], value=v,
                passed=p, lo_violated=lo_f, hi_violated=hi_f,
            ))

        vc = bin(mask).count("1")
        return ExactResult(
            error_mask=mask,
            severity=_SEVERITY_TABLE[vc] if vc < len(_SEVERITY_TABLE) else Severity.CRITICAL,
            violated_lo=lo_mask,
            violated_hi=hi_mask,
            violated_count=vc,
            details=details,
        )

    # ── Batch: backward compat ─────────────────────────────

    def check_batch(self, values) -> Tuple[List[ExactResult], Dict[str, int]]:
        """Check multiple values. Returns (results, stats). Backward compat."""
        results = []
        stats = {"pass": 0, "caution": 0, "warning": 0, "critical": 0}
        for v in values:
            r = self.check(v)
            results.append(r)
            stats[r.severity.name.lower()] += 1
        return results, stats

    # ── Numpy batch (vectorized) ────────────────────────────

    def check_batch_numpy(self, values) -> np.ndarray:
        """Vectorized batch check. Returns np.ndarray of uint8 error_masks."""
        vals = np.asarray(values, dtype=np.float64)
        flat = vals.ravel()
        masks = np.zeros(len(flat), dtype=np.uint8)
        nan_mask = np.isnan(flat)
        if self.n <= 8:
            masks[nan_mask] = np.uint8((1 << self.n) - 1)
        valid = ~nan_mask
        for i in range(self.n):
            violated = valid & ((flat < self._lo[i]) | (flat > self._hi[i]))
            masks[violated] |= np.uint8(1 << i)
        return masks.reshape(vals.shape)

    # ── Detail path (dict, allocates) ───────────────────────

    def check_detail(self, value: Number) -> dict:
        """Full result as dict. Allocates — not for hot path."""
        v = float(value)
        is_nan = v != v
        mask = 0
        lo_mask = 0
        hi_mask = 0
        details = []
        for i in range(self.n):
            if is_nan:
                lo_f = hi_f = True
            else:
                lo_f = v < self._lo[i]
                hi_f = v > self._hi[i]
            p = not lo_f and not hi_f
            if not p:
                mask |= (1 << i)
            if lo_f:
                lo_mask |= (1 << i)
            if hi_f:
                hi_mask |= (1 << i)
            details.append({
                "name": self._names[i], "lo": self._lo[i], "hi": self._hi[i],
                "value": v, "passed": p, "lo_violated": lo_f, "hi_violated": hi_f,
            })
        vc = bin(mask).count("1")
        return {
            "error_mask": mask,
            "severity": int(_SEVERITY_TABLE[vc] if vc < len(_SEVERITY_TABLE) else Severity.CRITICAL),
            "violated_lo": lo_mask, "violated_hi": hi_mask,
            "violated_count": vc, "passed": mask == 0, "details": details,
        }

    def check_batch_detail(self, values) -> List[dict]:
        return [self.check_detail(v) for v in values]

    # ── Benchmark ───────────────────────────────────────────

    def benchmark(self, iterations: int = 1_000_000) -> float:
        """Returns checks/sec."""
        t0 = time.perf_counter()
        for i in range(iterations):
            self.check_mask((i % 1000) - 500)
        return iterations / (time.perf_counter() - t0)

    def benchmark_detail(self, iterations: int = 1_000_000) -> Dict:
        """Legacy benchmark returning dict."""
        rate = self.benchmark(iterations)
        return {
            "rate": rate, "rate_M": rate / 1e6,
            "total_ms": iterations / rate * 1000,
            "iterations": iterations, "constraints": self.n,
        }

    # ── Presets ─────────────────────────────────────────────

    @classmethod
    def from_preset(cls, name: str) -> "FluxExact":
        if name not in PRESETS:
            raise ValueError(f"Unknown preset: {name}. Available: {', '.join(PRESETS.keys())}")
        return cls(PRESETS[name])

    @classmethod
    def available_presets(cls) -> List[str]:
        return list(PRESETS.keys())


flux_check_exact = FluxExact


if __name__ == "__main__":
    fc = FluxExact([{"lo": -40, "hi": 150, "name": "coolant_temp"}])
    for v in [150, 151, -40, -41, float("nan"), float("inf"), float("-inf")]:
        m = fc.check_mask(v)
        print(f"  val={str(v):>6}: mask=0x{m:02x} passed={passed(m)} sev={severity(m).name}")

    print("\nBenchmark (automotive_can, 1M iterations):")
    fc_can = FluxExact.from_preset("automotive_can")
    rate = fc_can.benchmark()
    print(f"  {rate/1e6:.1f}M checks/sec")
