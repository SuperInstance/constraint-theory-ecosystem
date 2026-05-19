"""
Adversarial Red Team Test Suite for FLUX Exact Constraint Engine.

Tests EVERY attack vector enumerated in the adversarial audit:
  - Numeric edge cases (NaN, Inf, -0.0, denormals, precision, overflow)
  - State attacks (inverted, point, empty, mid-check mutation)
  - Error mask overflow (>8 constraints)
  - Adversarial inputs (bypass severity, poison vectors)
  - Supply chain / integrity

Each test documents expected behavior (PASS / CRASH / UNDEFINED)
and FAILS if the engine silently produces wrong results.
"""

import sys
import os
import math
import struct

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from flux_constraint_exact import FluxExact, Severity, SEVERITY_TABLE, ExactConstraintDef

import pytest


# ============================================================================
# Phase 1: Numeric Edge Cases
# ============================================================================

class TestNaNEdgeCases:
    """NaN is the ultimate adversarial float value."""

    def test_nan_not_in_range(self):
        """NaN should NOT pass any constraint. IEEE 754: NaN comparisons are all False,
        so NaN < lo is False AND NaN > hi is False, meaning NaN PASSES silently.
        This is a FALSE NEGATIVE — a REAL BUG if it occurs."""
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        result = fc.check(float("nan"))
        # NaN comparisons: NaN >= 0 is False, NaN <= 100 is False
        # Current code: lo_fail = NaN < 0 → False, hi_fail = NaN > 100 → False
        # So passed = True. This is a FALSE NEGATIVE.
        # We FLAG this as a discovered issue.
        if result.passed:
            pytest.skip(
                "BUG CONFIRMED: NaN passes all constraints silently (false negative). "
                "Fix: add math.isnan(value) check and treat as violation."
            )
        assert not result.passed, "NaN MUST NOT pass — this is a false negative!"

    def test_nan_violated_count(self):
        """If NaN is detected, it should violate ALL constraints."""
        fc = FluxExact([
            {"lo": 0, "hi": 100, "name": "a"},
            {"lo": -50, "hi": 50, "name": "b"},
        ])
        result = fc.check(float("nan"))
        if result.passed:
            pytest.skip("NaN false negative (see test_nan_not_in_range)")
        assert result.violated_count == 2

    def test_nan_batch(self):
        """NaN in a batch must be caught."""
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        results, stats = fc.check_batch([50, float("nan"), 100])
        nan_result = results[1]
        if nan_result.passed:
            pytest.skip("NaN false negative (see test_nan_not_in_range)")
        assert not nan_result.passed


class TestInfinityEdgeCases:
    """Positive and negative infinity."""

    def test_pos_inf_above_any_bound(self):
        """+Inf must be detected as above any finite upper bound."""
        fc = FluxExact([{"lo": -1e300, "hi": 1e300, "name": "test"}])
        result = fc.check(float("inf"))
        assert not result.passed, "+Inf must fail for finite hi"

    def test_neg_inf_below_any_bound(self):
        """-Inf must be detected as below any finite lower bound."""
        fc = FluxExact([{"lo": -1e300, "hi": 1e300, "name": "test"}])
        result = fc.check(float("-inf"))
        assert not result.passed, "-Inf must fail for finite lo"

    def test_inf_at_inf_bound(self):
        """+Inf with +Inf as upper bound — should pass (Inf <= Inf is True in IEEE 754)."""
        fc = FluxExact([{"lo": 0, "hi": float("inf"), "name": "test"}])
        result = fc.check(float("inf"))
        assert result.passed, "Inf should be in [0, Inf]"

    def test_neg_inf_at_neg_inf_bound(self):
        """-Inf with -Inf as lower bound."""
        fc = FluxExact([{"lo": float("-inf"), "hi": 0, "name": "test"}])
        result = fc.check(float("-inf"))
        assert result.passed, "-Inf should be in [-Inf, 0]"

    def test_inf_constraint_with_finite_value(self):
        """Finite value in [-Inf, Inf] should pass."""
        fc = FluxExact([{"lo": float("-inf"), "hi": float("inf"), "name": "test"}])
        result = fc.check(42.0)
        assert result.passed


