"""
Tests for flux_boltzmann.py — Boltzmann Distribution for Sensor Constraints
"""

import math
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from flux_boltzmann import (
    violation_energy,
    violation_energy_array,
    boltzmann_violation_prob,
    boltzmann_violation_distribution,
    infer_temperature,
    infer_temperature_from_data,
    BoltzmannSensorModel,
    fit_boltzmann_model,
    temperature_sweep,
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


# --- violation_energy ---
print("\n=== violation_energy ===")

check("inside bounds → E=0", violation_energy(5.0, 0.0, 10.0) == 0.0)
check("below bound → E > 0", violation_energy(-1.0, 0.0, 10.0) > 0)
check("above bound → E > 0", violation_energy(12.0, 0.0, 10.0) > 0)
check("energy at lower bound = 0", violation_energy(0.0, 0.0, 10.0) == 0.0)
check("energy at upper bound = 0", violation_energy(10.0, 0.0, 10.0) == 0.0)
check("energy grows with distance", violation_energy(-2.0, 0.0, 10.0) > violation_energy(-1.0, 0.0, 10.0))
check("symmetric violation energy", abs(violation_energy(-1.0, 0.0, 10.0) - violation_energy(11.0, 0.0, 10.0)) < 1e-10)
check("sigma=2 reduces energy", violation_energy(-1.0, 0.0, 10.0, sigma=2.0) < violation_energy(-1.0, 0.0, 10.0, sigma=1.0))

# --- violation_energy_array ---
print("\n=== violation_energy_array ===")

values = np.array([-1.0, 3.0, 5.0, 10.0, 12.0])
energies = violation_energy_array(values, 0.0, 10.0)
check("vectorized matches scalar",
      all(abs(energies[i] - violation_energy(values[i], 0.0, 10.0)) < 1e-10 for i in range(len(values))))
check("inside values have E=0", energies[1] == 0 and energies[2] == 0 and energies[3] == 0)

# --- boltzmann_violation_prob ---
print("\n=== boltzmann_violation_prob ===")

check("distance=0 → P=1.0", abs(boltzmann_violation_prob(0.0, 1.0) - 1.0) < 1e-10)
check("P decreases with distance", boltzmann_violation_prob(1.0, 1.0) > boltzmann_violation_prob(2.0, 1.0))
check("P increases with temperature", boltzmann_violation_prob(1.0, 2.0) > boltzmann_violation_prob(1.0, 1.0))
check("T=0 → P=0", boltzmann_violation_prob(1.0, 0.0) == 0.0)

# --- boltzmann_violation_distribution ---
print("\n=== boltzmann_violation_distribution ===")

distances = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
probs = boltzmann_violation_distribution(distances, temperature=1.0)
check("probabilities sum to ~1", abs(np.sum(probs) - 1.0) < 0.01)
check("monotonically decreasing", all(probs[i] >= probs[i+1] for i in range(len(probs)-1)))
check("highest prob at d=0", probs[0] > probs[1])

probs_empty = boltzmann_violation_distribution(np.array([]), temperature=1.0)
check("empty input → empty output", len(probs_empty) == 0)

# --- infer_temperature ---
print("\n=== infer_temperature ===")

T = infer_temperature(distance=1.0, violation_rate=0.5, sigma=1.0)
check("positive temperature inferred", T > 0)
check("T = d²/(-2σ²ln(p))", abs(T - 1.0 / (-2.0 * math.log(0.5))) < 0.01)

# T = d²/(-2σ²ln(p))
# Lower rate at same distance → system is "colder" → lower T
T_low_rate = infer_temperature(distance=1.0, violation_rate=0.01, sigma=1.0)
check("lower rate at same distance → lower temperature", T_low_rate < T)

try:
    infer_temperature(1.0, 0.0)
    check("raises on p=0", False)
except ValueError:
    check("raises on p=0", True)

try:
    infer_temperature(1.0, 1.5)
    check("raises on p>1", False)
except ValueError:
    check("raises on p>1", True)

# --- infer_temperature_from_data ---
print("\n=== infer_temperature_from_data ===")

# Generate data: mostly inside [0, 10] with some violations
rng = np.random.RandomState(42)
data = rng.normal(5.0, 2.0, 1000)
result = infer_temperature_from_data(data, 0.0, 10.0)
check("result has expected keys", all(k in result for k in ["temperature", "sigma", "violation_rate", "n_violations"]))
check("sigma estimated", result["sigma"] > 0)
check("temperature is positive or inf", result["temperature"] > 0 or math.isinf(result["temperature"]))
check("violation_rate in [0,1]", 0 <= result["violation_rate"] <= 1)

# --- BoltzmannSensorModel ---
print("\n=== BoltzmannSensorModel ===")

model = BoltzmannSensorModel(
    lower=0.0, upper=10.0,
    temperature=4.0, sigma=2.0,
    mean=5.0, std=2.0,
)
p_inside = model.violation_probability_at(5.0)
p_outside = model.violation_probability_at(-1.0)
check("inside probability > outside probability", p_inside > p_outside)
check("inside probability > 0", p_inside > 0)

vr = model.expected_violation_rate()
check("expected violation rate in [0,1]", 0 <= vr <= 1)

# --- fit_boltzmann_model ---
print("\n=== fit_boltzmann_model ===")

rng = np.random.RandomState(123)
data2 = rng.normal(5.0, 1.5, 500)
fitted = fit_boltzmann_model(data2, 2.0, 8.0)
check("fitted model has reasonable mean", 3.0 < fitted.mean < 7.0)
check("fitted model has reasonable std", 0.5 < fitted.std < 3.0)
check("fitted model temperature > 0", fitted.temperature > 0)

# --- temperature_sweep ---
print("\n=== temperature_sweep ===")

from flux_thermo import compute_partition_function  # needed by temperature_sweep

weights = np.array([1.0, 2.0, 3.0])
sweep = temperature_sweep(weights, t_min=0.01, t_max=10.0, n_steps=50)
check("sweep has correct shape", len(sweep.temperatures) == 50)
check("violation rates increase with T", sweep.violation_rates[-1] > sweep.violation_rates[0])
check("free energies computed", len(sweep.free_energies) == 50)
check("entropies computed", len(sweep.entropies) == 50)
check("mean energies computed", len(sweep.mean_energies) == 50)

# --- Summary ---
print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
if failed > 0:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("ALL TESTS PASSED ✓")
