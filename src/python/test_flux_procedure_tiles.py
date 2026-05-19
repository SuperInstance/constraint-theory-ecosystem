"""
Tests for flux_procedure_tiles — proving tiles ARE intelligence transfer.
"""

import math
import json
import pytest

from flux_procedure_tiles import (
    ConstraintProcedureTile,
    ExecutionResult,
    build_preset_procedure,
    execute_procedure,
    refine_procedure,
    demonstrate_capability_ladder,
)


# ── Tile construction tests ─────────────────────────────────

class TestBuildPresetProcedure:
    def test_automotive_can(self):
        tile = build_preset_procedure("automotive_can")
        assert tile.domain == "automotive_can"
        assert len(tile.constraints) == 8
        assert tile.version == 1
        assert len(tile.steps) == 5

    def test_aviation_adsb(self):
        tile = build_preset_procedure("aviation_adsb")
        assert len(tile.constraints) == 8

    def test_medical_fhir(self):
        tile = build_preset_procedure("medical_fhir")
        assert len(tile.constraints) == 8

    def test_energy_scada(self):
        tile = build_preset_procedure("energy_scada")
        assert len(tile.constraints) == 8

    def test_iot_mqtt(self):
        tile = build_preset_procedure("iot_mqtt")
        assert len(tile.constraints) == 8

    def test_financial_fix(self):
        tile = build_preset_procedure("financial_fix")
        assert len(tile.constraints) == 8

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown preset"):
            build_preset_procedure("nonexistent")

    def test_tile_has_hash(self):
        tile = build_preset_procedure("automotive_can")
        assert len(tile.tile_hash) == 16
        assert all(c in "0123456789abcdef" for c in tile.tile_hash)

    def test_hash_is_deterministic(self):
        t1 = build_preset_procedure("automotive_can")
        t2 = build_preset_procedure("automotive_can")
        assert t1.tile_hash == t2.tile_hash

    def test_tile_serialization(self):
        tile = build_preset_procedure("automotive_can")
        d = tile.to_dict()
        assert d["name"] == "flux-automotive_can-procedure"
        assert d["version"] == 1
        assert len(d["steps"]) == 5
        assert len(d["constraints"]) == 8
        # Round-trip through JSON
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["version"] == 1

    def test_compact_form_readable(self):
        tile = build_preset_procedure("automotive_can")
        compact = tile.to_compact()
        assert "Procedure Tile" in compact
        assert "Pre-conditions" in compact
        assert "Steps" in compact
        assert "Post-conditions" in compact
        assert "Contingencies" in compact
        assert "Constraints" in compact

    def test_all_presets_build(self):
        """Every preset in FLUX should build a valid tile."""
        from flux_constraint_exact import PRESETS
        for name in PRESETS:
            tile = build_preset_procedure(name)
            assert tile.domain == name
            assert len(tile.steps) == 5
            assert len(tile.pre_conditions) > 0
            assert len(tile.post_conditions) > 0


# ── Execution tests ─────────────────────────────────────────

