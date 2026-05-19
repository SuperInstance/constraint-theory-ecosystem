"""
test_distributed.py — Tests for flux_distributed

Tests the distributed constraint coordination system across:
- ConstraintPartition (watertight, range, node, auto strategies)
- VotingChecker (majority, unanimous, quorum modes)
- CascadeDetector (proximity and dependency models)
- DistributedMerger (join, meet, majority merge modes)
- ConsensusProtocol (agreed, majority, escalation, degraded outcomes)
- DistributedFlux orchestrator (3-node and 10-node configurations)

Forgemaster ⚒️ — 2026-05-19
"""

import pytest
import sys
import os

# Add src/python to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from flux_algebra import ErrorMask, Severity, SeverityMonoid
from flux_distributed import (
    ConstraintPartition,
    Partition,
    VotingChecker,
    VoteResult,
    CascadeDetector,
    CascadeWarning,
    DistributedMerger,
    MergeResult,
    ConsensusProtocol,
    ConsensusOutcome,
    ConsensusResult,
    DistributedFlux,
    NodeConfig,
    NodeResult,
)


# =============================================================================
# ConstraintPartition Tests
# =============================================================================

class TestConstraintPartition:
    """Tests for the watertight compartment partitioning."""

    def test_watertight_each_constraint_isolated(self):
        cp = ConstraintPartition(strategy="watertight")
        parts = cp.partition_constraints([(0, 10), (20, 30), (40, 50)])
        assert len(parts) == 3
        assert all(p.size == 1 for p in parts)

    def test_watertight_empty_constraints(self):
        cp = ConstraintPartition(strategy="watertight")
        parts = cp.partition_constraints([])
        assert len(parts) == 0

    def test_watertight_single_constraint(self):
        cp = ConstraintPartition(strategy="watertight")
        parts = cp.partition_constraints([(0, 100)])
        assert len(parts) == 1
        assert parts[0].constraints == [(0, 100)]

    def test_range_overlapping_grouped(self):
        cp = ConstraintPartition(strategy="range")
        parts = cp.partition_constraints([(0, 10), (5, 15), (20, 30)])
        # (0,10) and (5,15) overlap → same group
        # (20,30) is separate
        assert len(parts) == 2
        sizes = sorted(p.size for p in parts)
        assert sizes == [1, 2]

    def test_range_no_overlap(self):
        cp = ConstraintPartition(strategy="range")
        parts = cp.partition_constraints([(0, 5), (10, 15), (20, 25)])
        assert len(parts) == 3  # All separate

    def test_range_all_overlap(self):
        cp = ConstraintPartition(strategy="range")
        parts = cp.partition_constraints([(0, 10), (5, 15), (12, 20)])
        assert len(parts) == 1  # Chain overlaps → one group

    def test_node_partition(self):
        cp = ConstraintPartition(strategy="node")
        parts = cp.partition_constraints([(0, 10)], node_ids={"a", "b", "c"})
        assert len(parts) == 3
        names = {p.name for p in parts}
        assert "node_a" in names
        assert "node_b" in names

    def test_auto_partition_no_conflicts(self):
        cp = ConstraintPartition(strategy="auto")
        parts = cp.partition_constraints([(0, 5), (10, 15), (20, 25)])
        # No overlaps → all can share same color
        assert len(parts) >= 1

    def test_auto_partition_with_conflicts(self):
        cp = ConstraintPartition(strategy="auto")
        parts = cp.partition_constraints([(0, 10), (5, 15), (0, 10)])
        # (0,10) conflicts with (5,15); both (0,10) copies conflict
        assert len(parts) >= 2

    def test_partition_has_node_ids(self):
        cp = ConstraintPartition(strategy="watertight")
        parts = cp.partition_constraints([(0, 10)], node_ids={"x"})
        assert "x" in parts[0].node_ids

    def test_unknown_strategy_defaults_to_watertight(self):
        cp = ConstraintPartition(strategy="unknown_strategy")
        parts = cp.partition_constraints([(0, 10), (20, 30)])
        assert len(parts) == 2  # Falls back to watertight


# =============================================================================
# VotingChecker Tests
# =============================================================================

