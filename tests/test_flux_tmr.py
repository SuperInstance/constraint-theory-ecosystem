"""Tests for flux_tmr — Triple Modular Redundancy."""

import sys
sys.path.insert(0, "/home/phoenix/.openclaw/workspace/constraint-theory-ecosystem/src/python")

from flux_tmr import (
    TMRChecker, TMRResult, TMRVoter, Vote, ChannelResult,
    DirectRangeChecker, NegatedLogicChecker, OffsetChecker, EpsilonChecker,
    NMRChecker,
)

import pytest


# ---------------------------------------------------------------------------
# Individual checker tests
# ---------------------------------------------------------------------------

class TestDirectRangeChecker:
    def test_pass_in_range(self):
        c = DirectRangeChecker(0, 100)
        r = c.check(50)
        assert r.vote == Vote.PASS

    def test_fail_below_range(self):
        c = DirectRangeChecker(0, 100)
        r = c.check(-1)
        assert r.vote == Vote.FAIL

    def test_fail_above_range(self):
        c = DirectRangeChecker(0, 100)
        r = c.check(101)
        assert r.vote == Vote.FAIL

    def test_boundary_min(self):
        c = DirectRangeChecker(0, 100)
        assert c.check(0).vote == Vote.PASS

    def test_boundary_max(self):
        c = DirectRangeChecker(0, 100)
        assert c.check(100).vote == Vote.PASS

    def test_type_error(self):
        c = DirectRangeChecker(0, 100)
        r = c.check("not_a_number")
        assert r.vote == Vote.ERROR


class TestNegatedLogicChecker:
    def test_pass_in_range(self):
        c = NegatedLogicChecker(0, 100)
        assert c.check(50).vote == Vote.PASS

    def test_fail_out_of_range(self):
        c = NegatedLogicChecker(0, 100)
        assert c.check(-1).vote == Vote.FAIL
        assert c.check(101).vote == Vote.FAIL

    def test_type_error(self):
        c = NegatedLogicChecker(0, 100)
        assert c.check("bad").vote == Vote.ERROR


class TestOffsetChecker:
    def test_pass_in_range(self):
        c = OffsetChecker(0, 100)
        assert c.check(50).vote == Vote.PASS

    def test_fail_out_of_range(self):
        c = OffsetChecker(0, 100)
        assert c.check(-1).vote == Vote.FAIL
        assert c.check(101).vote == Vote.FAIL

    def test_center_value(self):
        c = OffsetChecker(0, 100)
        assert c.check(50).vote == Vote.PASS
        assert c.center == 50.0
        assert c.half_span == 50.0


class TestEpsilonChecker:
    def test_pass_in_range(self):
        c = EpsilonChecker(0, 100)
        assert c.check(50).vote == Vote.PASS

    def test_boundary_with_epsilon(self):
        c = EpsilonChecker(0, 100, epsilon=1e-9)
        assert c.check(0).vote == Vote.PASS
        assert c.check(100).vote == Vote.PASS


# ---------------------------------------------------------------------------
# TMR Voter tests
# ---------------------------------------------------------------------------

class TestTMRVoter:
    def test_unanimous_pass(self):
        voter = TMRVoter()
        results = [
            ChannelResult(0, Vote.PASS),
            ChannelResult(1, Vote.PASS),
            ChannelResult(2, Vote.PASS),
        ]
        r = voter.vote(results)
        assert r.passed
        assert r.consensus
        assert r.confidence == 1.0

    def test_unanimous_fail(self):
        voter = TMRVoter()
        results = [
            ChannelResult(0, Vote.FAIL),
            ChannelResult(1, Vote.FAIL),
            ChannelResult(2, Vote.FAIL),
        ]
        r = voter.vote(results)
        assert not r.passed
        assert r.consensus

    def test_majority_pass_2of3(self):
        voter = TMRVoter()
        results = [
            ChannelResult(0, Vote.PASS),
            ChannelResult(1, Vote.PASS),
            ChannelResult(2, Vote.FAIL),
        ]
        r = voter.vote(results)
        assert r.passed
        assert not r.consensus
        assert r.faulted_channel == 2
        assert r.confidence == 0.6667

    def test_majority_fail_2of3(self):
        voter = TMRVoter()
        results = [
            ChannelResult(0, Vote.FAIL),
            ChannelResult(1, Vote.FAIL),
            ChannelResult(2, Vote.PASS),
        ]
        r = voter.vote(results)
        assert not r.passed
        assert r.faulted_channel == 2

    def test_no_majority_all_disagree(self):
        voter = TMRVoter()
        results = [
            ChannelResult(0, Vote.PASS),
            ChannelResult(1, Vote.FAIL),
            ChannelResult(2, Vote.ERROR),
        ]
        r = voter.vote(results)
        assert not r.passed
        assert not r.consensus
        assert r.confidence == 0.0


# ---------------------------------------------------------------------------
# TMR Checker integration tests
# ---------------------------------------------------------------------------

class TestTMRChecker:
    def test_consensus_pass(self):
        checker = TMRChecker(
            DirectRangeChecker(0, 100),
            NegatedLogicChecker(0, 100),
            OffsetChecker(0, 100),
        )
        result = checker.check(50)
        assert result.passed
        assert result.consensus

    def test_consensus_fail(self):
        checker = TMRChecker(
            DirectRangeChecker(0, 100),
            NegatedLogicChecker(0, 100),
            OffsetChecker(0, 100),
        )
        result = checker.check(-1)
        assert not result.passed
        assert result.consensus

    def test_channel_health(self):
        checker = TMRChecker(
            DirectRangeChecker(0, 100),
            NegatedLogicChecker(0, 100),
            OffsetChecker(0, 100),
        )
        health = checker.channel_health
        assert len(health) == 3
        assert all(not h["disabled"] for h in health.values())

    def test_history_tracking(self):
        checker = TMRChecker(
            DirectRangeChecker(0, 100),
            NegatedLogicChecker(0, 100),
            OffsetChecker(0, 100),
        )
        checker.check(50)
        checker.check(75)
        assert len(checker.history) == 2

    def test_fault_reset(self):
        checker = TMRChecker(
            DirectRangeChecker(0, 100),
            NegatedLogicChecker(0, 100),
            OffsetChecker(0, 100),
        )
        checker._fault_counts[0] = 3
        checker.reset_faults()
        assert all(v == 0 for v in checker._fault_counts.values())

    def test_boundary_values(self):
        checker = TMRChecker(
            DirectRangeChecker(0, 100),
            NegatedLogicChecker(0, 100),
            OffsetChecker(0, 100),
        )
        assert checker.check(0).passed
        assert checker.check(100).passed

    def test_float_values(self):
        checker = TMRChecker(
            DirectRangeChecker(0.0, 1.0),
            NegatedLogicChecker(0.0, 1.0),
            OffsetChecker(0.0, 1.0),
        )
        assert checker.check(0.5).passed
        assert not checker.check(1.1).passed


class TestNMRChecker:
    def test_5_channel_consensus(self):
        checkers = [
            DirectRangeChecker(0, 100, i) for i in range(3)
        ] + [
            NegatedLogicChecker(0, 100, 3),
            OffsetChecker(0, 100, 4),
        ]
        nmr = NMRChecker(checkers)
        result = nmr.check(50)
        assert result.passed

    def test_requires_minimum_3(self):
        with pytest.raises(ValueError):
            NMRChecker([DirectRangeChecker(0, 100)])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
