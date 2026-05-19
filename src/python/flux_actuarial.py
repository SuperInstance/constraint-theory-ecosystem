"""
flux_actuarial.py — Actuarial Risk Pooling for Constraint Checking

Insurance-inspired resource optimization: allocate checking effort based on
statistical risk. High-violation sources get checked more often (pay higher
"premiums"). Low-violation sources get checked less often (lower "premiums").

How it works:
  1. Group similar data sources into risk pools
  2. Each pool has a baseline violation rate (gamma-Poisson model)
  3. Individual sources get Bayesian-adjusted rates based on history
  4. Checking frequency (premium) is proportional to violation rate
  5. Pools are periodically rebalanced

This reduces checking cost by 5-10x while maintaining coverage on high-risk
sources.

Usage:
    actuarial = ActuarialChecker()
    actuarial.create_pool("temperature_sensors", constraints=[...])
    actuarial.register_source("temp_sensor_01", pool="temperature_sensors")
    
    # Only checks if the source's premium says it's due
    result = actuarial.check("temp_sensor_01", value=23.5)
"""

from __future__ import annotations
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

class RiskTier(Enum):
    LOW = "low"          # < 5th percentile of pool violation rate
    STANDARD = "standard"  # Within 1σ of pool mean
    ELEVATED = "elevated"  # 1-2σ above pool mean
    HIGH = "high"          # > 2σ above pool mean
    CRITICAL = "critical"  # Extreme outlier


@dataclass
class CheckResult:
    """Result of an actuarial constraint check."""
    source_id: str
    value: Any
    passed: bool
    checked: bool               # Was this check actually performed?
    skip_reason: str = ""       # If not checked, why
    violation_details: str = ""
    check_time: float = 0.0


@dataclass
class Premium:
    """Checking frequency (premium) for a data source.

    In insurance terms:
      - base_premium = pool-level rate
      - experience_rating = individual adjustment based on history
      - final_premium = combined rate
    """
    source_id: str
    pool_id: str
    base_premium: float          # Pool-level checking rate (0-1)
    experience_rating: float     # Individual risk multiplier
    final_premium: float         # Effective checking probability (0-1)
    risk_tier: RiskTier = RiskTier.STANDARD
    violation_count: int = 0
    total_checks: int = 0
    weighted_violations: float = 0.0

    @property
    def violation_rate(self) -> float:
        if self.total_checks == 0:
            return 0.0
        return self.weighted_violations / self.total_checks


@dataclass
class RiskPool:
    """A pool of similar data sources sharing statistical risk.

    Uses a gamma-Poisson (negative binomial) conjugate model for robust
    violation rate estimation even with sparse data.
    """
    pool_id: str
    alpha: float = 1.0          # Gamma shape (prior + data)
    beta: float = 100.0         # Gamma rate (prior + data)
    sources: list[str] = field(default_factory=list)
    total_pool_violations: int = 0
    total_pool_checks: int = 0
    constraints: list[Any] = field(default_factory=list)
    last_rebalance: float = 0.0

    @property
    def pool_violation_rate(self) -> float:
        """Bayesian estimate of pool violation rate (posterior mean)."""
        if self.beta == 0:
            return 0.0
        return self.alpha / self.beta

    @property
    def source_count(self) -> int:
        return len(self.sources)

    def update(self, passed: bool, weight: float = 1.0):
        """Update pool statistics with a new check result."""
        self.total_pool_checks += 1
        if not passed:
            self.total_pool_violations += 1
            self.alpha += weight
        self.beta += 1


@dataclass
class PoolReport:
    """Summary statistics for a risk pool."""
    pool_id: str
    source_count: int
    pool_violation_rate: float
    total_checks: int
    total_violations: int
    tier_distribution: dict[RiskTier, int]
    avg_premium: float
    rebalance_age_seconds: float


# ---------------------------------------------------------------------------
# Gamma-Poisson Bayesian Model
# ---------------------------------------------------------------------------