class TestVotingChecker:
    """Tests for the TMR-style voting checker."""

    def test_majority_2_of_3_pass(self):
        vc = VotingChecker(mode="majority")
        vc.cast_vote("a", True)
        vc.cast_vote("b", True)
        vc.cast_vote("c", False)
        result = vc.tally()
        assert result.passed
        assert result.pass_count == 2
        assert result.fail_count == 1
        assert not result.unanimous

    def test_majority_2_of_3_fail(self):
        vc = VotingChecker(mode="majority")
        vc.cast_vote("a", False)
        vc.cast_vote("b", False)
        vc.cast_vote("c", True)
        result = vc.tally()
        assert not result.passed
        assert result.fail_count == 2

    def test_unanimous_all_pass(self):
        vc = VotingChecker(mode="unanimous")
        vc.cast_vote("a", True)
        vc.cast_vote("b", True)
        vc.cast_vote("c", True)
        result = vc.tally()
        assert result.passed
        assert result.unanimous

    def test_unanimous_one_dissent(self):
        vc = VotingChecker(mode="unanimous")
        vc.cast_vote("a", True)
        vc.cast_vote("b", True)
        vc.cast_vote("c", False)
        result = vc.tally()
        assert not result.passed
        assert not result.unanimous

    def test_quorum_met(self):
        vc = VotingChecker(mode="quorum", quorum_size=3)
        vc.cast_vote("a", True)
        vc.cast_vote("b", True)
        vc.cast_vote("c", True)
        vc.cast_vote("d", False)
        vc.cast_vote("e", False)
        result = vc.tally()
        assert result.passed  # 3 pass >= quorum 3

    def test_quorum_not_met(self):
        vc = VotingChecker(mode="quorum", quorum_size=4)
        vc.cast_vote("a", True)
        vc.cast_vote("b", True)
        vc.cast_vote("c", True)
        vc.cast_vote("d", False)
        result = vc.tally()
        assert not result.passed  # 3 pass < quorum 4

    def test_faulted_voter_identified(self):
        vc = VotingChecker(mode="majority")
        vc.cast_vote("a", True)
        vc.cast_vote("b", True)
        vc.cast_vote("c", False)
        result = vc.tally()
        assert result.faulted_voter == "c"

    def test_confidence(self):
        vc = VotingChecker(mode="majority")
        vc.cast_vote("a", True)
        vc.cast_vote("b", True)
        vc.cast_vote("c", False)
        result = vc.tally()
        assert abs(result.confidence - 2.0 / 3.0) < 0.01

    def test_empty_votes(self):
        vc = VotingChecker(mode="majority")
        result = vc.tally()
        assert not result.passed
        assert result.total_voters == 0
        assert result.confidence == 0.0

    def test_reset_clears_votes(self):
        vc = VotingChecker(mode="majority")
        vc.cast_vote("a", True)
        vc.reset()
        result = vc.tally()
        assert result.total_voters == 0

    def test_tie_vote(self):
        """2 nodes, 1 pass, 1 fail → no strict majority."""
        vc = VotingChecker(mode="majority")
        vc.cast_vote("a", True)
        vc.cast_vote("b", False)
        result = vc.tally()
        assert not result.passed  # No strict majority

    def test_5_node_majority(self):
        vc = VotingChecker(mode="majority")
        for nid in ["a", "b", "c"]:
            vc.cast_vote(nid, True)
        for nid in ["d", "e"]:
            vc.cast_vote(nid, False)
        result = vc.tally()
        assert result.passed
        assert result.pass_count == 3


# =============================================================================
# CascadeDetector Tests
# =============================================================================

