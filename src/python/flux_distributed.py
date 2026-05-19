"""
flux_distributed.py — Distributed Constraint Coordination System

FLUX v4: Constraint checking across multiple nodes (sensors, devices, edge computers).

Cross-industry insights baked in:
  - Maritime watertight compartments → ConstraintPartition isolates failure domains
  - Aviation TMR → VotingChecker runs 3 independent checkers, majority wins
  - Insurance risk pooling → Adaptive checking intensity based on violation history
  - Ecology predator-prey → CascadeDetector adapts to violation density

Architecture:
  1. ConstraintPartition — partitions constraints into independent groups
  2. VotingChecker — TMR-style voting across independent checkers
  3. CascadeDetector — detects cascading failure propagation
  4. DistributedMerger — merges error masks from multiple nodes (Boolean algebra)
  5. ConsensusProtocol — severity-monoid-based consensus when nodes disagree
  6. DistributedFlux — top-level orchestrator

Usage:
    df = DistributedFlux(
        nodes={
            "sensor_a": {"constraints": [(0, 100)], "weight": 1.0},
            "sensor_b": {"constraints": [(0, 100)], "weight": 1.0},
            "sensor_c": {"constraints": [(0, 100)], "weight": 1.0},
        },
        voting="majority",
        cascade_detection=True,
        partition="watertight",
    )
    df.check("sensor_a", 42.0)
    df.check("sensor_b", 42.0)
    df.check("sensor_c", 42.0)
    result = df.consensus()

Forgemaster ⚒️ — 2026-05-19
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from flux_algebra import ErrorMask, Severity, SeverityMonoid
from flux_tmr import (
    CheckerBase,
    ChannelResult,
    DirectRangeChecker,
    NegatedLogicChecker,
    OffsetChecker,
    TMRVoter,
    Vote,
)


# =============================================================================
# 1. Constraint Partition (Maritime Watertight Compartments)
# =============================================================================

@dataclass
class Partition:
    """A watertight compartment: an independent group of constraints.

    Failures in one compartment cannot cascade to another.
    """
    name: str
    constraints: List[Tuple[float, float]]  # [(min, max), ...]
    node_ids: Set[str] = field(default_factory=set)

    @property
    def size(self) -> int:
        return len(self.constraints)


class ConstraintPartition:
    """Partitions constraints into independent watertight compartments.

    Maritime insight: ships have watertight compartments so a hull breach in
    one section doesn't sink the whole ship. Similarly, constraints are grouped
    so a cascade in one group can't propagate to others.

    Partitioning strategies:
      - "watertight" — each constraint gets its own compartment (max isolation)
      - "range" — constraints with overlapping ranges share a compartment
      - "node" — constraints are grouped by which node owns them
      - "auto" — use graph coloring on constraint conflict graph
    """

    def __init__(self, strategy: str = "watertight"):
        self.strategy = strategy
        self.partitions: List[Partition] = []

    def partition_constraints(
        self,
        constraints: List[Tuple[float, float]],
        node_ids: Optional[Set[str]] = None,
    ) -> List[Partition]:
        """Partition a list of (min, max) range constraints into compartments."""
        if self.strategy == "watertight":
            return self._watertight(constraints, node_ids or set())
        elif self.strategy == "range":
            return self._by_range(constraints, node_ids or set())
        elif self.strategy == "node":
            return self._by_node(constraints, node_ids or set())
        elif self.strategy == "auto":
            return self._auto(constraints, node_ids or set())
        else:
            return self._watertight(constraints, node_ids or set())

    def _watertight(
        self, constraints: List[Tuple[float, float]], node_ids: Set[str]
    ) -> List[Partition]:
        """Each constraint is its own compartment — maximum isolation."""
        self.partitions = [
            Partition(name=f"compartment_{i}", constraints=[c], node_ids=set(node_ids))
            for i, c in enumerate(constraints)
        ]
        return self.partitions

    def _by_range(
        self, constraints: List[Tuple[float, float]], node_ids: Set[str]
    ) -> List[Partition]:
        """Group constraints with overlapping ranges into same compartment."""
        if not constraints:
            return []

        # Sort by min value
        indexed = sorted(enumerate(constraints), key=lambda x: x[1][0])
        groups: List[List[Tuple[int, Tuple[float, float]]]] = []
        current_group: List[Tuple[int, Tuple[float, float]]] = [indexed[0]]

        for item in indexed[1:]:
            _, (lo, hi) = item
            _, (prev_lo, prev_hi) = current_group[-1]
            # Overlap if this range starts before previous ends
            if lo <= prev_hi:
                current_group.append(item)
            else:
                groups.append(current_group)
                current_group = [item]
        groups.append(current_group)

        self.partitions = [
            Partition(
                name=f"range_group_{i}",
                constraints=[c for _, c in group],
                node_ids=set(node_ids),
            )
            for i, group in enumerate(groups)
        ]
        return self.partitions

    def _by_node(
        self, constraints: List[Tuple[float, float]], node_ids: Set[str]
    ) -> List[Partition]:
        """One compartment per node."""
        if not node_ids:
            return [Partition(name="single", constraints=constraints)]
        self.partitions = [
            Partition(name=f"node_{nid}", constraints=list(constraints), node_ids={nid})
            for nid in sorted(node_ids)
        ]
        return self.partitions

    def _auto(
        self, constraints: List[Tuple[float, float]], node_ids: Set[str]
    ) -> List[Partition]:
        """Graph coloring: constraints that can conflict share a partition,
        then color the conflict graph for minimum partitions."""
        n = len(constraints)
        if n == 0:
            return []

        # Build conflict graph: edges between overlapping constraints
        adj: Dict[int, Set[int]] = defaultdict(set)
        for i in range(n):
            for j in range(i + 1, n):
                lo_i, hi_i = constraints[i]
                lo_j, hi_j = constraints[j]
                # Conflict if ranges overlap
                if lo_i <= hi_j and lo_j <= hi_i:
                    adj[i].add(j)
                    adj[j].add(i)

        # Greedy coloring
        colors: Dict[int, int] = {}
        for node in range(n):
            neighbor_colors = {colors[nb] for nb in adj[node] if nb in colors}
            color = 0
            while color in neighbor_colors:
                color += 1
            colors[node] = color

        # Group by color
        num_colors = max(colors.values()) + 1 if colors else 1
        groups: List[List[int]] = [[] for _ in range(num_colors)]
        for idx, color in colors.items():
            groups[color].append(idx)

        self.partitions = [
            Partition(
                name=f"color_{i}",
                constraints=[constraints[idx] for idx in group],
                node_ids=set(node_ids),
            )
            for i, group in enumerate(groups) if group
        ]
        return self.partitions


# =============================================================================
# 2. Voting Checker (Aviation TMR)
# =============================================================================

@dataclass
class VoteResult:
    """Result of a distributed vote across nodes."""
    passed: bool
    majority: bool          # True if strict majority agreed
    unanimous: bool         # True if all agreed
    pass_count: int
    fail_count: int
    total_voters: int
    faulted_voter: Optional[str] = None
    confidence: float = 1.0


class VotingChecker:
    """TMR-style voting across N independent checkers.

    Aviation insight: DO-178C requires triple modular redundancy. Three
    independent systems vote on every decision. Majority wins, minority
    is flagged as faulted.

    Modes:
      - "majority": >50% must agree (2 of 3, 3 of 5, etc.)
      - "unanimous": 100% must agree (any disagreement = fail)
      - "quorum": need at least `quorum_size` agreeing
    """

    def __init__(
        self,
        mode: str = "majority",
        quorum_size: Optional[int] = None,
    ):
        self.mode = mode
        self.quorum_size = quorum_size
        self._results: Dict[str, bool] = {}  # node_id -> last result

    def cast_vote(self, node_id: str, passed: bool) -> None:
        """Record a node's vote."""
        self._results[node_id] = passed

    def tally(self) -> VoteResult:
        """Count votes and determine outcome."""
        if not self._results:
            return VoteResult(
                passed=False, majority=False, unanimous=False,
                pass_count=0, fail_count=0, total_voters=0,
                confidence=0.0,
            )

        pass_count = sum(1 for v in self._results.values() if v)
        fail_count = len(self._results) - pass_count
        total = len(self._results)

        unanimous = (pass_count == total) or (fail_count == total)
        majority_pass = pass_count > total // 2
        majority_fail = fail_count > total // 2

        # Identify faulted voter (the one in the minority)
        faulted = None
        if not unanimous and (majority_pass or majority_fail):
            if majority_pass:
                # Fail voters are faulted
                faulted_nodes = [nid for nid, v in self._results.items() if not v]
                faulted = faulted_nodes[0] if len(faulted_nodes) == 1 else None
            else:
                faulted_nodes = [nid for nid, v in self._results.items() if v]
                faulted = faulted_nodes[0] if len(faulted_nodes) == 1 else None

        # Quorum check
        if self.mode == "quorum" and self.quorum_size is not None:
            passed = pass_count >= self.quorum_size
        elif self.mode == "unanimous":
            passed = pass_count == total
        else:  # majority
            passed = majority_pass

        confidence = max(pass_count, fail_count) / total if total else 0.0

        return VoteResult(
            passed=passed,
            majority=majority_pass or majority_fail,
            unanimous=unanimous,
            pass_count=pass_count,
            fail_count=fail_count,
            total_voters=total,
            faulted_voter=faulted,
            confidence=round(confidence, 4),
        )

    def reset(self) -> None:
        """Clear all votes."""
        self._results.clear()