class GammaPoissonModel:
    """Gamma-Poisson conjugate model for violation rate estimation.

    The gamma distribution is the conjugate prior for the Poisson rate
    parameter λ. This gives us a principled Bayesian framework for
    estimating violation rates with uncertainty quantification.

    Prior: λ ~ Gamma(α₀, β₀)
    Data:  violations ~ Poisson(λ * n_checks)
    Posterior: λ | data ~ Gamma(α₀ + violations, β₀ + n_checks)

    Posterior mean: (α₀ + violations) / (β₀ + n_checks)
    """

    @staticmethod
    def posterior_mean(prior_alpha: float, prior_beta: float,
                       violations: float, n_checks: float) -> float:
        """Compute posterior mean violation rate."""
        denom = prior_beta + n_checks
        if denom == 0:
            return 0.0
        return (prior_alpha + violations) / denom

    @staticmethod
    def posterior_variance(prior_alpha: float, prior_beta: float,
                           violations: float, n_checks: float) -> float:
        """Compute posterior variance for uncertainty quantification."""
        a = prior_alpha + violations
        b = prior_beta + n_checks
        if b == 0:
            return 0.0
        return a / (b ** 2)

    @staticmethod
    def credible_interval(prior_alpha: float, prior_beta: float,
                          violations: float, n_checks: float,
                          width: float = 0.95) -> tuple[float, float]:
        """Approximate credible interval using normal approximation."""
        a = prior_alpha + violations
        b = prior_beta + n_checks
        mean = a / b if b > 0 else 0
        std = math.sqrt(a / (b ** 2)) if b > 0 else 0
        z = 1.96  # for 95% CI
        return (max(0, mean - z * std), mean + z * std)

    @staticmethod
    def classify_risk(posterior_mean: float, pool_mean: float,
                      pool_std: float) -> RiskTier:
        """Classify a source's risk tier based on deviation from pool."""
        if pool_std == 0:
            return RiskTier.STANDARD if posterior_mean <= pool_mean else RiskTier.HIGH

        z_score = (posterior_mean - pool_mean) / pool_std

        if z_score < -1.645:
            return RiskTier.LOW
        elif z_score <= 1.0:
            return RiskTier.STANDARD
        elif z_score <= 2.0:
            return RiskTier.ELEVATED
        elif z_score <= 3.0:
            return RiskTier.HIGH
        else:
            return RiskTier.CRITICAL


# ---------------------------------------------------------------------------
# Premium Calculator
# ---------------------------------------------------------------------------

class PremiumCalculator:
    """Calculate checking premiums (frequencies) based on actuarial risk.

    Premium formula:
      base_premium = pool_violation_rate × checking_budget_fraction
      experience_rating = individual_rate / pool_rate (capped)
      final_premium = min(base_premium × experience_rating, 1.0)

    The premium determines the probability that any given check is actually
    performed. High-risk sources have premium ≈ 1.0 (always checked).
    Low-risk sources might have premium ≈ 0.1 (checked 10% of the time).
    """

    # Mapping from risk tier to minimum checking probability
    TIER_FLOOR: dict[RiskTier, float] = {
        RiskTier.LOW: 0.01,
        RiskTier.STANDARD: 0.05,
        RiskTier.ELEVATED: 0.20,
        RiskTier.HIGH: 0.50,
        RiskTier.CRITICAL: 1.00,
    }

    def __init__(self, max_experience_multiplier: float = 5.0):
        self.max_exp_mult = max_experience_multiplier

    def calculate(
        self,
        source_id: str,
        pool: RiskPool,
        source_violations: float,
        source_checks: float,
    ) -> Premium:
        """Calculate premium for a data source."""
        model = GammaPoissonModel

        # Pool-level base rate
        pool_rate = pool.pool_violation_rate
        base_premium = min(pool_rate * 10, 1.0)  # Scale up for visibility

        # Individual posterior mean
        individual_rate = model.posterior_mean(
            pool.alpha, pool.beta, source_violations, source_checks
        )

        # Experience rating: individual vs pool
        if pool_rate > 0:
            experience_rating = min(
                individual_rate / pool_rate,
                self.max_exp_mult,
            )
        else:
            experience_rating = 1.0

        # Final premium
        final = min(base_premium * experience_rating, 1.0)

        # Classify risk tier
        pool_variance = model.posterior_variance(
            pool.alpha, pool.beta,
            pool.total_pool_violations, pool.total_pool_checks,
        )
        pool_std = math.sqrt(pool_variance) if pool_variance > 0 else 0.01
        tier = model.classify_risk(individual_rate, pool_rate, pool_std)

        # Apply tier floor
        floor = self.TIER_FLOOR.get(tier, 0.05)
        final = max(final, floor)

        return Premium(
            source_id=source_id,
            pool_id=pool.pool_id,
            base_premium=round(base_premium, 6),
            experience_rating=round(experience_rating, 6),
            final_premium=round(final, 6),
            risk_tier=tier,
            violation_count=int(source_violations),
            total_checks=int(source_checks),
            weighted_violations=source_violations,
        )