class TestCascadeDetector:
    """Tests for the cascade failure detector."""

    def test_no_cascade_on_first_violation(self):
        cd = CascadeDetector(model="proximity")
        constraints = [(0, 10), (5, 15)]
        warnings = cd.register_violation(0, constraints, "comp_0")
        assert len(warnings) == 0  # No prior history → no cascade risk

    def test_cascade_with_prior_history(self):
        cd = CascadeDetector(model="proximity")
        constraints = [(0, 10), (5, 15)]
        cd.register_violation(0, constraints, "comp_0")
        cd.register_violation(1, constraints, "comp_1")
        # Now violating 0 again — constraint 1 has history and overlaps
        warnings = cd.register_violation(0, constraints, "comp_0")
        assert len(warnings) == 1
        assert 1 in warnings[0].cascade_targets

    def test_no_cascade_non_overlapping(self):
        cd = CascadeDetector(model="proximity")
        constraints = [(0, 10), (20, 30)]
        cd.register_violation(0, constraints, "comp_0")
        cd.register_violation(1, constraints, "comp_1")
        # Constraint 1 has history but doesn't overlap with 0
        warnings = cd.register_violation(0, constraints, "comp_0")
        assert len(warnings) == 0

    def test_dependency_cascade(self):
        cd = CascadeDetector(model="dependency", dependencies={0: {1, 2}, 1: {3}})
        warnings = cd.register_violation(0, [], "dep")
        assert len(warnings) == 1
        assert set(warnings[0].cascade_targets) == {1, 2}

    def test_dependency_no_cascade_for_leaf(self):
        cd = CascadeDetector(model="dependency", dependencies={0: {1}})
        warnings = cd.register_violation(1, [], "leaf")
        assert len(warnings) == 0

    def test_checking_intensity_increases(self):
        cd = CascadeDetector(model="proximity")
        initial = cd.checking_intensity
        cd.register_violation(0, [(0, 10)], "c")
        assert cd.checking_intensity >= initial

    def test_checking_intensity_capped_at_1(self):
        cd = CascadeDetector(model="proximity")
        for i in range(20):
            cd.register_violation(0, [(0, 10)], "c")
        assert cd.checking_intensity <= 1.0

    def test_severity_escalation(self):
        cd = CascadeDetector(model="proximity")
        constraints = [(0, 10), (0, 10), (0, 10), (0, 10)]
        for i in range(4):
            cd.register_violation(i, constraints, "c")
        # Many overlapping violations → high severity
        warnings = cd.register_violation(0, constraints, "c")
        if warnings:
            assert warnings[0].severity in (Severity.ERROR, Severity.FATAL)

    def test_reset_clears_state(self):
        cd = CascadeDetector(model="proximity")
        cd.register_violation(0, [(0, 10)], "c")
        cd.reset()
        assert cd.checking_intensity <= 0.15  # Near baseline
        assert len(cd.cascade_history) == 0

    def test_cascade_history_recorded(self):
        cd = CascadeDetector(model="dependency", dependencies={0: {1}})
        cd.register_violation(0, [], "c")
        assert len(cd.cascade_history) == 1


# =============================================================================
# DistributedMerger Tests
# =============================================================================

class TestDistributedMerger:
    """Tests for the Boolean algebra error mask merger."""

    def test_join_merge_any_failure(self):
        dm = DistributedMerger(mode="join")
        dm.submit_mask("a", ErrorMask.from_list([True, False, False]))
        dm.submit_mask("b", ErrorMask.from_list([False, True, False]))
        dm.submit_mask("c", ErrorMask.from_list([False, False, True]))
        result = dm.merge()
        assert result.merged_mask.all_fail()

    def test_meet_merge_all_must_fail(self):
        dm = DistributedMerger(mode="meet")
        dm.submit_mask("a", ErrorMask.from_list([True, True, False]))
        dm.submit_mask("b", ErrorMask.from_list([True, False, True]))
        result = dm.merge()
        expected = ErrorMask.from_list([True, False, False])
        assert result.merged_mask == expected

    def test_majority_merge(self):
        dm = DistributedMerger(mode="majority")
        dm.submit_mask("a", ErrorMask.from_list([True, False, False]))
        dm.submit_mask("b", ErrorMask.from_list([True, True, False]))
        dm.submit_mask("c", ErrorMask.from_list([False, False, False]))
        result = dm.merge()
        assert result.merged_mask[0]  # 2/3 True → True
        assert not result.merged_mask[1]  # 1/3 True → False
        assert not result.merged_mask[2]  # 0/3 True → False

    def test_consensus_all_agree(self):
        dm = DistributedMerger(mode="join")
        dm.submit_mask("a", ErrorMask.from_list([True, False]))
        dm.submit_mask("b", ErrorMask.from_list([True, False]))
        result = dm.merge()
        assert result.consensus
        assert result.disagreement_mask.all_pass()

    def test_disagreement_detected(self):
        dm = DistributedMerger(mode="join")
        dm.submit_mask("a", ErrorMask.from_list([True, False]))
        dm.submit_mask("b", ErrorMask.from_list([False, True]))
        result = dm.merge()
        assert not result.consensus
        assert result.disagreement_mask.rank() == 2

    def test_empty_merge(self):
        dm = DistributedMerger(mode="join")
        result = dm.merge()
        assert result.node_count == 0
        assert result.consensus

    def test_single_node_merge(self):
        dm = DistributedMerger(mode="join")
        dm.submit_mask("a", ErrorMask.from_list([True, False]))
        result = dm.merge()
        assert result.consensus
        assert result.merged_mask == ErrorMask.from_list([True, False])

    def test_reset_clears_masks(self):
        dm = DistributedMerger(mode="join")
        dm.submit_mask("a", ErrorMask.from_list([True]))
        dm.reset()
        result = dm.merge()
        assert result.node_count == 0


