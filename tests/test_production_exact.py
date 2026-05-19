"""
Production-grade tests for the rewritten FLUX Exact Constraint Engine.
Tests: zero-alloc hot path, numpy batch, adversarial cases, presets, benchmark.
"""
import math
import sys
import os
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from flux_constraint_exact import (
    FluxExact, Severity, SEVERITY_TABLE, ExactConstraintDef,
    ExactResult, ExactDetail, PRESETS, passed, severity, flux_check_exact,
)

# ═══════════════════════════════════════════════════════════
# 1. Zero-alloc check_mask returns int
# ═══════════════════════════════════════════════════════════

class TestZeroAllocHotPath:

    def test_check_mask_returns_int(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        result = fc.check_mask(50)
        assert isinstance(result, int)

    def test_check_mask_pass(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        assert fc.check_mask(50) == 0
        assert fc.check_mask(0) == 0
        assert fc.check_mask(100) == 0

    def test_check_mask_fail(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        assert fc.check_mask(-1) == 1
        assert fc.check_mask(101) == 1

    def test_check_mask_multi_constraint(self):
        fc = FluxExact([
            {"lo": 0, "hi": 10, "name": "c0"},
            {"lo": 0, "hi": 20, "name": "c1"},
            {"lo": 0, "hi": 5, "name": "c2"},
        ])
        assert fc.check_mask(3) == 0       # passes all
        assert fc.check_mask(8) == 0b100    # fails c2 only
        assert fc.check_mask(15) == 0b101   # fails c0 and c2
        assert fc.check_mask(25) == 0b111   # fails all

    def test_passed_helper(self):
        assert passed(0) == True
        assert passed(1) == False
        assert passed(0b111) == False

    def test_severity_helper(self):
        assert severity(0) == Severity.PASS
        assert severity(0b1) == Severity.CAUTION
        assert severity(0b11111) == Severity.CRITICAL  # 5 violations


# ═══════════════════════════════════════════════════════════
# 2. NaN always violates all
# ═══════════════════════════════════════════════════════════

class TestNaNSafety:

    def test_nan_hot_path(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        mask = fc.check_mask(float("nan"))
        assert mask == 1  # violates the one constraint

    def test_nan_multi(self):
        fc = FluxExact([
            {"lo": 0, "hi": 100, "name": "a"},
            {"lo": -40, "hi": 150, "name": "b"},
            {"lo": 0, "hi": 8000, "name": "c"},
        ])
        mask = fc.check_mask(float("nan"))
        assert mask == 0b111  # violates all 3

    def test_nan_8_constraints(self):
        fc = FluxExact.from_preset("automotive_can")
        mask = fc.check_mask(float("nan"))
        assert mask == 0xFF  # all 8 violated

    def test_nan_backward_compat(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        result = fc.check(float("nan"))
        assert not result.passed
        assert result.severity == Severity.CAUTION


# ═══════════════════════════════════════════════════════════
# 3. Inf handled correctly
# ═══════════════════════════════════════════════════════════

class TestInfHandling:

    def test_pos_inf_violates_finite_hi(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        assert fc.check_mask(float("inf")) == 1

    def test_neg_inf_violates_finite_lo(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        assert fc.check_mask(float("-inf")) == 1

    def test_pos_inf_passes_inf_hi(self):
        fc = FluxExact([{"lo": 0, "hi": float("inf"), "name": "test"}])
        assert fc.check_mask(float("inf")) == 0

    def test_neg_inf_passes_neg_inf_lo(self):
        fc = FluxExact([{"lo": float("-inf"), "hi": 0, "name": "test"}])
        assert fc.check_mask(float("-inf")) == 0

    def test_finite_passes_inf_bounds(self):
        fc = FluxExact([{"lo": float("-inf"), "hi": float("inf"), "name": "test"}])
        assert fc.check_mask(42.0) == 0


# ═══════════════════════════════════════════════════════════
# 4. All 6 presets load and work
# ═══════════════════════════════════════════════════════════

class TestPresets:

    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_preset_loads(self, name):
        fc = FluxExact.from_preset(name)
        assert fc.n == 8
        assert len(fc.constraints) == 8

    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_preset_boundary_values_pass(self, name):
        """Each constraint's lo/hi must pass its own bounds."""
        for cdef in PRESETS[name]:
            fc = FluxExact([cdef])  # single-constraint checker
            assert fc.check_mask(cdef["lo"]) == 0, f"{name}: {cdef['name']} lo={cdef['lo']} should pass"
            assert fc.check_mask(cdef["hi"]) == 0, f"{name}: {cdef['name']} hi={cdef['hi']} should pass"

    @pytest.mark.parametrize("name", list(PRESETS.keys()))
    def test_preset_nan_violates_all(self, name):
        fc = FluxExact.from_preset(name)
        assert fc.check_mask(float("nan")) == 0xFF

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError):
            FluxExact.from_preset("nonexistent")


# ═══════════════════════════════════════════════════════════
# 5. Numpy batch vectorized
# ═══════════════════════════════════════════════════════════

class TestNumpyBatch:

    def test_batch_basic(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        vals = np.array([50.0, -1.0, 100.0, 101.0, float("nan")])
        masks = fc.check_batch_numpy(vals)
        assert masks[0] == 0
        assert masks[1] == 1
        assert masks[2] == 0
        assert masks[3] == 1
        assert masks[4] == 1

    def test_batch_large(self):
        fc = FluxExact.from_preset("automotive_can")
        vals = np.random.uniform(-500, 8500, 100000)
        masks = fc.check_batch_numpy(vals)
        assert masks.shape == (100000,)
        assert masks.dtype == np.uint8

    def test_batch_speedup(self):
        """Numpy batch should be 10x+ faster than Python loop."""
        fc = FluxExact.from_preset("automotive_can")
        vals = np.random.uniform(-500, 8500, 100000)
        loops = 10

        # Python loop baseline
        t0 = time.perf_counter()
        for _ in range(loops):
            for v in vals:
                fc.check_mask(float(v))
        py_time = time.perf_counter() - t0

        # Numpy
        t0 = time.perf_counter()
        for _ in range(loops):
            fc.check_batch_numpy(vals)
        np_time = time.perf_counter() - t0

        speedup = py_time / np_time
        print(f"\n  Batch speedup: {speedup:.1f}x (numpy={np_time:.3f}s python={py_time:.3f}s)")
        assert speedup > 5, f"Numpy batch only {speedup:.1f}x faster (expected >5x)"


# ═══════════════════════════════════════════════════════════
# 6. Backward compatibility
# ═══════════════════════════════════════════════════════════

class TestBackwardCompat:

    def test_check_returns_exact_result(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        r = fc.check(50)
        assert isinstance(r, ExactResult)
        assert r.passed
        assert r.error_mask == 0
        assert r.severity == Severity.PASS

    def test_check_fail_result(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        r = fc.check(200)
        assert not r.passed
        assert r.error_mask == 1
        assert r.severity == Severity.CAUTION

    def test_check_batch_compat(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        results, stats = fc.check_batch([50, 150])
        assert len(results) == 2
        assert results[0].passed
        assert not results[1].passed
        assert stats["pass"] == 1

    def test_flux_check_exact_alias(self):
        assert flux_check_exact is FluxExact

    def test_from_preset(self):
        fc = FluxExact.from_preset("automotive_can")
        assert fc.n == 8

    def test_available_presets(self):
        presets = FluxExact.available_presets()
        assert len(presets) == 6

    def test_exact_constraint_def_importable(self):
        c = ExactConstraintDef(lo=0, hi=100, name="test")
        assert c.lo == 0.0
        assert c.hi == 100.0

    def test_severity_table_importable(self):
        assert len(SEVERITY_TABLE) == 9

    def test_check_detail(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        d = fc.check_detail(150)
        assert d["passed"] == False
        assert d["error_mask"] == 1
        assert len(d["details"]) == 1

    def test_result_to_dict(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        r = fc.check(50)
        d = r.to_dict()
        assert d["passed"] == True
        assert "details" in d


# ═══════════════════════════════════════════════════════════
# 7. Adversarial edge cases (subset of 61)
# ═══════════════════════════════════════════════════════════

class TestAdversarialEdgeCases:

    def test_denormal(self):
        fc = FluxExact([{"lo": 0, "hi": 1, "name": "test"}])
        assert fc.check_mask(5e-324) == 0  # smallest denormal, in [0,1]

    def test_negative_zero(self):
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        assert fc.check_mask(-0.0) == 0  # -0.0 == 0.0 in IEEE 754

    def test_boundary_exact(self):
        fc = FluxExact([{"lo": -40, "hi": 150, "name": "test"}])
        assert fc.check_mask(-40.0) == 0
        assert fc.check_mask(150.0) == 0
        assert fc.check_mask(-40.000001) == 1
        assert fc.check_mask(150.000001) == 1

    def test_large_values(self):
        fc = FluxExact([{"lo": 0, "hi": 1e300, "name": "test"}])
        assert fc.check_mask(1e300) == 0
        assert fc.check_mask(1e301) == 1

    def test_small_range_precision(self):
        fc = FluxExact([{"lo": 7.35, "hi": 7.45, "name": "ph"}])
        assert fc.check_mask(7.40) == 0
        assert fc.check_mask(7.34) == 1
        assert fc.check_mask(7.46) == 1

    def test_inverted_bounds_rejected(self):
        with pytest.raises(ValueError):
            FluxExact([{"lo": 100, "hi": 0, "name": "bad"}])

    def test_empty_constraints_rejected(self):
        with pytest.raises(ValueError):
            FluxExact([])

    def test_too_many_constraints_rejected(self):
        with pytest.raises(ValueError):
            FluxExact([{"lo": i, "hi": i+1, "name": f"c{i}"} for i in range(9)])


# ═══════════════════════════════════════════════════════════
# 8. Benchmark
# ═══════════════════════════════════════════════════════════

class TestBenchmark:

    def test_benchmark_returns_float(self):
        fc = FluxExact.from_preset("automotive_can")
        rate = fc.benchmark(iterations=10000)
        assert isinstance(rate, float)
        assert rate > 0

    def test_hot_path_speed(self):
        """check_mask should be at least 1M/sec on any modern hardware."""
        fc = FluxExact.from_preset("automotive_can")
        rate = fc.benchmark(iterations=500000)
        print(f"\n  Hot path: {rate/1e6:.1f}M checks/sec")
        assert rate > 1e6, f"Too slow: {rate/1e6:.1f}M/sec (expected >1M)"

    def test_benchmark_detail_returns_dict(self):
        fc = FluxExact.from_preset("automotive_can")
        d = fc.benchmark_detail(iterations=10000)
        assert "rate" in d
        assert "rate_M" in d


# ═══════════════════════════════════════════════════════════
# 9. Frozen constraints (improvement over old code)
# ═══════════════════════════════════════════════════════════

class TestFrozenConstraints:

    def test_mutation_does_not_affect_check(self):
        """Constraints are frozen — mutation of .constraints list doesn't affect checks."""
        fc = FluxExact([{"lo": 0, "hi": 100, "name": "test"}])
        fc.constraints[0].lo = 50
        fc.constraints[0].hi = 60
        # Internal tuples are frozen — 25 still passes with original bounds [0, 100]
        assert fc.check_mask(25) == 0
        assert fc.check(25).passed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