# =============================================================================
# 3. Cascade Detector (Ecology predator-prey dynamics)
# =============================================================================

@dataclass
class CascadeWarning:
    """Warning about a potential cascading failure."""
    source_constraint: int       # Index of the constraint that failed
    cascade_targets: List[int]   # Constraints at risk of cascading
    severity: Severity           # How bad the cascade could be
    compartment: str             # Which compartment is affected
    description: str = ""


class CascadeDetector:
    """Detects when one constraint failure could cascade to others.

    Ecology insight: in predator-prey systems, the population of one species
    affects others through the food web. Similarly, constraint failures can
    propagate through dependency chains. The detector adapts checking intensity
    based on violation density — more violations = more vigilant.

    Two cascade models:
      - "proximity": constraints with overlapping ranges can cascade
      - "dependency": explicit dependency graph between constraints
    """

    def __init__(
        self,
        model: str = "proximity",
        dependencies: Optional[Dict[int, Set[int]]] = None,
    ):
        self.model = model
        self.dependencies = dependencies or {}
        self._cascade_history: List[CascadeWarning] = []
        self._violation_counts: Dict[int, int] = defaultdict(int)  # constraint_idx -> count

    def register_violation(
        self,
        constraint_idx: int,
        constraints: List[Tuple[float, float]],
        compartment_name: str = "",
    ) -> List[CascadeWarning]:
        """Register a violation and check for cascade risks."""
        self._violation_counts[constraint_idx] += 1
        warnings = []

        if self.model == "proximity":
            warnings = self._proximity_cascade(constraint_idx, constraints, compartment_name)
        elif self.model == "dependency":
            warnings = self._dependency_cascade(constraint_idx, compartment_name)

        self._cascade_history.extend(warnings)
        return warnings

    def _proximity_cascade(
        self,
        idx: int,
        constraints: List[Tuple[float, float]],
        compartment_name: str,
    ) -> List[CascadeWarning]:
        """Check if a violation at idx could cascade to neighboring constraints."""
        lo, hi = constraints[idx]
        targets: List[int] = []

        for i, (clo, chi) in enumerate(constraints):
            if i == idx:
                continue
            # Cascade risk: ranges overlap, so a value that violates one
            # might also violate the other
            if lo <= chi and clo <= hi:
                # Higher risk if the other constraint has been violated before
                if self._violation_counts.get(i, 0) > 0:
                    targets.append(i)

        if not targets:
            return []

        severity = self._compute_cascade_severity(idx, targets)
        return [CascadeWarning(
            source_constraint=idx,
            cascade_targets=targets,
            severity=severity,
            compartment=compartment_name,
            description=f"Constraint {idx} violation may cascade to {targets}",
        )]

    def _dependency_cascade(
        self, idx: int, compartment_name: str
    ) -> List[CascadeWarning]:
        """Check explicit dependency graph for cascade risks."""
        targets = list(self.dependencies.get(idx, set()))
        if not targets:
            return []

        severity = self._compute_cascade_severity(idx, targets)
        return [CascadeWarning(
            source_constraint=idx,
            cascade_targets=targets,
            severity=severity,
            compartment=compartment_name,
            description=f"Dependency cascade from {idx} to {targets}",
        )]

    def _compute_cascade_severity(self, source: int, targets: List[int]) -> Severity:
        """Compute severity of a potential cascade."""
        total_risk = 1 + len(targets)
        for t in targets:
            total_risk += self._violation_counts.get(t, 0)

        if total_risk >= 5:
            return Severity.FATAL
        elif total_risk >= 3:
            return Severity.ERROR
        elif total_risk >= 1:
            return Severity.WARN
        return Severity.PASS

    @property
    def checking_intensity(self) -> float:
        """Adaptive checking intensity based on violation density.

        Ecology insight: predators concentrate where prey is dense.
        Similarly, we check more intensely where violations cluster.
        Returns 0.0 (relaxed) to 1.0 (maximum vigilance).
        """
        total = sum(self._violation_counts.values())
        if total == 0:
            return 0.1  # Baseline vigilance
        return min(1.0, 0.1 + total * 0.1)

    @property
    def cascade_history(self) -> List[CascadeWarning]:
        return list(self._cascade_history)

    def reset(self) -> None:
        self._cascade_history.clear()
        self._violation_counts.clear()