# =============================================================================
# ConsensusProtocol Tests
# =============================================================================

class TestConsensusProtocol:
    """Tests for the severity monoid consensus protocol."""

    def test_all_agree_pass(self):
        cp = ConsensusProtocol(min_nodes=2)
        cp.submit_severity("a", Severity.PASS)
        cp.submit_severity("b", Severity.PASS)
        cp.submit_severity("c", Severity.PASS)
        result = cp.resolve()
        assert result.outcome == ConsensusOutcome.AGREED
        assert result.passed
        assert result.severity == Severity.PASS
        assert len(result.dissenting_nodes) == 0

    def test_all_agree_fatal(self):
        cp = ConsensusProtocol(min_nodes=2)
        cp.submit_severity("a", Severity.FATAL)
        cp.submit_severity("b", Severity.FATAL)
        result = cp.resolve()
        assert result.outcome == ConsensusOutcome.AGREED
        assert not result.passed
        assert result.severity == Severity.FATAL

    def test_majority_with_one_dissent(self):
        cp = ConsensusProtocol(min_nodes=2)
        cp.submit_severity("a", Severity.PASS)
        cp.submit_severity("b", Severity.PASS)
        cp.submit_severity("c", Severity.ERROR)
        result = cp.resolve()
        assert result.outcome == ConsensusOutcome.MAJORITY
        assert "c" in result.dissenting_nodes
        # Monoid: worst wins, so severity = ERROR
        assert result.severity == Severity.ERROR
        assert not result.passed

    def test_severity_monoid_worst_wins(self):
        """The key property: severity monoid always returns worst."""
        cp = ConsensusProtocol(min_nodes=2)
        cp.submit_severity("a", Severity.PASS)
        cp.submit_severity("b", Severity.WARN)
        cp.submit_severity("c", Severity.ERROR)
        result = cp.resolve()
        assert result.severity == Severity.ERROR

    def test_escalation_no_majority(self):
        cp = ConsensusProtocol(min_nodes=2, escalation_threshold=0.5)
        cp.submit_severity("a", Severity.PASS)
        cp.submit_severity("b", Severity.ERROR)
        cp.submit_severity("c", Severity.FATAL)
        result = cp.resolve()
        assert result.outcome == ConsensusOutcome.ESCALATION

    def test_degraded_too_few_nodes(self):
        cp = ConsensusProtocol(min_nodes=3)
        cp.submit_severity("a", Severity.PASS)
        result = cp.resolve()
        assert result.outcome == ConsensusOutcome.DEGRADED

    def test_degraded_no_nodes(self):
        cp = ConsensusProtocol(min_nodes=1)
        result = cp.resolve()
        assert result.outcome == ConsensusOutcome.DEGRADED

    def test_confidence_unanimous(self):
        cp = ConsensusProtocol(min_nodes=2)
        cp.submit_severity("a", Severity.PASS)
        cp.submit_severity("b", Severity.PASS)
        result = cp.resolve()
        assert result.confidence == 1.0

    def test_reset_clears_state(self):
        cp = ConsensusProtocol(min_nodes=1)
        cp.submit_severity("a", Severity.PASS)
        cp.reset()
        result = cp.resolve()
        assert result.outcome == ConsensusOutcome.DEGRADED

    def test_two_node_split(self):
        cp = ConsensusProtocol(min_nodes=2, escalation_threshold=0.5)
        cp.submit_severity("a", Severity.PASS)
        cp.submit_severity("b", Severity.ERROR)
        result = cp.resolve()
        assert result.outcome == ConsensusOutcome.ESCALATION


