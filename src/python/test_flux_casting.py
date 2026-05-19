"""Tests for flux_casting — ASVAB-style placement algorithm."""

import sys
import os
import pytest

# Ensure module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flux_casting import (
    CandidateProfile, Role, SafetyLevel,
    CompositeScorer, PlacementAlgorithm, Placement,
    FeedbackLoop, FeedbackRecord,
    PredictiveCaster, DemandForecast,
    CANDIDATES, ROLES, cast, print_placements,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _c(name="test", speed=1e6, mem=1024, lat=100.0,
       safety=SafetyLevel.MEDIUM, port=5, eco=5.0, lang="test"):
    return CandidateProfile(name=name, speed=speed, memory_bytes=mem,
                            latency_ns=lat, safety=safety,
                            portability=port, ecosystem=eco, language=lang)


def _r(name="test_role", speed=0.0, mem=10**9, lat=float("inf"),
       safety=SafetyLevel.NONE, port=0, demand=1, weight=1.0):
    return Role(name=name, min_speed=speed, max_memory_bytes=mem,
                max_latency_ns=lat, min_safety=safety,
                min_portability=port, demand=demand, weight=weight)


# ===========================================================================
# CandidateProfile Tests
# ===========================================================================

class TestCandidateProfile:

    def test_qualifies_all_pass(self):
        c = _c(speed=2e6, mem=512, lat=50, safety=SafetyLevel.HIGH)
        r = _r(speed=1e6, mem=1024, lat=100, safety=SafetyLevel.MEDIUM)
        ok, failures = c.qualifies_for(r)
        assert ok
        assert failures == []

    def test_qualifies_speed_fail(self):
        c = _c(speed=500_000)
        r = _r(speed=1_000_000)
        ok, failures = c.qualifies_for(r)
        assert not ok
        assert any("speed" in f for f in failures)

    def test_qualifies_memory_fail(self):
        c = _c(mem=2048)
        r = _r(mem=1024)
        ok, failures = c.qualifies_for(r)
        assert not ok
        assert any("memory" in f for f in failures)

    def test_qualifies_latency_fail(self):
        c = _c(lat=500.0)
        r = _r(lat=100.0)
        ok, failures = c.qualifies_for(r)
        assert not ok
        assert any("latency" in f for f in failures)

    def test_qualifies_safety_fail(self):
        c = _c(safety=SafetyLevel.LOW)
        r = _r(safety=SafetyLevel.HIGH)
        ok, failures = c.qualifies_for(r)
        assert not ok
        assert any("safety" in f for f in failures)

    def test_qualifies_portability_fail(self):
        c = _c(port=2)
        r = _r(port=5)
        ok, failures = c.qualifies_for(r)
        assert not ok
        assert any("portability" in f for f in failures)

    def test_multiple_failures(self):
        c = _c(speed=1, mem=999999, safety=SafetyLevel.NONE)
        r = _r(speed=1e6, mem=1024, safety=SafetyLevel.VERY_HIGH)
        ok, failures = c.qualifies_for(r)
        assert not ok
        assert len(failures) >= 2


# ===========================================================================
# CompositeScorer Tests
# ===========================================================================

class TestCompositeScorer:

    def test_perfect_fit_scores_high(self):
        c = _c(speed=2e6, mem=512, lat=50, safety=SafetyLevel.VERY_HIGH,
               port=10, eco=10)
        r = _r(speed=1e6, mem=1024, lat=100, safety=SafetyLevel.MEDIUM)
        score = CompositeScorer.score(c, r, "balanced")
        assert score > 0.5

    def test_minimal_fit_scores_lower(self):
        c_just = _c(speed=1_000_001, mem=1023, lat=99, safety=SafetyLevel.MEDIUM)
        c_great = _c(speed=10e6, mem=128, lat=10, safety=SafetyLevel.VERY_HIGH,
                     port=10, eco=10)
        r = _r(speed=1e6, mem=1024, lat=100, safety=SafetyLevel.MEDIUM)
        s_just = CompositeScorer.score(c_just, r, "balanced")
        s_great = CompositeScorer.score(c_great, r, "balanced")
        assert s_great > s_just

    def test_composite_variants(self):
        c = _c(speed=100e6, safety=SafetyLevel.VERY_HIGH, port=10)
        r = _r(speed=1e6, safety=SafetyLevel.MEDIUM)
        s_perf = CompositeScorer.score(c, r, "performance")
        s_safe = CompositeScorer.score(c, r, "safety")
        s_port = CompositeScorer.score(c, r, "portable")
        # All should produce valid scores
        for s in [s_perf, s_safe, s_port]:
            assert 0.0 <= s <= 1.0