# =============================================================================
# 4. Distributed Merger (Boolean algebra from flux_algebra)
# =============================================================================

@dataclass
class MergeResult:
    """Result of merging error masks from multiple nodes."""
    merged_mask: ErrorMask
    agreement_mask: ErrorMask   # All nodes agree on these bits
    disagreement_mask: ErrorMask  # Nodes disagree on these bits
    node_count: int
    consensus: bool              # All nodes agreed on everything


class DistributedMerger:
    """Merges error masks from multiple nodes using Boolean algebra.

    Uses ErrorMask operations from flux_algebra:
      - join (OR): union of all failures (pessimistic merge)
      - meet (AND): intersection of failures (optimistic merge)
      - xor: disagreement detection
    """

    def __init__(self, mode: str = "join"):
        """
        Args:
            mode: "join" (any failure = merged failure), "meet" (all must fail),
                  "majority" (majority of nodes must report failure)
        """
        self.mode = mode
        self._node_masks: Dict[str, ErrorMask] = {}

    def submit_mask(self, node_id: str, mask: ErrorMask) -> None:
        """Submit a node's error mask."""
        self._node_masks[node_id] = mask

    def merge(self) -> MergeResult:
        """Merge all submitted error masks."""
        if not self._node_masks:
            return MergeResult(
                merged_mask=ErrorMask(0, 0),
                agreement_mask=ErrorMask(0, 0),
                disagreement_mask=ErrorMask(0, 0),
                node_count=0,
                consensus=True,
            )

        masks = list(self._node_masks.values())
        n = masks[0].n
        if n == 0:
            return MergeResult(
                merged_mask=ErrorMask(0, 0),
                agreement_mask=ErrorMask(0, 0),
                disagreement_mask=ErrorMask(0, 0),
                node_count=len(masks),
                consensus=True,
            )

        # Compute merged mask based on mode
        if self.mode == "join":
            merged = masks[0]
            for m in masks[1:]:
                merged = merged.join(m)
        elif self.mode == "meet":
            merged = masks[0]
            for m in masks[1:]:
                merged = merged.meet(m)
        elif self.mode == "majority":
            merged = self._majority_merge(masks, n)
        else:
            merged = masks[0]
            for m in masks[1:]:
                merged = merged.join(m)

        # Compute agreement (all identical bits) and disagreement
        agreement_bits = 0
        disagreement_bits = 0
        for i in range(n):
            bit_values = set()
            for m in masks:
                bit_values.add(m[i])
            if len(bit_values) == 1:
                if masks[0][i]:
                    agreement_bits |= (1 << i)
            else:
                disagreement_bits |= (1 << i)

        consensus = disagreement_bits == 0

        return MergeResult(
            merged_mask=merged,
            agreement_mask=ErrorMask(agreement_bits, n),
            disagreement_mask=ErrorMask(disagreement_bits, n),
            node_count=len(masks),
            consensus=consensus,
        )

    def _majority_merge(self, masks: List[ErrorMask], n: int) -> ErrorMask:
        """Per-bit majority voting across masks."""
        threshold = len(masks) / 2.0
        bits = 0
        for i in range(n):
            fail_count = sum(1 for m in masks if m[i])
            if fail_count > threshold:
                bits |= (1 << i)
        return ErrorMask(bits, n)

    def reset(self) -> None:
        self._node_masks.clear()