# =============================================================================
# DistributedFlux 3-Node Tests
# =============================================================================

class TestDistributedFlux3Node:
    """Tests for the full distributed system with 3 nodes."""

    @pytest.fixture
    def df(self):
        return DistributedFlux(
            nodes={
                "node_a": {"constraints": [(0, 100), (-50, 50)], "weight": 1.0},
                "node_b": {"constraints": [(0, 100), (-50, 50)], "weight": 1.0},
                "node_c": {"constraints": [(0, 100), (-50, 50)], "weight": 1.0},
            },
            voting="majority",
            cascade_detection=True,
            partition="watertight",
        )

    def test_all_pass(self, df):
        df.check("node_a", 42.0)
        df.check("node_b", 42.0)
        df.check("node_c", 42.0)
        result = df.consensus()
        assert result.passed
        assert result.outcome == ConsensusOutcome.AGREED

    def test_one_node_fails(self, df):
        df.check("node_a", 42.0)
        df.check("node_b", 200.0)
        df.check("node_c", 42.0)
        result = df.consensus()
        assert not result.passed  # Severity monoid: worst wins
        assert "node_b" in result.dissenting_nodes

    def test_two_nodes_fail(self, df):
        df.check("node_a", 200.0)
        df.check("node_b", 200.0)
        df.check("node_c", 42.0)
        result = df.consensus()
        assert not result.passed

    def test_all_fail(self, df):
        df.check("node_a", 200.0)
        df.check("node_b", -100.0)
        df.check("node_c", 150.0)
        result = df.consensus()
        assert not result.passed
        assert result.severity in (Severity.ERROR, Severity.FATAL)

    def test_node_result_has_error_mask(self, df):
        r = df.check("node_a", 42.0)
        assert isinstance(r.error_mask, ErrorMask)
        assert r.error_mask.all_pass()

    def test_node_result_has_severity(self, df):
        r = df.check("node_a", 200.0)
        assert r.severity in (Severity.ERROR, Severity.FATAL)

    def test_reset_clears_state(self, df):
        df.check("node_a", 42.0)
        df.reset()
        assert len(df.node_results) == 0
        assert len(df.cascade_warnings) == 0

    def test_partition_results_populated(self, df):
        df.check("node_a", 42.0)
        df.check("node_b", 200.0)
        df.check("node_c", 42.0)
        result = df.consensus()
        assert "node_a" in result.partition_results
        assert result.partition_results["node_a"]
        assert not result.partition_results["node_b"]

    def test_unknown_node_raises(self, df):
        with pytest.raises(ValueError, match="Unknown node"):
            df.check("nonexistent", 42.0)

    def test_consensus_before_any_check(self, df):
        result = df.consensus()
        assert result.outcome == ConsensusOutcome.DEGRADED

    def test_merged_mask_in_consensus(self, df):
        df.check("node_a", 42.0)
        df.check("node_b", 200.0)
        df.check("node_c", 42.0)
        result = df.consensus()
        assert result.merged_mask is not None

    def test_node_specific_values(self, df):
        """Each node can be checked with different values."""
        df.check("node_a", 0.0)
        df.check("node_b", 100.0)
        df.check("node_c", 50.0)
        results = df.node_results
        assert results["node_a"].value == 0.0
        assert results["node_b"].value == 100.0
        assert results["node_c"].value == 50.0


# =============================================================================
# DistributedFlux 10-Node Tests
# =============================================================================

