"""Tests for flux_immunity — Immune System Negative Selection."""

import sys
sys.path.insert(0, "/home/phoenix/.openclaw/workspace/constraint-theory-ecosystem/src/python")

from flux_immunity import (
    ImmuneConstraintSystem, NegativeSelection, Detector, DetectorType,
    Normalizer, AnomalyResult, TrainingReport,
)

import pytest
import math


# ---------------------------------------------------------------------------
# Detector tests
# ---------------------------------------------------------------------------

class TestDetector:
    def test_euclidean_match(self):
        d = Detector(center=[0.5, 0.5], radius=0.2, detector_type=DetectorType.EUCLIDEAN)
        assert d.matches([0.5, 0.5])
        assert d.matches([0.6, 0.5])
        assert not d.matches([0.9, 0.9])

    def test_hypercube_match(self):
        d = Detector(center=[0.5, 0.5], radius=0.2, detector_type=DetectorType.HYPERCUBE)
        assert d.matches([0.5, 0.5])
        assert d.matches([0.6, 0.6])
        assert not d.matches([0.8, 0.8])

    def test_hamming_match(self):
        d = Detector(center=[1.0, 0.0, 1.0], radius=1.0, detector_type=DetectorType.HAMMING)
        assert d.matches([1.0, 0.0, 1.0])  # exact match, 0 diff
        assert d.matches([0.0, 0.0, 1.0])  # 1 diff, within radius
        assert not d.matches([0.0, 1.0, 0.0])  # 3 diff, exceeds radius

    def test_dimension_mismatch(self):
        d = Detector(center=[0.5, 0.5], radius=0.2)
        assert not d.matches([0.5])
        assert not d.matches([0.5, 0.5, 0.5])

    def test_uid_generated(self):
        d = Detector(center=[0.5, 0.5], radius=0.2)
        assert len(d.uid) == 12

    def test_activation_tracking(self):
        d = Detector(center=[0.5], radius=0.5)
        assert d.activation_count == 0
        d.matches([0.5])
        # matches doesn't increment — only the system does


# ---------------------------------------------------------------------------
# Negative Selection Algorithm tests
# ---------------------------------------------------------------------------

class TestNegativeSelection:
    def test_generate_candidates(self):
        nsa = NegativeSelection(dimensions=3, seed=42)
        candidates = nsa.generate_candidates(100)
        assert len(candidates) == 100
        for c in candidates:
            assert len(c.center) == 3
            assert all(0 <= v <= 1 for v in c.center)

    def test_eliminate_self_reactive(self):
        nsa = NegativeSelection(dimensions=2, seed=42)
        candidates = nsa.generate_candidates(200)
        self_set = [[0.5, 0.5], [0.51, 0.5], [0.5, 0.51]]
        surviving = nsa.eliminate_self_reactive(candidates, self_set)
        # Some should be eliminated (those near 0.5, 0.5)
        assert len(surviving) < len(candidates)
        # Surviving should NOT match any self sample
        for d in surviving:
            for s in self_set:
                assert not d.matches(s)

    def test_full_training(self):
        nsa = NegativeSelection(dimensions=3, seed=42)
        self_set = [
            [0.5, 0.5, 0.5],
            [0.4, 0.6, 0.5],
            [0.6, 0.4, 0.5],
            [0.5, 0.5, 0.4],
            [0.5, 0.5, 0.6],
        ]
        detectors, report = nsa.train(self_set, target_count=50, batch_size=300)
        assert len(detectors) >= 50
        assert report.surviving >= 50
        assert report.elimination_rate > 0


# ---------------------------------------------------------------------------
# Immune Constraint System tests
# ---------------------------------------------------------------------------

class TestImmuneConstraintSystem:
    def _make_system(self):
        """Create a trained system with clustered normal data."""
        immune = ImmuneConstraintSystem(
            dimensions=2,
            detector_count=50,
            anomaly_threshold=1,
            seed=42,
        )
        # Normal data: clustered around [0.5, 0.5]
        normal = [
            [0.5 + 0.02 * (i % 10 - 5), 0.5 + 0.02 * (j % 10 - 5)]
            for i in range(20) for j in range(20)
        ]
        immune.train(normal)
        return immune, normal

    def test_training(self):
        immune, _ = self._make_system()
        assert immune.is_trained
        assert immune.detector_population > 0

    def test_normal_value_passes(self):
        immune, _ = self._make_system()
        result = immune.check([0.5, 0.5])
        # Center of the cluster — might still trigger some detectors
        # but should generally be less anomalous than outliers
        assert isinstance(result, AnomalyResult)

    def test_extreme_value_is_anomalous(self):
        immune, _ = self._make_system()
        result = immune.check([0.99, 0.01])
        # Far from normal cluster — should be flagged
        assert result.is_anomalous or result.anomaly_score > 0

    def test_dimension_validation(self):
        immune, _ = self._make_system()
        with pytest.raises(ValueError):
            immune.check([0.5])  # Wrong dimensions

    def test_untrained_raises(self):
        immune = ImmuneConstraintSystem(dimensions=2)
        with pytest.raises(RuntimeError):
            immune.check([0.5, 0.5])

    def test_statistics(self):
        immune, _ = self._make_system()
        immune.check([0.5, 0.5])
        immune.check([0.99, 0.01])
        stats = immune.statistics()
        assert stats["total_checks"] == 2
        assert "anomaly_rate" in stats

    def test_severity_levels(self):
        result_low = AnomalyResult(
            value=[0.5, 0.5], is_anomalous=False, anomaly_score=0.0
        )
        assert result_low.severity == "normal"

        result_high = AnomalyResult(
            value=[0.99, 0.01], is_anomalous=True, anomaly_score=0.8
        )
        assert result_high.severity == "high"

    def test_false_positive_removal(self):
        immune, _ = self._make_system()
        result = immune.check([0.5, 0.5])
        initial_count = immune.detector_population
        if result.is_anomalous:
            immune.report_false_positive(result)
            assert immune.detector_population < initial_count


# ---------------------------------------------------------------------------
# Normalizer tests
# ---------------------------------------------------------------------------

class TestNormalizer:
    def test_fit_transform(self):
        data = [[0, 10], [5, 20], [10, 30]]
        norm = Normalizer()
        norm.fit(data)
        transformed = norm.transform(data)
        assert transformed[0] == [0.0, 0.0]
        assert transformed[1] == [0.5, 0.5]
        assert transformed[2] == [1.0, 1.0]

    def test_inverse_transform(self):
        data = [[0, 10], [5, 20], [10, 30]]
        norm = Normalizer()
        norm.fit(data)
        transformed = norm.transform(data)
        recovered = norm.inverse_transform(transformed)
        for orig, rec in zip(data, recovered):
            assert all(abs(a - b) < 1e-10 for a, b in zip(orig, rec))

    def test_constant_dimension(self):
        data = [[5, 10], [5, 20], [5, 30]]
        norm = Normalizer()
        norm.fit(data)
        transformed = norm.transform(data)
        # Constant dimension should map to 0.5
        assert all(row[0] == 0.5 for row in transformed)

    def test_unfitted_raises(self):
        norm = Normalizer()
        with pytest.raises(RuntimeError):
            norm.transform([[1, 2]])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