# =============================================================================
# 5. Consensus Protocol (Severity Monoid)
# =============================================================================

class ConsensusOutcome(Enum):
    """Possible outcomes of the consensus protocol."""
    AGREED = auto()          # All nodes agree
    MAJORITY = auto()        # Majority agrees, minority dissenting
    ESCALATION = auto()      # No clear majority, needs human intervention
    DEGRADED = auto()        # Too few nodes to reach consensus


@dataclass
class ConsensusResult:
    """Final consensus result from the distributed system."""
    outcome: ConsensusOutcome
    passed: bool
    severity: Severity
    confidence: float
    agreeing_nodes: List[str]
    dissenting_nodes: List[str]
    merged_mask: Optional[ErrorMask] = None
    cascade_warnings: List[CascadeWarning] = field(default_factory=list)
    partition_results: Dict[str, bool] = field(default_factory=dict)
    description: str = ""


class ConsensusProtocol:
    """Reaches consensus when nodes disagree using severity monoid.

    The severity monoid (max-wins) is the right choice for consensus because:
    - In safety-critical systems, the worst assessment must prevail
    - It's idempotent: max(a, a) = a, so duplicate reports don't inflate
    - It's commutative: order doesn't matter
    - It's associative: grouping doesn't matter
    """

    def __init__(
        self,
        min_nodes: int = 2,
        escalation_threshold: float = 0.5,
    ):
        self.min_nodes = min_nodes
        self.escalation_threshold = escalation_threshold
        self._node_severities: Dict[str, Severity] = {}

    def submit_severity(self, node_id: str, severity: Severity) -> None:
        """Submit a node's assessed severity."""
        self._node_severities[node_id] = severity

    def resolve(self) -> ConsensusResult:
        """Resolve consensus across all submitted severities."""
        if len(self._node_severities) < self.min_nodes:
            return ConsensusResult(
                outcome=ConsensusOutcome.DEGRADED,
                passed=False,
                severity=Severity.FATAL,
                confidence=0.0,
                agreeing_nodes=[],
                dissenting_nodes=list(self._node_severities.keys()),
                description=f"Only {len(self._node_severities)} nodes, need {self.min_nodes}",
            )

        if not self._node_severities:
            return ConsensusResult(
                outcome=ConsensusOutcome.DEGRADED,
                passed=False,
                severity=Severity.PASS,
                confidence=0.0,
                agreeing_nodes=[],
                dissenting_nodes=[],
                description="No nodes submitted",
            )

        # Use severity monoid: worst severity wins
        all_severities = list(self._node_severities.values())
        combined = SeverityMonoid.combine_all(all_severities)

        # Group nodes by their severity
        severity_groups: Dict[Severity, List[str]] = defaultdict(list)
        for nid, sev in self._node_severities.items():
            severity_groups[sev].append(nid)

        # The consensus severity is the majority severity (or worst if tied)
        total = len(self._node_severities)
        majority_severity = max(severity_groups.keys(), key=lambda s: len(severity_groups[s]))
        majority_count = len(severity_groups[majority_severity])
        majority_ratio = majority_count / total

        # Determine outcome
        if len(severity_groups) == 1:
            outcome = ConsensusOutcome.AGREED
            agreeing = list(self._node_severities.keys())
            dissenting: List[str] = []
        elif majority_ratio > self.escalation_threshold:
            outcome = ConsensusOutcome.MAJORITY
            agreeing = severity_groups[majority_severity]
            dissenting = [nid for nid in self._node_severities if nid not in agreeing]
        else:
            outcome = ConsensusOutcome.ESCALATION
            agreeing = severity_groups.get(majority_severity, [])
            dissenting = [nid for nid in self._node_severities if nid not in agreeing]

        # Pass = worst severity from monoid is PASS or WARN
        passed = combined in (Severity.PASS, Severity.WARN)

        confidence = majority_ratio if outcome != ConsensusOutcome.ESCALATION else 0.0

        descriptions = {
            ConsensusOutcome.AGREED: f"All {total} nodes agree: {combined.name}",
            ConsensusOutcome.MAJORITY: f"{majority_count}/{total} nodes agree: {majority_severity.name} (worst: {combined.name})",
            ConsensusOutcome.ESCALATION: f"No clear majority among {total} nodes — escalation required",
            ConsensusOutcome.DEGRADED: f"Insufficient nodes ({total}/{self.min_nodes})",
        }

        return ConsensusResult(
            outcome=outcome,
            passed=passed,
            severity=combined,
            confidence=round(confidence, 4),
            agreeing_nodes=agreeing,
            dissenting_nodes=dissenting,
            description=descriptions[outcome],
        )

    def reset(self) -> None:
        self._node_severities.clear()