class TestDistributedFlux10Node:
    """Tests for the full distributed system with 10 nodes."""

    @pytest.fixture
    def df10(self):
        nodes = {
            f"node_{i}": {"constraints": [(0, 100), (10, 90)], "weight": 1.0}
            for i in range(10)
        }
        return DistributedFlux(
            nodes=nodes,
            voting="majority",
            cascade_detection=True,
            partition="watertight",
        )

    def test_majority_pass(self, df10):
        """7/10 pass, 3/10 fail. Majority vote says pass,
        but severity monoid picks worst → overall not passed."""
        for i in range(7):
            df10.check(f"node_{i}", 50.0)
        for i in range(7, 10):
            df10.check(f"node_{i}", 200.0)
        result = df10.consensus()
        # Majority vote says pass, but severity monoid takes worst → fail
        assert not result.passed  # severity monoid: worst node wins
        assert len(result.dissenting_nodes) == 3  # 3 failing nodes

    def test_majority_fail(self, df10):
        for i in range(4):
            df10.check(f"node_{i}", 50.0)
        for i in range(4, 10):
            df10.check(f"node_{i}", 200.0)
        result = df10.consensus()
        assert not result.passed
        assert result.severity in (Severity.ERROR, Severity.FATAL)

    def test_unanimous_pass(self, df10):
        for i in range(10):
            df10.check(f"node_{i}", 50.0)
        result = df10.consensus()
        assert result.passed
        assert result.outcome == ConsensusOutcome.AGREED

    def test_unanimous_fail(self, df10):
        for i in range(10):
            df10.check(f"node_{i}", 200.0)
        result = df10.consensus()
        assert not result.passed
        assert result.outcome == ConsensusOutcome.AGREED

    def test_one_pass_nine_fail(self, df10):
        df10.check("node_0", 50.0)
        for i in range(1, 10):
            df10.check(f"node_{i}", 200.0)
        result = df10.consensus()
        assert not result.passed
        assert "node_0" in result.dissenting_nodes

    def test_five_and_five_split(self, df10):
        """5 pass, 5 fail → no strict majority → depends on implementation."""
        for i in range(5):
            df10.check(f"node_{i}", 50.0)
        for i in range(5, 10):
            df10.check(f"node_{i}", 200.0)
        result = df10.consensus()
        # With 5/10 pass, no strict majority (>50%), so fail
        assert not result.passed

    def test_partial_check(self, df10):
        """Only check some nodes, not all."""
        df10.check("node_0", 50.0)
        df10.check("node_1", 50.0)
        df10.check("node_2", 200.0)
        result = df10.consensus()
        # 2/3 pass → majority pass, but severity monoid may override
        assert result.merged_mask is not None

    def test_reset_and_recheck(self, df10):
        for i in range(10):
            df10.check(f"node_{i}", 200.0)
        df10.reset()
        for i in range(10):
            df10.check(f"node_{i}", 50.0)
        result = df10.consensus()
        assert result.passed


# =============================================================================
# NodeConfig Tests
# =============================================================================

