"""
test_sediment.py — Tests for flux_sediment module

Tests SedimentLayer, SedimentStack, SedimentAccumulator, and convergence experiment.
Forgemaster ⚒️ — 2026-05-19
"""

import sys
import os
import math
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from flux_sediment import (
    ConstraintCorrection,
    SedimentLayer,
    SedimentStack,
    SedimentResult,
    SedimentAccumulator,
    SedimentExperiment,
    AccumulationMetrics,
)


# =============================================================================
# SedimentLayer Tests
# =============================================================================

def test_correction_apply_to_bounds_only():
    """Correction with new bounds overrides lo/hi."""
    c = ConstraintCorrection(
        constraint_name="temp",
        new_lo=-50.0,
        new_hi=200.0,
        reason="wider operating range",
    )
    lo, hi, passed = c.apply_to(-40.0, 150.0, False)
    assert lo == -50.0
    assert hi == 200.0
    assert passed is False  # No override


def test_correction_apply_to_override_pass():
    """override_pass forces the result regardless of bounds."""
    c = ConstraintCorrection(
        constraint_name="temp",
        override_pass=True,
        reason="known sensor glitch",
    )
    lo, hi, passed = c.apply_to(-40.0, 150.0, False)
    assert passed is True
    assert lo == -40.0
    assert hi == 150.0


def test_correction_apply_to_override_fail():
    """override_pass=False forces failure."""
    c = ConstraintCorrection(
        constraint_name="temp",
        override_pass=False,
        reason="dangerous even in range",
    )
    _, _, passed = c.apply_to(-40.0, 150.0, True)
    assert passed is False


def test_correction_apply_to_no_change():
    """Correction with no modifications is identity."""
    c = ConstraintCorrection(constraint_name="temp")
    lo, hi, passed = c.apply_to(-40.0, 150.0, True)
    assert lo == -40.0
    assert hi == 150.0
    assert passed is True


def test_layer_creation():
    """SedimentLayer stores metadata correctly."""
    corrections = [
        ConstraintCorrection("temp", new_lo=-50.0, reason="cold start"),
    ]
    layer = SedimentLayer(
        layer_id=0,
        input_context={"sensor": "temp_sensor_1", "value": -45.0},
        corrections=corrections,
        provenance="test",
        model="unit_test",
    )
    assert layer.layer_id == 0
    assert len(layer.corrections) == 1
    assert not layer.superseded
    assert layer.catch_count == 0


def test_layer_content_hash_deterministic():
    """Same layer content produces same hash."""
    corrections = [ConstraintCorrection("temp", new_lo=-50.0)]
    l1 = SedimentLayer(layer_id=0, input_context={}, corrections=corrections)
    l2 = SedimentLayer(layer_id=0, input_context={}, corrections=corrections)
    assert l1.content_hash() == l2.content_hash()


def test_layer_tile_round_trip():
    """Serialize to PLATO tile and back preserves content."""
    corrections = [
        ConstraintCorrection("temp", old_lo=-40.0, new_lo=-50.0, reason="cold start"),
    ]
    layer = SedimentLayer(
        layer_id=42,
        input_context={"crisis": "arctic deployment"},
        corrections=corrections,
        provenance="test_suite",
        model="flux_sediment",
    )
    tile = layer.to_tile()
    assert tile["tile_type"] == "sediment_layer"
    assert tile["layer_id"] == 42

    restored = SedimentLayer.from_tile(tile)
    assert restored.layer_id == 42
    assert len(restored.corrections) == 1
    assert restored.corrections[0].constraint_name == "temp"
    assert restored.corrections[0].new_lo == -50.0
    assert restored.provenance == "test_suite"


# =============================================================================
# SedimentStack Tests
# =============================================================================

def test_stack_empty():
    """Empty stack has depth 0."""
    stack = SedimentStack()
    assert stack.depth == 0
    assert stack.active_layers == []


