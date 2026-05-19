"""
flux_boltzmann.py — Boltzmann Distribution for Sensor Constraint Violations

Models the probability of sensor values violating constraints using a
Boltzmann-like distribution. Violation probability decays exponentially
with distance from the constraint bounds.

Provides:
- Violation energy computation
- Boltzmann violation probability modeling
- Temperature inference from observed violation rates
- Full violation probability distribution
- Temperature sweep analysis

Author: Forgemaster ⚒️ (Constraint Theory Ecosystem)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# 1. Violation Energy
# ---------------------------------------------------------------------------

def violation_energy(x: float, lower: float, upper: float,
                     sigma: float = 1.0) -> float:
    """
    Compute the violation energy of a sensor value relative to bounds.

    E(x) = 0                    if L ≤ x ≤ U
    E(x) = (L - x)² / (2σ²)   if x < L
    E(x) = (x - U)² / (2σ²)   if x > U

    Parameters
    ----------
    x : float
        Sensor value.
    lower, upper : float
        Constraint bounds [L, U].
    sigma : float
        Natural standard deviation of sensor readings.

    Returns
    -------
    float
        Non-negative violation energy.
    """
    if lower <= x <= upper:
        return 0.0
    if x < lower:
        return (lower - x) ** 2 / (2.0 * sigma**2)
    return (x - upper) ** 2 / (2.0 * sigma**2)


def violation_energy_array(values: NDArray[np.floating],
                           lower: float, upper: float,
                           sigma: float = 1.0) -> NDArray[np.floating]:
    """Vectorized violation energy for an array of sensor values."""
    x = np.asarray(values, dtype=float)
    energies = np.zeros_like(x)
    below = x < lower
    above = x > upper
    energies[below] = (lower - x[below]) ** 2 / (2.0 * sigma**2)
    energies[above] = (x[above] - upper) ** 2 / (2.0 * sigma**2)
    return energies


# ---------------------------------------------------------------------------
# 2. Boltzmann Violation Probability
# ---------------------------------------------------------------------------

def boltzmann_violation_prob(distance: float, temperature: float,
                             sigma: float = 1.0) -> float:
    """
    Probability of a sensor value being at distance `d` outside bounds,
    under the Boltzmann violation model.

    P ∝ exp(-d² / (2σ²T))

    Parameters
    ----------
    distance : float
        Distance from the nearest bound (≥ 0).
    temperature : float
        Effective temperature (noise/variance parameter).
    sigma : float
        Natural standard deviation.

    Returns
    -------
    float
        Unnormalized probability (0 to 1 for distance=0).
    """
    if temperature <= 0:
        return 0.0
    return math.exp(-(distance**2) / (2.0 * sigma**2 * temperature))


def boltzmann_violation_distribution(distances: NDArray[np.floating],
                                     temperature: float,
                                     sigma: float = 1.0) -> NDArray[np.floating]:
    """
    Normalized Boltzmann violation probability distribution.

    Parameters
    ----------
    distances : array
        Distances from nearest bound (≥ 0).
    temperature : float
        Effective temperature.
    sigma : float
        Natural standard deviation.

    Returns
    -------
    array
        Normalized probabilities summing to 1.
    """
    d = np.asarray(distances, dtype=float)
    if temperature <= 0 or len(d) == 0:
        return np.zeros_like(d)
    log_probs = -(d**2) / (2.0 * sigma**2 * temperature)
    # Numerically stable softmax-like normalization
    log_probs -= np.max(log_probs)
    probs = np.exp(log_probs)
    total = np.sum(probs)
    if total > 0:
        probs /= total
    return probs


# ---------------------------------------------------------------------------
# 3. Temperature Inference
# ---------------------------------------------------------------------------

def infer_temperature(distance: float, violation_rate: float,
                      sigma: float = 1.0) -> float:
    """
    Infer effective temperature from observed violation rate at a given distance.

    From P = exp(-d²/(2σ²T)), solve for T:
        T = d² / (-2σ² · ln(P))

    Parameters
    ----------
    distance : float
        Distance from bound at which violation rate was measured.
    violation_rate : float
        Observed fraction of violations at this distance (in (0, 1]).
    sigma : float
        Natural standard deviation.

    Returns
    -------
    float
        Inferred temperature.
    """
    if violation_rate <= 0 or violation_rate > 1:
        raise ValueError(f"violation_rate must be in (0, 1], got {violation_rate}")
    if distance <= 0:
        return 0.0
    ln_p = math.log(violation_rate)
    if ln_p >= 0:
        return float("inf")
    return distance**2 / (-2.0 * sigma**2 * ln_p)


def infer_temperature_from_data(values: NDArray[np.floating],
                                lower: float, upper: float,
                                sigma: Optional[float] = None) -> dict:
    """
    Infer temperature from a dataset of sensor values and bounds.

    Uses maximum-likelihood estimation on the violation energies.

    Parameters
    ----------
    values : array
        Observed sensor values.
    lower, upper : float
        Constraint bounds.
    sigma : float or None
        If None, estimated from data.

    Returns
    -------
    dict with keys: temperature, sigma, violation_rate, mean_energy, n_violations
    """
    x = np.asarray(values, dtype=float)
    if sigma is None:
        sigma = float(np.std(x))
        if sigma <= 0:
            sigma = 1.0

    energies = violation_energy_array(x, lower, upper, sigma)
    violated = energies > 0
    n_violated = int(np.sum(violated))
    v_rate = n_violated / len(x) if len(x) > 0 else 0.0

    if n_violated > 0:
        mean_energy = float(np.mean(energies[violated]))
        # MLE temperature: T = <E> (for exponential energy distribution)
        temperature = mean_energy if mean_energy > 0 else 1.0
    else:
        mean_energy = 0.0
        temperature = float("inf")

    return {
        "temperature": temperature,
        "sigma": sigma,
        "violation_rate": v_rate,
        "mean_energy": mean_energy,
        "n_violations": n_violated,
        "n_total": len(x),
    }


# ---------------------------------------------------------------------------
# 4. Boltzmann Model — Full Sensor Distribution
# ---------------------------------------------------------------------------

@dataclass
class BoltzmannSensorModel:
    """
    Complete Boltzmann model for a sensor under constraints.

    Models the sensor value distribution as a Boltzmann-weighted combination:
    - Inside bounds: natural distribution (typically Gaussian)
    - Outside bounds: exponentially decaying violation probability
    """
    lower: float
    upper: float
    temperature: float
    sigma: float
    mean: float
    std: float

    def violation_probability_at(self, x: float) -> float:
        """Probability density of observing value x under the Boltzmann model."""
        if self.lower <= x <= self.upper:
            # Inside bounds: Gaussian density centered at mean
            return self._gaussian_density(x)
        # Outside bounds: Gaussian * Boltzmann decay
        distance = self.lower - x if x < self.lower else x - self.upper
        return self._gaussian_density(x) * math.exp(
            -(distance**2) / (2.0 * self.sigma**2 * self.temperature)
        )

    def _gaussian_density(self, x: float) -> float:
        """Standard Gaussian density."""
        z = (x - self.mean) / self.std
        return math.exp(-0.5 * z**2) / (self.std * math.sqrt(2.0 * math.pi))

    def expected_violation_rate(self) -> float:
        """
        Estimate expected violation rate via numerical integration.
        Uses a simple quadrature over a ±5σ range.
        """
        lo = self.mean - 5 * self.std
        hi = self.mean + 5 * self.std
        n_points = 1000
        xs = np.linspace(lo, hi, n_points)
        dx = (hi - lo) / n_points

        total_prob = 0.0
        violation_prob = 0.0
        for x in xs:
            p = self.violation_probability_at(x)
            total_prob += p * dx
            if x < self.lower or x > self.upper:
                violation_prob += p * dx

        return violation_prob / total_prob if total_prob > 0 else 0.0

    def cdf_violation(self, x: float) -> float:
        """Cumulative violation probability up to value x (for x < lower)."""
        if x >= self.lower:
            return 0.0
        n_points = 500
        xs = np.linspace(self.mean - 5 * self.std, x, n_points)
        dx = (x - (self.mean - 5 * self.std)) / n_points
        total = 0.0
        for xi in xs:
            if xi < self.lower:
                total += self.violation_probability_at(xi) * dx
        return total


def fit_boltzmann_model(values: NDArray[np.floating],
                        lower: float, upper: float) -> BoltzmannSensorModel:
    """
    Fit a Boltzmann sensor model to observed data.

    Parameters
    ----------
    values : array
        Observed sensor readings.
    lower, upper : float
        Constraint bounds.

    Returns
    -------
    BoltzmannSensorModel
    """
    x = np.asarray(values, dtype=float)
    mean = float(np.mean(x))
    std = float(np.std(x))
    if std <= 0:
        std = 1.0

    result = infer_temperature_from_data(values, lower, upper, sigma=std)
    temperature = result["temperature"]
    if math.isinf(temperature):
        temperature = std**2  # fallback: use variance as temperature

    return BoltzmannSensorModel(
        lower=lower,
        upper=upper,
        temperature=temperature,
        sigma=std,
        mean=mean,
        std=std,
    )


# ---------------------------------------------------------------------------
# 5. Temperature Sweep Analysis
# ---------------------------------------------------------------------------

@dataclass
class TemperatureSweepResult:
    """Results of sweeping temperature and observing system properties."""
    temperatures: NDArray[np.floating]
    violation_rates: NDArray[np.floating]
    free_energies: NDArray[np.floating]
    mean_energies: NDArray[np.floating]
    entropies: NDArray[np.floating]


def temperature_sweep(weights: NDArray[np.floating],
                      t_min: float = 0.01,
                      t_max: float = 10.0,
                      n_steps: int = 100,
                      k: float = 1.0) -> TemperatureSweepResult:
    """
    Sweep temperature and compute thermodynamic properties at each point.

    This reveals the system's behavior from "frozen" (T→0, all or nothing)
    to "hot" (T→∞, uniform violation probabilities).

    Parameters
    ----------
    weights : array
        Violation energy weights.
    t_min, t_max : float
        Temperature range.
    n_steps : int
        Number of temperature steps.
    k : float
        Boltzmann constant.

    Returns
    -------
    TemperatureSweepResult
    """
    from flux_thermo import compute_partition_function

    temps = np.linspace(t_min, t_max, n_steps)
    v_rates = np.zeros(n_steps)
    free_es = np.zeros(n_steps)
    mean_es = np.zeros(n_steps)
    entropies = np.zeros(n_steps)

    w = np.asarray(weights, dtype=float)

    for i, t in enumerate(temps):
        pf = compute_partition_function(w, temperature=t, k=k)
        v_rates[i] = float(np.mean(pf.violation_probabilities))
        free_es[i] = pf.free_energy
        mean_es[i] = pf.mean_energy
        entropies[i] = pf.entropy

    return TemperatureSweepResult(
        temperatures=temps,
        violation_rates=v_rates,
        free_energies=free_es,
        mean_energies=mean_es,
        entropies=entropies,
    )