# =============================================================================
# 6. DistributedFlux — Top-Level Orchestrator
# =============================================================================

@dataclass
class NodeConfig:
    """Configuration for a single node."""
    constraints: List[Tuple[float, float]]  # [(min, max), ...]
    weight: float = 1.0

    def check_value(self, value: float) -> ErrorMask:
        """Check a value against all constraints, return error mask."""
        return ErrorMask.from_checks(self.constraints, value)

    def compute_severity(self, mask: ErrorMask) -> Severity:
        """Map error mask to severity level."""
        n_failing = mask.rank()
        n_total = mask.n
        if n_total == 0:
            return Severity.PASS
        ratio = n_failing / n_total
        if ratio == 0:
            return Severity.PASS
        elif ratio <= 0.25:
            return Severity.WARN
        elif ratio <= 0.5:
            return Severity.ERROR
        else:
            return Severity.FATAL


@dataclass
class NodeResult:
    """Result from a single node check."""
    node_id: str
    value: float
    error_mask: ErrorMask
    severity: Severity
    passed: bool
    cascade_warnings: List[CascadeWarning] = field(default_factory=list)
    timestamp: float = 0.0


class DistributedFlux:
    """Distributed constraint coordination system.

    Orchestrates constraint checking across multiple nodes using:
      - Watertight partitioning (maritime)
      - TMR-style voting (aviation)
      - Cascade detection (ecology)
      - Boolean algebra merging
      - Severity monoid consensus

    Example:
        df = DistributedFlux(
            nodes={
                "node_a": {"constraints": [(0, 100)], "weight": 1.0},
                "node_b": {"constraints": [(0, 100)], "weight": 1.0},
                "node_c": {"constraints": [(0, 100)], "weight": 1.0},
            },
            voting="majority",
            cascade_detection=True,
            partition="watertight",
        )
        df.check("node_a", 42.0)
        df.check("node_b", 42.0)
        df.check("node_c", 42.0)
        result = df.consensus()
    """

    def __init__(
        self,
        nodes: Dict[str, Dict[str, Any]],
        voting: str = "majority",
        cascade_detection: bool = True,
        partition: str = "watertight",
        merge_mode: str = "join",
        min_consensus_nodes: int = 2,
    ):
        # Build node configs
        self.nodes: Dict[str, NodeConfig] = {}
        for nid, cfg in nodes.items():
            self.nodes[nid] = NodeConfig(
                constraints=cfg.get("constraints", []),
                weight=cfg.get("weight", 1.0),
            )

        # Subsystems
        self.voting_checker = VotingChecker(mode=voting)
        self.cascade_detector = CascadeDetector(model="proximity") if cascade_detection else None
        self.merger = DistributedMerger(mode=merge_mode)
        self.consensus_protocol = ConsensusProtocol(min_nodes=min_consensus_nodes)
        self.constraint_partition = ConstraintPartition(strategy=partition)

        # State
        self._node_results: Dict[str, NodeResult] = {}
        self._cascade_warnings: List[CascadeWarning] = []

        # Partition all node constraints
        self._build_partitions()

    def _build_partitions(self) -> None:
        """Build constraint partitions for each node."""
        self._partitions_by_node: Dict[str, List[Partition]] = {}
        for nid, cfg in self.nodes.items():
            partitions = self.constraint_partition.partition_constraints(
                cfg.constraints, node_ids={nid}
            )
            self._partitions_by_node[nid] = partitions

    def check(self, node_id: str, value: float) -> NodeResult:
        """Check a value at a specific node."""
        if node_id not in self.nodes:
            raise ValueError(f"Unknown node: {node_id}")

        cfg = self.nodes[node_id]
        error_mask = cfg.check_value(value)
        severity = cfg.compute_severity(error_mask)
        passed = error_mask.all_pass()

        # Cascade detection
        cascade_warnings: List[CascadeWarning] = []
        if self.cascade_detector and not passed:
            for idx in error_mask.failing_constraints():
                warnings = self.cascade_detector.register_violation(
                    idx, cfg.constraints,
                    compartment_name=self._partitions_by_node.get(node_id, [Partition("?", [])])[0].name,
                )
                cascade_warnings.extend(warnings)

        self._cascade_warnings.extend(cascade_warnings)

        result = NodeResult(
            node_id=node_id,
            value=value,
            error_mask=error_mask,
            severity=severity,
            passed=passed,
            cascade_warnings=cascade_warnings,
            timestamp=time.time(),
        )
        self._node_results[node_id] = result
        return result

    def consensus(self) -> ConsensusResult:
        """Reach consensus across all checked nodes.

        Steps:
        1. Submit votes to voting checker
        2. Submit error masks to merger
        3. Submit severities to consensus protocol
        4. Resolve consensus
        """
        if not self._node_results:
            return ConsensusResult(
                outcome=ConsensusOutcome.DEGRADED,
                passed=False,
                severity=Severity.PASS,
                confidence=0.0,
                agreeing_nodes=[],
                dissenting_nodes=[],
                description="No nodes have been checked yet",
            )

        # Reset subsystems
        self.voting_checker.reset()
        self.merger.reset()
        self.consensus_protocol.reset()

        # Submit to all subsystems
        for nid, result in self._node_results.items():
            self.voting_checker.cast_vote(nid, result.passed)
            self.merger.submit_mask(nid, result.error_mask)
            self.consensus_protocol.submit_severity(nid, result.severity)

        # Resolve
        vote_result = self.voting_checker.tally()
        merge_result = self.merger.merge()
        consensus_result = self.consensus_protocol.resolve()

        # Build partition results
        partition_results = {nid: r.passed for nid, r in self._node_results.items()}

        # Enhance consensus result
        consensus_result.merged_mask = merge_result.merged_mask
        consensus_result.cascade_warnings = list(self._cascade_warnings)
        consensus_result.partition_results = partition_results

        return consensus_result

    def reset(self) -> None:
        """Reset all state for a new consensus round."""
        self._node_results.clear()
        self._cascade_warnings.clear()
        self.voting_checker.reset()
        self.merger.reset()
        self.consensus_protocol.reset()
        if self.cascade_detector:
            self.cascade_detector.reset()

    @property
    def node_results(self) -> Dict[str, NodeResult]:
        return dict(self._node_results)

    @property
    def cascade_warnings(self) -> List[CascadeWarning]:
        return list(self._cascade_warnings)

    @property
    def checking_intensity(self) -> float:
        """Current cascade-adaptive checking intensity."""
        if self.cascade_detector:
            return self.cascade_detector.checking_intensity
        return 0.1


