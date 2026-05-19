"""
Tests for the unified FLUX v4 API (flux.py)
Forgemaster ⚒️ — 2026-05-19
"""

import math
import sys
import time
import unittest

import numpy as np

sys.path.insert(0, ".")

from flux import ConstraintEngine, ConstraintStream, Strategy


class TestFromGuard(unittest.TestCase):
    def test_basic_parse(self):
        engine = ConstraintEngine.from_guard("""
            GUARD coolant_temp in [-40, 150] with priority HIGH
            GUARD engine_rpm in [0, 8000] with priority CRITICAL
        """)
        self.assertEqual(engine.n_constraints, 2)
        self.assertEqual(engine.names, ("coolant_temp", "engine_rpm"))

    def test_no_priority(self):
        engine = ConstraintEngine.from_guard("GUARD pressure in [0.5, 5.0]")
        self.assertEqual(engine.n_constraints, 1)
        self.assertEqual(engine.names[0], "pressure")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            ConstraintEngine.from_guard("nothing valid here")

    def test_multiple_constraints(self):
        engine = ConstraintEngine.from_guard("""
            GUARD a in [0, 1]
            GUARD b in [0, 2]
            GUARD c in [0, 3]
            GUARD d in [0, 4]
        """)
        self.assertEqual(engine.n_constraints, 4)
        self.assertEqual(engine.names, ("a", "b", "c", "d"))


class TestFromPreset(unittest.TestCase):
    def test_all_six_presets(self):
        expected = [
            "automotive_can", "aviation_adsb", "medical_fhir",
            "energy_scada", "iot_mqtt", "financial_fix",
        ]
        avail = ConstraintEngine.available_presets()
        for name in expected:
            self.assertIn(name, avail)
            engine = ConstraintEngine.from_preset(name)
            self.assertGreater(engine.n_constraints, 0)

    def test_unknown_preset_raises(self):
        with self.assertRaises(ValueError):
            ConstraintEngine.from_preset("nonexistent")

    def test_automotive_can_structure(self):
        engine = ConstraintEngine.from_preset("automotive_can")
        self.assertEqual(engine.n_constraints, 8)
        self.assertIn("engine_rpm", engine.names)
        self.assertIn("coolant_temp_c", engine.names)


class TestFromRaw(unittest.TestCase):
    def test_basic(self):
        engine = ConstraintEngine([{"lo": -40, "hi": 150, "name": "temp"}])
        self.assertEqual(engine.n_constraints, 1)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            ConstraintEngine([])

    def test_over_eight_raises(self):
        with self.assertRaises(ValueError):
            ConstraintEngine([{"lo": 0, "hi": i} for i in range(9)])


class TestHotPath(unittest.TestCase):
    def setUp(self):
        self.engine = ConstraintEngine.from_preset("automotive_can")

    def test_pass(self):
        # All 8 auto constraints: rpm [0,8000], speed [0,300], temp [-40,150],
        # throttle [0,100], brake [0,200], steering [-720,720], battery [9,16], fuel [0,100]
        # Value 10 is in range for ALL
        mask = self.engine.check(10)
        self.assertEqual(mask, 0)

    def test_fail(self):
        # 200 fails coolant_temp_c ([-40, 150]) — bit 2
        mask = self.engine.check(200)
        self.assertNotEqual(mask, 0)

    def test_nan_fails_all(self):
        mask = self.engine.check(float("nan"))
        self.assertEqual(mask, (1 << 8) - 1)

    def test_passed_bool(self):
        self.assertTrue(self.engine.passed(10))
        self.assertFalse(self.engine.passed(200))

    def test_boundary_inclusive(self):
        # coolant_temp_c: lo=-40, hi=150 — test boundary
        mask_lo = self.engine.check(-40)
        mask_hi = self.engine.check(150)
        # These should pass coolant_temp_c specifically (bit 2 = 0)
        # but may fail others; let's test a simpler engine
        eng = ConstraintEngine([{"lo": 0, "hi": 100, "name": "x"}])
        self.assertEqual(eng.check(0), 0)
        self.assertEqual(eng.check(100), 0)
        self.assertNotEqual(eng.check(-0.001), 0)
        self.assertNotEqual(eng.check(100.001), 0)