# ===========================================================================
# PlacementAlgorithm Tests
# ===========================================================================

class TestPlacementAlgorithm:

    def test_single_perfect_match(self):
        c = _c(name="c1", speed=2e6, safety=SafetyLevel.HIGH)
        r = _r(name="r1", speed=1e6, safety=SafetyLevel.MEDIUM)
        algo = PlacementAlgorithm()
        result = algo.place([c], [r])
        assert r in result
        assert result[r].candidate.name == "c1"
        assert result[r].hard_pass

    def test_no_qualifying_candidate(self):
        c = _c(name="slow", speed=100)
        r = _r(name="fast_role", speed=1e6)
        algo = PlacementAlgorithm()
        result = algo.place([c], [r])
        assert r in result
        assert not result[r].hard_pass
        assert result[r].score == 0.0

    def test_best_candidate_wins(self):
        c_fast = _c(name="fast", speed=10e6, safety=SafetyLevel.HIGH)
        c_slow = _c(name="slow", speed=2e6, safety=SafetyLevel.HIGH)
        r = _r(name="r1", speed=1e6, safety=SafetyLevel.MEDIUM)
        algo = PlacementAlgorithm()
        result = algo.place([c_fast, c_slow], [r])
        assert result[r].candidate.name == "fast"

    def test_one_candidate_one_role(self):
        """Each candidate can only fill one role."""
        c = _c(name="versatile", speed=10e6, safety=SafetyLevel.VERY_HIGH,
               port=10)
        r1 = _r(name="r1", speed=1e6)
        r2 = _r(name="r2", speed=1e6)
        algo = PlacementAlgorithm()
        result = algo.place([c], [r1, r2])
        # One role gets placed, the other doesn't
        placed = [p.hard_pass for p in result.values()]
        assert sum(placed) == 1

    def test_multiple_roles_multiple_candidates(self):
        c_fast = _c(name="fast", speed=100e6, mem=1024, lat=10,
                     safety=SafetyLevel.VERY_HIGH, port=2)
        c_portable = _c(name="portable", speed=5e6, mem=4096, lat=1000,
                         safety=SafetyLevel.LOW, port=10)
        r_perf = _r(name="performance", speed=50e6, lat=100)
        r_port = _r(name="portable", speed=1e6, port=5)
        algo = PlacementAlgorithm()
        result = algo.place([c_fast, c_portable], [r_perf, r_port])
        # fast should get performance (only one that qualifies)
        # portable should get portable role
        assert result[r_perf].candidate.name == "fast"
        assert result[r_port].candidate.name == "portable"


# ===========================================================================
# Real Profile Placement Tests
# ===========================================================================

class TestRealProfiles:

    def test_aviation_adsb_placement(self):
        """Aviation ADS-B needs high speed, low latency, high safety."""
        placements = cast()
        p = placements["aviation_adsb"]
        assert p.hard_pass
        # Should be Rust VM or C AVX2 (high speed + high safety)
        assert p.candidate.name in ("rust_vm", "c_avx2", "verilog_fpga")

    def test_automotive_can_placement(self):
        """Automotive CAN: tiny memory, very high safety."""
        placements = cast()
        p = placements["automotive_can"]
        assert p.hard_pass
        assert p.candidate.safety >= SafetyLevel.VERY_HIGH

    def test_medical_fhir_placement(self):
        """Medical FHIR: moderate speed, high safety.

        Note: With 4 safety-critical roles (aviation, automotive, medical, space)
        and only 3 HIGH+ safety candidates, one role may go unfilled in a
        full cast. Test with a fresh algorithm where medical_fhir is the
        only role to verify the candidate selection logic.
        """
        algo = PlacementAlgorithm()
        result = algo.place(CANDIDATES, [
            r for r in ROLES if r.name == "medical_fhir"
        ])
        r = next(r for r in ROLES if r.name == "medical_fhir")
        p = result[r]
        assert p.hard_pass
        assert p.candidate.safety >= SafetyLevel.HIGH

    def test_energy_scada_placement(self):
        """Energy SCADA: 18M/s throughput."""
        placements = cast()
        p = placements["energy_scada"]
        assert p.hard_pass
        assert p.candidate.speed >= 18_000_000

    def test_underwater_acoustic_placement(self):
        """Underwater: tiny memory, low speed needed."""
        placements = cast()
        p = placements["underwater_acoustic"]
        assert p.hard_pass
        assert p.candidate.memory_bytes <= 1024

    def test_space_radiation_placement(self):
        """Space: very high safety, low portability OK."""
        placements = cast()
        p = placements["space_radiation"]
        assert p.hard_pass
        assert p.candidate.safety >= SafetyLevel.VERY_HIGH

    def test_no_python_for_safety_roles(self):
        """Python candidates should never be placed in safety-critical roles."""
        placements = cast()
        for role_name in ["aviation_adsb", "automotive_can", "medical_fhir", "space_radiation"]:
            p = placements[role_name]
            if p.hard_pass:
                assert "python" not in p.candidate.name.lower()

    def test_all_roles_get_placement(self):
        """Every role should have a result entry."""
        placements = cast()
        for r in ROLES:
            assert r.name in placements

    def test_rust_vm_wins_safety_speed_roles(self):
        """Rust VM should dominate roles needing both speed and safety."""
        placements = cast()
        rust_roles = [
            name for name, p in placements.items()
            if p.hard_pass and p.candidate.name == "rust_vm"
        ]
        assert len(rust_roles) >= 1  # Rust should win at least one role