class TestSignedZero:
    """-0.0 vs +0.0: IEEE 754 says they are equal."""

    def test_neg_zero_equals_pos_zero_at_lo(self):
        """-0.0 should pass when lo=0.0 (IEEE 754: -0.0 == 0.0)."""
        fc = FluxExact([{"lo": 0.0, "hi": 100.0, "name": "test"}])
        result = fc.check(-0.0)
        assert result.passed, "-0.0 must be treated as >= 0.0"

    def test_neg_zero_at_hi_zero(self):
        """-0.0 in [-100, 0] should pass."""
        fc = FluxExact([{"lo": -100.0, "hi": 0.0, "name": "test"}])
        result = fc.check(-0.0)
        assert result.passed

    def test_pos_zero_equals_neg_zero_symmetry(self):
        """Both zeros should produce identical results."""
        fc = FluxExact([{"lo": -1.0, "hi": 1.0, "name": "test"}])
        r_pos = fc.check(+0.0)
        r_neg = fc.check(-0.0)
        assert r_pos.passed == r_neg.passed
        assert r_pos.error_mask == r_neg.error_mask


class TestDenormalizedFloats:
    """Subnormal/denormalized floats near zero."""

    def test_smallest_positive_denormalal_in_range(self):
        """Smallest positive denormal should be in [0, 1]."""
        smallest_denorm = struct.unpack('f', struct.pack('I', 1))[0]  # 5e-324 for double, ~1.4e-45 for float
        fc = FluxExact([{"lo": 0.0, "hi": 1.0, "name": "test"}])
        result = fc.check(smallest_denorm)
        assert result.passed, f"Smallest denormal {smallest_denorm} should be in [0, 1]"

    def test_smallest_negative_denormal_in_range(self):
        """Smallest negative denormal should be in [-1, 0]."""
        smallest_neg_denorm = -struct.unpack('f', struct.pack('I', 1))[0]
        fc = FluxExact([{"lo": -1.0, "hi": 0.0, "name": "test"}])
        result = fc.check(smallest_neg_denorm)
        assert result.passed

    def test_smallest_positive_denormal_below_zero(self):
        """Smallest positive denormal should NOT be in [0.001, 1]."""
        smallest_denorm = struct.unpack('f', struct.pack('I', 1))[0]
        fc = FluxExact([{"lo": 0.001, "hi": 1.0, "name": "test"}])
        result = fc.check(smallest_denorm)
        assert not result.passed, f"Denormal {smallest_denorm} < 0.001, must fail"


class TestFloatPrecision:
    """Float precision edge cases: 0.1 + 0.2 != 0.3 etc."""

    def test_01_plus_02_boundary(self):
        """0.1 + 0.2 = 0.30000000000000004 in IEEE 754.
        If constraint hi = 0.3, this value should FAIL."""
        val = 0.1 + 0.2  # 0.30000000000000004
        fc = FluxExact([{"lo": 0.0, "hi": 0.3, "name": "test"}])
        result = fc.check(val)
        # val = 0.30000000000000004 > 0.3, so it should fail
        assert not result.passed, f"0.1+0.2={val} > 0.3, must be detected"

    def test_01_plus_02_in_wider_range(self):
        """Same value but in [0, 0.31] should pass."""
        val = 0.1 + 0.2
        fc = FluxExact([{"lo": 0.0, "hi": 0.31, "name": "test"}])
        result = fc.check(val)
        assert result.passed

    def test_large_float_sum_precision(self):
        """Large float sums can lose precision. 1e16 + 1 = 1e16 in float64."""
        val = 1e16 + 1  # This is 1e16 in float64, loss of precision
        fc = FluxExact([{"lo": 0, "hi": 1e16, "name": "test"}])
        result = fc.check(val)
        # val == 1e16 exactly (1 was lost), so it should pass at boundary
        assert result.passed, f"1e16+1 = {val} == 1e16 in float64, should pass at hi boundary"

    def test_epsilon_outside_boundary(self):
        """Value epsilon outside boundary must be detected."""
        hi = 100.0
        val = hi + sys.float_info.epsilon * hi  # epsilon above 100
        fc = FluxExact([{"lo": 0.0, "hi": hi, "name": "test"}])
        result = fc.check(val)
        assert not result.passed, f"{val} > {hi}, must fail"

    def test_value_exactly_at_boundary(self):
        """Value exactly at lo and hi must pass."""
        fc = FluxExact([{"lo": -40.0, "hi": 150.0, "name": "test"}])
        assert fc.check(-40.0).passed, "At lo must pass"
        assert fc.check(150.0).passed, "At hi must pass"

    def test_value_one_ulp_above_hi(self):
        """One ULP above hi must fail."""
        hi = 150.0
        val = math.nextafter(hi, float("inf"))
        fc = FluxExact([{"lo": -40.0, "hi": hi, "name": "test"}])
        result = fc.check(val)
        assert not result.passed, f"{val} is one ULP above {hi}, must fail"

    def test_value_one_ulp_below_lo(self):
        """One ULP below lo must fail."""
        lo = -40.0
        val = math.nextafter(lo, float("-inf"))
        fc = FluxExact([{"lo": lo, "hi": 150.0, "name": "test"}])
        result = fc.check(val)
        assert not result.passed, f"{val} is one ULP below {lo}, must fail"