def test_stack_add_layer():
    """Adding layers increases depth."""
    stack = SedimentStack()
    l0 = stack.add_layer(
        input_context={"test": 1},
        corrections=[ConstraintCorrection("temp", override_pass=True)],
    )
    assert stack.depth == 1
    assert l0.layer_id == 0

    l1 = stack.add_layer(
        input_context={"test": 2},
        corrections=[ConstraintCorrection("pressure", new_hi=300.0)],
    )
    assert stack.depth == 2
    assert l1.layer_id == 1


def test_stack_supersede():
    """Superseding a layer marks it and excludes from active."""
    stack = SedimentStack()
    l0 = stack.add_layer({"i": 0}, [ConstraintCorrection("temp", override_pass=True)])
    l1 = stack.add_layer({"i": 1}, [ConstraintCorrection("temp", new_lo=-60.0)])

    ok = stack.supersede_layer(l0.layer_id, l1.layer_id)
    assert ok
    assert l0.superseded
    assert l0.superseded_by == 1
    assert len(stack.active_layers) == 1
    assert stack.active_layers[0].layer_id == 1


def test_stack_check_with_sediment_override_pass():
    """Sediment layer can override a violation to pass."""
    stack = SedimentStack()
    stack.add_layer(
        input_context={"sensor_glitch": True},
        corrections=[ConstraintCorrection("temp", override_pass=True, reason="known glitch")],
    )

    # Simulate: temp violated (bit 0 set)
    result = stack.check_with_sediment(
        base_error_mask=0b1,  # temp violated
        base_severity=1,
        constraint_names=["temp"],
        values={"temp": -45.0},
    )
    assert result.passed
    assert result.final_error_mask == 0
    assert 0 in result.layers_applied


def test_stack_check_with_sediment_no_change():
    """No corrections matching = result unchanged."""
    stack = SedimentStack()
    stack.add_layer(
        input_context={"test": True},
        corrections=[ConstraintCorrection("pressure", override_pass=True)],
    )

    result = stack.check_with_sediment(
        base_error_mask=0b1,  # temp violated
        base_severity=1,
        constraint_names=["temp"],
        values={"temp": -45.0},
    )
    assert not result.passed
    assert result.final_error_mask == 0b1


def test_stack_multiple_layers_applied():
    """Multiple layers can each catch different things."""
    stack = SedimentStack()
    stack.add_layer(
        {"i": 0},
        [ConstraintCorrection("temp", override_pass=True)],
    )
    stack.add_layer(
        {"i": 1},
        [ConstraintCorrection("pressure", override_pass=True)],
    )

    # Both violated: bits 0 and 1
    result = stack.check_with_sediment(
        base_error_mask=0b11,
        base_severity=2,
        constraint_names=["temp", "pressure"],
        values={"temp": -45.0, "pressure": 500.0},
    )
    assert result.passed
    assert 0 in result.layers_applied
    assert 1 in result.layers_applied


def test_stack_superseded_layer_not_applied():
    """Superseded layers don't modify results."""
    stack = SedimentStack()
    l0 = stack.add_layer(
        {"i": 0},
        [ConstraintCorrection("temp", override_pass=True)],
    )
    l1 = stack.add_layer(
        {"i": 1},
        [ConstraintCorrection("temp", override_pass=False)],  # Opposite correction
    )
    stack.supersede_layer(l0.layer_id, l1.layer_id)

    result = stack.check_with_sediment(
        base_error_mask=0b1,
        base_severity=1,
        constraint_names=["temp"],
        values={"temp": -45.0},
    )
    # l1 overrides to fail, l0 is superseded and ignored
    assert not result.passed


def test_stack_bounds_correction():
    """Sediment layer widens bounds to fix violation."""
    stack = SedimentStack()
    stack.add_layer(
        {"crisis": "arctic"},
        [ConstraintCorrection("temp", new_lo=-60.0, new_hi=150.0, reason="arctic ops")],
    )

    # Value -45 violates original [-40, 150] but passes with [-60, 150]
    result = stack.check_with_sediment(
        base_error_mask=0b1,  # violated under original bounds
        base_severity=1,
        constraint_names=["temp"],
        values={"temp": -45.0},
        constraint_defs={"temp": (-40.0, 150.0)},
    )
    assert result.passed
    assert result.final_error_mask == 0


