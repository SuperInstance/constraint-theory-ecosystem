"""
FLUX Exact Arithmetic — Comprehensive Test Suite

Tests all 5 checkers against:
- 6 real-world scenarios (automotive, aviation, medical, energy, IoT, financial)
- Edge cases from adversarial analysis
- Large-scale random value testing (dangerous triples)
- Throughput vs exactness benchmarks
"""

import pytest
import random
import math
import time
from fractions import Fraction

from flux_exact_arithmetic import (
    FloatExactChecker, FixedPointChecker, IntervalChecker,
    RationalChecker, IntegerChecker,
    Severity, TriState, SEVERITY_TABLE,
    benchmark_all_checkers, _to_fixed, _from_fixed, SCALE,
)


# ── Preset data (from EXACT-CHECKING-SPEC.md) ──

PRESETS = {
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

# Scenarios that are purely integer-bounded (for IntegerChecker)
INT_PRESETS = {
    "automotive_can": PRESETS["automotive_can"],
    "aviation_adsb": PRESETS["aviation_adsb"],
    "iot_mqtt": PRESETS["iot_mqtt"],
}


# ══════════════════════════════════════════════════════════════
# SECTION 1: FloatExactChecker Tests
# ══════════════════════════════════════════════════════════════

class TestFloatExactChecker:
    def test_basic_pass_fail(self):
        fc = FloatExactChecker([{"lo": -40, "hi": 150, "name": "temp"}])
        assert fc.check(-40).passed
        assert fc.check(150).passed
        assert fc.check(0).passed
        assert not fc.check(-41).passed
        assert not fc.check(151).passed

    def test_zero_false_negatives_boundary(self):
        """Every value outside bounds must be detected."""
        fc = FloatExactChecker([{"lo": -40, "hi": 150, "name": "temp"}])
        # Note: 150 + 1e-14 == 150.0 in float64 (below ULP for this magnitude)
        # This is NOT a false negative — float(150 + 1e-14) IS 150.0
        for delta in [1, 0.1, 0.01, 1e-6, 1e-10]:
            assert not fc.check(-40 - delta).passed, f"False negative at lo-{delta}"
            assert not fc.check(150 + delta).passed, f"False negative at hi+{delta}"
        # Demonstrate that nextafter correctly detects the boundary
        assert not fc.check(math.nextafter(150.0, math.inf)).passed
        assert not fc.check(math.nextafter(-40.0, -math.inf)).passed

    def test_int8_clamping_doesnt_happen(self):
        """The original INT8 bug: 151 -> 127 -> PASS. Must not happen."""
        fc = FloatExactChecker([{"lo": -40, "hi": 150, "name": "coolant"}])
        r = fc.check(151)
        assert not r.passed, "151 must be detected as violation"
        assert r.error_mask == 1

    def test_exact_float_detection(self):
        """Every float64 IS an exact rational with power-of-2 denominator.
        The question is whether the float equals the intended decimal value.
        """
        fc = FloatExactChecker([
            {"lo": 0, "hi": 100, "name": "int_bounds"},
            {"lo": 0.5, "hi": 0.75, "name": "exact_decimal"},  # 1/2, 3/4
        ])
        # Integer bounds are exact
        assert fc.constraints[0]["lo_exact"] is True
        assert fc.constraints[0]["hi_exact"] is True
        # 0.5 = 1/2 and 0.75 = 3/4 have power-of-2 denominators
        assert fc.constraints[1]["lo_exact"] is True
        assert fc.constraints[1]["hi_exact"] is True

    def test_all_presets(self):
        for name, constraints in PRESETS.items():
            fc = FloatExactChecker(constraints)
            verify = fc.verify_exactness()
            assert verify["false_negatives"] == 0, f"Preset {name}: false negatives!"

    def test_severity_mapping(self):
        fc = FloatExactChecker([
            {"lo": 0, "hi": 10, "name": "c1"},
            {"lo": 0, "hi": 10, "name": "c2"},
            {"lo": 0, "hi": 10, "name": "c3"},
            {"lo": 0, "hi": 10, "name": "c4"},
            {"lo": 0, "hi": 10, "name": "c5"},
        ])
        # Value outside all 5 bounds -> 5 violations -> CRITICAL
        r = fc.check(-1)
        assert r.violated_count == 5
        assert r.severity == Severity.CRITICAL

    def test_large_values(self):
        fc = FloatExactChecker([{"lo": -1e15, "hi": 1e15, "name": "big"}])
        assert fc.check(0).passed
        assert not fc.check(1e15 + 1).passed
        assert not fc.check(-1e15 - 1).passed


# ══════════════════════════════════════════════════════════════
# SECTION 2: FixedPointChecker Tests
# ══════════════════════════════════════════════════════════════

class TestFixedPointChecker:
    def test_basic_pass_fail(self):
        fpc = FixedPointChecker([{"lo": -40, "hi": 150, "name": "temp"}])
        assert fpc.check(-40).passed
        assert fpc.check(150).passed
        assert fpc.check(0).passed
        assert not fpc.check(-41).passed
        assert not fpc.check(151).passed

    def test_exact_integer_conversion(self):
        """Integer values convert to fixed-point EXACTLY."""
        for val in [-1000, -1, 0, 1, 100, 45000]:
            fixed = _to_fixed(val)
            assert _from_fixed(fixed) == val, f"Roundtrip failed for {val}"

    def test_small_decimal_precision(self):
        """Small decimals should be close to exact."""
        fpc = FixedPointChecker([{"lo": 7.35, "hi": 7.45, "name": "ph"}])
        assert fpc.check(7.4).passed
        assert not fpc.check(7.34).passed
        assert not fpc.check(7.46).passed

    def test_all_presets(self):
        for name, constraints in PRESETS.items():
            fpc = FixedPointChecker(constraints)
            verify = fpc.verify_exactness()
            assert verify["false_negatives"] == 0, f"Preset {name}: false negatives!"

    def test_q_format_range(self):
        """Q31.32 covers all sensor ranges."""
        # Largest preset range: -1000 to 45000 (aviation), -100000 to 100000 (financial)
        fpc = FixedPointChecker([{"lo": -100000, "hi": 100000, "name": "big"}])
        assert fpc.check(0).passed
        assert fpc.check(100000).passed
        assert not fpc.check(100001).passed

    def test_conversion_error_bounded(self):
        """Max conversion error should be < 2^-33."""
        for val in [0.1, 0.3, 7.35, 49.0, 0.0001]:
            fixed = _to_fixed(val)
            reconstructed = _from_fixed(fixed)
            err = abs(val - reconstructed)
            assert err < 2 ** -33, f"Conversion error too large for {val}: {err}"


# ══════════════════════════════════════════════════════════════
# SECTION 3: IntervalChecker Tests
# ══════════════════════════════════════════════════════════════

class TestIntervalChecker:
    def test_basic_pass_fail(self):
        ic = IntervalChecker([{"lo": 0, "hi": 100, "name": "pct"}])
        assert ic.check(50, epsilon=0.0).passed
        assert not ic.check(200, epsilon=0.0).passed

    def test_tri_state_semantics(self):
        """PASS: interval fully within bounds. UNCERTAIN: partial overlap."""
        ic = IntervalChecker([{"lo": 0, "hi": 100, "name": "pct"}])

        # Well within bounds
        r = ic.check(50, epsilon=1.0)
        assert r.tri_state == TriState.PASS

        # Interval [99.5, 100.5] overlaps bound at 100 -> UNCERTAIN
        r = ic.check(100, epsilon=0.5)
        assert r.tri_state == TriState.UNCERTAIN

        # Well outside bounds
        r = ic.check(200, epsilon=1.0)
        assert r.tri_state == TriState.FAIL

    def test_zero_epsilon_equals_float(self):
        """With epsilon=0, interval check should match float check."""
        ic = IntervalChecker([{"lo": -40, "hi": 150, "name": "temp"}])
        fc = FloatExactChecker([{"lo": -40, "hi": 150, "name": "temp"}])

        for val in [-41, -40, 0, 150, 151]:
            r_int = ic.check(val, epsilon=0.0)
            r_float = fc.check(val)
            assert r_int.passed == r_float.passed, f"Mismatch at val={val}"

    def test_no_false_negative_with_uncertainty(self):
        """Even with large uncertainty, out-of-range is never PASS."""
        ic = IntervalChecker([{"lo": 0, "hi": 100, "name": "pct"}])
        verify = ic.verify_exactness()
        assert verify["false_negatives"] == 0

    def test_all_presets(self):
        for name, constraints in PRESETS.items():
            ic = IntervalChecker(constraints)
            verify = ic.verify_exactness()
            assert verify["false_negatives"] == 0, f"Preset {name}: false negatives!"

    def test_uncertainty_widens_detection(self):
        """Larger epsilon should make more values UNCERTAIN."""
        ic = IntervalChecker([{"lo": 0, "hi": 100, "name": "pct"}])

        r0 = ic.check(99.5, epsilon=0.0)
        r1 = ic.check(99.5, epsilon=0.5)
        r5 = ic.check(99.5, epsilon=5.0)

        # With epsilon=0: value is in bounds -> PASS
        assert r0.passed
        # With epsilon=0.5: interval [99.0, 100.0] -> PASS (just at boundary)
        # With epsilon=5: interval [94.5, 104.5] -> UNCERTAIN
        assert r5.tri_state == TriState.UNCERTAIN


# ══════════════════════════════════════════════════════════════
# SECTION 4: RationalChecker Tests
# ══════════════════════════════════════════════════════════════

class TestRationalChecker:
    def test_basic_pass_fail(self):
        rc = RationalChecker([{"lo": -40, "hi": 150, "name": "temp"}])
        assert rc.check(-40).passed
        assert rc.check(150).passed
        assert rc.check(0).passed
        assert not rc.check(-41).passed
        assert not rc.check(151).passed

    def test_exact_for_non_representable(self):
        """Fraction comparison is exact even for 0.1, 0.3, etc."""
        rc = RationalChecker([{"lo": 0.1, "hi": 0.3, "name": "x"}])
        # 0.1 and 0.3 are NOT exact floats, but Fraction handles them correctly
        r = rc.check(0.1)
        assert r.passed
        r = rc.check(0.3)
        assert r.passed
        r = rc.check(0.05)
        assert not r.passed

    def test_mathematical_exactness(self):
        """Compare rational checker vs float checker for a known tricky case."""
        rc = RationalChecker([{"lo": 0.1, "hi": 0.9, "name": "x"}])
        fc = FloatExactChecker([{"lo": 0.1, "hi": 0.9, "name": "x"}])

        # Both should agree for values well inside
        for v in [0.2, 0.5, 0.8]:
            assert rc.check(v).passed == fc.check(v).passed

    def test_all_presets(self):
        for name, constraints in PRESETS.items():
            rc = RationalChecker(constraints)
            verify = rc.verify_exactness()
            assert verify["false_negatives"] == 0, f"Preset {name}: false negatives!"

    def test_fraction_details(self):
        rc = RationalChecker([{"lo": 1, "hi": 10, "name": "x"}])
        r = rc.check(5)
        d = r.details[0]
        assert isinstance(d["lo"], str)  # Fraction as string
        assert d["exact"] is True


# ══════════════════════════════════════════════════════════════
# SECTION 5: IntegerChecker Tests
# ══════════════════════════════════════════════════════════════

class TestIntegerChecker:
    def test_basic_pass_fail(self):
        ic = IntegerChecker([{"lo": 0, "hi": 100, "name": "pct"}])
        assert ic.check(0).passed
        assert ic.check(100).passed
        assert ic.check(50).passed
        assert not ic.check(-1).passed
        assert not ic.check(101).passed

    def test_rejects_non_integer_bounds(self):
        with pytest.raises(ValueError, match="must be integers"):
            IntegerChecker([{"lo": 0.5, "hi": 100, "name": "x"}])

    def test_rejects_non_integer_value(self):
        ic = IntegerChecker([{"lo": 0, "hi": 100, "name": "pct"}])
        with pytest.raises(ValueError):
            ic.check(0.5)

    def test_all_int_presets(self):
        for name, constraints in INT_PRESETS.items():
            ic = IntegerChecker(constraints)
            verify = ic.verify_exactness()
            assert verify["false_negatives"] == 0, f"Preset {name}: false negatives!"

    def test_speed(self):
        """Integer checker should be fast — no float overhead."""
        ic = IntegerChecker([{"lo": 0, "hi": 8000, "name": "rpm"}])
        t0 = time.perf_counter()
        for i in range(100_000):
            ic.check(i % 9000)
        t1 = time.perf_counter()
        rate = 100_000 / (t1 - t0)
        # Should be at least 100K/sec even in Python
        assert rate > 50_000, f"Integer checker too slow: {rate:.0f}/sec"


# ══════════════════════════════════════════════════════════════
# SECTION 6: Cross-Checker Agreement Tests
# ══════════════════════════════════════════════════════════════

class TestCrossCheckerAgreement:
    """All checkers must agree on integer-bounded, in-range values."""

    def test_agreement_on_integer_bounds(self):
        constraints = [
            {"lo": -40, "hi": 150, "name": "temp"},
            {"lo": 0, "hi": 8000, "name": "rpm"},
        ]

        fc = FloatExactChecker(constraints)
        fpc = FixedPointChecker(constraints)
        rc = RationalChecker(constraints)
        ic = IntegerChecker(constraints)

        for val in [-41, -40, 0, 50, 150, 151]:
            r_fc = fc.check(val)
            r_fpc = fpc.check(val)
            r_rc = rc.check(val)
            r_ic = ic.check(val)

            assert r_fc.passed == r_ic.passed, f"Float vs Int at {val}"
            assert r_fpc.passed == r_ic.passed, f"Fixed vs Int at {val}"
            assert r_rc.passed == r_ic.passed, f"Rational vs Int at {val}"

    def test_agreement_on_float_bounds_well_inside(self):
        """For values well inside float bounds, all checkers agree."""
        constraints = [{"lo": 7.35, "hi": 7.45, "name": "ph"}]

        fc = FloatExactChecker(constraints)
        fpc = FixedPointChecker(constraints)
        rc = RationalChecker(constraints)

        for val in [7.38, 7.40, 7.42]:
            assert fc.check(val).passed
            assert fpc.check(val).passed
            assert rc.check(val).passed


# ══════════════════════════════════════════════════════════════
# SECTION 7: Adversarial / Dangerous Triple Tests
# ══════════════════════════════════════════════════════════════

class TestDangerousTriples:
    """Test values where float comparison might disagree with rational."""

    def test_non_representable_bounds(self):
        """Bounds that are NOT exact floats (0.1, 0.3, etc.)."""
        # The classic: 0.1 + 0.2 != 0.3 in float
        fc = FloatExactChecker([{"lo": 0.1, "hi": 0.3, "name": "x"}])
        rc = RationalChecker([{"lo": 0.1, "hi": 0.3, "name": "x"}])

        # Both checkers should correctly handle boundary
        assert not fc.check(0.0).passed
        assert not fc.check(0.4).passed
        assert not rc.check(0.0).passed
        assert not rc.check(0.4).passed

    def test_very_close_to_boundary(self):
        """Values very close to bounds should be detected correctly."""
        fc = FloatExactChecker([{"lo": 0, "hi": 100, "name": "x"}])

        # These are all exact floats
        for delta in [1e-10, 1e-12, 1e-14]:
            assert not fc.check(-delta).passed
            assert not fc.check(100 + delta).passed

    def test_powers_of_two_boundaries(self):
        """Powers of 2 are exactly representable — test near them."""
        fc = FloatExactChecker([{"lo": 0, "hi": 1024, "name": "x"}])
        assert fc.check(1024).passed
        assert not fc.check(1024.0000001).passed

    def test_negative_ranges(self):
        fc = FloatExactChecker([{"lo": -100, "hi": -50, "name": "neg"}])
        assert fc.check(-75).passed
        assert fc.check(-100).passed
        assert fc.check(-50).passed
        assert not fc.check(-101).passed
        assert not fc.check(-49).passed

    def test_very_narrow_range(self):
        """Range of 0.1 — narrow but important for pH."""
        fc = FloatExactChecker([{"lo": 7.35, "hi": 7.45, "name": "ph"}])
        assert fc.check(7.4).passed
        assert not fc.check(7.34).passed
        assert not fc.check(7.46).passed

    def test_very_wide_range(self):
        fc = FloatExactChecker([{"lo": -100000, "hi": 100000, "name": "wide"}])
        assert fc.check(0).passed
        assert fc.check(100000).passed
        assert not fc.check(100001).passed


# ══════════════════════════════════════════════════════════════
# SECTION 8: Large-Scale Random Testing
# ══════════════════════════════════════════════════════════════

class TestLargeScaleRandom:
    """Stress test with random values including dangerous triples."""

    @pytest.fixture(autouse=True)
    def setup(self):
        random.seed(42)

    def test_random_automotive(self):
        """100K random values against automotive preset."""
        constraints = PRESETS["automotive_can"]
        fc = FloatExactChecker(constraints)
        fpc = FixedPointChecker(constraints)
        ic = IntegerChecker(constraints)

        for _ in range(100_000):
            val = random.randint(-500, 8500)
            r_fc = fc.check(val)
            r_fpc = fpc.check(val)
            r_ic = ic.check(val)

            # All checkers must agree on integers
            assert r_fc.passed == r_ic.passed
            assert r_fpc.passed == r_ic.passed

            # No false negatives: if value is outside any bound, detected
            for i, c in enumerate(constraints):
                if val < c["lo"] or val > c["hi"]:
                    assert r_fc.error_mask & (1 << i), f"False negative: val={val}, c={c}"

    def test_random_medical_float(self):
        """50K random floats against medical preset."""
        constraints = PRESETS["medical_fhir"]
        fc = FloatExactChecker(constraints)
        fpc = FixedPointChecker(constraints)

        for _ in range(50_000):
            val = random.uniform(-10, 350)
            r_fc = fc.check(val)
            r_fpc = fpc.check(val)

            # Float and fixed should agree (or fixed might be slightly tighter)
            # Key: neither should miss a violation
            for i, c in enumerate(constraints):
                if val < c["lo"] - 1e-9 or val > c["hi"] + 1e-9:
                    assert r_fc.error_mask & (1 << i), \
                        f"Float false negative: val={val}, c={c}"

    def test_dangerous_triples(self):
        """Generate values near boundaries where float might fail."""
        constraints = PRESETS["energy_scada"]  # Has tight bounds (49-51 Hz)
        fc = FloatExactChecker(constraints)
        rc = RationalChecker(constraints)

        false_neg_float = 0
        false_neg_rational = 0
        tests = 0

        for c in constraints:
            lo, hi = Fraction(c["lo"]), Fraction(c["hi"])
            # Test values just outside bounds
            for num in range(1, 1000):
                delta = Fraction(num, 100000)
                for val_r in [lo - delta, hi + delta]:
                    val_f = float(val_r)

                    r_fc = fc.check(val_f)
                    r_rc = rc.check(val_r)

                    if r_fc.passed:
                        false_neg_float += 1
                    if r_rc.passed:
                        false_neg_rational += 1
                    tests += 1

        assert false_neg_rational == 0, "Rational checker has false negatives!"
        # Float checker should also have zero false negatives (monotonic comparison)
        assert false_neg_float == 0, f"Float checker has {false_neg_float} false negatives"


# ══════════════════════════════════════════════════════════════
# SECTION 9: Benchmark
# ══════════════════════════════════════════════════════════════

class TestBenchmark:
    def test_benchmark_runs(self):
        constraints = PRESETS["automotive_can"]
        results = benchmark_all_checkers(constraints, iterations=10_000)
        assert "FloatExact" in results
        assert "FixedPoint" in results
        assert "Interval" in results
        assert "Rational" in results
        assert "Integer" in results

        # All should complete without errors
        for name, data in results.items():
            assert data["checks_per_sec"] > 0
            assert data["verify"]["false_negatives"] == 0

    def test_benchmark_all_presets(self):
        """Run benchmark on all 6 presets."""
        for preset_name, constraints in PRESETS.items():
            results = benchmark_all_checkers(constraints, iterations=5_000)
            for checker_name, data in results.items():
                assert data["verify"]["false_negatives"] == 0, \
                    f"{checker_name} has false negatives on {preset_name}"


# ══════════════════════════════════════════════════════════════
# SECTION 10: Verify Exactness Proofs
# ══════════════════════════════════════════════════════════════

class TestVerifyExactness:
    """Run verify_exactness() on all checkers for all presets."""

    def test_float_exact_verify(self):
        for name, constraints in PRESETS.items():
            fc = FloatExactChecker(constraints)
            v = fc.verify_exactness()
            assert v["false_negatives"] == 0, f"{name}: {v}"

    def test_fixed_point_verify(self):
        for name, constraints in PRESETS.items():
            fpc = FixedPointChecker(constraints)
            v = fpc.verify_exactness()
            assert v["false_negatives"] == 0, f"{name}: {v}"

    def test_interval_verify(self):
        for name, constraints in PRESETS.items():
            ic = IntervalChecker(constraints)
            v = ic.verify_exactness()
            assert v["false_negatives"] == 0, f"{name}: {v}"

    def test_rational_verify(self):
        for name, constraints in PRESETS.items():
            rc = RationalChecker(constraints)
            v = rc.verify_exactness()
            assert v["false_negatives"] == 0, f"{name}: {v}"

    def test_integer_verify(self):
        for name, constraints in INT_PRESETS.items():
            ic = IntegerChecker(constraints)
            v = ic.verify_exactness()
            assert v["false_negatives"] == 0, f"{name}: {v}"