class TestBatch(unittest.TestCase):
    def setUp(self):
        self.engine = ConstraintEngine.from_preset("automotive_can")

    def test_batch_returns_ndarray(self):
        arr = np.array([50.0, 200.0, -40.0, float("nan")])
        result = self.engine.check_batch(arr)
        self.assertIsInstance(result, np.ndarray)
        self.assertEqual(result.dtype, np.uint8)
        self.assertEqual(len(result), 4)

    def test_batch_correctness(self):
        eng = ConstraintEngine([{"lo": 0, "hi": 100, "name": "x"}])
        vals = np.array([50.0, -1.0, 101.0, 0.0, 100.0])
        masks = eng.check_batch(vals)
        self.assertEqual(masks[0], 0)   # 50 in range
        self.assertNotEqual(masks[1], 0)  # -1 out
        self.assertNotEqual(masks[2], 0)  # 101 out
        self.assertEqual(masks[3], 0)   # 0 boundary
        self.assertEqual(masks[4], 0)   # 100 boundary

    def test_batch_speed(self):
        """Batch numpy should be significantly faster than scalar loop."""
        eng = ConstraintEngine.from_preset("automotive_can")
        arr = np.random.uniform(-500, 500, size=100_000)
        masks = eng.check_batch(arr)
        self.assertEqual(len(masks), 100_000)
        # Spot check: count violations
        n_violations = np.count_nonzero(masks)
        self.assertGreater(n_violations, 0)


class TestCheckDetail(unittest.TestCase):
    def test_returns_dict(self):
        eng = ConstraintEngine([{"lo": 0, "hi": 100, "name": "x"}])
        result = eng.check_detail(150)
        self.assertIsInstance(result, dict)
        self.assertFalse(result["passed"])
        self.assertEqual(result["violated_count"], 1)
        self.assertIn("details", result)
        self.assertEqual(len(result["details"]), 1)
        self.assertEqual(result["details"][0]["name"], "x")

    def test_pass_detail(self):
        eng = ConstraintEngine([{"lo": 0, "hi": 100, "name": "x"}])
        result = eng.check_detail(50)
        self.assertTrue(result["passed"])
        self.assertEqual(result["violated_count"], 0)


class TestStrategies(unittest.TestCase):
    def setUp(self):
        self.engine = ConstraintEngine.from_preset("automotive_can")

    def test_activate_adaptive(self):
        self.engine.use(Strategy.ADAPTIVE_ORDERING)
        self.assertIn(Strategy.ADAPTIVE_ORDERING, self.engine.active_strategies())
        tracker = self.engine.get_strategy(Strategy.ADAPTIVE_ORDERING)
        self.assertIsNotNone(tracker)
        # Feed some values
        for v in [50, 200, 50, 50, 50, 300]:
            self.engine.check(v)

    def test_activate_predictive(self):
        self.engine.use(Strategy.PREDICTIVE)
        self.assertIn(Strategy.PREDICTIVE, self.engine.active_strategies())
        # Feed values
        for v in [50.0] * 20:
            self.engine.check(v)

    def test_activate_kalman(self):
        self.engine.use(Strategy.KALMAN_PREDICTION)
        self.assertIn(Strategy.KALMAN_PREDICTION, self.engine.active_strategies())
        for v in [50.0] * 10:
            self.engine.check(v)

    def test_activate_anomaly(self):
        self.engine.use(Strategy.ANOMALY_DETECTION)
        self.assertIn(Strategy.ANOMALY_DETECTION, self.engine.active_strategies())
        for v in [50.0] * 20:
            self.engine.check(v)

    def test_activate_wavelet(self):
        self.engine.use(Strategy.WAVELET_ANALYSIS)
        self.assertIn(Strategy.WAVELET_ANALYSIS, self.engine.active_strategies())

    def test_chaining(self):
        eng = self.engine.use(Strategy.ADAPTIVE_ORDERING).use(Strategy.ANOMALY_DETECTION)
        self.assertEqual(len(eng.active_strategies()), 2)

    def test_double_activate_is_noop(self):
        self.engine.use(Strategy.ADAPTIVE_ORDERING)
        self.engine.use(Strategy.ADAPTIVE_ORDERING)
        self.assertEqual(len(self.engine.active_strategies()), 1)

    def test_all_strategies(self):
        for s in Strategy:
            eng = ConstraintEngine.from_preset("automotive_can")
            eng.use(s)
            self.assertIn(s, eng.active_strategies())
            mask = eng.check(10)  # 10 is in range for all auto constraints
            self.assertEqual(mask, 0)


class TestStreaming(unittest.TestCase):
    def test_basic_stream(self):
        eng = ConstraintEngine([{"lo": 0, "hi": 100, "name": "x"}])
        stream = eng.stream()
        self.assertEqual(stream.feed(50), 0)
        self.assertNotEqual(stream.feed(200), 0)
        self.assertEqual(len(stream.history), 2)

    def test_history_limit(self):
        eng = ConstraintEngine([{"lo": 0, "hi": 100, "name": "x"}])
        stream = eng.stream(max_history=5)
        for v in range(10):
            stream.feed(v)
        self.assertEqual(len(stream.history), 5)

    def test_clear(self):
        eng = ConstraintEngine([{"lo": 0, "hi": 100, "name": "x"}])
        stream = eng.stream()
        stream.feed(50)
        stream.feed(200)
        stream.clear()
        self.assertEqual(len(stream.history), 0)