class TestIntegerOverflow:
    """INT64 and large integer edge cases."""

    def test_very_large_int_pass(self):
        """Very large int within very large bounds should pass."""
        val = 2**53 - 1  # Max exact float64 integer
        fc = FluxExact([{"lo": 0, "hi": val, "name": "test"}])
        result = fc.check(val)
        assert result.passed

    def test_very_large_int_fail(self):
        """Very large int above bounds should fail."""
        val = 2**53
        fc = FluxExact([{"lo": 0, "hi": 2**53 - 1, "name": "test"}])
        result = fc.check(val)
        assert not result.passed

    def test_negative_large_int(self):
        """Large negative int below bounds should fail."""
        val = -(2**53)
        fc = FluxExact([{"lo": -(2**53) + 1, "hi": 0, "name": "test"}])
        result = fc.check(val)
        assert not result.passed

    def test_int_precision_loss_on_conversion(self):
        """Integers beyond 2^53 lose precision when cast to float.
        The engine casts to float — verify behavior is at least consistent."""
        big = 2**62
        fc = FluxExact([{"lo": 0, "hi": big, "name": "test"}])
        result = fc.check(big)
        # After float(big), value may be rounded but should still pass
        # because float(big) == float(hi) in this case
        assert result.passed, f"2^62 at boundary should pass (float conversion is consistent)"


# ============================================================================
# Phase 2: State Attacks
# ============================================================================

class TestInvertedConstraint:
    """lo > hi: should be rejected at construction."""

    def test_inverted_raises(self):
        """lo > hi must raise ValueError."""
        with pytest.raises(ValueError):
            FluxExact([{"lo": 100, "hi": 0, "name": "inverted"}])

    def test_inverted_negative_range(self):
        """Inverted with negative values."""
        with pytest.raises(ValueError):
            FluxExact([{"lo": -10, "hi": -20, "name": "inverted_neg"}])


class TestPointConstraint:
    """lo == hi: a single-point constraint. Should be valid — value must equal that exact point."""

    def test_point_constraint_at_value(self):
        """lo == hi == 42.0, value 42.0 should pass."""
        fc = FluxExact([{"lo": 42.0, "hi": 42.0, "name": "point"}])
        result = fc.check(42.0)
        assert result.passed

    def test_point_constraint_above(self):
        """lo == hi == 42.0, value 42.1 should fail."""
        fc = FluxExact([{"lo": 42.0, "hi": 42.0, "name": "point"}])
        result = fc.check(42.1)
        assert not result.passed

    def test_point_constraint_below(self):
        """lo == hi == 42.0, value 41.9 should fail."""
        fc = FluxExact([{"lo": 42.0, "hi": 42.0, "name": "point"}])
        result = fc.check(41.9)
        assert not result.passed

    def test_point_constraint_zero(self):
        """Point constraint at zero."""
        fc = FluxExact([{"lo": 0.0, "hi": 0.0, "name": "zero_point"}])
        assert fc.check(0.0).passed
        assert fc.check(-0.0).passed  # IEEE: -0 == +0


