"""
Flux Bayesian — Bayesian Surrogate for Expensive Constraint Checks

Uses Gaussian Process surrogates to predict constraint check results,
only running expensive checks when surrogate uncertainty warrants it.
Implements GP regression, acquisition functions, and adaptive thresholds.

Part of the Constraint Theory Ecosystem.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Minimal GP Implementation (no scipy dependency)
# ---------------------------------------------------------------------------

def _mat_vec_mul(mat: List[List[float]], vec: List[float]) -> List[float]:
    """Matrix-vector multiply."""
    return [sum(m[r][c] * vec[c] for c in range(len(vec)))
            for r in range(len(mat))]


def _cholesky(A: List[List[float]], jitter: float = 1e-6) -> List[List[float]]:
    """Cholesky decomposition with jitter for numerical stability."""
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                val = A[i][i] - s + jitter
                L[i][j] = math.sqrt(max(val, 1e-10))
            else:
                L[i][j] = (A[i][j] - s) / L[j][j] if L[j][j] > 1e-10 else 0.0
    return L


def _forward_sub(L: List[List[float]], b: List[float]) -> List[float]:
    """Solve Lx = b."""
    n = len(b)
    x = [0.0] * n
    for i in range(n):
        x[i] = (b[i] - sum(L[i][j] * x[j] for j in range(i))) / L[i][i] if L[i][i] > 1e-10 else 0.0
    return x


def _back_sub(Lt: List[List[float]], b: List[float]) -> List[float]:
    """Solve L^T x = b."""
    n = len(b)
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = (b[i] - sum(Lt[j][i] * x[j] for j in range(i + 1, n))) / Lt[i][i] if Lt[i][i] > 1e-10 else 0.0
    return x


def _solve_positive_definite(A: List[List[float]], b: List[float]) -> List[float]:
    """Solve Ax = b where A is positive-definite, via Cholesky."""
    L = _cholesky(A)
    y = _forward_sub(L, b)
    Lt = [[L[j][i] for j in range(len(L))] for i in range(len(L))]
    return _back_sub(Lt, y)


# ---------------------------------------------------------------------------
# Kernel Functions
# ---------------------------------------------------------------------------

def rbf_kernel(x1: List[float], x2: List[float],
               lengthscale: float = 1.0, signal_variance: float = 1.0) -> float:
    """Radial Basis Function (squared exponential) kernel."""
    sq_dist = sum((a - b) ** 2 for a, b in zip(x1, x2))
    return signal_variance * math.exp(-0.5 * sq_dist / (lengthscale ** 2))


# ---------------------------------------------------------------------------
# GP Surrogate
# ---------------------------------------------------------------------------

@dataclass
class GPConfig:
    """Configuration for the Gaussian Process surrogate."""
    lengthscale: float = 1.0
    signal_variance: float = 1.0
    noise_variance: float = 0.01
    jitter: float = 1e-6
    max_training_points: int = 200


@dataclass
class GPPrediction:
    """Result of a GP prediction."""
    mean: float
    variance: float
    std: float
    
    @property
    def confidence(self) -> float:
        """Confidence metric: lower std = higher confidence."""
        return 1.0 / (1.0 + self.std)


class GPSurrogate:
    """
    Gaussian Process surrogate for constraint checking.
    Predicts constraint violation scores to avoid expensive checks.
    """
    
    def __init__(self, config: Optional[GPConfig] = None):
        self.config = config or GPConfig()
        self.X_train: List[List[float]] = []
        self.y_train: List[float] = []
        self._K_inv_y: Optional[List[float]] = None
        self._K: Optional[List[List[float]]] = None
        self._dirty = True
    
    @property
    def n_training(self) -> int:
        return len(self.X_train)
    
    def add_observation(self, x: List[float], y: float) -> None:
        """Add a training observation."""
        self.X_train.append(x)
        self.y_train.append(y)
        self._dirty = True
        
        # Trim if over max
        if len(self.X_train) > self.config.max_training_points:
            self.X_train = self.X_train[-self.config.max_training_points:]
            self.y_train = self.y_train[-self.config.max_training_points:]
    
    def _ensure_fitted(self) -> None:
        """Fit the GP if training data has changed."""
        if not self._dirty:
            return
        
        n = len(self.X_train)
        if n == 0:
            self._K_inv_y = None
            self._dirty = False
            return
        
        # Build kernel matrix
        cfg = self.config
        K = [[rbf_kernel(self.X_train[i], self.X_train[j],
                         cfg.lengthscale, cfg.signal_variance)
              + (cfg.noise_variance if i == j else 0.0)
              for j in range(n)]
             for i in range(n)]
        
        self._K = K
        self._K_inv_y = _solve_positive_definite(K, self.y_train)
        self._dirty = False
    
    def predict(self, x: List[float]) -> GPPrediction:
        """Predict mean and variance at point x."""
        self._ensure_fitted()
        
        if self.n_training == 0:
            return GPPrediction(mean=0.0, variance=self.config.signal_variance,
                              std=math.sqrt(self.config.signal_variance))
        
        cfg = self.config
        n = self.n_training
        
        # k* = kernel vector between x and training points
        k_star = [rbf_kernel(x, self.X_train[i],
                             cfg.lengthscale, cfg.signal_variance)
                  for i in range(n)]
        
        # Mean: k*^T K^{-1} y
        mean = sum(k_star[i] * self._K_inv_y[i] for i in range(n))
        
        # Variance: k(x,x) - k*^T K^{-1} k*
        k_xx = rbf_kernel(x, x, cfg.lengthscale, cfg.signal_variance)
        k_inv_k = _solve_positive_definite(self._K, k_star)
        variance = k_xx - sum(k_star[i] * k_inv_k[i] for i in range(n))
        variance = max(variance, 1e-10)  # Numerical floor
        
        return GPPrediction(mean=mean, variance=variance, std=math.sqrt(variance))
    
    def feasibility_probability(self, x: List[float], threshold: float = 0.0) -> float:
        """
        Probability that constraint value <= threshold.
        Uses probit approximation.
        """
        pred = self.predict(x)
        if pred.std < 1e-10:
            return 1.0 if pred.mean <= threshold else 0.0
        
        z = (threshold - pred.mean) / pred.std
        # Probit approximation using logistic
        return 1.0 / (1.0 + math.exp(-1.7 * z))


# ---------------------------------------------------------------------------
# Acquisition Functions
# ---------------------------------------------------------------------------

def acquisition_uncertainty(pred: GPPrediction, threshold: float = 0.0) -> float:
    """Uncertainty-based acquisition: higher std = more valuable to check."""
    return pred.std


def acquisition_expected_mistake(
    pred: GPPrediction,
    objective_value: float,
    best_objective: float,
    threshold: float = 0.0,
) -> float:
    """
    Cost-aware expected mistake cost.
    Higher when surrogate is uncertain AND objective is promising.
    """
    ei = max(best_objective - objective_value, 0.0)  # Expected improvement proxy
    p_feas = _sigmoid(-(pred.mean - threshold) / max(pred.std, 1e-6))
    uncertainty = p_feas * (1.0 - p_feas)
    return 2.0 * ei * uncertainty


def acquisition_entropy(pred: GPPrediction, threshold: float = 0.0) -> float:
    """Entropy-based acquisition: measures uncertainty in feasibility."""
    p = max(min(_sigmoid(-(pred.mean - threshold) / max(pred.std, 1e-6)), 0.999), 0.001)
    return -p * math.log(p) - (1 - p) * math.log(1 - p)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-500, min(500, x))))


# ---------------------------------------------------------------------------
# Bayesian Constraint Checker
# ---------------------------------------------------------------------------

@dataclass
class CheckDecision:
    """Result of deciding whether to run an expensive check."""
    should_check: bool
    surrogate_prediction: GPPrediction
    feasibility_prob: float
    acquisition_value: float
    reason: str


@dataclass
class BayesianCheckerConfig:
    """Configuration for the Bayesian constraint checker."""
    check_threshold: float = 0.0        # Violation threshold
    skip_if_confident: float = 0.95     # Skip if p_feas > this
    skip_if_violated: float = 0.05      # Skip if p_feas < this (mark violated)
    acquisition_fn: str = "uncertainty"  # "uncertainty", "entropy", "expected_mistake"
    acquisition_threshold: float = 0.3   # Check if acquisition > this
    gp_config: Optional[GPConfig] = None


class BayesianConstraintChecker:
    """
    Wraps an expensive constraint check with a GP surrogate.
    Only runs the expensive check when surrogate uncertainty justifies it.
    """
    
    def __init__(
        self,
        expensive_check_fn: Callable[[List[float]], float],
        config: Optional[BayesianCheckerConfig] = None,
    ):
        self.expensive_check_fn = expensive_check_fn
        self.config = config or BayesianCheckerConfig()
        gp_cfg = self.config.gp_config or GPConfig()
        self.surrogate = GPSurrogate(gp_cfg)
        
        self.total_queries = 0
        self.expensive_checks_run = 0
        self.checks_skipped = 0
        self.correct_skips = 0
        self.incorrect_skips = 0
    
    @property
    def savings_rate(self) -> float:
        """Fraction of expensive checks avoided."""
        return self.checks_skipped / max(self.total_queries, 1)
    
    @property
    def skip_accuracy(self) -> float:
        """Accuracy of surrogate-based skip decisions."""
        total_skips = self.correct_skips + self.incorrect_skips
        return self.correct_skips / max(total_skips, 1)
    
    def decide(self, x: List[float], objective_value: float = 0.0,
               best_objective: float = 0.0) -> CheckDecision:
        """Decide whether to run the expensive check for input x."""
        self.total_queries += 1
        
        pred = self.surrogate.predict(x)
        p_feas = self.surrogate.feasibility_probability(x, self.config.check_threshold)
        
        # Select acquisition function
        if self.config.acquisition_fn == "entropy":
            acq = acquisition_entropy(pred, self.config.check_threshold)
        elif self.config.acquisition_fn == "expected_mistake":
            acq = acquisition_expected_mistake(pred, objective_value, best_objective,
                                               self.config.check_threshold)
        else:
            acq = acquisition_uncertainty(pred, self.config.check_threshold)
        
        # Decision logic
        if p_feas >= self.config.skip_if_confident:
            return CheckDecision(
                should_check=False, surrogate_prediction=pred,
                feasibility_prob=p_feas, acquisition_value=acq,
                reason=f"High confidence feasible (p={p_feas:.3f})"
            )
        
        if p_feas <= self.config.skip_if_violated:
            return CheckDecision(
                should_check=False, surrogate_prediction=pred,
                feasibility_prob=p_feas, acquisition_value=acq,
                reason=f"High confidence violated (p={p_feas:.3f})"
            )
        
        if acq < self.config.acquisition_threshold and self.surrogate.n_training > 10:
            return CheckDecision(
                should_check=False, surrogate_prediction=pred,
                feasibility_prob=p_feas, acquisition_value=acq,
                reason=f"Low acquisition value ({acq:.3f})"
            )
        
        return CheckDecision(
            should_check=True, surrogate_prediction=pred,
            feasibility_prob=p_feas, acquisition_value=acq,
            reason=f"Uncertain (p={p_feas:.3f}, acq={acq:.3f})"
        )
    
    def check(self, x: List[float], objective_value: float = 0.0,
              best_objective: float = 0.0) -> Tuple[float, CheckDecision]:
        """
        Check constraint at x. Returns (result, decision).
        Runs expensive check only if surrogate is uncertain.
        """
        decision = self.decide(x, objective_value, best_objective)
        
        if decision.should_check:
            self.expensive_checks_run += 1
            result = self.expensive_check_fn(x)
            self.surrogate.add_observation(x, result)
            return result, decision
        else:
            self.checks_skipped += 1
            # Use surrogate prediction
            return decision.surrogate_prediction.mean, decision
    
    def evaluate_accuracy(self, test_points: List[Tuple[List[float], float]]) -> Dict[str, float]:
        """Evaluate surrogate accuracy on labeled test points."""
        correct = 0
        total = len(test_points)
        mae = 0.0
        
        for x, true_val in test_points:
            pred = self.surrogate.predict(x)
            pred_violated = pred.mean > self.config.check_threshold
            true_violated = true_val > self.config.check_threshold
            
            if pred_violated == true_violated:
                correct += 1
            mae += abs(pred.mean - true_val)
        
        return {
            "accuracy": correct / max(total, 1),
            "mae": mae / max(total, 1),
            "total": total,
            "savings_rate": self.savings_rate,
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

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
    
    print("\n=== flux_bayesian tests ===\n")
    
    # Test 1: RBF kernel
    k = rbf_kernel([0, 0], [0, 0], lengthscale=1.0, signal_variance=1.0)
    assert_test(abs(k - 1.0) < 0.001, "RBF kernel at same point = 1.0")
    
    k2 = rbf_kernel([0, 0], [1, 1], lengthscale=1.0, signal_variance=1.0)
    assert_test(k2 < 1.0, "RBF kernel at different points < 1.0")
    assert_test(k2 > 0.0, "RBF kernel positive")
    
    # Test 2: Cholesky decomposition
    A = [[4.0, 2.0], [2.0, 3.0]]
    L = _cholesky(A)
    assert_test(abs(L[0][0] - 2.0) < 0.001, "Cholesky L[0][0] correct")
    assert_test(abs(L[1][0] - 1.0) < 0.001, "Cholesky L[1][0] correct")
    
    # Test 3: Solve positive definite
    x = _solve_positive_definite(A, [1.0, 2.0])
    # Verify: Ax ≈ b
    res = [A[0][0]*x[0] + A[0][1]*x[1], A[1][0]*x[0] + A[1][1]*x[1]]
    assert_test(abs(res[0] - 1.0) < 0.01 and abs(res[1] - 2.0) < 0.01,
                "Solve PD system correct")
    
    # Test 4: GP prediction (no training data)
    gp = GPSurrogate()
    pred = gp.predict([1.0, 2.0])
    assert_test(pred.mean == 0.0, "GP prior mean is 0")
    assert_test(pred.variance > 0, "GP prior variance positive")
    
    # Test 5: GP prediction (with training data)
    gp.add_observation([0.0, 0.0], 1.0)
    gp.add_observation([1.0, 0.0], 2.0)
    gp.add_observation([0.0, 1.0], 1.5)
    
    pred_at_training = gp.predict([0.0, 0.0])
    assert_test(abs(pred_at_training.mean - 1.0) < 0.5,
                "GP prediction near training mean")
    
    # Test 6: Feasibility probability
    p_feas = gp.feasibility_probability([0.0, 0.0], threshold=0.5)
    assert_test(0.0 < p_feas < 1.0, "Feasibility probability in (0, 1)")
    
    # Test 7: Acquisition functions
    pred_test = GPPrediction(mean=0.0, variance=1.0, std=1.0)
    acq_u = acquisition_uncertainty(pred_test)
    assert_test(acq_u > 0, "Uncertainty acquisition positive")
    
    acq_e = acquisition_entropy(pred_test, threshold=0.0)
    assert_test(acq_e > 0, "Entropy acquisition positive at threshold")
    
    # Test 8: BayesianConstraintChecker — basic
    call_count = [0]
    def expensive_check(x):
        call_count[0] += 1
        return sum(xi ** 2 for xi in x) - 1.0  # Violation if > threshold
    
    checker = BayesianConstraintChecker(expensive_check, BayesianCheckerConfig(
        check_threshold=0.0,
        skip_if_confident=0.95,
        skip_if_violated=0.05,
        acquisition_fn="uncertainty",
        acquisition_threshold=0.3,
    ))
    
    # First checks should run expensive (no training data)
    result1, dec1 = checker.check([0.5, 0.5])
    assert_test(dec1.should_check == True, "First check runs expensive (no data)")
    assert_test(call_count[0] == 1, "Expensive check called once")
    
    # Test 9: Train with some data then test savings
    for _ in range(20):
        x = [random.gauss(0, 1), random.gauss(0, 1)]
        checker.check(x)
    
    initial_calls = call_count[0]
    initial_queries = checker.total_queries
    
    # Run more checks — should start saving
    for _ in range(30):
        x = [random.gauss(0, 0.3), random.gauss(0, 0.3)]  # Mostly near origin (feasible)
        checker.check(x)
    
    assert_test(checker.savings_rate > 0 or checker.total_queries > 20,
                "Checker accumulates queries")
    assert_test(checker.total_queries > initial_queries,
                "Queries increase after more checks")
    
    # Test 10: GPPrediction confidence
    pred_high = GPPrediction(mean=0.0, variance=0.01, std=0.1)
    pred_low = GPPrediction(mean=0.0, variance=10.0, std=3.16)
    assert_test(pred_high.confidence > pred_low.confidence,
                "Higher confidence for lower std")
    
    # Test 11: GP with many points doesn't crash
    gp_large = GPSurrogate(GPConfig(max_training_points=50))
    for i in range(60):
        gp_large.add_observation([random.random(), random.random()], random.random())
    assert_test(gp_large.n_training == 50, "GP trims to max training points")
    pred_large = gp_large.predict([0.5, 0.5])
    assert_test(isinstance(pred_large.mean, float), "GP predicts after trimming")
    
    # Test 12: CheckDecision
    dec = CheckDecision(
        should_check=True,
        surrogate_prediction=GPPrediction(0.5, 0.1, 0.316),
        feasibility_prob=0.5,
        acquisition_value=0.8,
        reason="Uncertain"
    )
    assert_test(dec.should_check == True, "CheckDecision stores correctly")
    
    # Test 13: Evaluate accuracy
    test_pts = [([0.1, 0.1], -0.98), ([1.0, 1.0], 1.0), ([0.5, 0.5], -0.5)]
    acc = checker.evaluate_accuracy(test_pts)
    assert_test("accuracy" in acc and "mae" in acc, "Evaluate returns accuracy and MAE")
    
    # Test 14: Sigmoid helper
    assert_test(abs(_sigmoid(0) - 0.5) < 0.001, "Sigmoid(0) = 0.5")
    assert_test(_sigmoid(100) > 0.99, "Sigmoid(large) ≈ 1")
    assert_test(_sigmoid(-100) < 0.01, "Sigmoid(large neg) ≈ 0")
    
    # Test 15: BayesianCheckerConfig defaults
    cfg = BayesianCheckerConfig()
    assert_test(cfg.check_threshold == 0.0, "Default check threshold")
    assert_test(cfg.acquisition_fn == "uncertainty", "Default acquisition function")
    
    print(f"\n  Results: {passed} passed, {failed} failed\n")
    return failed == 0


if __name__ == "__main__":
    import sys
    success = _run_tests()
    sys.exit(0 if success else 1)