# =============================================================================
# Built-in tests
# =============================================================================

def _run_tests():
    """Run built-in tests."""
    passed = 0
    failed = 0

    def assert_test(condition, name):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name}")

    print("\n=== flux_distributed tests ===\n")

    # --- ConstraintPartition ---
    print("  -- ConstraintPartition --")

    cp = ConstraintPartition(strategy="watertight")
    parts = cp.partition_constraints([(0, 10), (20, 30), (40, 50)])
    assert_test(len(parts) == 3, "Watertight: 3 constraints → 3 partitions")
    assert_test(all(p.size == 1 for p in parts), "Watertight: each partition has 1 constraint")

    cp_range = ConstraintPartition(strategy="range")
    parts = cp_range.partition_constraints([(0, 10), (5, 15), (20, 30)])
    assert_test(len(parts) == 2, "Range: overlapping constraints in same partition")

    cp_auto = ConstraintPartition(strategy="auto")
    parts = cp_auto.partition_constraints([(0, 10), (5, 15), (20, 30)])
    assert_test(len(parts) >= 1, "Auto: produces at least 1 partition")

    # --- VotingChecker ---
    print("  -- VotingChecker --")

    vc = VotingChecker(mode="majority")
    vc.cast_vote("a", True)
    vc.cast_vote("b", True)
    vc.cast_vote("c", False)
    vr = vc.tally()
    assert_test(vr.passed, "Majority: 2/3 pass → pass")
    assert_test(not vr.unanimous, "Majority: not unanimous")
    assert_test(vr.pass_count == 2, "Majority: 2 pass votes")
    assert_test(vr.faulted_voter == "c", "Majority: faulted voter identified")

    vc2 = VotingChecker(mode="unanimous")
    vc2.cast_vote("a", True)
    vc2.cast_vote("b", True)
    vc2.cast_vote("c", False)
    vr2 = vc2.tally()
    assert_test(not vr2.passed, "Unanimous: 1 dissent → fail")

    vc3 = VotingChecker(mode="quorum", quorum_size=2)
    vc3.cast_vote("a", True)
    vc3.cast_vote("b", False)
    vc3.cast_vote("c", False)
    vr3 = vc3.tally()
    assert_test(not vr3.passed, "Quorum 2: only 1 pass → fail")

    # --- CascadeDetector ---
    print("  -- CascadeDetector --")

    cd = CascadeDetector(model="proximity")
    constraints = [(0, 10), (5, 15), (20, 30), (25, 35)]
    # Violate constraint 0 — overlaps with constraint 1
    warnings = cd.register_violation(0, constraints, "comp_0")
    assert_test(len(warnings) == 0, "Cascade: no prior violations → no cascade risk")

    # Now violate constraint 1 — constraint 0 has history, overlap exists
    warnings = cd.register_violation(1, constraints, "comp_1")
    assert_test(len(warnings) == 1, "Cascade: overlapping + history → warning")
    assert_test(0 in warnings[0].cascade_targets, "Cascade: constraint 0 is a target")

    intensity = cd.checking_intensity
    assert_test(intensity > 0.1, "Cascade: intensity increases with violations")

    # Dependency model
    cd_dep = CascadeDetector(model="dependency", dependencies={0: {1, 2}, 1: {2}})
    warnings = cd_dep.register_violation(0, [], "dep_comp")
    assert_test(len(warnings) == 1, "Dependency: cascade detected")
    assert_test(1 in warnings[0].cascade_targets and 2 in warnings[0].cascade_targets,
                "Dependency: correct targets")

    # --- DistributedMerger ---
    print("  -- DistributedMerger --")

    dm = DistributedMerger(mode="join")
    dm.submit_mask("a", ErrorMask.from_list([True, False, False]))
    dm.submit_mask("b", ErrorMask.from_list([False, True, False]))
    dm.submit_mask("c", ErrorMask.from_list([False, False, True]))
    mr = dm.merge()
    assert_test(mr.merged_mask.all_fail(), "Join merge: OR of all failures")
    assert_test(not mr.consensus, "Join merge: nodes disagree")
    assert_test(mr.disagreement_mask.rank() == 3, "Join merge: all 3 bits disagree")

    dm2 = DistributedMerger(mode="meet")
    dm2.submit_mask("a", ErrorMask.from_list([True, True, False]))
    dm2.submit_mask("b", ErrorMask.from_list([True, False, False]))
    mr2 = dm2.merge()
    assert_test(mr2.merged_mask == ErrorMask.from_list([True, False, False]),
                "Meet merge: AND of failures")

    dm3 = DistributedMerger(mode="majority")
    dm3.submit_mask("a", ErrorMask.from_list([True, False, False]))
    dm3.submit_mask("b", ErrorMask.from_list([True, False, False]))
    dm3.submit_mask("c", ErrorMask.from_list([False, True, False]))
    mr3 = dm3.merge()
    assert_test(mr3.merged_mask[0], "Majority merge: bit 0 passes (2/3)")
    assert_test(not mr3.merged_mask[1], "Majority merge: bit 1 fails (1/3)")
    assert_test(not mr3.merged_mask[2], "Majority merge: bit 2 fails (0/3)")

    # --- ConsensusProtocol ---
    print("  -- ConsensusProtocol --")

    cp1 = ConsensusProtocol(min_nodes=2)
    cp1.submit_severity("a", Severity.PASS)
    cp1.submit_severity("b", Severity.PASS)
    cp1.submit_severity("c", Severity.PASS)
    cr = cp1.resolve()
    assert_test(cr.outcome == ConsensusOutcome.AGREED, "Consensus: all agree")
    assert_test(cr.passed, "Consensus: all pass → pass")
    assert_test(cr.severity == Severity.PASS, "Consensus: severity = PASS")

    cp2 = ConsensusProtocol(min_nodes=2)
    cp2.submit_severity("a", Severity.PASS)
    cp2.submit_severity("b", Severity.ERROR)
    cp2.submit_severity("c", Severity.PASS)
    cr2 = cp2.resolve()
    assert_test(cr2.outcome == ConsensusOutcome.MAJORITY, "Consensus: majority wins")
    assert_test(not cr2.passed, "Consensus: worst severity (ERROR) → fail")
    assert_test(cr2.severity == Severity.ERROR, "Consensus: monoid gives ERROR (worst)")

    cp3 = ConsensusProtocol(min_nodes=2)
    cr3 = cp3.resolve()
    assert_test(cr3.outcome == ConsensusOutcome.DEGRADED, "Consensus: no nodes → degraded")

    # Escalation: no majority
    cp4 = ConsensusProtocol(min_nodes=2, escalation_threshold=0.5)
    cp4.submit_severity("a", Severity.PASS)
    cp4.submit_severity("b", Severity.ERROR)
    cp4.submit_severity("c", Severity.FATAL)
    cr4 = cp4.resolve()
    assert_test(cr4.outcome == ConsensusOutcome.ESCALATION,
                "Consensus: all different → escalation")

    # --- DistributedFlux (3-node) ---
    print("  -- DistributedFlux 3-node --")

    df = DistributedFlux(
        nodes={
            "node_a": {"constraints": [(0, 100), (-50, 50)], "weight": 1.0},
            "node_b": {"constraints": [(0, 100), (-50, 50)], "weight": 1.0},
            "node_c": {"constraints": [(0, 100), (-50, 50)], "weight": 1.0},
        },
        voting="majority",
        cascade_detection=True,
        partition="watertight",
    )

    # All pass
    df.check("node_a", 42.0)
    df.check("node_b", 42.0)
    df.check("node_c", 42.0)
    cr = df.consensus()
    assert_test(cr.passed, "3-node: all pass value → consensus pass")
    assert_test(cr.outcome == ConsensusOutcome.AGREED, "3-node: unanimous agreement")

    df.reset()

    # One node fails
    df.check("node_a", 42.0)
    df.check("node_b", 200.0)  # Fails both constraints
    df.check("node_c", 42.0)
    cr = df.consensus()
    assert_test(not cr.passed, "3-node: severity monoid picks worst → fail")
    assert_test("node_b" in cr.dissenting_nodes, "3-node: node_b is dissenting")

    df.reset()

    # All fail differently
    df.check("node_a", 200.0)
    df.check("node_b", -100.0)
    df.check("node_c", 150.0)
    cr = df.consensus()
    assert_test(not cr.passed, "3-node: all fail → consensus fail")

    # --- DistributedFlux (10-node) ---
    print("  -- DistributedFlux 10-node --")

    ten_nodes = {
        f"node_{i}": {"constraints": [(0, 100), (10, 90)], "weight": 1.0}
        for i in range(10)
    }
    df10 = DistributedFlux(
        nodes=ten_nodes,
        voting="majority",
        cascade_detection=True,
        partition="watertight",
    )

    # 7 pass, 3 fail → majority votes pass, but severity monoid picks worst
    for i in range(7):
        df10.check(f"node_{i}", 50.0)
    for i in range(7, 10):
        df10.check(f"node_{i}", 200.0)

    cr10 = df10.consensus()
    assert_test(not cr10.passed, "10-node: severity monoid overrides majority → fail")
    assert_test(len(cr10.dissenting_nodes) == 3, "10-node: 3 dissenting")

    df10.reset()

    # 4 pass, 6 fail → majority fail
    for i in range(4):
        df10.check(f"node_{i}", 50.0)
    for i in range(4, 10):
        df10.check(f"node_{i}", 200.0)

    cr10 = df10.consensus()
    assert_test(not cr10.passed, "10-node: 4/10 pass → majority fail")
    assert_test(cr10.severity in (Severity.ERROR, Severity.FATAL),
                "10-node: high severity on majority fail")

    # --- Edge cases ---
    print("  -- Edge cases --")

    # Single node
    df1 = DistributedFlux(
        nodes={"only": {"constraints": [(0, 10)], "weight": 1.0}},
        min_consensus_nodes=1,
    )
    df1.check("only", 5.0)
    cr1 = df1.consensus()
    assert_test(cr1.passed, "Single node: passes correctly")

    # Empty constraints
    df_empty = DistributedFlux(
        nodes={"e1": {"constraints": [], "weight": 1.0}},
        min_consensus_nodes=1,
    )
    df_empty.check("e1", 42.0)
    assert_test(df_empty.node_results["e1"].passed, "Empty constraints → pass")

    # Unknown node
    try:
        df.check("nonexistent", 42.0)
        assert_test(False, "Unknown node raises ValueError")
    except ValueError:
        assert_test(True, "Unknown node raises ValueError")

    print(f"\n  Results: {passed} passed, {failed} failed\n")
    return failed == 0


if __name__ == "__main__":
    import sys
    success = _run_tests()
    sys.exit(0 if success else 1)