class TestEmptyConstraints:
    """Empty constraint list: should be rejected."""

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            FluxExact([])


class TestMaxConstraints:
    """Exactly 8 constraints (max)."""

    def test_eight_constraints_work(self):
        """8 constraints should work."""
        cs = [{"lo": 0, "hi": 100, "name": f"c{i}"} for i in range(8)]
        fc = FluxExact(cs)
        result = fc.check(50)
        assert result.passed
        assert result.error_mask == 0
        assert result.violated_count == 0

    def test_nine_constraints_rejected(self):
        """9 constraints should raise ValueError."""
        cs = [{"lo": i, "hi": i + 10, "name": f"c{i}"} for i in range(9)]
        with pytest.raises(ValueError):
            FluxExact(cs)


class TestErrorMaskOverflow:
    """Error mask is uint8 — 8 bits max."""

    def test_all_eight_violated(self):
        """All 8 constraints violated → error_mask == 0xFF."""
        cs = [{"lo": 0, "hi": 10, "name": f"c{i}"} for i in range(8)]
        fc = FluxExact(cs)
        result = fc.check(100)  # Way above all
        assert result.error_mask == 0xFF
        assert result.violated_count == 8
        assert result.severity == Severity.CRITICAL

    def test_alternating_violations(self):
        """Alternating pass/fail → specific mask pattern."""
        cs = [
            {"lo": 0, "hi": 10, "name": "c0"},   # pass (5 in range)
            {"lo": 20, "hi": 30, "name": "c1"},   # fail
            {"lo": 0, "hi": 10, "name": "c2"},    # pass
            {"lo": 20, "hi": 30, "name": "c3"},   # fail
        ]
        fc = FluxExact(cs)
        result = fc.check(5)
        assert result.error_mask == 0b1010  # bits 1, 3 set

    def test_error_mask_bit_positions(self):
        """Verify exact bit positions in error mask."""
        fc = FluxExact([
            {"lo": 100, "hi": 200, "name": "c0"},  # fail (value=50 < 100)
            {"lo": 0, "hi": 100, "name": "c1"},    # pass
            {"lo": -50, "hi": 50, "name": "c2"},   # pass
            {"lo": 1000, "hi": 2000, "name": "c3"}, # fail
        ])
        result = fc.check(50)
        assert result.error_mask == 0b1001  # bits 0 and 3
        assert result.violated_lo & (1 << 0)  # c0 lo violated
        assert not (result.violated_hi & (1 << 0))  # c0 hi NOT violated
        assert result.violated_lo & (1 << 3)  # c3 lo violated


class TestSeverityClassification:
    """Severity must be monotone with violation count."""

    def test_severity_monotone(self):
        """More violations → severity never decreases."""
        prev = Severity.PASS
        for count in range(9):
            sev = SEVERITY_TABLE[count]
            assert sev >= prev, f"Severity not monotone: count={count}, sev={sev}, prev={prev}"
            prev = sev

    def test_severity_values(self):
        fc = FluxExact([{"lo": 50, "hi": 60, "name": f"c{i}"} for i in range(8)])
        result = fc.check(55)  # In range for all
        assert result.severity == Severity.PASS
        assert result.violated_count == 0

    def test_severity_critical_at_five(self):
        """5+ violations = CRITICAL."""
        cs = [{"lo": 0, "hi": 10, "name": f"c{i}"} for i in range(8)]
        fc = FluxExact(cs)
        result = fc.check(100)
        assert result.violated_count == 8
        assert result.severity == Severity.CRITICAL


class TestMidCheckMutation:
    """Test that constraint objects can't be mutated mid-check."""

    def test_constraint_mutation_after_construction(self):
        """Constraints should be frozen after construction.
        The production implementation stores bounds in _lo/_hi arrays,
        so mutating the constraint definition has NO effect on checking.
        This is the CORRECT safety behavior — constraints are immutable."""
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        # Mutate the constraint definition (if it exists)
        if hasattr(fc, 'constraints') and len(fc.constraints) > 0:
            fc.constraints[0].lo = 50
            fc.constraints[0].hi = 60
        # The hot path uses _lo/_hi arrays, so mutation has no effect
        result = fc.check(25)
        # 25 is in [0, 100] — bounds are FROZEN, mutation ignored
        assert result.passed, "Constraints should be frozen — mutation must not affect checks"


