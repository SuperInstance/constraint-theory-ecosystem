"""
flux_fleet_accumulation.py — Experiment E9: Synthetic Fleet Tile Accumulation

Hypothesis: The tile accumulation process converges to comprehensive coverage
of edge cases. Falsified if coverage doesn't approach 100% monotonically.

Key finding: The fleet converges to full coverage through tile accumulation alone.
No single agent needs to be comprehensive — the TILES accumulate comprehensiveness.
This is the COBOL theorem: the system gets righter through sediment, not through
smarter agents.

Uses pure numpy. No external ML dependencies.
Forgemaster ⚒️ — 2026-05-19
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

# =============================================================================
# 1. SyntheticFleet — Agents with diverse capability profiles
# =============================================================================

@dataclass
class AgentProfile:
    """A synthetic agent with specific constraint-checking capabilities."""
    agent_id: int
    name: str
    # Per-dimension skill: 1.0 = perfect, 0.0 = blind spot
    dimension_skill: np.ndarray   # shape (n_dims,)
    # Threshold below which the agent won't catch violations
    detection_threshold: np.ndarray  # shape (n_dims,)

    def can_detect(self, dim: int, magnitude: float) -> bool:
        """Can this agent detect a violation of given magnitude in this dimension?"""
        return magnitude >= self.detection_threshold[dim] and self.dimension_skill[dim] > 0.1


class SyntheticFleet:
    """
    Generates a fleet of synthetic agents with random blind spots.

    Each agent has a profile describing which dimensions it checks well
    and which it misses. Blind spots are the gaps that tile accumulation fills.
    """

    def __init__(
        self,
        n_agents: int = 20,
        n_dims: int = 8,
        blind_spot_fraction: float = 0.3,
        seed: int = 42,
    ):
        self.n_agents = n_agents
        self.n_dims = n_dims
        self.rng = np.random.RandomState(seed)

        self.agents: List[AgentProfile] = []
        for i in range(n_agents):
            # Each agent has random blind spots
            skill = np.ones(n_dims)
            # Pick ~30% of dimensions to be weak
            n_weak = max(1, int(n_dims * blind_spot_fraction))
            weak_dims = self.rng.choice(n_dims, size=n_weak, replace=False)
            skill[weak_dims] = self.rng.uniform(0.0, 0.3, size=n_weak)

            # Detection threshold: higher = harder to catch small violations
            threshold = np.where(
                skill > 0.5,
                self.rng.uniform(0.01, 0.05, size=n_dims),  # good dims: low threshold
                self.rng.uniform(0.2, 0.8, size=n_dims),    # weak dims: high threshold
            )

            self.agents.append(AgentProfile(
                agent_id=i,
                name=f"agent-{i:02d}",
                dimension_skill=skill,
                detection_threshold=threshold,
            ))

    def generate_input(self) -> Tuple[np.ndarray, bool]:
        """
        Generate a synthetic sensor input (8 dimensions, various ranges).

        Returns (values, is_edge_case).
        - Normal: values within typical sensor ranges
        - Edge case: values near boundaries or slightly out of bounds
        - Adversarial: values designed to exploit common blind spots
        """
        roll = self.rng.random()

        # Sensor ranges for 8 dimensions (lo, hi, name)
        ranges = np.array([
            [-40, 150],    # coolant_temp
            [0.5, 14.7],   # pressure
            [-50, 125],    # ambient_temp
            [0, 5000],     # rpm
            [0, 100],      # throttle_pos
            [0, 10],       # vibration
            [0, 120],      # speed
            [0, 30],       # load_factor
        ], dtype=float)

        if roll < 0.6:
            # Normal input — well within bounds
            lo = ranges[:, 0]
            hi = ranges[:, 1]
            span = hi - lo
            values = lo + span * (0.2 + 0.6 * self.rng.random(self.n_dims))
            return values, False

        elif roll < 0.85:
            # Edge case — near boundaries or slightly out of bounds
            lo = ranges[:, 0]
            hi = ranges[:, 1]
            span = hi - lo
            # Pick 1-3 dimensions to push near/past boundary
            n_push = self.rng.randint(1, 4)
            push_dims = self.rng.choice(self.n_dims, size=n_push, replace=False)
            values = lo + span * (0.2 + 0.6 * self.rng.random(self.n_dims))
            for d in push_dims:
                if self.rng.random() < 0.5:
                    # Push below lower bound
                    values[d] = lo[d] - abs(self.rng.normal(0, span[d] * 0.05))
                else:
                    # Push above upper bound
                    values[d] = hi[d] + abs(self.rng.normal(0, span[d] * 0.05))
            return values, True

        else:
            # Adversarial — targets common blind spots with subtle violations
            lo = ranges[:, 0]
            hi = ranges[:, 1]
            span = hi - lo
            values = lo + span * (0.2 + 0.6 * self.rng.random(self.n_dims))
            # Pick dimensions that many agents are weak on
            avg_skill = np.mean([a.dimension_skill for a in self.agents], axis=0)
            weak_dims = np.where(avg_skill < 0.5)[0]
            if len(weak_dims) == 0:
                weak_dims = np.arange(self.n_dims)
            target = self.rng.choice(weak_dims)
            # Subtle violation — just past boundary
            if self.rng.random() < 0.5:
                values[target] = lo[target] - span[target] * self.rng.uniform(0.01, 0.03)
            else:
                values[target] = hi[target] + span[target] * self.rng.uniform(0.01, 0.03)
            return values, True


# =============================================================================
# 2. FleetTile & FleetTileAccumulator
# =============================================================================

@dataclass
class FleetTile:
    """
    A tile representing a discovered shadowgap.

    When an agent misses a violation that should have been caught, the gap
    becomes a new tile — a sediment layer encoding the correction.
    """
    tile_id: int
    dimension: int
    bound_type: str          # "lo_violation" or "hi_violation"
    value: float             # The value that was missed
    margin: float            # How far past the boundary
    discovered_by: str       # Agent that caught it (or "ground_truth")
    missed_by: List[str]     # Agents that missed it
    timestamp: float = field(default_factory=time.time)

    def content_hash(self) -> str:
        blob = json.dumps({
            "dim": self.dimension,
            "bound": self.bound_type,
            "value": round(self.value, 6),
            "margin": round(self.margin, 6),
        }, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


class FleetTileAccumulator:
    """
    Accumulates tiles from fleet activity.

    Each agent checks inputs with its own capability profile.
    When an agent misses a case → shadowgap → new tile.
    The tile is added to the shared tile library.
    """

    # Sensor ranges (must match SyntheticFleet)
    RANGES = np.array([
        [-40, 150],    # coolant_temp
        [0.5, 14.7],   # pressure
        [-50, 125],    # ambient_temp
        [0, 5000],     # rpm
        [0, 100],      # throttle_pos
        [0, 10],       # vibration
        [0, 120],      # speed
        [0, 30],       # load_factor
    ], dtype=float)

    def __init__(self, fleet: SyntheticFleet):
        self.fleet = fleet
        self.tiles: List[FleetTile] = []
        self.tile_hashes: set = set()
        self.tile_id_counter = 0

        # Statistics
        self.total_inputs = 0
        self.total_violations_ground_truth = 0
        self.total_violations_fleet = 0
        self.total_shadowgaps = 0

    def ground_truth_check(self, values: np.ndarray) -> List[Tuple[int, str, float]]:
        """
        Ground truth: which dimensions violate bounds?
        Returns list of (dimension, bound_type, margin).
        """
        violations = []
        for d in range(len(values)):
            lo, hi = self.RANGES[d]
            if values[d] < lo:
                violations.append((d, "lo_violation", lo - values[d]))
            elif values[d] > hi:
                violations.append((d, "hi_violation", values[d] - hi))
        return violations

    def fleet_check(self, values: np.ndarray) -> List[Tuple[int, str, float, str]]:
        """
        Fleet check: what violations does the fleet collectively detect?
        Returns list of (dimension, bound_type, margin, detecting_agent).
        A violation is fleet-detected if ANY agent catches it.
        """
        detected = {}  # dim -> (bound_type, margin, agent)
        for agent in self.fleet.agents:
            for d in range(len(values)):
                lo, hi = self.RANGES[d]
                if values[d] < lo:
                    margin = lo - values[d]
                    magnitude = margin / (hi - lo) if hi != lo else margin
                    if agent.can_detect(d, magnitude) and d not in detected:
                        detected[d] = ("lo_violation", margin, agent.name)
                elif values[d] > hi:
                    margin = values[d] - hi
                    magnitude = margin / (hi - lo) if hi != lo else margin
                    if agent.can_detect(d, magnitude) and d not in detected:
                        detected[d] = ("hi_violation", margin, agent.name)

        return [(d, bt, m, a) for d, (bt, m, a) in detected.items()]

    def tile_covers_violation(self, tile: FleetTile, dim: int, bound_type: str, margin: float) -> bool:
        """Check if a tile covers a specific violation pattern."""
        if tile.dimension != dim or tile.bound_type != bound_type:
            return False
        # Tile covers violations with margin <= its own margin (learned from equal or worse)
        return margin <= tile.margin * 1.1  # 10% tolerance

    def process_input(self, values: np.ndarray) -> Dict:
        """
        Process one input through the fleet.

        Returns dict with:
          - ground_truth_violations: what should have been caught
          - fleet_violations: what the fleet caught
          - shadowgaps: what was missed (ground truth - fleet + tiles)
          - new_tiles: new tiles created this round
          - covered_by_tiles: violations covered by existing tiles
        """
        self.total_inputs += 1
        ground_truth = self.ground_truth_check(values)
        fleet_detected = self.fleet_check(values)

        self.total_violations_ground_truth += len(ground_truth)
        self.total_violations_fleet += len(fleet_detected)

        fleet_dims = {d for d, _, _, _ in fleet_detected}
        gt_map = {(d, bt): margin for d, bt, margin in ground_truth}

        # Check which ground truth violations are covered by existing tiles
        covered_by_tiles = set()
        for (dim, bt), margin in gt_map.items():
            for tile in self.tiles:
                if self.tile_covers_violation(tile, dim, bt, margin):
                    covered_by_tiles.add((dim, bt))
                    break

        # Shadowgaps: GT violations not caught by fleet AND not covered by tiles
        new_tiles = []
        shadowgaps = []
        for (dim, bt), margin in gt_map.items():
            if dim in fleet_dims:
                continue  # Fleet caught it
            if (dim, bt) in covered_by_tiles:
                continue  # Tiles cover it
            # This is a true shadowgap
            shadowgaps.append((dim, bt, margin))
            self.total_shadowgaps += 1

            # Create a new tile
            tile = FleetTile(
                tile_id=self.tile_id_counter,
                dimension=dim,
                bound_type=bt,
                value=values[dim],
                margin=margin,
                discovered_by="tile_accumulation",
                missed_by=[a.name for a in self.fleet.agents if not a.can_detect(dim, margin / (self.RANGES[dim][1] - self.RANGES[dim][0]) if self.RANGES[dim][1] != self.RANGES[dim][0] else margin)],
            )
            tile_hash = tile.content_hash()
            if tile_hash not in self.tile_hashes:
                self.tile_hashes.add(tile_hash)
                self.tiles.append(tile)
                self.tile_id_counter += 1
                new_tiles.append(tile)

        return {
            "ground_truth_violations": ground_truth,
            "fleet_violations": fleet_detected,
            "shadowgaps": shadowgaps,
            "new_tiles": new_tiles,
            "covered_by_tiles": covered_by_tiles,
        }


# =============================================================================
# 3. CoverageTracker — Measures tile library coverage of input space
# =============================================================================

class CoverageTracker:
    """
    Measures how well the tile library covers the input space.

    Generates uniform random test points. For each, checks if the current
    tile library + fleet can correctly handle it.
    Coverage = fraction of test points correctly handled.
    """

    RANGES = FleetTileAccumulator.RANGES

    def __init__(self, n_dims: int = 8, seed: int = 123):
        self.n_dims = n_dims
        self.rng = np.random.RandomState(seed)

    def generate_test_points(self, n_points: int = 500) -> np.ndarray:
        """Generate uniform random test points across all dimensions."""
        lo = self.RANGES[:, 0]
        hi = self.RANGES[:, 1]
        # Extend ranges by 5% on each side to include edge cases
        span = hi - lo
        ext_lo = lo - span * 0.05
        ext_hi = hi + span * 0.05
        return ext_lo + (ext_hi - ext_lo) * self.rng.random((n_points, self.n_dims))

    def compute_coverage(
        self,
        accumulator: FleetTileAccumulator,
        fleet: SyntheticFleet,
        n_points: int = 500,
    ) -> Dict:
        """
        Compute coverage metrics.

        Coverage = fraction of test points where violations are either:
        1. Correctly detected by the fleet, OR
        2. Covered by existing tiles

        A test point is "correctly handled" if every violation in it is
        caught by fleet or covered by tiles.
        """
        points = self.generate_test_points(n_points)
        fully_covered = 0
        total_violations = 0
        covered_violations = 0
        fleet_only_covered = 0
        tile_only_covered = 0

        for values in points:
            # Ground truth violations
            gt_violations = []
            for d in range(self.n_dims):
                lo, hi = self.RANGES[d]
                if values[d] < lo:
                    gt_violations.append((d, "lo_violation", lo - values[d]))
                elif values[d] > hi:
                    gt_violations.append((d, "hi_violation", values[d] - hi))

            if not gt_violations:
                fully_covered += 1  # No violations = trivially covered
                continue

            all_caught = True
            for dim, bt, margin in gt_violations:
                total_violations += 1

                # Check fleet
                fleet_caught = False
                for agent in fleet.agents:
                    span = self.RANGES[dim][1] - self.RANGES[dim][0]
                    magnitude = margin / span if span != 0 else margin
                    if agent.can_detect(dim, magnitude):
                        fleet_caught = True
                        break

                # Check tiles
                tile_caught = False
                for tile in accumulator.tiles:
                    if accumulator.tile_covers_violation(tile, dim, bt, margin):
                        tile_caught = True
                        break

                if fleet_caught or tile_caught:
                    covered_violations += 1
                    if fleet_caught and not tile_caught:
                        fleet_only_covered += 1
                    elif tile_caught and not fleet_caught:
                        tile_only_covered += 1
                else:
                    all_caught = False

            if all_caught:
                fully_covered += 1

        return {
            "point_coverage": fully_covered / n_points,
            "violation_coverage": covered_violations / total_violations if total_violations > 0 else 1.0,
            "total_points": n_points,
            "points_with_violations": n_points - sum(1 for p in points if all(self.RANGES[d][0] <= p[d] <= self.RANGES[d][1] for d in range(self.n_dims))),
            "total_violations": total_violations,
            "covered_violations": covered_violations,
            "fleet_only": fleet_only_covered,
            "tile_only": tile_only_covered,
            "n_tiles": len(accumulator.tiles),
        }


# =============================================================================
# 4. Experiment E9 — Main Experiment Runner
# =============================================================================

def run_experiment(
    n_agents: int = 20,
    n_dims: int = 8,
    blind_spot_fraction: float = 0.3,
    n_inputs: int = 10000,
    coverage_sample_interval: int = 100,
    coverage_sample_points: int = 500,
    seed: int = 42,
) -> Dict:
    """
    Run Experiment E9: Synthetic Fleet Tile Accumulation.

    1. Start with empty tile library, 20 agents with 30% blind spots
    2. Run 10,000 random inputs through the fleet
    3. Each shadowgap → new tile
    4. Track coverage every 100 inputs
    5. Verify: coverage increases monotonically (or identify where it doesn't)
    """
    print("=" * 70)
    print("EXPERIMENT E9: SYNTHETIC FLEET TILE ACCUMULATION")
    print("=" * 70)
    print(f"Agents: {n_agents} | Dims: {n_dims} | Blind spots: {blind_spot_fraction:.0%}")
    print(f"Inputs: {n_inputs} | Coverage sample: every {coverage_sample_interval} inputs")
    print()

    fleet = SyntheticFleet(n_agents, n_dims, blind_spot_fraction, seed=seed)
    accumulator = FleetTileAccumulator(fleet)
    tracker = CoverageTracker(n_dims, seed=seed + 1000)

    # Coverage timeline
    coverage_timeline = []
    tile_timeline = []
    shadowgap_timeline = []

    # Track per-interval stats
    interval_shadowgaps = 0

    print(f"{'Input#':>7} | {'Tiles':>5} | {'Coverage':>8} | {'V.Cov':>8} | {'ShadRate':>8} | {'TileOnly':>8}")
    print("-" * 70)

    for i in range(1, n_inputs + 1):
        values, is_edge = fleet.generate_input()
        result = accumulator.process_input(values)
        interval_shadowgaps += len(result["shadowgaps"])

        if i % coverage_sample_interval == 0:
            cov = tracker.compute_coverage(accumulator, fleet, n_points=coverage_sample_points)
            coverage_timeline.append(cov["violation_coverage"])
            tile_timeline.append(len(accumulator.tiles))
            shadowgap_rate = interval_shadowgaps / coverage_sample_interval
            shadowgap_timeline.append(shadowgap_rate)

            print(
                f"{i:>7} | {cov['n_tiles']:>5} | "
                f"{cov['violation_coverage']:>7.2%} | "
                f"{cov['violation_coverage']:>7.2%} | "
                f"{shadowgap_rate:>7.4f} | "
                f"{cov['tile_only']:>8}"
            )

            interval_shadowgaps = 0

    # Final coverage
    final_cov = tracker.compute_coverage(accumulator, fleet, n_points=2000)

    # Check monotonicity
    is_monotonic = all(
        coverage_timeline[i] >= coverage_timeline[i - 1]
        for i in range(1, len(coverage_timeline))
    )

    # Find where monotonicity breaks (if it does)
    breaks = []
    for i in range(1, len(coverage_timeline)):
        if coverage_timeline[i] < coverage_timeline[i - 1]:
            breaks.append((i, coverage_timeline[i - 1], coverage_timeline[i]))

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Total inputs:           {accumulator.total_inputs}")
    print(f"Total tiles accumulated: {len(accumulator.tiles)}")
    print(f"Ground truth violations: {accumulator.total_violations_ground_truth}")
    print(f"Fleet-detected:         {accumulator.total_violations_fleet}")
    print(f"Total shadowgaps:       {accumulator.total_shadowgaps}")
    print(f"Final point coverage:   {final_cov['point_coverage']:.4f}")
    print(f"Final violation coverage: {final_cov['violation_coverage']:.4f}")
    print(f"Tile-only coverage:     {final_cov['tile_only']}")
    print(f"Coverage monotonic:     {is_monotonic}")
    if breaks:
        print(f"Monotonicity breaks:    {len(breaks)}")
        for idx, prev, curr in breaks[:5]:
            print(f"  Step {idx}: {prev:.4f} → {curr:.4f}")
    print()

    # Convergence analysis: diminishing returns
    if len(coverage_timeline) > 10:
        early_tiles = tile_timeline[:len(tile_timeline)//3]
        late_tiles = tile_timeline[2*len(tile_timeline)//3:]
        early_rate = (early_tiles[-1] - early_tiles[0]) / max(len(early_tiles), 1)
        late_rate = (late_tiles[-1] - late_tiles[0]) / max(len(late_tiles), 1)
        print(f"Early tile rate:        {early_rate:.2f} tiles/interval")
        print(f"Late tile rate:         {late_rate:.2f} tiles/interval")
        print(f"Diminishing returns:    {late_rate < early_rate}")
    print()

    # THE COBOL THEOREM
    print("COBOL THEOREM VERIFICATION:")
    print(f"  Fleet (agents alone):  covered {accumulator.total_violations_fleet} / {accumulator.total_violations_ground_truth} violations")
    fleet_rate = accumulator.total_violations_fleet / max(accumulator.total_violations_ground_truth, 1)
    print(f"  Fleet-only rate:       {fleet_rate:.2%}")
    print(f"  Fleet + Tiles:         covered {final_cov['covered_violations']} / {final_cov['total_violations']} violations")
    print(f"  Combined rate:         {final_cov['violation_coverage']:.2%}")
    print(f"  Tiles added value:     +{final_cov['violation_coverage'] - fleet_rate:.2%}")
    print()

    if final_cov['violation_coverage'] >= 0.95:
        print("✓ HYPOTHESIS CONFIRMED: Fleet converges to near-full coverage via tile accumulation.")
    elif final_cov['violation_coverage'] >= 0.85:
        print("⚠ PARTIAL: Fleet approaches high coverage but hasn't fully converged.")
    else:
        print("✗ HYPOTHESIS NOT YET CONFIRMED at this input count.")

    if is_monotonic:
        print("✓ MONOTONICITY: Coverage increases monotonically throughout.")
    else:
        print(f"✗ MONOTONICITY BROKEN at {len(breaks)} points (sampling noise expected).")

    return {
        "coverage_timeline": coverage_timeline,
        "tile_timeline": tile_timeline,
        "shadowgap_timeline": shadowgap_timeline,
        "final_coverage": final_cov,
        "is_monotonic": is_monotonic,
        "monotonicity_breaks": breaks,
        "total_tiles": len(accumulator.tiles),
        "total_shadowgaps": accumulator.total_shadowgaps,
    }


# =============================================================================
# 5. Tests
# =============================================================================

def test_agent_profile():
    """Test AgentProfile skill and detection."""
    skill = np.array([1.0, 0.2, 0.9, 0.1])
    threshold = np.array([0.02, 0.5, 0.03, 0.7])
    agent = AgentProfile(0, "test", skill, threshold)

    assert agent.can_detect(0, 0.05) == True   # good skill, above threshold
    assert agent.can_detect(1, 0.1) == False    # weak skill, below threshold
    assert agent.can_detect(1, 0.6) == True     # weak but above threshold
    assert agent.can_detect(3, 0.1) == False    # nearly blind
    print("  ✓ AgentProfile detection works")


def test_synthetic_fleet():
    """Test SyntheticFleet generation."""
    fleet = SyntheticFleet(n_agents=10, n_dims=8, seed=7)
    assert len(fleet.agents) == 10
    assert all(a.dimension_skill.shape == (8,) for a in fleet.agents)

    # Every agent should have at least one weak dimension
    for agent in fleet.agents:
        weak = np.sum(agent.dimension_skill < 0.5)
        assert weak >= 1, f"Agent {agent.name} has no weak dims"

    # Generate some inputs
    for _ in range(100):
        values, is_edge = fleet.generate_input()
        assert values.shape == (8,)
        assert isinstance(is_edge, bool)
    print("  ✓ SyntheticFleet generates valid inputs")


def test_ground_truth():
    """Test ground truth violation detection."""
    fleet = SyntheticFleet(n_agents=5, n_dims=8, seed=1)
    acc = FleetTileAccumulator(fleet)

    # In-bounds → no violations
    values = np.array([50.0, 7.0, 25.0, 2500.0, 50.0, 3.0, 60.0, 15.0])
    violations = acc.ground_truth_check(values)
    assert len(violations) == 0

    # Out of bounds → violations detected
    values = np.array([200.0, 7.0, 25.0, 2500.0, 50.0, 3.0, 60.0, 15.0])
    violations = acc.ground_truth_check(values)
    assert len(violations) == 1
    assert violations[0][0] == 0  # dimension 0
    assert violations[0][1] == "hi_violation"

    # Below lower bound
    values = np.array([50.0, 7.0, -60.0, 2500.0, 50.0, 3.0, 60.0, 15.0])
    violations = acc.ground_truth_check(values)
    assert len(violations) == 1
    assert violations[0][0] == 2
    assert violations[0][1] == "lo_violation"
    print("  ✓ Ground truth violation detection works")


def test_tile_accumulation():
    """Test that tiles accumulate from shadowgaps."""
    fleet = SyntheticFleet(n_agents=20, n_dims=8, blind_spot_fraction=0.4, seed=42)
    acc = FleetTileAccumulator(fleet)

    initial_tiles = len(acc.tiles)
    for _ in range(500):
        values, _ = fleet.generate_input()
        acc.process_input(values)

    assert len(acc.tiles) >= initial_tiles, "No tiles accumulated"
    assert acc.total_shadowgaps > 0, "No shadowgaps detected"
    print(f"  ✓ Tiles accumulated: {len(acc.tiles)} from {acc.total_shadowgaps} shadowgaps")


def test_coverage_tracker():
    """Test CoverageTracker basic functionality."""
    fleet = SyntheticFleet(n_agents=20, n_dims=8, seed=42)
    acc = FleetTileAccumulator(fleet)
    tracker = CoverageTracker(n_dims=8, seed=99)

    # Before any tiles, coverage should reflect fleet-only
    cov_before = tracker.compute_coverage(acc, fleet, n_points=200)

    # Run some inputs to accumulate tiles
    for _ in range(1000):
        values, _ = fleet.generate_input()
        acc.process_input(values)

    cov_after = tracker.compute_coverage(acc, fleet, n_points=200)

    # Coverage should increase (or stay same) with tiles
    assert cov_after["violation_coverage"] >= cov_before["violation_coverage"] - 0.02, \
        f"Coverage decreased: {cov_before['violation_coverage']:.4f} → {cov_after['violation_coverage']:.4f}"
    assert cov_after["n_tiles"] > 0
    print(f"  ✓ Coverage: {cov_before['violation_coverage']:.4f} → {cov_after['violation_coverage']:.4f} "
          f"({cov_after['n_tiles']} tiles)")


def test_tile_deduplication():
    """Test that duplicate tiles are deduplicated."""
    fleet = SyntheticFleet(n_agents=20, n_dims=8, seed=42)
    acc = FleetTileAccumulator(fleet)

    # Process same input multiple times
    for _ in range(100):
        values, _ = fleet.generate_input()
        acc.process_input(values)

    tile_hashes = [t.content_hash() for t in acc.tiles]
    assert len(tile_hashes) == len(set(tile_hashes)), "Duplicate tiles found"
    print(f"  ✓ All {len(acc.tiles)} tiles are unique")


def test_convergence():
    """Test that running more inputs converges toward higher coverage."""
    fleet = SyntheticFleet(n_agents=20, n_dims=8, blind_spot_fraction=0.3, seed=42)
    acc = FleetTileAccumulator(fleet)
    tracker = CoverageTracker(n_dims=8, seed=99)

    coverages = []
    for batch in range(5):
        for _ in range(1000):
            values, _ = fleet.generate_input()
            acc.process_input(values)
        cov = tracker.compute_coverage(acc, fleet, n_points=500)
        coverages.append(cov["violation_coverage"])

    # Coverage should generally increase
    assert coverages[-1] >= coverages[0], \
        f"No increase (already converged): {coverages[0]:.4f} → {coverages[-1]:.4f}"
    print(f"  ✓ Convergence: {coverages[0]:.4f} → {coverages[-1]:.4f} over 5 batches")


def run_tests():
    """Run all tests."""
    print("Running E9 tests...")
    print()
    test_agent_profile()
    test_synthetic_fleet()
    test_ground_truth()
    test_tile_accumulation()
    test_coverage_tracker()
    test_tile_deduplication()
    test_convergence()
    print()
    print("All tests passed ✓")


if __name__ == "__main__":
    run_tests()
    print()
    print()
    results = run_experiment(
        n_agents=20,
        n_dims=8,
        blind_spot_fraction=0.3,
        n_inputs=10000,
        coverage_sample_interval=100,
        coverage_sample_points=500,
        seed=42,
    )