class TestExecuteProcedure:
    @pytest.fixture
    def auto_tile(self):
        return build_preset_procedure("automotive_can")

    def test_all_pass(self, auto_tile):
        values = [3000, 80, 90, 50, 50, 0, 12.6, 75]
        result = execute_procedure(auto_tile, values)
        assert result.severity == "PASS"
        assert result.error_mask == 0
        assert result.violation_count == 0
        assert len(result.proof_hash) == 16
        assert result.tile_hash == auto_tile.tile_hash

    def test_boundary_values_pass(self, auto_tile):
        """Values exactly at lo and hi are in-bounds (inclusive)."""
        values = [0, 300, -40, 100, 200, 720, 9, 0]  # All at boundaries
        result = execute_procedure(auto_tile, values)
        assert result.severity == "PASS"
        assert result.error_mask == 0

    def test_single_violation(self, auto_tile):
        values = [9000, 80, 90, 50, 50, 0, 12.6, 75]  # RPM over
        result = execute_procedure(auto_tile, values)
        assert result.violation_count >= 1
        assert result.error_mask & 1  # Bit 0 set

    def test_multiple_violations(self, auto_tile):
        values = [9000, 400, 200, 150, 300, 800, 20, 150]
        result = execute_procedure(auto_tile, values)
        assert result.violation_count >= 4
        assert result.severity in ("WARNING", "CRITICAL")

    def test_nan_input(self, auto_tile):
        values = [3000, float('nan'), 90, 50, 50, 0, 12.6, 75]
        result = execute_procedure(auto_tile, values)
        assert result.severity == "CRITICAL"
        assert result.violation_count >= 1

    def test_inf_input(self, auto_tile):
        values = [float('inf'), 80, 90, 50, 50, 0, 12.6, 75]
        result = execute_procedure(auto_tile, values)
        assert result.violation_count >= 1

    def test_negative_inf(self, auto_tile):
        values = [float('-inf'), 80, 90, 50, 50, 0, 12.6, 75]
        result = execute_procedure(auto_tile, values)
        assert result.violation_count >= 1

    def test_wrong_count(self, auto_tile):
        result = execute_procedure(auto_tile, [1, 2, 3])
        assert result.severity == "CRITICAL"
        assert any("Count mismatch" in w for w in result.warnings)

    def test_empty_input(self, auto_tile):
        result = execute_procedure(auto_tile, [])
        assert result.severity == "CRITICAL"

    def test_non_numeric_input(self, auto_tile):
        values = [3000, "hello", 90, 50, 50, 0, 12.6, 75]
        result = execute_procedure(auto_tile, values)
        assert result.severity == "CRITICAL"
        assert result.violation_count >= 1

    def test_proof_hash_deterministic(self, auto_tile):
        values = [3000, 80, 90, 50, 50, 0, 12.6, 75]
        r1 = execute_procedure(auto_tile, values)
        r2 = execute_procedure(auto_tile, values)
        assert r1.proof_hash == r2.proof_hash

    def test_proof_hash_differs_for_different_inputs(self, auto_tile):
        r1 = execute_procedure(auto_tile, [3000, 80, 90, 50, 50, 0, 12.6, 75])
        r2 = execute_procedure(auto_tile, [9000, 80, 90, 50, 50, 0, 12.6, 75])
        assert r1.proof_hash != r2.proof_hash

    def test_execution_time_recorded(self, auto_tile):
        result = execute_procedure(auto_tile, [3000, 80, 90, 50, 50, 0, 12.6, 75])
        assert result.execution_time_ms >= 0

    def test_details_populated(self, auto_tile):
        result = execute_procedure(auto_tile, [3000, 80, 90, 50, 50, 0, 12.6, 75])
        assert len(result.details) == 8
        for d in result.details:
            assert "name" in d
            assert "passed" in d

    def test_all_nan(self, auto_tile):
        values = [float('nan')] * 8
        result = execute_procedure(auto_tile, values)
        assert result.severity == "CRITICAL"
        assert result.error_mask == 0xFF  # All 8 bits set

    def test_result_serialization(self, auto_tile):
        result = execute_procedure(auto_tile, [3000, 80, 90, 50, 50, 0, 12.6, 75])
        d = result.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["severity"] == "PASS"


# ── Refinement tests ────────────────────────────────────────

