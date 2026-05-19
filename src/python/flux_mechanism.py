"""
FLUX Mechanism Design — Truthful mechanisms for constraint systems.

Designs incentive-compatible systems where sensors/constraints
report truthfully because it's their dominant strategy.

Key concepts:
1. Truthful reporting via Vickrey-Clarke-Groves (VCG) mechanism
2. Reputation-weighted checking intensity
3. Payment/penalty schedules that align incentives

Forgemaster ⚒️ — 2026-05-19
"""

import math
import hashlib
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class Sensor:
    """A sensor that reports values and has a reputation score."""
    name: str
    reputation: float = 1.0  # 0.0 to 1.0
    total_reports: int = 0
    violations_caught: int = 0
    false_alarms: int = 0
    
    @property
    def trust_score(self) -> float:
        """Computed trust: (caught / total) - (false_alarms / total)."""
        if self.total_reports == 0:
            return 0.5
        return (self.violations_caught - self.false_alarms) / max(1, self.total_reports)


@dataclass
class ConstraintReport:
    """A constraint bound report from a sensor/operator."""
    sensor: str
    lo: float
    hi: float
    confidence: float = 1.0  # How confident the reporter is
    timestamp: float = 0.0


class VCGMechanism:
    """
    Vickrey-Clarke-Groves mechanism for constraint bound determination.
    
    Multiple parties report their preferred constraint bounds.
    The mechanism selects bounds that maximize social welfare
    and charges each party their externality (harm to others).
    
    Truthful reporting is a dominant strategy.
    """

    def __init__(self, n_constraints: int = 1,
                 penalty_missed: float = 10.0,
                 penalty_false_alarm: float = 1.0):
        self.n_constraints = n_constraints
        self.penalty_missed = penalty_missed
        self.penalty_false_alarm = penalty_false_alarm

    def social_welfare(self, bounds: List[Tuple[float, float]],
                       reports: List[ConstraintReport],
                       test_data: List[Tuple[float, bool]]) -> float:
        """
        Total welfare: sum of all reporters' utilities given these bounds.
        """
        welfare = 0.0
        for report in reports:
            for lo, hi in bounds:
                for value, is_anomaly in test_data:
                    violates = not (lo <= value <= hi) or value != value
                    if violates and is_anomaly:
                        welfare += report.confidence
                    elif violates and not is_anomaly:
                        welfare -= self.penalty_false_alarm * report.confidence
                    elif not violates and is_anomaly:
                        welfare -= self.penalty_missed * report.confidence
        return welfare

    def allocate(self, reports: List[ConstraintReport],
                 test_data: List[Tuple[float, bool]]) -> Dict:
        """
        Run VCG allocation:
        1. Find optimal bounds (maximize social welfare)
        2. Charge each reporter their externality
        
        Returns allocation with payments.
        """
        if not reports:
            return {"bounds": [], "payments": [], "welfare": 0.0}
        
        # Aggregate reported bounds (median for robustness)
        los = sorted([r.lo for r in reports])
        his = sorted([r.hi for r in reports])
        n = len(reports)
        
        if n % 2 == 0:
            best_lo = (los[n // 2 - 1] + los[n // 2]) / 2
            best_hi = (his[n // 2 - 1] + his[n // 2]) / 2
        else:
            best_lo = los[n // 2]
            best_hi = his[n // 2]
        
        best_bounds = [(best_lo, best_hi)] * self.n_constraints
        
        # Social welfare with all reporters
        welfare_with_all = self.social_welfare(best_bounds, reports, test_data)
        
        # VCG payments: externality of each reporter
        payments = []
        for i, report in enumerate(reports):
            others = [r for j, r in enumerate(reports) if j != i]
            if not others:
                payments.append(0.0)
                continue
            
            # Welfare without this reporter
            welfare_without = self.social_welfare(best_bounds, others, test_data)
            
            # Payment = externality = welfare_without_others - welfare_with_all_excluding_i
            payment = max(0, welfare_without - (welfare_with_all - report.confidence))
            payments.append(payment)
        
        return {
            "bounds": best_bounds,
            "payments": payments,
            "welfare": welfare_with_all,
            "n_reporters": len(reports),
        }


class ReputationWeightedChecker:
    """
    Checking intensity adapts based on sensor reputation.
    
    High-reputation sensors: checked less often (trusted)
    Low-reputation sensors: checked more often (distrusted)
    
    This is the 'insurance pooling' insight — risky sensors pay more
    (in checking overhead) just like risky drivers pay higher premiums.
    """

    def __init__(self, sensors: List[Sensor],
                 base_check_rate: float = 1.0,
                 min_check_rate: float = 0.01,
                 max_check_rate: float = 1.0):
        self.sensors = {s.name: s for s in sensors}
        self.base_rate = base_check_rate
        self.min_rate = min_check_rate
        self.max_rate = max_check_rate

    def check_rate(self, sensor_name: str) -> float:
        """
        Compute checking rate for a sensor based on reputation.
        High reputation → low checking (trust).
        Low reputation → high checking (verify).
        
        rate = base_rate * (1 - reputation) + min_rate
        """
        sensor = self.sensors.get(sensor_name)
        if not sensor:
            return self.max_rate  # Unknown sensor: always check
        
        rate = self.base_rate * (1.0 - sensor.reputation) + self.min_rate
        return max(self.min_rate, min(self.max_rate, rate))

    def should_check(self, sensor_name: str, random_value: float) -> bool:
        """Determine if this reading should be checked."""
        rate = self.check_rate(sensor_name)
        return random_value < rate

    def update_reputation(self, sensor_name: str, was_correct: bool):
        """
        Update sensor reputation after a check.
        Correct readings increase reputation, violations decrease it.
        """
        sensor = self.sensors.get(sensor_name)
        if not sensor:
            return
        
        sensor.total_reports += 1
        alpha = 0.1  # Learning rate
        
        if was_correct:
            sensor.reputation = sensor.reputation * (1 - alpha) + alpha
        else:
            sensor.reputation = sensor.reputation * (1 - alpha)
        
        sensor.reputation = max(0.0, min(1.0, sensor.reputation))

    def system_overhead(self) -> float:
        """Average checking overhead across all sensors."""
        if not self.sensors:
            return self.base_rate
        return sum(self.check_rate(name) for name in self.sensors) / len(self.sensors)


class PenaltySchedule:
    """
    Payment/penalty schedule that aligns incentives.
    
    Sensors that correctly detect violations are rewarded.
    Sensors that miss violations or false-alarm are penalized.
    
    The schedule is designed so expected value is maximized at truthful reporting.
    """

    def __init__(self, reward_detection: float = 1.0,
                 penalty_miss: float = 10.0,
                 penalty_false_alarm: float = 1.0):
        self.reward = reward_detection
        self.penalty_miss = penalty_miss
        self.penalty_fp = penalty_false_alarm

    def expected_payment(self, detection_rate: float,
                         false_positive_rate: float,
                         anomaly_rate: float = 0.01) -> float:
        """
        Expected payment given performance characteristics.
        
        E[payment] = reward * P(detect) * P(anomaly)
                   - penalty_miss * P(miss) * P(anomaly)
                   - penalty_fp * P(FP) * P(normal)
        """
        p_detect = detection_rate * anomaly_rate * self.reward
        p_miss = (1 - detection_rate) * anomaly_rate * self.penalty_miss
        p_fp = false_positive_rate * (1 - anomaly_rate) * self.penalty_fp
        
        return p_detect - p_miss - p_fp

    def optimal_threshold(self, anomaly_rate: float = 0.01) -> float:
        """
        Find the optimal detection threshold that maximizes expected payment.
        
        For Gaussian distributions, this is related to the likelihood ratio test.
        threshold = sigma * sqrt(2 * ln((1-p)/p * penalty_miss/reward))
        """
        if anomaly_rate <= 0 or anomaly_rate >= 1:
            return 0.0
        
        ratio = ((1 - anomaly_rate) / anomaly_rate) * (self.penalty_miss / self.reward)
        if ratio <= 0:
            return 0.0
        
        return math.sqrt(2 * math.log(ratio))
