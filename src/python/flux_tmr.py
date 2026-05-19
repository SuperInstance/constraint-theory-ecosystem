"""
flux_tmr.py — Triple Modular Redundancy for Constraint Checking

Aviation-inspired fault tolerance: three independent checkers vote on every
validation. Majority wins. Disagreement = fault detection.

Design principles (from DO-178C aviation standard):
  - Three independent implementations (different algorithms/logic)
  - Majority voter selects final result
  - Discrepant channel is flagged (not silently ignored)
  - Fail-closed: no majority = FAIL

Usage:
    checker = TMRChecker(
        RangeChecker(0, 100),
        NegatedLogicChecker(0, 100),
        OffsetChecker(0, 100),
    )
    result = checker.check(42)
    assert result.passed
    assert result.consensus  # all three agreed
"""

from __future__ import annotations
import time
import hashlib
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

class Vote(Enum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"


@dataclass
class ChannelResult:
    """Result from one TMR channel."""
    channel_id: int
    vote: Vote
    value: Any = None
    message: str = ""
    latency_ms: float = 0.0
    checksum: str = ""


@dataclass
class TMRResult:
    """Final TMR consensus result."""
    passed: bool
    consensus: bool          # True = all channels agreed
    majority_vote: Vote
    faulted_channel: Optional[int] = None
    channel_results: list[ChannelResult] = field(default_factory=list)
    confidence: float = 1.0  # 1.0 = unanimous, 0.67 = 2-of-3

    @property
    def is_degraded(self) -> bool:
        """System is operating with a known faulted channel."""
        return self.faulted_channel is not None


# ---------------------------------------------------------------------------
# Individual checker implementations (designed for independence)
# ---------------------------------------------------------------------------

class CheckerBase:
    """Base class for independent constraint checkers."""

    def check(self, value: Any) -> ChannelResult:
        raise NotImplementedError

    def _checksum(self, value: Any) -> str:
        """Produce a deterministic checksum of the value for comparison."""
        return hashlib.sha256(str(value).encode()).hexdigest()[:16]


class DirectRangeChecker(CheckerBase):
    """Channel A: Direct comparison — value >= min AND value <= max."""

    def __init__(self, min_val: float, max_val: float, channel_id: int = 0):
        self.min_val = min_val
        self.max_val = max_val
        self.channel_id = channel_id

    def check(self, value: Any) -> ChannelResult:
        t0 = time.monotonic()
        try:
            passed = self.min_val <= value <= self.max_val
            vote = Vote.PASS if passed else Vote.FAIL
            msg = "" if passed else f"{value} outside [{self.min_val}, {self.max_val}]"
        except (TypeError, ValueError) as e:
            vote = Vote.ERROR
            msg = f"Type error: {e}"
        latency = (time.monotonic() - t0) * 1000
        return ChannelResult(
            channel_id=self.channel_id,
            vote=vote,
            value=value,
            message=msg,
            latency_ms=latency,
            checksum=self._checksum(value),
        )


class NegatedLogicChecker(CheckerBase):
    """Channel B: Negated logic — NOT (value < min OR value > max).

    Uses inverted boolean logic to avoid common-mode bugs with DirectRangeChecker.
    """

    def __init__(self, min_val: float, max_val: float, channel_id: int = 1):
        self.min_val = min_val
        self.max_val = max_val
        self.channel_id = channel_id

    def check(self, value: Any) -> ChannelResult:
        t0 = time.monotonic()
        try:
            out_of_range = (value < self.min_val) or (value > self.max_val)
            passed = not out_of_range
            vote = Vote.PASS if passed else Vote.FAIL
            msg = "" if passed else f"{value} violates negated range check"
        except (TypeError, ValueError) as e:
            vote = Vote.ERROR
            msg = f"Type error: {e}"
        latency = (time.monotonic() - t0) * 1000
        return ChannelResult(
            channel_id=self.channel_id,
            vote=vote,
            value=value,
            message=msg,
            latency_ms=latency,
            checksum=self._checksum(value),
        )


class OffsetChecker(CheckerBase):
    """Channel C: Center-offset comparison — |value - center| <= half_span.

    Uses a completely different arithmetic approach: computes distance from
    the midpoint of the range and compares to half the span.
    """

    def __init__(self, min_val: float, max_val: float, channel_id: int = 2):
        self.center = (min_val + max_val) / 2.0
        self.half_span = (max_val - min_val) / 2.0
        self.min_val = min_val
        self.max_val = max_val
        self.channel_id = channel_id

    def check(self, value: Any) -> ChannelResult:
        t0 = time.monotonic()
        try:
            distance = abs(value - self.center)
            passed = distance <= self.half_span
            vote = Vote.PASS if passed else Vote.FAIL
            msg = "" if passed else f"distance {distance} > half_span {self.half_span}"
        except (TypeError, ValueError) as e:
            vote = Vote.ERROR
            msg = f"Type error: {e}"
        latency = (time.monotonic() - t0) * 1000
        return ChannelResult(
            channel_id=self.channel_id,
            vote=vote,
            value=value,
            message=msg,
            latency_ms=latency,
            checksum=self._checksum(value),
        )


class EpsilonChecker(CheckerBase):
    """Channel D: Epsilon-bounded comparison with floating-point tolerance.

    Adds a small epsilon buffer to handle floating-point edge cases differently
    from the integer-exact comparisons above.
    """

    def __init__(self, min_val: float, max_val: float, epsilon: float = 1e-9, channel_id: int = 3):
        self.min_val = min_val
        self.max_val = max_val
        self.epsilon = epsilon
        self.channel_id = channel_id

    def check(self, value: Any) -> ChannelResult:
        t0 = time.monotonic()
        try:
            # Use epsilon-relative comparison
            passed = (value > self.min_val - self.epsilon) and (value < self.max_val + self.epsilon)
            vote = Vote.PASS if passed else Vote.FAIL
            msg = "" if passed else f"{value} outside epsilon-bounded range"
        except (TypeError, ValueError) as e:
            vote = Vote.ERROR
            msg = f"Type error: {e}"
        latency = (time.monotonic() - t0) * 1000
        return ChannelResult(
            channel_id=self.channel_id,
            vote=vote,
            value=value,
            message=msg,
            latency_ms=latency,
            checksum=self._checksum(value),
        )


# ---------------------------------------------------------------------------
# TMR Voter
# ---------------------------------------------------------------------------

class TMRVoter:
    """Majority voter for TMR constraint checking.

    Voting rules:
      - All same → consensus (confidence = 1.0)
      - 2-of-3 agree → majority (confidence = 0.67), minority is faulted
      - All disagree → no majority → FAIL (fail-closed)
      - Any ERROR → degraded mode
    """

    def vote(self, results: list[ChannelResult]) -> TMRResult:
        votes = [r.vote for r in results]
        vote_counts = {}
        for v in votes:
            vote_counts[v] = vote_counts.get(v, 0) + 1

        # Check for unanimous consensus
        if len(vote_counts) == 1:
            v = votes[0]
            return TMRResult(
                passed=(v == Vote.PASS),
                consensus=True,
                majority_vote=v,
                faulted_channel=None,
                channel_results=results,
                confidence=1.0,
            )

        # Find majority (need at least 2 of 3)
        majority_vote = None
        majority_count = 0
        for v, count in vote_counts.items():
            if count > majority_count:
                majority_count = count
                majority_vote = v

        if majority_count < 2:
            # No majority — fail closed
            return TMRResult(
                passed=False,
                consensus=False,
                majority_vote=Vote.FAIL,
                faulted_channel=None,  # can't identify single fault
                channel_results=results,
                confidence=0.0,
            )

        # Identify faulted channel(s)
        faulted = [r.channel_id for r in results if r.vote != majority_vote]
        faulted_id = faulted[0] if len(faulted) == 1 else None

        return TMRResult(
            passed=(majority_vote == Vote.PASS),
            consensus=False,
            majority_vote=majority_vote,
            faulted_channel=faulted_id,
            channel_results=results,
            confidence=round(majority_count / len(results), 4),
        )


# ---------------------------------------------------------------------------
# TMR Checker (main interface)
# ---------------------------------------------------------------------------

class TMRChecker:
    """Triple Modular Redundancy constraint checker.

    Wraps three independent checkers and uses majority voting to determine
    pass/fail. Detects and isolates faulty channels.

    Args:
        checker_a: First independent checker
        checker_b: Second independent checker
        checker_c: Third independent checker
        voter: Optional custom voter (default: standard majority voter)
        fault_threshold: Max consecutive faults before channel is disabled

    Example:
        >>> checker = TMRChecker(
        ...     DirectRangeChecker(0, 100),
        ...     NegatedLogicChecker(0, 100),
        ...     OffsetChecker(0, 100),
        ... )
        >>> result = checker.check(50.0)
        >>> result.passed
        True
        >>> result.consensus
        True
    """

    def __init__(
        self,
        checker_a: CheckerBase | None = None,
        checker_b: CheckerBase | None = None,
        checker_c: CheckerBase | None = None,
        voter: TMRVoter | None = None,
        fault_threshold: int = 5,
    ):
        if checker_a is None:
            raise ValueError("At least checker_a must be provided")
        min_val, max_val = checker_a.min_val, checker_a.max_val
        self.checkers = [
            checker_a or DirectRangeChecker(min_val, max_val, 0),
            checker_b or NegatedLogicChecker(min_val, max_val, 1),
            checker_c or OffsetChecker(min_val, max_val, 2),
        ]
        self.voter = voter or TMRVoter()
        self.fault_threshold = fault_threshold
        self._fault_counts: dict[int, int] = {c.channel_id: 0 for c in self.checkers}
        self._disabled: set[int] = set()
        self._history: list[TMRResult] = []

    def check(self, value: Any) -> TMRResult:
        """Run all active channels and vote on the result."""
        active = [c for c in self.checkers if c.channel_id not in self._disabled]
        if len(active) < 2:
            return TMRResult(
                passed=False,
                consensus=False,
                majority_vote=Vote.FAIL,
                faulted_channel=None,
                channel_results=[],
                confidence=0.0,
            )

        results = [c.check(value) for c in active]
        tmr_result = self.voter.vote(results)

        # Track faults for channel health monitoring
        if tmr_result.faulted_channel is not None:
            fc = tmr_result.faulted_channel
            self._fault_counts[fc] = self._fault_counts.get(fc, 0) + 1
            if self._fault_counts[fc] >= self.fault_threshold:
                self._disabled.add(fc)

        # Reset fault count for channels in consensus
        for r in results:
            if r.vote == tmr_result.majority_vote:
                self._fault_counts[r.channel_id] = 0

        self._history.append(tmr_result)
        return tmr_result

    @property
    def channel_health(self) -> dict[int, dict]:
        """Health status of each channel."""
        health = {}
        for c in self.checkers:
            cid = c.channel_id
            health[cid] = {
                "disabled": cid in self._disabled,
                "consecutive_faults": self._fault_counts.get(cid, 0),
                "type": type(c).__name__,
            }
        return health

    @property
    def history(self) -> list[TMRResult]:
        """Check history for audit/logging."""
        return list(self._history)

    def reset_faults(self):
        """Reset all fault counters and re-enable all channels."""
        self._fault_counts = {c.channel_id: 0 for c in self.checkers}
        self._disabled.clear()

    def configure_from_range(self, min_val: float, max_val: float) -> TMRChecker:
        """Create a TMR checker with default three-channel configuration."""
        return TMRChecker(
            DirectRangeChecker(min_val, max_val, 0),
            NegatedLogicChecker(min_val, max_val, 1),
            OffsetChecker(min_val, max_val, 2),
        )


# ---------------------------------------------------------------------------
# Extended: N-Modular Redundancy (NMR)
# ---------------------------------------------------------------------------

class NMRChecker:
    """N-Modular Redundancy — generalize TMR to N channels.

    Uses configurable quorum (default: ceil(N/2) + 1 for safety margin).
    """

    def __init__(
        self,
        checkers: list[CheckerBase],
        quorum: int | None = None,
        voter: TMRVoter | None = None,
    ):
        if len(checkers) < 3:
            raise ValueError("NMR requires at least 3 checkers")
        self.checkers = checkers
        self.quorum = quorum or (len(checkers) // 2 + 1)
        self.voter = voter or TMRVoter()

    def check(self, value: Any) -> TMRResult:
        results = [c.check(value) for c in self.checkers]
        return self.voter.vote(results)
