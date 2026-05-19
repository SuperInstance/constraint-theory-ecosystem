"""
FLUX Casting — Application-First Placement Algorithm

ASVAB-style constrained assignment solver for constraint implementations.
Matches candidate implementations (languages/runtimes) to deployment roles
based on composite scoring, hard constraints, and feedback loops.

Architecture:
  Application (need) → Capability Inventory (what's available) → Placement (optimal match)
       ↑                        ↑                                    |
       |                        |                                    |
       └──── FEEDBACK LOOP ─────┘ ←── PREDICTION (future needs) ────┘

Mathematical formulation:
  maximize  Σ v(c,a) · x(c,a)
  subject to:
    Σ_a x(c,a) ≤ 1              ∀c  (each candidate placed at most once)
    Σ_c x(c,a) = d(a)           ∀a  (each role filled to demand)
    φ(c) ≥ τ(a)                 ∀(c,a)∈x  (hard constraints)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple
import math
import itertools


# ---------------------------------------------------------------------------
# Enums & Data Structures
# ---------------------------------------------------------------------------

class SafetyLevel(IntEnum):
    """Formal verification / assurance level."""
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERY_HIGH = 4


@dataclass(frozen=True)
class CandidateProfile:
    """Capability vector for a constraint implementation.

    Mirrors an ASVAB subtest score sheet — each dimension is independently
    measured and combined into composites for placement decisions.
    """
    name: str
    speed: float              # operations/sec (benchmarked)
    memory_bytes: int         # peak memory usage in bytes
    latency_ns: float         # worst-case response time in nanoseconds
    safety: SafetyLevel       # formal verification level
    portability: int          # number of target platforms supported
    ecosystem: float          # library/tool availability score (0-10)
    language: str = ""        # human-readable language/runtime tag

    def qualifies_for(self, role: "Role") -> Tuple[bool, List[str]]:
        """Check hard constraints. Returns (passes, list_of_failures)."""
        failures: List[str] = []
        if self.speed < role.min_speed:
            failures.append(
                f"speed {self.speed:.0f}/s < min {role.min_speed:.0f}/s"
            )
        if self.memory_bytes > role.max_memory_bytes:
            failures.append(
                f"memory {self.memory_bytes}B > max {role.max_memory_bytes}B"
            )
        if self.latency_ns > role.max_latency_ns:
            failures.append(
                f"latency {self.latency_ns:.0f}ns > max {role.max_latency_ns:.0f}ns"
            )
        if self.safety < role.min_safety:
            failures.append(
                f"safety {self.safety.name} < min {role.min_safety.name}"
            )
        if role.min_portability > 0 and self.portability < role.min_portability:
            failures.append(
                f"portability {self.portability} < min {role.min_portability}"
            )
        return (len(failures) == 0, failures)


@dataclass(frozen=True)
class Role:
    """What an application needs — the job description.

    Like an MOS (Military Occupational Specialty) defining minimum composite
    thresholds for qualification.
    """
    name: str
    min_speed: float = 0.0
    max_memory_bytes: int = 10**9       # 1 GB default — generous
    max_latency_ns: float = float("inf")
    min_safety: SafetyLevel = SafetyLevel.NONE
    min_portability: int = 0
    demand: int = 1                     # how many candidates needed
    weight: float = 1.0                 # priority weight for optimization


# ---------------------------------------------------------------------------
# Composite Scoring (ASVAB-style)
# ---------------------------------------------------------------------------

class CompositeScorer:
    """Computes composite scores from candidate capability vectors.

    Analogous to ASVAB composites (GT, EL, ST, MM, CL) — each composite
    is a weighted combination of raw scores, tuned for a role category.
    """

    # Composite definitions: (speed_w, memory_w, latency_w, safety_w,
    #                          portability_w, ecosystem_w)
    COMPOSITES = {
        "performance": (0.40, 0.10, 0.30, 0.05, 0.05, 0.10),
        "embedded":    (0.20, 0.30, 0.10, 0.15, 0.10, 0.15),
        "safety":      (0.10, 0.05, 0.10, 0.50, 0.10, 0.15),
        "portable":    (0.10, 0.05, 0.05, 0.10, 0.40, 0.30),
        "balanced":    (1/6,  1/6,  1/6,  1/6,  1/6,  1/6),
    }

    @staticmethod
    def _normalize(raw: float, reference_max: float) -> float:
        """Normalize to [0, 1] with log scaling for wide ranges."""
        if reference_max <= 0:
            return 0.0
        ratio = raw / reference_max
        return min(1.0, ratio) if ratio < 1.0 else 1.0

    @classmethod
    def score(
        cls,
        candidate: CandidateProfile,
        role: Role,
        composite: str = "balanced",
    ) -> float:
        """Compute a placement quality score ∈ [0, 1].

        Higher = better fit. Accounts for how well the candidate's
        capabilities align with the role's requirements.
        """
        weights = cls.COMPOSITES.get(composite, cls.COMPOSITES["balanced"])
        w_speed, w_mem, w_lat, w_safe, w_port, w_eco = weights

        # Speed: how much headroom above minimum?
        speed_headroom = (
            (candidate.speed - role.min_speed) / role.min_speed
            if role.min_speed > 0 else candidate.speed / 1e9
        )
        speed_score = min(1.0, max(0.0, speed_headroom))

        # Memory: how much budget remains?
        mem_ratio = (
            candidate.memory_bytes / role.max_memory_bytes
            if role.max_memory_bytes > 0 else 1.0
        )
        mem_score = min(1.0, max(0.0, 1.0 - mem_ratio))

        # Latency: headroom below max
        if role.max_latency_ns < float("inf"):
            lat_headroom = (
                (role.max_latency_ns - candidate.latency_ns) / role.max_latency_ns
            )
            lat_score = min(1.0, max(0.0, lat_headroom))
        else:
            lat_score = 1.0  # no constraint → perfect

        # Safety: discrete levels above minimum
        safe_above = candidate.safety.value - role.min_safety.value
        safe_score = min(1.0, max(0.0, safe_above / max(1, 4 - role.min_safety.value)))

        # Portability
        port_score = min(1.0, candidate.portability / max(1, role.min_portability + 2))

        # Ecosystem: direct 0-10 → 0-1
        eco_score = min(1.0, candidate.ecosystem / 10.0)

        return (
            w_speed * speed_score
            + w_mem * mem_score
            + w_lat * lat_score
            + w_safe * safe_score
            + w_port * port_score
            + w_eco * eco_score
        )


# ---------------------------------------------------------------------------
# Placement Algorithm
# ---------------------------------------------------------------------------

@dataclass
class Placement:
    """A single assignment of a candidate to a role."""
    candidate: CandidateProfile
    role: Role
    score: float
    hard_pass: bool
    failures: List[str] = field(default_factory=list)


class PlacementAlgorithm:
    """Constrained assignment solver — the ASVAB placement engine.

    Given candidates and roles, finds the assignment that maximizes total
    system utility while respecting hard constraints.

    Strategy:
      1. Filter: eliminate candidates that fail hard constraints
      2. Score: compute composite scores for all (candidate, role) pairs
      3. Assign: greedy weighted assignment (high score first), with
         fallback to soft-constraint relaxation if roles go unfilled
    """

    def __init__(self, composite: str = "balanced"):
        self.composite = composite

    def _build_matrix(
        self,
        candidates: List[CandidateProfile],
        roles: List[Role],
    ) -> List[Placement]:
        """Evaluate all (candidate, role) pairs."""
        placements: List[Placement] = []
        for c in candidates:
            for r in roles:
                passes, failures = c.qualifies_for(r)
                sc = CompositeScorer.score(c, r, self.composite) if passes else 0.0
                placements.append(Placement(
                    candidate=c, role=r, score=sc,
                    hard_pass=passes, failures=failures,
                ))
        return placements

    def place(
        self,
        candidates: List[CandidateProfile],
        roles: List[Role],
    ) -> Dict[Role, Placement]:
        """Assign candidates to roles.

        Returns a mapping from each role to its assigned placement.
        Roles with no qualifying candidate get Placement with score=0.

        Uses a two-phase approach:
          Phase 1: For each role (hardest first = fewest qualified candidates),
                    assign the best qualifying candidate not yet used.
          Phase 2: Fill remaining roles with any qualifying candidates left.
        """
        matrix = self._build_matrix(candidates, roles)

        # Build lookup: role -> qualified placements sorted by score desc
        qualified_by_role: Dict[Role, List[Placement]] = {}
        for p in matrix:
            if p.hard_pass:
                qualified_by_role.setdefault(p.role, []).append(p)
        for role_list in qualified_by_role.values():
            role_list.sort(key=lambda p: p.score * p.role.weight, reverse=True)

        assigned_candidates: set = set()
        result: Dict[Role, Placement] = {}

        # Phase 1: Assign hardest-to-fill roles first
        # (fewest qualified candidates = most constrained)
        roles_by_difficulty = sorted(
            roles,
            key=lambda r: len(qualified_by_role.get(r, [])),
        )

        for r in roles_by_difficulty:
            for p in qualified_by_role.get(r, []):
                if p.candidate.name not in assigned_candidates:
                    result[r] = p
                    assigned_candidates.add(p.candidate.name)
                    break

        # Mark unfilled roles
        for r in roles:
            if r not in result:
                # Find the best unassigned candidate for diagnostics
                best_unqualified = max(
                    (p for p in matrix
                     if p.role == r and p.candidate.name not in assigned_candidates),
                    key=lambda p: CompositeScorer.score(
                        p.candidate, p.role, self.composite
                    ),
                    default=None,
                )
                if best_unqualified:
                    _, failures = best_unqualified.candidate.qualifies_for(r)
                    result[r] = Placement(
                        candidate=best_unqualified.candidate,
                        role=r,
                        score=0.0,
                        hard_pass=False,
                        failures=failures,
                    )
                else:
                    result[r] = Placement(
                        candidate=CandidateProfile(
                            name="NONE", speed=0, memory_bytes=0,
                            latency_ns=float("inf"), safety=SafetyLevel.NONE,
                            portability=0, ecosystem=0,
                        ),
                        role=r,
                        score=0.0,
                        hard_pass=False,
                        failures=["no candidates available"],
                    )

        return result


# ---------------------------------------------------------------------------
# Feedback Loop
# ---------------------------------------------------------------------------

@dataclass
class FeedbackRecord:
    """Actual vs predicted performance for a placed candidate."""
    candidate_name: str
    role_name: str
    predicted_speed: float
    actual_speed: float
    predicted_memory: int
    actual_memory: int
    predicted_latency: float
    actual_latency: float
    timestamp: float = 0.0

    def speed_error(self) -> float:
        return self.actual_speed - self.predicted_speed

    def memory_error(self) -> int:
        return self.actual_memory - self.predicted_memory

    def latency_error(self) -> float:
        return self.actual_latency - self.predicted_latency


class FeedbackLoop:
    """Adjusts candidate profiles based on real-world performance data.

    When placement fails in production, the feedback loop:
      1. Records actual vs predicted metrics
      2. Adjusts the candidate profile to reflect reality
      3. Escalates when no candidate meets role requirements
    """

    def __init__(self):
        self.records: List[FeedbackRecord] = []
        self.adjustments: Dict[str, Dict[str, float]] = {}
        self.escalations: List[str] = []

    def record(self, feedback: FeedbackRecord) -> None:
        """Record a feedback observation."""
        self.records.append(feedback)
        self._compute_adjustment(feedback)

    def _compute_adjustment(self, fb: FeedbackRecord) -> None:
        """Compute running adjustment factors for a candidate."""
        name = fb.candidate_name
        if name not in self.adjustments:
            self.adjustments[name] = {
                "speed_factor": 1.0,
                "memory_factor": 1.0,
                "latency_factor": 1.0,
            }

        adj = self.adjustments[name]

        # Exponential moving average of correction factors
        alpha = 0.3  # learning rate
        if fb.predicted_speed > 0:
            actual_ratio = fb.actual_speed / fb.predicted_speed
            adj["speed_factor"] = (1 - alpha) * adj["speed_factor"] + alpha * actual_ratio

        if fb.predicted_memory > 0:
            actual_ratio = fb.actual_memory / fb.predicted_memory
            adj["memory_factor"] = (1 - alpha) * adj["memory_factor"] + alpha * actual_ratio

        if fb.predicted_latency > 0:
            actual_ratio = fb.actual_latency / fb.predicted_latency
            adj["latency_factor"] = (1 - alpha) * adj["latency_factor"] + alpha * actual_ratio

    def adjust_profile(self, profile: CandidateProfile) -> CandidateProfile:
        """Apply learned adjustments to a candidate profile."""
        adj = self.adjustments.get(profile.name)
        if not adj:
            return profile

        return CandidateProfile(
            name=profile.name,
            speed=profile.speed * adj["speed_factor"],
            memory_bytes=int(profile.memory_bytes * adj["memory_factor"]),
            latency_ns=profile.latency_ns * adj["latency_factor"],
            safety=profile.safety,
            portability=profile.portability,
            ecosystem=profile.ecosystem,
            language=profile.language,
        )

    def check_escalation(
        self,
        candidates: List[CandidateProfile],
        roles: List[Role],
    ) -> List[str]:
        """Check if any role has no qualifying candidate (even after adjustment)."""
        adjusted = [self.adjust_profile(c) for c in candidates]
        escalations: List[str] = []

        for r in roles:
            any_qualified = False
            for c in adjusted:
                passes, _ = c.qualifies_for(r)
                if passes:
                    any_qualified = True
                    break
            if not any_qualified:
                escalations.append(
                    f"ESCALATE: No candidate qualifies for role '{r.name}' "
                    f"— need speed≥{r.min_speed:.0f}/s, "
                    f"memory≤{r.max_memory_bytes}B, "
                    f"latency≤{r.max_latency_ns:.0f}ns, "
                    f"safety≥{r.min_safety.name}"
                )

        self.escalations.extend(escalations)
        return escalations


# ---------------------------------------------------------------------------
# Predictive Caster
# ---------------------------------------------------------------------------

@dataclass
class DemandForecast:
    """Predicted future demand for a role."""
    role: Role
    predicted_demand: int
    confidence: float           # 0-1
    time_horizon: float         # seconds into the future


@dataclass
class CapabilityGap:
    """A predicted gap between available capability and future demand."""
    role_name: str
    required: str               # what's needed
    closest_candidate: str      # best current option
    gap_description: str        # what's missing
    severity: float             # 0-1, higher = more critical


class PredictiveCaster:
    """Anticipates future needs and pre-positions capability.

    Like the military forecasting recruit needs 2 years out and adjusting
    ASVAB thresholds / recruiting targets accordingly.
    """

    def __init__(self):
        self.forecasts: List[DemandForecast] = []
        self.gaps: List[CapabilityGap] = []

    def add_forecast(self, forecast: DemandForecast) -> None:
        """Register a demand forecast."""
        self.forecasts.append(forecast)

    def forecast_gaps(
        self,
        candidates: List[CandidateProfile],
        feedback: Optional[FeedbackLoop] = None,
    ) -> List[CapabilityGap]:
        """Analyze forecasted demand against current capability inventory.

        Returns gaps where no current candidate can fill a future role.
        """
        self.gaps.clear()

        # Apply feedback adjustments if available
        if feedback:
            candidates = [feedback.adjust_profile(c) for c in candidates]

        for fc in self.forecasts:
            qualified = []
            closest_score = -1.0
            closest_name = "NONE"
            closest_failures: List[str] = []

            for c in candidates:
                passes, failures = c.qualifies_for(fc.role)
                if passes:
                    score = CompositeScorer.score(c, fc.role)
                    qualified.append((c, score))
                else:
                    # Track the closest non-qualifying candidate
                    score = CompositeScorer.score(c, fc.role)
                    if score > closest_score:
                        closest_score = score
                        closest_name = c.name
                        closest_failures = failures

            if len(qualified) < fc.predicted_demand:
                gap_count = fc.predicted_demand - len(qualified)
                self.gaps.append(CapabilityGap(
                    role_name=fc.role.name,
                    required=(
                        f"speed≥{fc.role.min_speed:.0f}/s, "
                        f"memory≤{fc.role.max_memory_bytes}B, "
                        f"safety≥{fc.role.min_safety.name}"
                    ),
                    closest_candidate=closest_name,
                    gap_description=(
                        f"Need {gap_count} more candidates. "
                        f"Closest '{closest_name}' fails: "
                        + "; ".join(closest_failures)
                    ),
                    severity=min(1.0, gap_count / max(1, fc.predicted_demand))
                    * fc.confidence,
                ))

        return self.gaps

    def pre_position(
        self,
        candidates: List[CandidateProfile],
        roles: List[Role],
    ) -> Dict[str, str]:
        """Suggest pre-positioning: which candidates to ready for forecasted roles.

        Returns a mapping from role name to suggested candidate.
        """
        suggestions: Dict[str, str] = {}

        # Sort forecasts by confidence × demand (most critical first)
        sorted_forecasts = sorted(
            self.forecasts,
            key=lambda f: f.confidence * f.predicted_demand,
            reverse=True,
        )

        used_candidates: set = set()

        for fc in sorted_forecasts:
            best_candidate = None
            best_score = -1.0

            for c in candidates:
                if c.name in used_candidates:
                    continue
                passes, _ = c.qualifies_for(fc.role)
                if passes:
                    score = CompositeScorer.score(c, fc.role)
                    if score > best_score:
                        best_score = score
                        best_candidate = c

            if best_candidate:
                suggestions[fc.role.name] = best_candidate.name
                used_candidates.add(best_candidate.name)

        return suggestions


# ---------------------------------------------------------------------------
# Concrete Profiles — Real Implementations
# ---------------------------------------------------------------------------

# Memory estimates (bytes)
_KB = 1024
_MB = 1024 * 1024

CANDIDATES: List[CandidateProfile] = [
    CandidateProfile(
        name="c_avx2",
        speed=654_000_000,          # 654M ops/s
        memory_bytes=4 * _KB,       # tiny
        latency_ns=50,              # nanoseconds
        safety=SafetyLevel.HIGH,
        portability=5,              # x86 platforms mostly
        ecosystem=7.0,
        language="C (AVX2)",
    ),
    CandidateProfile(
        name="rust_vm",
        speed=1_000_000_000,        # 1B+ ops/s
        memory_bytes=16 * _KB,      # small
        latency_ns=80,              # nanoseconds
        safety=SafetyLevel.VERY_HIGH,
        portability=8,              # many targets
        ecosystem=8.5,
        language="Rust VM",
    ),
    CandidateProfile(
        name="python_numpy",
        speed=47_900_000,           # 47.9M ops/s
        memory_bytes=50 * _MB,      # medium
        latency_ns=5_000,           # microseconds
        safety=SafetyLevel.LOW,
        portability=10,             # runs everywhere
        ecosystem=9.5,
        language="Python (NumPy)",
    ),
    CandidateProfile(
        name="python_loop",
        speed=1_200_000,            # 1.2M ops/s
        memory_bytes=8 * _KB,       # small
        latency_ns=10_000,          # microseconds
        safety=SafetyLevel.LOW,
        portability=10,
        ecosystem=9.5,
        language="Python (loop)",
    ),
    CandidateProfile(
        name="wasm_sandbox",
        speed=100_000_000,          # ~100M ops/s
        memory_bytes=2 * _KB,       # tiny
        latency_ns=100,             # nanoseconds
        safety=SafetyLevel.MEDIUM,
        portability=10,             # browsers, servers, embedded
        ecosystem=7.0,
        language="WASM sandbox",
    ),
    CandidateProfile(
        name="arm_asm",
        speed=500_000_000,          # ~500M ops/s
        memory_bytes=1 * _KB,       # tiny
        latency_ns=30,              # nanoseconds
        safety=SafetyLevel.MEDIUM,
        portability=3,              # ARM only
        ecosystem=4.0,
        language="ARM Assembly",
    ),
    CandidateProfile(
        name="verilog_fpga",
        speed=1_000_000_000,        # 1 clock per op at ~1GHz
        memory_bytes=0,             # zero — hardware
        latency_ns=1,               # 1 cycle
        safety=SafetyLevel.VERY_HIGH,
        portability=2,              # FPGA only
        ecosystem=5.0,
        language="Verilog (FPGA)",
    ),
]


# ---------------------------------------------------------------------------
# Concrete Roles — Real Deployment Scenarios
# ---------------------------------------------------------------------------

ROLES: List[Role] = [
    Role(
        name="aviation_adsb",
        min_speed=1_000_000,        # 1M/s
        max_latency_ns=1_000,       # 1μs
        min_safety=SafetyLevel.HIGH,
        weight=1.5,                 # safety-critical, high priority
    ),
    Role(
        name="automotive_can",
        min_speed=80_000,           # 80K/s
        max_memory_bytes=4 * _KB,   # 4KB
        min_safety=SafetyLevel.VERY_HIGH,
        weight=1.5,
    ),
    Role(
        name="medical_fhir",
        min_speed=500_000,          # 500K/s
        min_safety=SafetyLevel.HIGH,
        weight=1.3,
    ),
    Role(
        name="energy_scada",
        min_speed=18_000_000,       # 18M/s
        weight=1.0,
    ),
    Role(
        name="underwater_acoustic",
        min_speed=1_000,            # 1K/s
        max_memory_bytes=1 * _KB,   # 1KB
        min_portability=0,          # low portability is fine
        weight=0.8,
    ),
    Role(
        name="space_radiation",
        min_safety=SafetyLevel.VERY_HIGH,
        min_portability=0,          # low portability expected
        weight=1.5,
    ),
]


# ---------------------------------------------------------------------------
# Public API — Convenience Functions
# ---------------------------------------------------------------------------

def cast(
    candidates: Optional[List[CandidateProfile]] = None,
    roles: Optional[List[Role]] = None,
    composite: str = "balanced",
) -> Dict[str, Placement]:
    """Run the full placement algorithm and return {role_name: Placement}."""
    if candidates is None:
        candidates = CANDIDATES
    if roles is None:
        roles = ROLES

    algo = PlacementAlgorithm(composite=composite)
    raw = algo.place(candidates, roles)
    return {r.name: p for r, p in raw.items()}


def print_placements(placements: Dict[str, Placement]) -> None:
    """Pretty-print placement results."""
    print("=" * 70)
    print("FLUX Casting — Placement Results")
    print("=" * 70)
    for role_name, p in sorted(placements.items()):
        status = "✓" if p.hard_pass else "✗"
        print(f"\n  [{status}] {role_name}")
        print(f"      Candidate: {p.candidate.name} ({p.candidate.language})")
        print(f"      Score:     {p.score:.4f}")
        if p.failures:
            print(f"      Failures:  {'; '.join(p.failures)}")
    print()