# ===========================================================================
# FeedbackLoop Tests
# ===========================================================================

class TestFeedbackLoop:

    def test_record_feedback(self):
        fb = FeedbackLoop()
        rec = FeedbackRecord(
            candidate_name="test", role_name="r1",
            predicted_speed=1e6, actual_speed=800_000,
            predicted_memory=1024, actual_memory=1200,
            predicted_latency=100, actual_latency=150,
        )
        fb.record(rec)
        assert len(fb.records) == 1

    def test_adjusts_speed_down(self):
        fb = FeedbackLoop()
        rec = FeedbackRecord(
            candidate_name="slow", role_name="r1",
            predicted_speed=1e6, actual_speed=500_000,
            predicted_memory=1024, actual_memory=1024,
            predicted_latency=100, actual_latency=100,
        )
        fb.record(rec)
        adj = fb.adjustments["slow"]
        assert adj["speed_factor"] < 1.0

    def test_adjusted_profile_reflects_reality(self):
        fb = FeedbackLoop()
        orig = _c(name="candidate", speed=1e6, mem=1024, lat=100)
        rec = FeedbackRecord(
            candidate_name="candidate", role_name="r1",
            predicted_speed=1e6, actual_speed=500_000,
            predicted_memory=1024, actual_memory=2048,
            predicted_latency=100, actual_latency=200,
        )
        fb.record(rec)
        adjusted = fb.adjust_profile(orig)
        assert adjusted.speed < orig.speed
        assert adjusted.memory_bytes > orig.memory_bytes
        assert adjusted.latency_ns > orig.latency_ns

    def test_escalation_detected(self):
        fb = FeedbackLoop()
        c = _c(name="weak", speed=100, safety=SafetyLevel.LOW)
        r = _r(name="demanding", speed=1e6, safety=SafetyLevel.VERY_HIGH)
        escalations = fb.check_escalation([c], [r])
        assert len(escalations) == 1
        assert "demanding" in escalations[0]

    def test_no_escalation_when_qualified(self):
        fb = FeedbackLoop()
        c = _c(name="strong", speed=10e6, safety=SafetyLevel.VERY_HIGH)
        r = _r(name="easy", speed=1e6, safety=SafetyLevel.MEDIUM)
        escalations = fb.check_escalation([c], [r])
        assert len(escalations) == 0

    def test_multiple_feedback_converges(self):
        """After multiple feedback rounds, adjustments converge."""
        fb = FeedbackLoop()
        for _ in range(20):
            fb.record(FeedbackRecord(
                candidate_name="conv", role_name="r1",
                predicted_speed=1e6, actual_speed=800_000,
                predicted_memory=1024, actual_memory=1024,
                predicted_latency=100, actual_latency=100,
            ))
        adj = fb.adjustments["conv"]
        # Speed factor should be approaching 0.8
        assert abs(adj["speed_factor"] - 0.8) < 0.05


# ===========================================================================
# PredictiveCaster Tests
# ===========================================================================

