"""
Tests for flux_thermo.py — Constraint Thermodynamics
"""

import math
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from flux_thermo import (
    violation_entropy,
    normalized_entropy,
    constraint_temperature,
    detect_phase_transition,
    compute_partition_function,
    binary_entropy,
    carnot_efficiency,
    max_checking_rate,
    fdt_predict_response,
    fdt_verify,
    full_thermo_profile,
)

passed = 0
failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}")


# --- violation_entropy ---
print("\n=== violation_entropy ===")

check("entropy at M=0 is 0", violation_entropy(10, 0) == 0.0)
check("entropy at M=N is 0", violation_entropy(10, 10) == 0.0)
check("entropy at M=N/2 > 0", violation_entropy(10, 5) > 0)
check("C(10,5) = 252, log2(252) ≈ 7.98", abs(violation_entropy(10, 5) - math.log2(252)) < 0.01)
check("entropy at M=1 = log2(N)", abs(violation_entropy(100, 1) - math.log2(100)) < 0.01)
check("natural log base works", abs(violation_entropy(10, 5, base=math.e) - math.log(252)) < 0.01)

# --- normalized_entropy ---
print("\n=== normalized_entropy ===")

check("normalized at M=0 is 0", normalized_entropy(10, 0) == 0.0)
check("normalized at M=N is 0", normalized_entropy(10, 10) == 0.0)
check("normalized at M=N/2 is <= 1", normalized_entropy(10, 5) <= 1.0)
check("normalized at M=1 is small", normalized_entropy(100, 1) < 0.1)

# --- constraint_temperature ---
print("\n=== constraint_temperature ===")

check("T=inf when no violations", math.isinf(constraint_temperature(np.array([]), 0, 10)))
check("T=inf when all violations", math.isinf(constraint_temperature(np.array([1.0]), 10, 10)))
energies = np.array([1.0, 2.0, 3.0])
T = constraint_temperature(energies, 3, 10)
check("finite T for partial violations", not math.isinf(T) and T > 0)

# --- detect_phase_transition ---
print("\n=== detect_phase_transition ===")

# Simulate a phase transition: low violation rate then sharp jump
rates_smooth = [0.01] * 100  # constant rate, no transition
result = detect_phase_transition(rates_smooth, threshold=3.0)
check("no spike detected in constant data", not result.is_transition_detected)

rates_sharp = [0.01] * 40 + [0.5] * 10 + [0.99] * 40  # sharp transition
result = detect_phase_transition(rates_sharp)
check("spike detected in sharp transition", result.is_transition_detected)
check("critical index near transition", 35 <= result.critical_index <= 50)

result_empty = detect_phase_transition([0.5])
check("handles short input", not result_empty.is_transition_detected)

# --- compute_partition_function ---
print("\n=== compute_partition_function ===")

# Single constraint with weight 1 at T=1
pf = compute_partition_function(np.array([1.0]), temperature=1.0)
check("Z = 1 + exp(-1) ≈ 1.368", abs(pf.Z - (1 + math.exp(-1))) < 0.01)
check("violation prob = exp(-1)/(1+exp(-1)) ≈ 0.269",
      abs(pf.violation_probabilities[0] - math.exp(-1) / (1 + math.exp(-1))) < 0.01)
check("free energy is negative", pf.free_energy < 0)

# All equal weights
pf3 = compute_partition_function(np.array([2.0, 2.0, 2.0]), temperature=1.0)
check("Z = (1 + exp(-2))³", abs(pf3.Z - (1 + math.exp(-2))**3) < 0.01)
check("all violation probs equal", np.allclose(pf3.violation_probabilities, pf3.violation_probabilities[0]))

# High temperature → P(v) → 0.5
pf_hot = compute_partition_function(np.array([1.0]), temperature=1000.0)
check("high T → P(v) ≈ 0.5", abs(pf_hot.violation_probabilities[0] - 0.5) < 0.01)

# Low temperature → P(v) → 0
pf_cold = compute_partition_function(np.array([1.0]), temperature=0.001)
check("low T → P(v) ≈ 0", pf_cold.violation_probabilities[0] < 0.01)

# Empty weights
pf_empty = compute_partition_function(np.array([]))
check("empty weights → Z=1", pf_empty.Z == 1.0)

# Specific heat is positive
check("specific heat ≥ 0", pf3.specific_heat >= 0)

# --- binary_entropy ---
print("\n=== binary_entropy ===")

check("H(0) = 0", binary_entropy(0.0) == 0.0)
check("H(1) = 0", binary_entropy(1.0) == 0.0)
check("H(0.5) = 1 bit", abs(binary_entropy(0.5) - 1.0) < 0.01)
check("H(0.1) < 1", binary_entropy(0.1) < 1.0)
check("H(0.1) > 0", binary_entropy(0.1) > 0.0)

# --- carnot_efficiency ---
print("\n=== carnot_efficiency ===")

check("η at r=0 is 1.0 (no violations = no entropy)", abs(carnot_efficiency(0.0, 8.0) - 1.0) < 0.01)
check("η at r=0.5 < 1", carnot_efficiency(0.5, 8.0) < 1.0)
check("η at r=0.5 > 0", carnot_efficiency(0.5, 8.0) > 0.0)
check("η increases as input entropy grows", carnot_efficiency(0.1, 16.0) > carnot_efficiency(0.1, 4.0))

# --- max_checking_rate ---
print("\n=== max_checking_rate ===")

check("R_max ≤ hardware_rate", max_checking_rate(0.1, 8.0, 1000) <= 1000)
check("R_max ≥ 0", max_checking_rate(0.5, 8.0, 1000) >= 0)

# --- fdt_predict_response ---
print("\n=== fdt_predict_response ===")

check("response = variance/(kT)", abs(fdt_predict_response(0.25, 1.0) - 0.25) < 0.01)
check("higher T → lower response", fdt_predict_response(0.25, 1.0) > fdt_predict_response(0.25, 2.0))

# --- fdt_verify ---
print("\n=== fdt_verify ===")

history = np.random.RandomState(42).choice([0, 1], size=1000, p=[0.9, 0.1])
result = fdt_verify(history, perturbation=1.0, observed_response=0.1, temperature=1.0)
check("FDT result has expected keys", all(k in result for k in ["predicted_response", "observed_response", "ratio", "is_consistent"]))

# --- full_thermo_profile ---
print("\n=== full_thermo_profile ===")

weights = np.array([1.0, 2.0, 0.5, 3.0, 1.5])
mask = np.array([0, 1, 0, 1, 0])
profile = full_thermo_profile(weights, mask)
check("n_constraints = 5", profile.n_constraints == 5)
check("n_violated = 2", profile.n_violated == 2)
check("entropy > 0", profile.entropy > 0)
check("Z > 0", profile.partition_Z > 0)
check("carnot > 0", profile.carnot_efficiency > 0)

# --- Summary ---
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
if failed > 0:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("ALL TESTS PASSED ✓")