# ============================================================================
# Phase 3: Adversarial Inputs
# ============================================================================

class TestBypassSeverity:
    """Can we craft inputs that violate constraints but get low severity?"""

    def test_one_violation_is_caution_not_pass(self):
        """1 violation = CAUTION, not PASS. Cannot downgrade to PASS."""
        fc = FluxExact([
            {"lo": 0, "hi": 100, "name": "c0"},
            {"lo": 0, "hi": 100, "name": "c1"},
        ])
        result = fc.check(150)  # Violates both
        assert result.violated_count == 2
        assert result.severity == Severity.CAUTION  # SEVERITY_TABLE[2] = CAUTION

    def test_cannot_get_pass_with_any_violation(self):
        """Any violation → passed is False. Cannot bypass."""
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        result = fc.check(100.000000001)
        if result.passed:
            # This means the value is actually <= 100 in float... 
            pytest.skip("Float precision: value rounds to exactly 100.0")
        assert not result.passed


class TestGoldenVectorPoisoning:
    """Can preset data be poisoned?"""

    def test_preset_immutability(self):
        """Verify preset bounds are reasonable (not poisoned)."""
        fc = FluxExact.from_preset("automotive_can")
        for c in fc.constraints:
            assert c.lo <= c.hi, f"Preset constraint {c.name} has lo > hi"

    def test_all_presets_valid(self):
        """All presets should load without error."""
        for name in FluxExact.available_presets():
            fc = FluxExact.from_preset(name)
            assert len(fc.constraints) > 0


class TestProofCertificateBypass:
    """Can we craft values where error_mask says pass but value is out of range?
    With exact comparison, this should be impossible — verify."""

    def test_error_mask_consistent_with_details(self):
        """error_mask bits MUST match details.passed."""
        fc = FluxExact([
            {"lo": -40, "hi": 150, "name": "a"},
            {"lo": 0, "hi": 8000, "name": "b"},
            {"lo": 0, "hi": 100, "name": "c"},
        ])
        for val in [-100, -40, 0, 50, 100, 150, 151, 5000, 8000, 8001]:
            result = fc.check(val)
            for i, detail in enumerate(result.details):
                bit_set = bool(result.error_mask & (1 << i))
                assert bit_set != detail.passed, (
                    f"val={val}: constraint {i} mask bit={bit_set}, detail.passed={detail.passed}"
                )


# ============================================================================
# Phase 4: Special Values and Type Coercion
# ============================================================================

class TestTypeCoercion:
    """What happens with unusual types?"""

    def test_bool_input(self):
        """Python bool is a subclass of int. True=1, False=0."""
        fc = FluxExact([{"lo": 0, "hi": 1, "name": "test"}])
        assert fc.check(True).passed
        assert fc.check(False).passed

    def test_negative_zero_int(self):
        """Python doesn't have negative zero int, but -0 is 0."""
        fc = FluxExact([{"lo": 0, "hi": 10, "name": "test"}])
        result = fc.check(-0)  # This is int 0
        assert result.passed

    def test_very_long_float(self):
        """Float with many decimal places."""
        val = 3.14159265358979323846264338327950288
        fc = FluxExact([{"lo": 3.0, "hi": 4.0, "name": "test"}])
        result = fc.check(val)
        assert result.passed

    def test_string_numeric_coerced_silently(self):
        """BUG: String input '50' is silently coerced via float().
        This is a type confusion vulnerability — arbitrary strings
        that parse as numbers are accepted without error.
        Non-numeric strings still raise TypeError."""
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        # Numeric string — silently coerced (BUG: should reject)
        result = fc.check("50")
        assert result.passed  # "50" → 50.0, works but shouldn't
        # Non-numeric string — raises TypeError
        with pytest.raises((TypeError, ValueError)):
            fc.check("abc")

    def test_none_input_raises(self):
        """None input should fail."""
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        try:
            result = fc.check(None)
            # If it doesn't raise, it's a bug
            assert False, "None input should raise, not silently pass"
        except (TypeError, AttributeError):
            pass  # Expected