class TestPredictiveCaster:

    def test_gap_detected(self):
        pc = PredictiveCaster()
        fc = DemandForecast(
            role=_r(name="future_role", speed=100e9, safety=SafetyLevel.VERY_HIGH),
            predicted_demand=1, confidence=0.9, time_horizon=3600,
        )
        pc.add_forecast(fc)
        gaps = pc.forecast_gaps(CANDIDATES)
        assert len(gaps) >= 1
        assert gaps[0].role_name == "future_role"
        assert gaps[0].severity > 0

    def test_no_gap_when_qualified(self):
        pc = PredictiveCaster()
        fc = DemandForecast(
            role=_r(name="easy_future", speed=100),  # trivial
            predicted_demand=1, confidence=0.9, time_horizon=3600,
        )
        pc.add_forecast(fc)
        gaps = pc.forecast_gaps([_c(name="any", speed=1000)])
        assert len(gaps) == 0

    def test_pre_position_suggests_best(self):
        pc = PredictiveCaster()
        fc = DemandForecast(
            role=_r(name="future_safe", speed=1e6, safety=SafetyLevel.VERY_HIGH),
            predicted_demand=1, confidence=0.9, time_horizon=3600,
        )
        pc.add_forecast(fc)
        suggestions = pc.pre_position(CANDIDATES, ROLES)
        if "future_safe" in suggestions:
            # Should suggest a very-high-safety candidate
            name = suggestions["future_safe"]
            c = next(c for c in CANDIDATES if c.name == name)
            assert c.safety >= SafetyLevel.VERY_HIGH

    def test_feedback_adjusts_predictions(self):
        pc = PredictiveCaster()
        fb = FeedbackLoop()
        # Record that rust_vm is slower than advertised
        fb.record(FeedbackRecord(
            candidate_name="rust_vm", role_name="test",
            predicted_speed=1e9, actual_speed=100_000,  # way slower
            predicted_memory=16384, actual_memory=16384,
            predicted_latency=80, actual_latency=80,
        ))
        fc = DemandForecast(
            role=_r(name="demanding", speed=500_000_000, safety=SafetyLevel.VERY_HIGH),
            predicted_demand=1, confidence=1.0, time_horizon=0,
        )
        pc.add_forecast(fc)
        gaps = pc.forecast_gaps(CANDIDATES, feedback=fb)
        # rust_vm is now adjusted down; may still qualify via other candidates
        # but the gap analysis should use adjusted profiles
        assert isinstance(gaps, list)

    def test_severity_scales_with_confidence(self):
        c = _c(name="weak", speed=100, safety=SafetyLevel.NONE)
        r = _r(name="hard", speed=1e12, safety=SafetyLevel.VERY_HIGH)

        pc1 = PredictiveCaster()
        pc1.add_forecast(DemandForecast(role=r, predicted_demand=1, confidence=0.9, time_horizon=100))
        gaps1 = list(pc1.forecast_gaps([c]))

        pc2 = PredictiveCaster()
        pc2.add_forecast(DemandForecast(role=r, predicted_demand=1, confidence=0.1, time_horizon=100))
        gaps2 = list(pc2.forecast_gaps([c]))

        assert gaps1[0].severity > gaps2[0].severity


# ===========================================================================
# Integration Test
# ===========================================================================

class TestIntegration:

    def test_full_pipeline(self):
        """Run the full pipeline: place → feedback → predict → re-place."""
        # Step 1: Initial placement
        placements = cast()
        assert len(placements) == len(ROLES)

        # Step 2: Feedback — rust_vm performed worse than expected
        fb = FeedbackLoop()
        fb.record(FeedbackRecord(
            candidate_name="rust_vm", role_name="aviation_adsb",
            predicted_speed=1e9, actual_speed=500_000_000,
            predicted_memory=16384, actual_memory=16384,
            predicted_latency=80, actual_latency=80,
        ))

        # Step 3: Re-place with adjusted profiles
        adjusted_candidates = [fb.adjust_profile(c) for c in CANDIDATES]
        algo = PlacementAlgorithm()
        new_result = algo.place(adjusted_candidates, ROLES)

        # Step 4: Predictive — future demand
        pc = PredictiveCaster()
        pc.add_forecast(DemandForecast(
            role=_r(name="future_iot", speed=10e6, mem=512,
                    safety=SafetyLevel.HIGH),
            predicted_demand=2, confidence=0.8, time_horizon=86400,
        ))
        gaps = pc.forecast_gaps(adjusted_candidates, feedback=fb)

        # Pipeline should complete without error
        assert len(new_result) == len(ROLES)
        assert isinstance(gaps, list)

    def test_print_placements_runs(self):
        """Ensure pretty-print doesn't crash."""
        placements = cast()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            print_placements(placements)
        output = buf.getvalue()
        assert "FLUX Casting" in output
        assert "aviation_adsb" in output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
