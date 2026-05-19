"""
flux_thermo.py — Thermodynamic Analysis of Constraint Systems

Provides:
- Constraint entropy (microstate/macrostate analysis)
- Phase transition detection
- Constraint partition function Z and derived quantities
- Carnot efficiency limit for constraint checking
- Fluctuation-dissipation verification

Author: Forgemaster ⚒️ (Constraint Theory Ecosystem)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# 1. Constraint Entropy
# ---------------------------------------------------------------------------

def violation_entropy(n_constraints: int, n_violated: int, base: float = 2.0) -> float:
    """
    Compute the constraint entropy S = log_base(Ω(M)) where Ω(M) = C(N, M).

    Parameters
    ----------
    n_constraints : int
        Total number of constraints N.
    n_violated : int
        Number of violated constraints M.
    base : float
        Logarithm base (2 for bits, e for nats).

    Returns
    -------
    float
        Constraint entropy S(M).
    """
    if n_violated < 0 or n_violated > n_constraints:
        raise ValueError(f"n_violated ({n_violated}) must be in [0, {n_constraints}]")
    if n_violated == 0 or n_violated == n_constraints:
        return 0.0
    # log(C(N,M)) using log-factorials to avoid overflow
    log_omega = (
        math.lgamma(n_constraints + 1)
        - math.lgamma(n_violated + 1)
        - math.lgamma(n_constraints - n_violated + 1)
    )
    if base == math.e:
        return log_omega
    return log_omega / math.log(base)


def normalized_entropy(n_constraints: int, n_violated: int) -> float:
    """
    Normalized constraint entropy in [0, 1].
    Maximum entropy at M = N/2, minimum at M = 0 or M = N.
    """
    if n_constraints == 0:
        return 0.0
    return violation_entropy(n_constraints, n_violated, base=2.0) / n_constraints


def constraint_temperature(violation_energies: NDArray[np.floating],
                           n_violated: int,
                           n_constraints: int) -> float:
    """
    Constraint temperature T = dE/dS.

    Approximated as T = <E> / S where <E> is mean violation energy
    and S is the constraint entropy.

    Parameters
    ----------
    violation_energies : array
        Energy values for violated constraints.
    n_violated : int
        Number of violated constraints.
    n_constraints : int
        Total number of constraints.

    Returns
    -------
    float
        Effective temperature. Returns float('inf') if S = 0.
    """
    if n_violated == 0 or n_violated == n_constraints:
        return float("inf")
    mean_energy = float(np.mean(violation_energies)) if len(violation_energies) > 0 else 0.0
    s = violation_entropy(n_constraints, n_violated, base=math.e)
    if s == 0:
        return float("inf")
    return mean_energy / s


# ---------------------------------------------------------------------------
# 2. Phase Transition Detection
# ---------------------------------------------------------------------------

@dataclass
class PhaseTransitionResult:
    """Result of phase transition detection."""
    critical_index: int
    critical_violation_rate: float
    is_transition_detected: bool
    violation_rates: NDArray[np.floating]
    second_derivative: NDArray[np.floating]


def detect_phase_transition(violation_rates: Sequence[float],
                            threshold: float = 2.0) -> PhaseTransitionResult:
    """
    Detect a phase transition in a sequence of violation rates
    as constraint density or bound tightness increases.

    Uses the second derivative (curvature) spike as an indicator.

    Parameters
    ----------
    violation_rates : sequence of float
        Violation rates as constraints tighten or density increases.
    threshold : float
        Number of standard deviations above mean for second derivative to count as transition.

    Returns
    -------
    PhaseTransitionResult
    """
    rates = np.array(violation_rates, dtype=float)
    if len(rates) < 3:
        return PhaseTransitionResult(
            critical_index=0,
            critical_violation_rate=rates[0] if len(rates) > 0 else 0.0,
            is_transition_detected=False,
            violation_rates=rates,
            second_derivative=np.array([]),
        )

    # Second derivative via finite differences
    first_deriv = np.diff(rates)
    second_deriv = np.diff(first_deriv)

    # Detect spike in |second derivative|
    abs_second = np.abs(second_deriv)
    mean_sd = float(np.mean(abs_second))
    std_sd = float(np.std(abs_second)) if len(abs_second) > 1 else 1.0

    spike_indices = np.where(abs_second > mean_sd + threshold * std_sd)[0]
    is_detected = len(spike_indices) > 0

    # Critical point is at the maximum spike
    if is_detected:
        max_spike_idx = int(spike_indices[np.argmax(abs_second[spike_indices])])
        critical_idx = max_spike_idx + 1  # offset for diff
    else:
        critical_idx = int(np.argmax(abs_second)) + 1

    return PhaseTransitionResult(
        critical_index=critical_idx,
        critical_violation_rate=float(rates[critical_idx]) if critical_idx < len(rates) else float(rates[-1]),
        is_transition_detected=is_detected,
        violation_rates=rates,
        second_derivative=second_deriv,
    )


# ---------------------------------------------------------------------------
# 3. Constraint Partition Function
# ---------------------------------------------------------------------------

@dataclass
class PartitionFunctionResult:
    """Thermodynamic quantities derived from the constraint partition function."""
    Z: float
    free_energy: float
    mean_energy: float
    entropy: float
    specific_heat: float
    violation_probabilities: NDArray[np.floating]


def compute_partition_function(weights: NDArray[np.floating],
                               temperature: float = 1.0,
                               k: float = 1.0) -> PartitionFunctionResult:
    """
    Compute the constraint partition function and derived thermodynamic quantities.

    For binary constraints with weights wᵢ:
        Z = Πᵢ (1 + exp(-wᵢ / kT))
        F = -kT · ln(Z)
        <E> = Σᵢ wᵢ · exp(-wᵢ/kT) / (1 + exp(-wᵢ/kT))
        S = (<E> - F) / T
        P(vᵢ) = exp(-wᵢ/kT) / (1 + exp(-wᵢ/kT))

    Parameters
    ----------
    weights : array
        Violation energy weights wᵢ for each constraint.
    temperature : float
        Effective temperature T.
    k : float
        Analogous to Boltzmann constant.

    Returns
    -------
    PartitionFunctionResult
    """
    w = np.asarray(weights, dtype=float)
    if temperature <= 0:
        raise ValueError("Temperature must be positive")
    if len(w) == 0:
        return PartitionFunctionResult(
            Z=1.0, free_energy=0.0, mean_energy=0.0,
            entropy=0.0, specific_heat=0.0,
            violation_probabilities=np.array([]),
        )

    kT = k * temperature
    boltzmann_factors = np.exp(-w / kT)

    # Z = Π (1 + exp(-w/kT))
    Z = float(np.prod(1 + boltzmann_factors))

    # Free energy F = -kT ln(Z)
    F = -kT * math.log(Z) if Z > 0 else float("-inf")

    # Violation probabilities
    P_v = boltzmann_factors / (1 + boltzmann_factors)

    # Mean energy <E> = Σ wᵢ · P(vᵢ)
    mean_E = float(np.sum(w * P_v))

    # Entropy S = (<E> - F) / T
    S = (mean_E - F) / temperature if temperature > 0 else 0.0

    # Specific heat: C = Σ wᵢ² · P(vᵢ) · (1 - P(vᵢ)) / (kT²)
    # For factorized binary system, C = Σ wᵢ² · pᵢ(1-pᵢ) / (kT)²
    C = float(np.sum(w**2 * P_v * (1 - P_v))) / (kT**2)

    return PartitionFunctionResult(
        Z=Z,
        free_energy=F,
        mean_energy=mean_E,
        entropy=S,
        specific_heat=C,
        violation_probabilities=P_v,
    )


# ---------------------------------------------------------------------------
# 4. Carnot Efficiency Limit
# ---------------------------------------------------------------------------

def binary_entropy(p: float, base: float = 2.0) -> float:
    """Shannon entropy of a Bernoulli(p) distribution."""
    if p <= 0 or p >= 1:
        return 0.0
    h = -p * math.log(p) - (1 - p) * math.log(1 - p)
    return h / math.log(base) if base != math.e else h


def carnot_efficiency(violation_rate: float,
                      input_entropy_bits: float) -> float:
    """
    Theoretical maximum checking efficiency (Carnot limit).

    η_max = 1 - H(violations) / H(input)

    Parameters
    ----------
    violation_rate : float
        Fraction of constraints violated (in [0, 1]).
    input_entropy_bits : float
        Shannon entropy of the raw input stream in bits.

    Returns
    -------
    float
        Maximum checking efficiency in [0, 1].
    """
    if input_entropy_bits <= 0:
        return 0.0
    h_violations = binary_entropy(violation_rate, base=2.0)
    return max(0.0, 1.0 - h_violations / input_entropy_bits)


def max_checking_rate(violation_rate: float,
                      input_entropy_bits: float,
                      hardware_rate: float) -> float:
    """
    Maximum theoretical checking rate.

    R_max = η_carnot × R_hardware

    Parameters
    ----------
    violation_rate : float
        Fraction of constraints violated.
    input_entropy_bits : float
        Shannon entropy of input stream in bits.
    hardware_rate : float
        Raw hardware throughput (checks/second).

    Returns
    -------
    float
        Maximum sustainable checking rate.
    """
    eta = carnot_efficiency(violation_rate, input_entropy_bits)
    return eta * hardware_rate


# ---------------------------------------------------------------------------
# 5. Fluctuation-Dissipation Verification
# ---------------------------------------------------------------------------

def fdt_predict_response(violation_variance: float,
                         temperature: float = 1.0,
                         k: float = 1.0) -> float:
    """
    Predict the response of violation rate to a unit perturbation of a constraint bound,
    using the fluctuation-dissipation theorem.

    Response = variance / (kT)

    Parameters
    ----------
    violation_variance : float
        Observed variance of the violation indicator (εᵢ).
    temperature : float
        Effective temperature.
    k : float
        Boltzmann-like constant.

    Returns
    -------
    float
        Predicted response (sensitivity) to perturbation.
    """
    kT = k * temperature
    if kT <= 0:
        return float("inf")
    return violation_variance / kT


def fdt_verify(violation_history: Sequence[float],
               perturbation: float,
               observed_response: float,
               temperature: float = 1.0,
               k: float = 1.0) -> dict:
    """
    Verify the fluctuation-dissipation theorem against observed data.

    Parameters
    ----------
    violation_history : sequence of float
        Time series of violation indicators (0/1 or continuous).
    perturbation : float
        Size of the bound perturbation applied.
    observed_response : float
        Observed change in violation rate after perturbation.
    temperature : float
        Effective temperature.
    k : float
        Boltzmann-like constant.

    Returns
    -------
    dict with keys: predicted_response, observed_response, ratio, is_consistent
    """
    var = float(np.var(violation_history))
    predicted = fdt_predict_response(var, temperature, k) * perturbation
    ratio = observed_response / predicted if predicted != 0 else float("inf")
    return {
        "predicted_response": predicted,
        "observed_response": observed_response,
        "ratio": ratio,
        "is_consistent": 0.5 < ratio < 2.0,  # within factor of 2
        "variance": var,
    }


# ---------------------------------------------------------------------------
# Convenience: full thermodynamic analysis
# ---------------------------------------------------------------------------

@dataclass
class ThermoProfile:
    """Complete thermodynamic profile of a constraint system."""
    n_constraints: int
    n_violated: int
    weights: NDArray[np.floating]
    temperature: float
    entropy: float
    normalized_entropy: float
    partition_Z: float
    free_energy: float
    mean_energy: float
    specific_heat: float
    violation_probabilities: NDArray[np.floating]
    carnot_efficiency: float
    input_entropy_bits: float


def full_thermo_profile(weights: NDArray[np.floating],
                        error_mask: NDArray[np.integer],
                        input_entropy_bits: float = 8.0,
                        temperature: float = 1.0,
                        k: float = 1.0) -> ThermoProfile:
    """
    Compute a complete thermodynamic profile for a constraint system.

    Parameters
    ----------
    weights : array
        Violation energy weights for each constraint.
    error_mask : array of int
        Binary error mask (1 = violated, 0 = satisfied).
    input_entropy_bits : float
        Shannon entropy of input stream in bits.
    temperature : float
        Effective temperature.
    k : float
        Boltzmann-like constant.

    Returns
    -------
    ThermoProfile
    """
    w = np.asarray(weights, dtype=float)
    mask = np.asarray(error_mask, dtype=int)
    n = len(w)
    n_violated = int(np.sum(mask))

    violated_energies = w[mask == 1]
    temp = constraint_temperature(violated_energies, n_violated, n) if n_violated > 0 else temperature

    s = violation_entropy(n, n_violated, base=2.0)
    s_norm = normalized_entropy(n, n_violated)

    pf = compute_partition_function(w, temperature=temp, k=k)
    v_rate = n_violated / n if n > 0 else 0.0
    carnot = carnot_efficiency(v_rate, input_entropy_bits)

    return ThermoProfile(
        n_constraints=n,
        n_violated=n_violated,
        weights=w,
        temperature=temp,
        entropy=s,
        normalized_entropy=s_norm,
        partition_Z=pf.Z,
        free_energy=pf.free_energy,
        mean_energy=pf.mean_energy,
        specific_heat=pf.specific_heat,
        violation_probabilities=pf.violation_probabilities,
        carnot_efficiency=carnot,
        input_entropy_bits=input_entropy_bits,
    )