class TestNodeConfig:
    """Tests for individual node configuration."""

    def test_check_value_pass(self):
        nc = NodeConfig(constraints=[(0, 100), (-50, 50)])
        mask = nc.check_value(42.0)
        assert mask.all_pass()

    def test_check_value_fail(self):
        nc = NodeConfig(constraints=[(0, 100)])
        mask = nc.check_value(200.0)
        assert mask.any_fail()

    def test_check_value_partial_fail(self):
        nc = NodeConfig(constraints=[(0, 100), (-50, 50)])
        mask = nc.check_value(75.0)
        assert not mask[0]  # 75 is in [0, 100]
        assert mask[1]      # 75 is NOT in [-50, 50]

    def test_severity_pass(self):
        nc = NodeConfig(constraints=[(0, 100)])
        mask = ErrorMask.from_list([False])
        assert nc.compute_severity(mask) == Severity.PASS

    def test_severity_warn(self):
        nc = NodeConfig(constraints=[(0, 100), (0, 100), (0, 100), (0, 100)])
        mask = ErrorMask.from_list([False, False, False, True])
        assert nc.compute_severity(mask) == Severity.WARN

    def test_severity_error(self):
        nc = NodeConfig(constraints=[(0, 100), (0, 100), (0, 100), (0, 100)])
        mask = ErrorMask.from_list([False, False, True, True])
        assert nc.compute_severity(mask) == Severity.ERROR

    def test_severity_fatal(self):
        nc = NodeConfig(constraints=[(0, 100), (0, 100)])
        mask = ErrorMask.from_list([True, True])
        assert nc.compute_severity(mask) == Severity.FATAL

    def test_empty_constraints(self):
        nc = NodeConfig(constraints=[])
        mask = nc.check_value(42.0)
        assert mask.all_pass()
        assert mask.n == 0

    def test_weight_default(self):
        nc = NodeConfig(constraints=[(0, 10)])
        assert nc.weight == 1.0


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_pass(self):
        df = DistributedFlux(
            nodes={
                "a": {"constraints": [(0, 100)], "weight": 1.0},
                "b": {"constraints": [(0, 100)], "weight": 1.0},
                "c": {"constraints": [(0, 100)], "weight": 1.0},
            },
            voting="majority",
            cascade_detection=True,
            partition="watertight",
        )
        for nid in ["a", "b", "c"]:
            r = df.check(nid, 50.0)
            assert r.passed
        result = df.consensus()
        assert result.passed
        assert result.outcome == ConsensusOutcome.AGREED
        assert result.severity == Severity.PASS

    def test_full_pipeline_with_cascade(self):
        df = DistributedFlux(
            nodes={
                "a": {"constraints": [(0, 10), (5, 15)], "weight": 1.0},
                "b": {"constraints": [(0, 10), (5, 15)], "weight": 1.0},
                "c": {"constraints": [(0, 10), (5, 15)], "weight": 1.0},
            },
            voting="majority",
            cascade_detection=True,
            partition="watertight",
        )
        # Cause violations that might cascade
        df.check("a", 20.0)  # Fails both
        df.check("b", 12.0)  # Fails first constraint only
        df.check("c", 20.0)  # Fails both
        result = df.consensus()
        assert not result.passed
        # Cascade warnings should be present
        assert len(df.cascade_warnings) > 0

    def test_different_constraints_per_node(self):
        df = DistributedFlux(
            nodes={
                "temp": {"constraints": [(0, 100)], "weight": 1.0},
                "pressure": {"constraints": [(800, 1200)], "weight": 1.0},
                "humidity": {"constraints": [(20, 80)], "weight": 1.0},
            },
            voting="majority",
            cascade_detection=False,
            partition="watertight",
        )
        df.check("temp", 50.0)
        df.check("pressure", 1000.0)
        df.check("humidity", 60.0)
        result = df.consensus()
        assert result.passed

    def test_different_constraints_mixed_results(self):
        df = DistributedFlux(
            nodes={
                "temp": {"constraints": [(0, 100)], "weight": 1.0},
                "pressure": {"constraints": [(800, 1200)], "weight": 1.0},
                "humidity": {"constraints": [(20, 80)], "weight": 1.0},
            },
            voting="majority",
            cascade_detection=False,
            partition="watertight",
        )
        df.check("temp", 50.0)
        df.check("pressure", 2000.0)  # Fail
        df.check("humidity", 60.0)
        result = df.consensus()
        # Severity monoid: worst wins → not passed
        assert not result.passed

    def test_checking_intensity_property(self):
        df = DistributedFlux(
            nodes={
                "a": {"constraints": [(0, 10)], "weight": 1.0},
                "b": {"constraints": [(0, 10)], "weight": 1.0},
            },
            cascade_detection=True,
            min_consensus_nodes=1,
        )
        # Before violations
        assert df.checking_intensity <= 0.15
        # After violations
        df.check("a", 20.0)
        assert df.checking_intensity > 0.1

    def test_multiple_consensus_rounds(self):
        df = DistributedFlux(
            nodes={
                "a": {"constraints": [(0, 100)], "weight": 1.0},
                "b": {"constraints": [(0, 100)], "weight": 1.0},
                "c": {"constraints": [(0, 100)], "weight": 1.0},
            },
            cascade_detection=True,
        )
        # Round 1: pass
        for nid in ["a", "b", "c"]:
            df.check(nid, 50.0)
        r1 = df.consensus()
        assert r1.passed

        # Round 2: fail (after reset)
        df.reset()
        for nid in ["a", "b", "c"]:
            df.check(nid, 200.0)
        r2 = df.consensus()
        assert not r2.passed

    def test_meet_merge_mode(self):
        """Meet mode: all nodes must report a failure for it to count."""
        df = DistributedFlux(
            nodes={
                "a": {"constraints": [(0, 100)], "weight": 1.0},
                "b": {"constraints": [(0, 100)], "weight": 1.0},
                "c": {"constraints": [(0, 100)], "weight": 1.0},
            },
            merge_mode="meet",
            cascade_detection=False,
        )
        df.check("a", 50.0)    # Pass
        df.check("b", 200.0)   # Fail
        df.check("c", 50.0)    # Pass
        result = df.consensus()
        # Merged mask via meet: only failures reported by ALL nodes
        assert result.merged_mask is not None
        assert result.merged_mask.all_pass()  # Not all nodes agreed on any failure