# =============================================================================
# SedimentAccumulator Tests
# =============================================================================

def test_accumulator_empty():
    """Empty accumulator has zero density."""
    acc = SedimentAccumulator(n_constraints=3)
    assert acc.correctness_density() == 0.0
    assert acc.total_checks == 0
    assert acc.sediment_catches == 0


def test_accumulator_records_checks():
    """Recording checks updates metrics."""
    acc = SedimentAccumulator(n_constraints=2)

    # No sediment applied
    r1 = SedimentResult(
        base_error_mask=0, base_severity=0,
        final_error_mask=0, final_severity=0,
        layers_applied=[], corrections_applied=0, passed=True,
    )
    acc.record_check({"temp": 50.0}, r1)
    assert acc.total_checks == 1
    assert acc.sediment_catches == 0

    # Sediment applied
    r2 = SedimentResult(
        base_error_mask=0b1, base_severity=1,
        final_error_mask=0, final_severity=0,
        layers_applied=[0], corrections_applied=1, passed=True,
    )
    acc.record_check({"temp": -45.0}, r2)
    assert acc.total_checks == 2
    assert acc.sediment_catches == 1


def test_accumulator_density():
    """Correctness density is fraction of checks with sediment catches."""
    acc = SedimentAccumulator(n_constraints=2)

    for i in range(10):
        layers = [0] if i % 5 == 0 else []
        r = SedimentResult(
            base_error_mask=0, base_severity=0,
            final_error_mask=0, final_severity=0,
            layers_applied=layers, corrections_applied=len(layers), passed=True,
        )
        acc.record_check({"temp": float(i)}, r)

    # 2 out of 10 checks had sediment applied
    assert acc.correctness_density() == 0.2


def test_accumulator_predict_surprise():
    """Surprise prediction returns rarest failure pattern."""
    acc = SedimentAccumulator(n_constraints=2)

    # Many passes
    for _ in range(100):
        r = SedimentResult(0, 0, 0, 0, [], 0, True)
        acc.record_check({"temp": 50.0}, r)

    # Few failures with mask=0b1
    for _ in range(5):
        r = SedimentResult(0b1, 1, 0b1, 1, [], 0, False)
        acc.record_check({"temp": -50.0}, r)

    # Single rare failure with mask=0b11
    r = SedimentResult(0b11, 2, 0b11, 2, [], 0, False)
    acc.record_check({"temp": -50.0, "pressure": 500.0}, r)

    prediction = acc.predict_next_surprise()
    assert prediction is not None
    # The rarest pattern (0b11) should be predicted
    assert "11" in prediction


def test_accumulator_compute_metrics():
    """Full metrics snapshot includes all layers."""
    stack = SedimentStack()
    stack.add_layer({"i": 0}, [ConstraintCorrection("temp", override_pass=True)])
    stack.add_layer({"i": 1}, [ConstraintCorrection("pressure", new_hi=300.0)])

    acc = SedimentAccumulator(n_constraints=2)
    r = SedimentResult(0b1, 1, 0, 0, [0], 1, True)
    acc.record_check({"temp": -45.0}, r)

    metrics = acc.compute_metrics(stack)
    assert isinstance(metrics, AccumulationMetrics)
    assert metrics.total_layers == 2
    assert metrics.active_layers == 2
    assert metrics.total_catches == 1
    assert 0 in metrics.coverage_by_layer or 1 in metrics.coverage_by_layer


# =============================================================================
# Convergence Experiment Tests
# =============================================================================