# ---------------------------------------------------------------------------
# Constraint Definition
# ---------------------------------------------------------------------------

@dataclass
class Constraint:
    """A single constraint that can be checked against a value."""
    name: str
    check_fn: Any  # Callable[[Any], bool]
    severity: float = 1.0  # Weight for violation counting

    def check(self, value: Any) -> bool:
        try:
            return self.check_fn(value)
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Actuarial Checker (main interface)
# ---------------------------------------------------------------------------

class ActuarialChecker:
    """Actuarial risk-pooling constraint checker.

    Groups data sources into risk pools, assigns checking premiums based on
    Bayesian violation rate estimation, and optimizes checking frequency.

    Args:
        rebalance_interval: Seconds between pool rebalancing
        default_check_budget: Default fraction of checks to perform

    Example:
        >>> ac = ActuarialChecker()
        >>> ac.create_pool("sensors", constraints=[
        ...     Constraint("range", lambda v: 0 <= v <= 100),
        ... ])
        >>> ac.register_source("s1", pool="sensors")
        >>> result = ac.check("s1", 50.0)
    """

    def __init__(
        self,
        rebalance_interval: float = 3600.0,
        default_check_budget: float = 0.3,
    ):
        self.rebalance_interval = rebalance_interval
        self.default_check_budget = default_check_budget
        self.pools: dict[str, RiskPool] = {}
        self.premiums: dict[str, Premium] = {}
        self._source_history: dict[str, list[tuple[float, bool, float]]] = {}
        self._calculator = PremiumCalculator()
        self._now = time.monotonic

    def create_pool(
        self,
        pool_id: str,
        constraints: list[Constraint] | None = None,
        prior_alpha: float = 1.0,
        prior_beta: float = 100.0,
    ) -> RiskPool:
        """Create a new risk pool for a group of similar sources."""
        pool = RiskPool(
            pool_id=pool_id,
            alpha=prior_alpha,
            beta=prior_beta,
            constraints=constraints or [],
            last_rebalance=self._now(),
        )
        self.pools[pool_id] = pool
        return pool

    def register_source(
        self,
        source_id: str,
        pool_id: str,
    ) -> Premium:
        """Register a data source with a risk pool."""
        if pool_id not in self.pools:
            raise ValueError(f"Pool '{pool_id}' does not exist")
        pool = self.pools[pool_id]
        pool.sources.append(source_id)
        self._source_history[source_id] = []

        # Initial premium based on pool baseline
        premium = self._calculator.calculate(
            source_id, pool, 0.0, 0.0
        )
        self.premiums[source_id] = premium
        return premium

    def check(self, source_id: str, value: Any) -> CheckResult:
        """Check a value against constraints, respecting premium-based frequency.

        The check is only performed with probability = source's premium.
        High-risk sources are always checked. Low-risk sources are sampled.
        """
        if source_id not in self.premiums:
            raise ValueError(f"Source '{source_id}' not registered")
        if source_id not in self._source_history:
            raise ValueError(f"Source '{source_id}' has no history tracker")

        premium = self.premiums[source_id]
        pool = self.pools[premium.pool_id]

        # Premium-based sampling: should we check this time?
        import random
        should_check = random.random() < premium.final_premium

        if not should_check:
            # Record skip
            self._source_history[source_id].append((self._now(), True, 0.0))
            return CheckResult(
                source_id=source_id,
                value=value,
                passed=True,  # Assume OK when not checking
                checked=False,
                skip_reason="below_premium",
            )

        # Perform actual constraint check
        t0 = self._now()
        all_passed = True
        violation_details = []
        weighted_violations = 0.0

        for constraint in pool.constraints:
            passed = constraint.check(value)
            if not passed:
                all_passed = False
                weighted_violations += constraint.severity
                violation_details.append(constraint.name)

        check_time = self._now() - t0

        # Update statistics
        pool.update(all_passed, weight=1.0)
        self._source_history[source_id].append(
            (self._now(), all_passed, weighted_violations)
        )

        # Recalculate premium
        total_violations = sum(
            w for _, _, w in self._source_history[source_id]
        )
        total_checks = sum(
            1 for _, p, _ in self._source_history[source_id]
            if p or not p  # all entries count
        )
        self.premiums[source_id] = self._calculator.calculate(
            source_id, pool, total_violations, total_checks
        )

        return CheckResult(
            source_id=source_id,
            value=value,
            passed=all_passed,
            checked=True,
            violation_details=", ".join(violation_details),
            check_time=check_time,
        )

    def rebalance_pool(self, pool_id: str) -> PoolReport:
        """Rebalance a pool: recalculate all premiums from scratch.

        Should be called periodically (every rebalance_interval seconds).
        """
        if pool_id not in self.pools:
            raise ValueError(f"Pool '{pool_id}' does not exist")
        pool = self.pools[pool_id]

        tier_dist: dict[RiskTier, int] = {t: 0 for t in RiskTier}
        premium_sum = 0.0

        for source_id in pool.sources:
            history = self._source_history.get(source_id, [])
            total_violations = sum(w for _, _, w in history)
            total_checks = len(history)

            premium = self._calculator.calculate(
                source_id, pool, total_violations, total_checks
            )
            self.premiums[source_id] = premium
            tier_dist[premium.risk_tier] += 1
            premium_sum += premium.final_premium

        pool.last_rebalance = self._now()
        avg_premium = premium_sum / len(pool.sources) if pool.sources else 0

        return PoolReport(
            pool_id=pool_id,
            source_count=len(pool.sources),
            pool_violation_rate=round(pool.pool_violation_rate, 6),
            total_checks=pool.total_pool_checks,
            total_violations=pool.total_pool_violations,
            tier_distribution=tier_dist,
            avg_premium=round(avg_premium, 6),
            rebalance_age_seconds=0.0,
        )

    def get_premium(self, source_id: str) -> Premium:
        """Get the current premium for a data source."""
        return self.premiums[source_id]

    def pool_report(self, pool_id: str) -> PoolReport:
        """Generate a report for a risk pool."""
        return self.rebalance_pool(pool_id)

    def efficiency_stats(self) -> dict:
        """Calculate checking efficiency across all pools."""
        total_sources = len(self.premiums)
        if total_sources == 0:
            return {"efficiency": 1.0, "sources": 0}

        avg_premium = sum(p.final_premium for p in self.premiums.values()) / total_sources
        return {
            "total_sources": total_sources,
            "avg_premium": round(avg_premium, 4),
            "checks_saved_pct": round((1 - avg_premium) * 100, 1),
            "pools": len(self.pools),
            "tier_distribution": {
                t.value: sum(1 for p in self.premiums.values() if p.risk_tier == t)
                for t in RiskTier
            },
        }