class TestRefineProcedure:
    @pytest.fixture
    def auto_tile(self):
        return build_preset_procedure("automotive_can")

    def test_version_increments(self, auto_tile):
        outcomes = [execute_procedure(auto_tile, [3000, 80, 90, 50, 50, 0, 12.6, 75]).to_dict()]
        refined = refine_procedure(auto_tile, outcomes)
        assert refined.version == 2
        assert auto_tile.version == 1  # Original unchanged

    def test_parent_hash_set(self, auto_tile):
        outcomes = [execute_procedure(auto_tile, [3000, 80, 90, 50, 50, 0, 12.6, 75]).to_dict()]
        refined = refine_procedure(auto_tile, outcomes)
        assert refined.parent_tile_hash == auto_tile.tile_hash

    def test_nan_contingency_added(self, auto_tile):
        outcomes = [
            execute_procedure(auto_tile, [float('nan')] * 8).to_dict(),
            execute_procedure(auto_tile, [float('nan')] * 8).to_dict(),
        ]
        refined = refine_procedure(auto_tile, outcomes)
        conditions = [c.condition for c in refined.contingencies]
        assert any("Batch NaN" in c for c in conditions)

    def test_inf_contingency_added(self, auto_tile):
        outcomes = [
            execute_procedure(auto_tile, [float('inf')] * 8).to_dict(),
        ]
        refined = refine_procedure(auto_tile, outcomes)
        conditions = [c.condition for c in refined.contingencies]
        assert any("Batch Inf" in c for c in conditions)

    def test_count_mismatch_contingency(self, auto_tile):
        outcomes = [
            execute_procedure(auto_tile, [1, 2]).to_dict(),
            execute_procedure(auto_tile, [1, 2]).to_dict(),
        ]
        refined = refine_procedure(auto_tile, outcomes)
        conditions = [c.condition for c in refined.contingencies]
        assert any("count mismatch" in c.lower() for c in conditions)

    def test_refinement_history(self, auto_tile):
        outcomes = [execute_procedure(auto_tile, [3000, 80, 90, 50, 50, 0, 12.6, 75]).to_dict()]
        refined = refine_procedure(auto_tile, outcomes)
        assert len(refined.refinement_history) == 1
        entry = refined.refinement_history[0]
        assert entry["from_version"] == 1
        assert entry["to_version"] == 2

    def test_multi_round_refinement(self, auto_tile):
        # Round 1
        o1 = [execute_procedure(auto_tile, [float('nan')] * 8).to_dict()]
        v2 = refine_procedure(auto_tile, o1)
        assert v2.version == 2

        # Round 2
        o2 = [execute_procedure(auto_tile, [1, 2]).to_dict()]
        v3 = refine_procedure(v2, o2)
        assert v3.version == 3
        assert len(v3.refinement_history) == 2

    def test_original_tile_unchanged(self, auto_tile):
        original_hash = auto_tile.tile_hash
        original_version = auto_tile.version
        original_contingencies = len(auto_tile.contingencies)

        outcomes = [execute_procedure(auto_tile, [float('nan')] * 8).to_dict()]
        refine_procedure(auto_tile, outcomes)

        assert auto_tile.tile_hash == original_hash
        assert auto_tile.version == original_version
        assert len(auto_tile.contingencies) == original_contingencies


# ── Cross-domain tests ──────────────────────────────────────

class TestCrossDomain:
    @pytest.mark.parametrize("preset", [
        "automotive_can", "aviation_adsb", "medical_fhir",
        "energy_scada", "iot_mqtt", "financial_fix",
    ])
    def test_execute_all_domains(self, preset):
        tile = build_preset_procedure(preset)
        # Mid-range values for each domain
        values = [(c["lo"] + c["hi"]) / 2 for c in tile.constraints]
        result = execute_procedure(tile, values)
        assert result.severity == "PASS"
        assert result.violation_count == 0

    @pytest.mark.parametrize("preset", [
        "automotive_can", "aviation_adsb", "medical_fhir",
        "energy_scada", "iot_mqtt", "financial_fix",
    ])
    def test_nan_detected_all_domains(self, preset):
        tile = build_preset_procedure(preset)
        values = [float('nan')] * len(tile.constraints)
        result = execute_procedure(tile, values)
        assert result.severity == "CRITICAL"


# ── Demonstration runs without error ────────────────────────

class TestDemonstration:
    def test_demo_runs(self):
        output = demonstrate_capability_ladder()
        assert "Capability Ladder" in output
        assert "PASS" in output
        assert "CRITICAL" in output
        assert "Intelligence accumulation" in output
        assert len(output) > 500  # Non-trivial output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