def test_convergence_monotonic():
    """
    KEY EXPERIMENT: Correctness monotonically increases with sediment layers.
    """
    constraints = [{"name": "temp", "lo": -40.0, "hi": 150.0}]

    # Test inputs: some in-range, some out-of-range
    test_inputs = [
        {"temp": 50.0},    # In range
        {"temp": -45.0},   # Below lo → violates
        {"temp": 200.0},   # Above hi → violates
        {"temp": 0.0},     # In range
        {"temp": -50.0},   # Below lo → violates
    ]

    # Edge cases and their corrections
    edge_cases = [
        # Fix cold violations by widening lower bound
        (
            {"temp": -45.0},
            [ConstraintCorrection("temp", new_lo=-60.0, reason="arctic ops")],
        ),
        # Fix hot violations by widening upper bound
        (
            {"temp": 200.0},
            [ConstraintCorrection("temp", new_hi=250.0, reason="desert ops")],
        ),
    ]

    result = SedimentExperiment.run_convergence_experiment(
        constraints=constraints,
        test_inputs=test_inputs,
        edge_cases=edge_cases,
    )

    assert result["is_monotonic"], f"Expected monotonic convergence, got: {result['convergence_data']}"
    assert result["final_correctness"] >= result["base_correctness"]
    assert result["improvement"] > 0

    # Check each step
    data = result["convergence_data"]
    for i in range(1, len(data)):
        assert data[i]["correctness_rate"] >= data[i - 1]["correctness_rate"], \
            f"Non-monotonic at step {i}: {data[i-1]} -> {data[i]}"


def test_convergence_multi_constraint():
    """Convergence with multiple constraints and targeted corrections."""
    constraints = [
        {"name": "temp", "lo": -40.0, "hi": 150.0},
        {"name": "pressure", "lo": 0.0, "hi": 200.0},
    ]

    test_inputs = [
        {"temp": 50.0, "pressure": 100.0},     # Both in range
        {"temp": -45.0, "pressure": 100.0},    # Temp violates
        {"temp": 50.0, "pressure": 250.0},     # Pressure violates
        {"temp": -50.0, "pressure": 300.0},    # Both violate
        {"temp": 0.0, "pressure": 50.0},       # Both in range
    ]

    edge_cases = [
        # Fix temp violations
        (
            {"temp": -50.0, "pressure": 100.0},
            [ConstraintCorrection("temp", new_lo=-60.0, reason="arctic")],
        ),
        # Fix pressure violations
        (
            {"temp": 50.0, "pressure": 250.0},
            [ConstraintCorrection("pressure", new_hi=350.0, reason="high-pressure mode")],
        ),
    ]

    result = SedimentExperiment.run_convergence_experiment(
        constraints=constraints,
        test_inputs=test_inputs,
        edge_cases=edge_cases,
    )

    assert result["is_monotonic"]
    assert result["final_correctness"] > result["base_correctness"]
    # With both fixes, the last two inputs should now pass
    # (temp=-50 with lo=-60 passes, pressure=300 with hi=350 passes)
    assert result["final_correctness"] == 1.0


def test_convergence_no_layers():
    """Zero layers = baseline correctness."""
    constraints = [{"name": "temp", "lo": -40.0, "hi": 150.0}]
    test_inputs = [{"temp": 50.0}, {"temp": -50.0}]

    result = SedimentExperiment.run_convergence_experiment(
        constraints=constraints,
        test_inputs=test_inputs,
        edge_cases=[],
    )

    assert result["n_layers"] == 0
    assert result["base_correctness"] == result["final_correctness"]
    assert result["is_monotonic"]  # Trivially monotonic


def test_convergence_strictly_higher():
    """
    THE KEY THEOREM: N layers > N-1 layers (when edge cases exist).
    """
    constraints = [{"name": "temp", "lo": -40.0, "hi": 150.0}]

    test_inputs = [
        {"temp": 50.0},
        {"temp": -45.0},
    ]

    edge_cases = [
        (
            {"temp": -45.0},
            [ConstraintCorrection("temp", new_lo=-60.0, reason="cold fix")],
        ),
    ]

    result = SedimentExperiment.run_convergence_experiment(
        constraints=constraints,
        test_inputs=test_inputs,
        edge_cases=edge_cases,
    )

    # With the layer, -45 is no longer a violation (new_lo=-60)
    assert result["final_correctness"] > result["base_correctness"]
    data = result["convergence_data"]
    assert data[1]["correctness_rate"] > data[0]["correctness_rate"]


# =============================================================================
# Run all tests
# =============================================================================

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        name = test.__name__
        try:
            test()
            print(f"  ✓ {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed, {passed + failed} total")
    sys.exit(1 if failed else 0)
