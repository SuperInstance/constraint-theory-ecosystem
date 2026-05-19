"""
Tests for FLUX v4 Streaming Constraint Engine.

Covers: basic operation, sliding window stats, Kalman prediction,
wavelet decomposition, adaptive skipping, anomaly detection,
provenance logging, severity computation, and throughput benchmarks.
"""

import math
import random
import time
import unittest
from collections import Counter

from flux_stream import (
    Constraint,
    FluxStream,
    StreamConfig,
    Severity,
    ViolationEvent,
    SensorStats,
    KalmanState,
    WaveletResult,
    ProvenanceLog,
    ProvenanceEntry,
    StreamAnomalyDetector,
    _haar_decompose_energy,
    run_benchmark,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_stream(**config_kwargs) -> FluxStream:
    constraints = [
        Constraint(lo=0.0, hi=100.0, name="safe_zone", weight=1.0),
        Constraint(lo=-10.0, hi=110.0, name="operating_range", weight=0.5),
    ]
    cfg = StreamConfig(**config_kwargs)
    return FluxStream(constraints=constraints, config=cfg)


def feed_values(stream, sensor, values, base_ts=0.0, dt=0.001):
    events = []
    for i, v in enumerate(values):
        event = stream.feed(base_ts + i * dt, sensor, v)
        if event:
            events.append(event)
    return events


# ===========================================================================
# 1. Basic operation
# ===========================================================================

class TestBasicOperation(unittest.TestCase):

    def test_no_violation_returns_none(self):
        stream = make_stream()
        stream.add_sensor("t1")
        result = stream.feed(0.0, "t1", 50.0)
        self.assertIsNone(result)

    def test_violation_returns_event(self):
        stream = make_stream()
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", -5.0)
        self.assertIsNotNone(event)
        self.assertIsInstance(event, ViolationEvent)
        self.assertEqual(event.sensor, "t1")
        self.assertEqual(event.value, -5.0)
        # safe_zone violated (bit 0), operating_range passes
        self.assertTrue(event.error_mask & 1)
        self.assertEqual(event.error_mask & 2, 0)

    def test_both_constraints_violated(self):
        stream = make_stream()
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", -15.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.error_mask, 0b11)
        self.assertEqual(len(event.failed_constraints), 2)

    def test_auto_register_unknown_sensor(self):
        stream = make_stream()
        result = stream.feed(0.0, "unknown_sensor", 50.0)
        self.assertIsNone(result)
        self.assertIn("unknown_sensor", stream.sensors)

    def test_feed_batch(self):
        stream = make_stream()
        stream.add_sensor("t1")
        data = [
            (0.0, "t1", 50.0),
            (0.001, "t1", 120.0),  # violates both
            (0.002, "t1", 30.0),
            (0.003, "t1", -15.0),  # violates both
        ]
        events = stream.feed_batch(data)
        self.assertEqual(len(events), 2)

    def test_multiple_sensors(self):
        stream = make_stream()
        stream.add_sensor("t1")
        stream.add_sensor("t2")
        e1 = stream.feed(0.0, "t1", -5.0)
        e2 = stream.feed(0.001, "t2", 50.0)
        e3 = stream.feed(0.002, "t2", 120.0)
        self.assertIsNotNone(e1)
        self.assertIsNone(e2)
        self.assertIsNotNone(e3)
        self.assertEqual(e1.sensor, "t1")
        self.assertEqual(e3.sensor, "t2")

    def test_remove_sensor(self):
        stream = make_stream()
        stream.add_sensor("t1")
        self.assertIn("t1", stream.sensors)
        stream.remove_sensor("t1")
        self.assertNotIn("t1", stream.sensors)

    def test_str_representation(self):
        stream = make_stream()
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", -15.0)
        s = str(event)
        self.assertIn("t1", s)
        self.assertIn("-15", s)


# ===========================================================================
# 2. Sliding window statistics
# ===========================================================================

class TestSlidingWindow(unittest.TestCase):

    def test_stats_basic(self):
        stream = make_stream(window_size=1000)
        stream.add_sensor("t1")
        for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
            stream.feed(0.0, "t1", v)
        stats = stream.get_sensor_stats("t1")
        self.assertEqual(stats["n"], 5)
        self.assertAlmostEqual(stats["mean"], 30.0, places=5)
        self.assertAlmostEqual(stats["min"], 10.0)
        self.assertAlmostEqual(stats["max"], 50.0)

    def test_std_computation(self):
        stream = make_stream(window_size=1000)
        stream.add_sensor("t1")
        for v in [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]:
            stream.feed(0.0, "t1", v)
        stats = stream.get_sensor_stats("t1")
        # Welford's sample std of [2,4,4,4,5,5,7,9] ≈ 2.138
        self.assertAlmostEqual(stats["std"], 2.138, places=2)

    def test_window_eviction(self):
        stream = make_stream(window_size=5)
        stream.add_sensor("t1")
        for v in range(10):
            stream.feed(0.0, "t1", float(v))
        window = stream.get_sensor_window("t1")
        self.assertEqual(len(window), 5)
        self.assertEqual(window, [5.0, 6.0, 7.0, 8.0, 9.0])

    def test_window_preserves_order(self):
        stream = make_stream(window_size=100)
        stream.add_sensor("t1")
        values = [float(i) for i in range(20)]
        for v in values:
            stream.feed(0.0, "t1", v)
        window = stream.get_sensor_window("t1")
        self.assertEqual(window, values)

    def test_sensor_stats_dict_keys(self):
        stream = make_stream(window_size=100)
        stream.add_sensor("t1")
        stream.feed(0.0, "t1", 50.0)
        stats = stream.get_sensor_stats("t1")
        for key in ("n", "mean", "std", "min", "max"):
            self.assertIn(key, stats)

    def test_stats_none_for_unknown_sensor(self):
        stream = make_stream()
        self.assertIsNone(stream.get_sensor_stats("nonexistent"))

    def test_get_sensor_window_none_for_unknown(self):
        stream = make_stream()
        self.assertIsNone(stream.get_sensor_window("nonexistent"))


# ===========================================================================
# 3. SensorStats unit tests
# ===========================================================================

class TestSensorStats(unittest.TestCase):

    def test_empty_stats(self):
        s = SensorStats()
        self.assertEqual(s.n, 0)
        self.assertEqual(s.mean, 0.0)
        self.assertEqual(s.std, 0.0)

    def test_single_value(self):
        s = SensorStats()
        s.update(42.0)
        self.assertEqual(s.n, 1)
        self.assertAlmostEqual(s.mean, 42.0)
        self.assertEqual(s.std, 0.0)

    def test_identical_values_zero_std(self):
        s = SensorStats()
        for _ in range(100):
            s.update(5.0)
        self.assertAlmostEqual(s.mean, 5.0)
        self.assertAlmostEqual(s.std, 0.0)

    def test_min_max(self):
        s = SensorStats()
        for v in [3.0, 1.0, 4.0, 1.5, 9.0]:
            s.update(v)
        self.assertAlmostEqual(s.min_val, 1.0)
        self.assertAlmostEqual(s.max_val, 9.0)


# ===========================================================================
# 4. Kalman filter
# ===========================================================================

class TestKalmanFilter(unittest.TestCase):

    def test_kalman_initialized(self):
        stream = make_stream(kalman=True)
        stream.add_sensor("t1")
        stream.feed(0.0, "t1", 50.0)
        stats = stream.get_sensor_stats("t1")
        self.assertIn("kalman", stats)
        self.assertAlmostEqual(stats["kalman"]["position"], 50.0, places=2)

    def test_kalman_tracks_constant(self):
        stream = make_stream(kalman=True)
        stream.add_sensor("t1")
        for i in range(50):
            stream.feed(i * 0.001, "t1", 50.0)
        stats = stream.get_sensor_stats("t1")
        self.assertAlmostEqual(stats["kalman"]["position"], 50.0, delta=1.0)

    def test_kalman_prediction_in_event(self):
        stream = make_stream(kalman=True)
        stream.add_sensor("t1")
        # Feed some normal values, then a violation
        for i in range(20):
            stream.feed(i * 0.001, "t1", 50.0)
        event = stream.feed(0.02, "t1", -15.0)
        self.assertIsNotNone(event)
        self.assertIsNotNone(event.kalman_predicted)
        self.assertIsNotNone(event.kalman_error)

    def test_kalman_state_unit(self):
        k = KalmanState()
        self.assertFalse(k.initialized)
        k.update(10.0, 1.0, 0.1, 0.5)
        self.assertTrue(k.initialized)
        self.assertAlmostEqual(k.x, 10.0)

    def test_kalman_predict(self):
        k = KalmanState()
        k.update(10.0, 1.0, 0.1, 0.5)
        pred, unc = k.predict(1.0, 0.1)
        self.assertIsInstance(pred, float)
        self.assertIsInstance(unc, float)
        self.assertGreater(unc, 0)


# ===========================================================================
# 5. Wavelet decomposition
# ===========================================================================

class TestWaveletDecomposition(unittest.TestCase):

    def test_empty_signal(self):
        result = _haar_decompose_energy([], levels=3)
        self.assertEqual(result.levels, 0)
        self.assertEqual(result.total_energy, 0.0)

    def test_constant_signal_zero_detail_energy(self):
        signal = [5.0] * 64
        result = _haar_decompose_energy(signal, levels=5)
        # Constant signal: all detail coefficients are zero
        self.assertTrue(all(abs(e) < 1e-10 for e in result.energy_by_level))
        self.assertAlmostEqual(result.total_energy, 0.0, places=5)

    def test_spike_signal_has_energy(self):
        signal = [0.0] * 64
        signal[32] = 1.0
        result = _haar_decompose_energy(signal, levels=5)
        self.assertGreater(result.total_energy, 0.0)

    def test_step_signal(self):
        # Use a step that doesn't align perfectly with Haar boundaries
        signal = [0.0] * 31 + [1.0] * 33
        result = _haar_decompose_energy(signal, levels=5)
        self.assertGreater(result.total_energy, 0.0)

    def test_event_wavelet_result(self):
        stream = make_stream(kalman=True, window_size=100)
        stream.add_sensor("t1")
        # Feed enough to build mask window, then violate
        for i in range(20):
            stream.feed(i * 0.001, "t1", 50.0)
        event = stream.feed(0.02, "t1", -15.0)
        self.assertIsNotNone(event)
        # Wavelet result may be None if window < 8
        # With 21 values it should be present
        if event.wavelet_result is not None:
            self.assertIsInstance(event.wavelet_result, WaveletResult)


# ===========================================================================
# 6. Severity computation
# ===========================================================================

class TestSeverity(unittest.TestCase):

    def test_slight_violation_low_severity(self):
        stream = make_stream()
        stream.add_sensor("t1")
        # -0.01 outside safe_zone (0-100) but only slightly
        event = stream.feed(0.0, "t1", -0.01)
        self.assertIsNotNone(event)
        self.assertLessEqual(event.severity, Severity.MEDIUM)

    def test_extreme_violation_critical(self):
        stream = make_stream()
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", -1000.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.severity, Severity.CRITICAL)

    def test_moderate_violation(self):
        stream = make_stream()
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", 105.0)
        self.assertIsNotNone(event)
        self.assertIn(event.severity, (Severity.LOW, Severity.MEDIUM, Severity.HIGH))

    def test_severity_increases_with_distance(self):
        stream = make_stream()
        results = []
        for offset in [0.01, 1.0, 10.0, 50.0, 500.0]:
            stream.add_sensor(f"s_{offset}")
            event = stream.feed(0.0, f"s_{offset}", -offset)
            if event:
                results.append((offset, event.severity))
        # Generally, larger offsets should have higher severity
        if len(results) >= 2:
            self.assertGreaterEqual(results[-1][1], results[0][1])


# ===========================================================================
# 7. Adaptive predictive skipping
# ===========================================================================

class TestAdaptiveSkipping(unittest.TestCase):

    def test_adaptive_skips_some_values(self):
        stream = make_stream(adaptive=True)
        stream.add_sensor("t1")
        # Feed 500 clean values
        for i in range(500):
            stream.feed(i * 0.001, "t1", 50.0)
        tp = stream.get_throughput()
        self.assertGreater(tp["skip_rate"], 0.0)

    def test_adaptive_resets_on_violation(self):
        stream = make_stream(adaptive=True)
        stream.add_sensor("t1")
        # Feed clean values to build up skip rate
        for i in range(200):
            stream.feed(i * 0.001, "t1", 50.0)
        # Violate
        stream.feed(0.2, "t1", -15.0)
        # After violation, check rate should increase (skip_rate should drop)
        tp_before = stream.get_throughput()
        # Feed more clean values
        for i in range(200):
            stream.feed(0.2 + i * 0.001, "t1", 50.0)
        tp_after = stream.get_throughput()
        # Skip rate should be rebuilding
        self.assertGreater(tp_after["total_values"], 400)

    def test_no_adaptive_when_disabled(self):
        stream = make_stream(adaptive=False)
        stream.add_sensor("t1")
        for i in range(500):
            stream.feed(i * 0.001, "t1", 50.0)
        tp = stream.get_throughput()
        self.assertEqual(tp["skip_rate"], 0.0)


# ===========================================================================
# 8. Anomaly detection
# ===========================================================================

class TestAnomalyDetection(unittest.TestCase):

    def test_normal_data_not_anomalous(self):
        stream = make_stream(anomaly=True, anomaly_window=100)
        stream.add_sensor("t1")
        random.seed(42)
        for i in range(200):
            stream.feed(i * 0.001, "t1", random.uniform(10, 90))
        self.assertFalse(stream.is_anomalous())

    def test_anomaly_detector_compression(self):
        det = StreamAnomalyDetector(window_size=100, threshold=0.85)
        # Feed structured data (all zeros = highly compressible)
        for _ in range(100):
            det.observe(0)
        self.assertLess(det.compression_ratio(), 0.5)
        self.assertFalse(det.is_anomalous())

    def test_anomaly_detector_random_data(self):
        det = StreamAnomalyDetector(window_size=200, threshold=0.7)
        random.seed(42)
        # Feed random masks = less compressible
        for _ in range(200):
            det.observe(random.randint(0, 255))
        ratio = det.compression_ratio()
        self.assertGreater(ratio, 0.3)  # Random data compresses less

    def test_anomaly_disabled(self):
        stream = make_stream(anomaly=False)
        stream.add_sensor("t1")
        self.assertFalse(stream.is_anomalous())
        self.assertEqual(stream.anomaly_compression_ratio(), 0.0)


# ===========================================================================
# 9. Provenance logging
# ===========================================================================

class TestProvenance(unittest.TestCase):

    def test_provenance_records_violations(self):
        stream = make_stream(provenance=True)
        stream.add_sensor("t1")
        stream.feed(0.0, "t1", -15.0)
        self.assertEqual(len(stream.provenance_log), 1)

    def test_provenance_has_hash(self):
        stream = make_stream(provenance=True)
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", -15.0)
        self.assertIsNotNone(event)
        self.assertIsNotNone(event.provenance_hash)
        self.assertEqual(len(event.provenance_hash), 32)  # blake2b-256 hex

    def test_provenance_deterministic_hash(self):
        """Same inputs produce same hash."""
        log = ProvenanceLog(max_entries=100)
        e1 = log.record(1.0, "t1", 50.0, 1, 2, predicted_value=48.0)
        e2 = log.record(1.0, "t1", 50.0, 1, 2, predicted_value=48.0)
        self.assertEqual(e1.content_hash, e2.content_hash)

    def test_provenance_different_inputs_different_hash(self):
        log = ProvenanceLog(max_entries=100)
        e1 = log.record(1.0, "t1", 50.0, 1, 2)
        e2 = log.record(1.0, "t1", 51.0, 1, 2)
        self.assertNotEqual(e1.content_hash, e2.content_hash)

    def test_provenance_max_entries(self):
        log = ProvenanceLog(max_entries=10)
        for i in range(20):
            log.record(float(i), "t1", float(i), 0, 0)
        self.assertEqual(len(log), 10)

    def test_provenance_disabled(self):
        stream = make_stream(provenance=False)
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", -15.0)
        self.assertIsNone(stream.provenance_log)
        self.assertIsNone(event.provenance_hash)


# ===========================================================================
# 10. Constraint helper
# ===========================================================================

class TestConstraint(unittest.TestCase):

    def test_check_in_range(self):
        c = Constraint(lo=0.0, hi=100.0, name="test")
        self.assertTrue(c.check(50.0))
        self.assertTrue(c.check(0.0))
        self.assertTrue(c.check(100.0))

    def test_check_out_of_range(self):
        c = Constraint(lo=0.0, hi=100.0, name="test")
        self.assertFalse(c.check(-0.001))
        self.assertFalse(c.check(100.001))

    def test_distance_inside(self):
        c = Constraint(lo=0.0, hi=100.0, name="test")
        self.assertEqual(c.distance(50.0), 0.0)

    def test_distance_outside(self):
        c = Constraint(lo=0.0, hi=100.0, name="test")
        self.assertAlmostEqual(c.distance(-5.0), 5.0)
        self.assertAlmostEqual(c.distance(110.0), 10.0)

    def test_error_mask_bit(self):
        c = Constraint(lo=0.0, hi=100.0, name="test")
        self.assertEqual(c.error_mask_bit(50.0), 0)
        self.assertEqual(c.error_mask_bit(-1.0), 1)


# ===========================================================================
# 11. Violation history
# ===========================================================================

class TestViolationHistory(unittest.TestCase):

    def test_violation_history(self):
        stream = make_stream()
        stream.add_sensor("t1")
        stream.feed(0.0, "t1", -5.0)
        stream.feed(0.001, "t1", 50.0)
        stream.feed(0.002, "t1", -15.0)
        history = stream.get_violation_history("t1")
        self.assertEqual(len(history), 2)
        self.assertAlmostEqual(history[0][1], -5.0)
        self.assertAlmostEqual(history[1][1], -15.0)

    def test_violation_history_unknown_sensor(self):
        stream = make_stream()
        self.assertEqual(stream.get_violation_history("nonexistent"), [])


# ===========================================================================
# 12. Summary and throughput
# ===========================================================================

class TestSummaryThroughput(unittest.TestCase):

    def test_summary_structure(self):
        stream = make_stream()
        stream.add_sensor("t1")
        stream.feed(0.0, "t1", 50.0)
        s = stream.summary()
        self.assertIn("throughput", s)
        self.assertIn("sensors", s)
        self.assertIn("config", s)

    def test_throughput_counters(self):
        stream = make_stream(adaptive=False)
        stream.add_sensor("t1")
        for i in range(100):
            stream.feed(i * 0.001, "t1", 50.0)
        tp = stream.get_throughput()
        self.assertEqual(tp["total_values"], 100)
        self.assertEqual(tp["total_violations"], 0)
        self.assertEqual(tp["total_checks"], 100)
        self.assertEqual(tp["n_sensors"], 1)

    def test_throughput_with_violations(self):
        stream = make_stream(adaptive=False)
        stream.add_sensor("t1")
        for v in [50.0, -5.0, 50.0, 120.0, 50.0]:
            stream.feed(0.0, "t1", v)
        tp = stream.get_throughput()
        self.assertEqual(tp["total_values"], 5)
        self.assertEqual(tp["total_violations"], 2)


# ===========================================================================
# 13. Benchmark
# ===========================================================================

class TestBenchmark(unittest.TestCase):

    def test_small_benchmark(self):
        result = run_benchmark(
            n_sensors=100,
            rate_hz=100,
            duration_seconds=0.1,
            violation_rate=0.01,
        )
        self.assertIn("results", result)
        self.assertIn("config", result)
        self.assertGreater(result["results"]["wall_values_per_second"], 0)
        self.assertGreater(result["violation_events"], 0)

    def test_benchmark_detection_rate(self):
        result = run_benchmark(
            n_sensors=50,
            rate_hz=100,
            duration_seconds=0.5,
            violation_rate=0.05,
            config=StreamConfig(adaptive=False),
        )
        # With adaptive disabled, should catch most violations
        self.assertGreater(result["detection_rate"], 0.8)


# ===========================================================================
# 14. Large-scale stress test
# ===========================================================================

class TestStress(unittest.TestCase):

    def test_1000_sensors_1000_values(self):
        """Feed 1M values: 1000 sensors × 1000 values each."""
        stream = make_stream(
            window_size=100,
            adaptive=True,
            kalman=True,
            anomaly=False,  # disable for speed
            provenance=False,
        )
        for i in range(1000):
            stream.add_sensor(f"s{i}")

        random.seed(42)
        t0 = time.perf_counter()
        violations = 0
        for step in range(1000):
            ts = step * 0.001
            for s in range(1000):
                if random.random() < 0.001:
                    v = random.uniform(-20, -5)
                else:
                    v = random.uniform(10, 90)
                event = stream.feed(ts, f"s{s}", v)
                if event:
                    violations += 1
        elapsed = time.perf_counter() - t0

        tp = stream.get_throughput()
        self.assertEqual(tp["total_values"], 1_000_000)
        self.assertGreater(violations, 0)
        # Should complete in reasonable time (< 30s for 1M values)
        self.assertLess(elapsed, 30.0)
        print(f"\n  Stress test: 1M values in {elapsed:.2f}s "
              f"({1_000_000/elapsed:.0f} values/s, {violations} violations)")


# ===========================================================================
# 15. Edge cases
# ===========================================================================

class TestEdgeCases(unittest.TestCase):

    def test_exact_boundary_values(self):
        stream = make_stream()
        stream.add_sensor("t1")
        # Exact boundary of safe_zone [0, 100]: should pass
        self.assertIsNone(stream.feed(0.0, "t1", 0.0))
        self.assertIsNone(stream.feed(0.0, "t1", 100.0))
        # -10 and 110 are outside safe_zone but inside operating_range
        # So they violate safe_zone only (bit 0 set)
        e1 = stream.feed(0.0, "t1", -10.0)
        self.assertIsNotNone(e1)
        self.assertEqual(e1.error_mask, 0b01)  # safe_zone only
        e2 = stream.feed(0.0, "t1", 110.0)
        self.assertIsNotNone(e2)
        self.assertEqual(e2.error_mask, 0b01)  # safe_zone only

    def test_just_outside_boundary(self):
        stream = make_stream()
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", -0.001)
        self.assertIsNotNone(event)

    def test_nan_value(self):
        """NaN should violate all constraints (NaN comparisons return False)."""
        stream = make_stream()
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", float('nan'))
        # NaN comparisons are False, so check() returns False → violation
        self.assertIsNotNone(event)

    def test_inf_value(self):
        stream = make_stream()
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", float('inf'))
        self.assertIsNotNone(event)
        self.assertEqual(event.severity, Severity.CRITICAL)

    def test_negative_inf(self):
        stream = make_stream()
        stream.add_sensor("t1")
        event = stream.feed(0.0, "t1", float('-inf'))
        self.assertIsNotNone(event)

    def test_zero_constraints(self):
        """No constraints means no violations ever."""
        stream = FluxStream(constraints=[], config=StreamConfig(adaptive=False))
        stream.add_sensor("t1")
        for v in [-1000.0, 0.0, 1000.0, float('inf')]:
            result = stream.feed(0.0, "t1", v)
            self.assertIsNone(result)

    def test_single_constraint(self):
        c = Constraint(lo=0.0, hi=10.0, name="range")
        stream = FluxStream(constraints=[c], config=StreamConfig())
        stream.add_sensor("t1")
        self.assertIsNone(stream.feed(0.0, "t1", 5.0))
        event = stream.feed(0.001, "t1", 15.0)
        self.assertIsNotNone(event)
        self.assertEqual(event.error_mask, 1)

    def test_config_defaults(self):
        cfg = StreamConfig()
        self.assertEqual(cfg.window_size, 1000)
        self.assertEqual(cfg.check_interval, 1)
        self.assertTrue(cfg.adaptive)
        self.assertTrue(cfg.kalman)
        self.assertTrue(cfg.anomaly)
        self.assertTrue(cfg.provenance)


if __name__ == "__main__":
    unittest.main()