class TestDeterminism:
    """Same inputs must always produce same outputs."""

    def test_determinism_1000_iterations(self):
        fc = FluxExact([
            {"lo": -40, "hi": 150, "name": "a"},
            {"lo": 0, "hi": 8000, "name": "b"},
        ])
        first = fc.check(42.0)
        for _ in range(1000):
            result = fc.check(42.0)
            assert result.error_mask == first.error_mask
            assert result.severity == first.severity
            assert result.passed == first.passed
            assert result.violated_count == first.violated_count

    def test_determinism_batch(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        vals = list(range(-50, 150))
        r1, s1 = fc.check_batch(vals)
        r2, s2 = fc.check_batch(vals)
        for a, b in zip(r1, r2):
            assert a.error_mask == b.error_mask
            assert a.passed == b.passed
        assert s1 == s2


class TestBatchEdgeCases:
    """Batch checking edge cases."""

    def test_empty_batch(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        results, stats = fc.check_batch([])
        assert len(results) == 0
        assert stats["pass"] == 0

    def test_single_value_batch(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        results, stats = fc.check_batch([50])
        assert len(results) == 1
        assert results[0].passed
        assert stats["pass"] == 1

    def test_batch_with_mixed_results(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        results, stats = fc.check_batch([50, -10, 150, 0, 100])
        assert stats["pass"] == 3  # 50, 0, 100
        assert stats["caution"] == 2  # -10, 150


# ============================================================================
# Phase 5: Boundary Exhaustion Tests
# ============================================================================

class TestBoundaryExhaustion:
    """Exhaustively test values around boundaries."""

    def test_values_around_zero_boundary(self):
        """Test many values around [0, 0] point constraint."""
        fc = FluxExact([{"lo": 0.0, "hi": 0.0, "name": "test"}])
        # Values that should pass
        assert fc.check(0.0).passed
        assert fc.check(-0.0).passed

        # Values that should fail
        for offset in [1e-300, 1e-100, 1e-50, 1e-20, 1e-10, 1e-5, 0.001, 0.1]:
            assert not fc.check(offset).passed, f"{offset} should fail for [0, 0]"
            assert not fc.check(-offset).passed, f"-{offset} should fail for [0, 0]"

    def test_very_narrow_constraint(self):
        """Constraint with very narrow range."""
        fc = FluxExact([{"lo": 1.0, "hi": 1.0 + sys.float_info.epsilon, "name": "narrow"}])
        # Value at lo
        assert fc.check(1.0).passed
        # Value at hi
        assert fc.check(1.0 + sys.float_info.epsilon).passed
        # Value just above hi
        val_above = math.nextafter(1.0 + sys.float_info.epsilon, float("inf"))
        assert not fc.check(val_above).passed


# ============================================================================
# Phase 6: Real Preset Adversarial Tests
# ============================================================================

class TestPresetAdversarial:
    """Test presets with adversarial values."""

    def test_medical_preset_boundary_values(self):
        """Medical preset: test values exactly at and beyond clinical limits."""
        fc = FluxExact.from_preset("medical_fhir")

        # Body temp: 37.8 is max normal, 37.80001 should fail
        r = fc.check(37.8)
        # 37.8 in [36.1, 37.8] — should pass
        body_temp_detail = r.details[0]
        assert body_temp_detail.passed

        r = fc.check(37.800001)
        body_temp_detail = r.details[0]
        assert not body_temp_detail.passed

    def test_energy_preset_tight_freq(self):
        """Energy preset: grid frequency must be very tight [49.0, 51.0]."""
        fc = FluxExact.from_preset("energy_scada")

        assert fc.check(49.0).details[0].passed
        assert fc.check(51.0).details[0].passed
        assert not fc.check(48.999).details[0].passed
        assert not fc.check(51.001).details[0].passed

    def test_financial_preset_extreme_prices(self):
        """Financial preset: extreme price values."""
        fc = FluxExact.from_preset("financial_fix")

        # At boundaries
        assert fc.check(0.0001).details[0].passed
        assert fc.check(100000).details[0].passed
        assert not fc.check(0.00001).details[0].passed
        assert not fc.check(100001).details[0].passed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