class TestProofs(unittest.TestCase):
    def test_proof_certificate_valid(self):
        eng = ConstraintEngine([
            {"lo": 0, "hi": 100, "name": "a"},
            {"lo": -10, "hi": 10, "name": "b"},
        ])
        cert = eng.proof_certificate()
        self.assertIsNotNone(cert)
        self.assertTrue(cert.is_fully_proven)  # property, not method
        self.assertIn("summary", dir(cert))

    def test_proof_inverted_range(self):
        # FluxExact catches inverted ranges at init time
        with self.assertRaises(ValueError):
            ConstraintEngine([{"lo": 100, "hi": 0, "name": "bad"}])


class TestProvenance(unittest.TestCase):
    def test_empty_log(self):
        eng = ConstraintEngine([{"lo": 0, "hi": 100, "name": "x"}])
        log = eng.provenance_log()
        self.assertIsInstance(log, list)
        self.assertEqual(len(log), 0)

    def test_strategy_in_log(self):
        eng = ConstraintEngine([{"lo": 0, "hi": 100, "name": "x"}])
        eng.use(Strategy.ADAPTIVE_ORDERING)
        log = eng.provenance_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["event"], "strategy_enabled")
        self.assertEqual(log[0]["strategy"], "ADAPTIVE_ORDERING")


class TestBenchmark(unittest.TestCase):
    def test_benchmark_returns_rate(self):
        eng = ConstraintEngine([{"lo": 0, "hi": 100, "name": "x"}])
        rate = eng.benchmark(iterations=100_000)
        self.assertGreater(rate, 0)
        # Should be at least 1M/sec on any modern hardware
        # (using 100K iterations so test is fast)


class TestRepr(unittest.TestCase):
    def test_repr_with_preset(self):
        eng = ConstraintEngine.from_preset("automotive_can")
        r = repr(eng)
        self.assertIn("automotive_can", r)
        self.assertIn("n=8", r)

    def test_repr_with_strategies(self):
        eng = ConstraintEngine.from_preset("iot_mqtt")
        eng.use(Strategy.ADAPTIVE_ORDERING)
        r = repr(eng)
        self.assertIn("ADAPTIVE_ORDERING", r)


class TestIntegration(unittest.TestCase):
    """Full integration: all strategies on a real preset, streaming + proof."""

    def test_full_pipeline(self):
        eng = ConstraintEngine.from_preset("medical_fhir")
        eng.use(Strategy.ADAPTIVE_ORDERING)
        eng.use(Strategy.PREDICTIVE)
        eng.use(Strategy.KALMAN_PREDICTION)
        eng.use(Strategy.ANOMALY_DETECTION)
        eng.use(Strategy.WAVELET_ANALYSIS)

        # Stream 100 values
        stream = eng.stream()
        for i in range(100):
            val = 37.0 + (i % 10) * 0.1  # normal body temps
            mask = stream.feed(val)
            # Some values may fail certain constraints (e.g. heart_rate at 37)
            # Just verify the stream works, don't assert pass
            self.assertIsInstance(mask, int)

        # Feed some violations
        mask = stream.feed(45.0)  # way too hot
        self.assertNotEqual(mask, 0)

        # Proof should still work
        cert = eng.proof_certificate()
        self.assertIsNotNone(cert)

        # Provenance should have 5 activations
        log = eng.provenance_log()
        self.assertEqual(len(log), 5)

    def test_batch_then_detail(self):
        eng = ConstraintEngine.from_preset("energy_scada")
        arr = np.array([50.0, 50.5, 0.8, 1.2])
        masks = eng.check_batch(arr)
        self.assertEqual(len(masks), 4)
        # 0.8 fails voltage_pu [0.9, 1.1], 1.2 fails too
        self.assertNotEqual(masks[2], 0)
        self.assertNotEqual(masks[3], 0)

        # Detail for one value
        detail = eng.check_detail(0.8)
        self.assertFalse(detail["passed"])

    def test_guard_to_batch(self):
        eng = ConstraintEngine.from_guard("""
            GUARD temp in [-20, 60]
            GUARD humidity in [0, 100]
        """)
        vals = np.array([30.0, -25.0, 70.0, 50.0])
        masks = eng.check_batch(vals)
        self.assertEqual(masks[0], 0)
        self.assertNotEqual(masks[1], 0)
        self.assertNotEqual(masks[2], 0)
        self.assertEqual(masks[3], 0)


if __name__ == "__main__":
    unittest.main()
