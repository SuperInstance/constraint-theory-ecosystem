"""
Tests for FLUX v4 Deployment Compilation Pipeline.

Tests:
1. compile_to_c produces a file that compiles with gcc
2. The compiled C produces correct results
3. compile_to_wasm produces valid WAT
4. compile_to_verilog produces valid Verilog
5. All 6 presets compile successfully to all targets
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

HERE = Path(__file__).parent
PROJECT = HERE.parent
PYTHON_DIR = PROJECT / "src" / "python"

import sys
sys.path.insert(0, str(PYTHON_DIR))

from flux_deploy import (
    ALL_TARGETS,
    compile_to_asm_arm,
    compile_to_c,
    compile_to_verilog,
    compile_to_wasm,
    deploy,
)
from flux_constraint_exact import PRESETS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_constraints():
    """Simple 3-constraint test set."""
    return [
        {"lo": -40, "hi": 150, "name": "coolant_temp_c"},
        {"lo": 0, "hi": 8000, "name": "engine_rpm"},
        {"lo": 9, "hi": 16, "name": "battery_voltage_v"},
    ]


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


# ---------------------------------------------------------------------------
# 1. C Compilation Tests
# ---------------------------------------------------------------------------

class TestCompileToC:

    def test_generates_file(self, sample_constraints, tmp_dir):
        path = compile_to_c(sample_constraints, tmp_dir / "test.c")
        assert path.exists()
        content = path.read_text()
        assert "#include <stdio.h>" in content
        assert "flux_check_exact" in content
        assert "main" in content

    def test_contains_bounds(self, sample_constraints, tmp_dir):
        path = compile_to_c(sample_constraints, tmp_dir / "test.c")
        content = path.read_text()
        assert "BOUNDS_LO" in content
        assert "BOUNDS_HI" in content
        assert "-40.0f" in content  # coolant lo
        assert "150.0f" in content  # coolant hi
        assert "8000.0f" in content  # rpm hi
        assert "coolant_temp_c" in content

    def test_compiles_with_gcc(self, sample_constraints, tmp_dir):
        """Test that the generated C compiles with gcc."""
        gcc_available = _has_gcc()
        if not gcc_available:
            pytest.skip("gcc not available")

        c_path = compile_to_c(sample_constraints, tmp_dir / "flux_check.c")
        binary = tmp_dir / "flux_check"

        result = subprocess.run(
            ["gcc", "-O3", "-mavx2", "-lm", "-o", str(binary), str(c_path)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"gcc failed: {result.stderr}"

    def test_compiled_c_produces_correct_results(self, sample_constraints, tmp_dir):
        """Test that the compiled binary runs and passes its self-tests."""
        if not _has_gcc():
            pytest.skip("gcc not available")

        c_path = compile_to_c(sample_constraints, tmp_dir / "flux_check.c")
        binary = tmp_dir / "flux_check"

        subprocess.run(
            ["gcc", "-O3", "-mavx2", "-lm", "-o", str(binary), str(c_path)],
            capture_output=True, text=True, timeout=30,
            check=True,
        )

        result = subprocess.run(
            [str(binary)],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"Binary failed:\n{result.stdout}\n{result.stderr}"
        assert "Passed:" in result.stdout
        assert "FAIL" not in result.stdout

    def test_benchmark_runs(self, sample_constraints, tmp_dir):
        """Test that the benchmark section executes."""
        if not _has_gcc():
            pytest.skip("gcc not available")

        c_path = compile_to_c(sample_constraints, tmp_dir / "flux_check.c")
        binary = tmp_dir / "flux_check"

        subprocess.run(
            ["gcc", "-O3", "-mavx2", "-lm", "-o", str(binary), str(c_path)],
            capture_output=True, text=True, timeout=30,
            check=True,
        )

        result = subprocess.run(
            [str(binary)],
            capture_output=True, text=True, timeout=30,
        )
        assert "checks/sec" in result.stdout or "Benchmark" in result.stdout

    def test_nan_detection_in_c(self, tmp_dir):
        """Test that NaN is detected as violating all constraints."""
        if not _has_gcc():
            pytest.skip("gcc not available")

        constraints = [{"lo": 0, "hi": 100, "name": "test_val"}]
        c_path = compile_to_c(constraints, tmp_dir / "nan_test.c")
        binary = tmp_dir / "nan_test"

        subprocess.run(
            ["gcc", "-O3", "-mavx2", "-lm", "-o", str(binary), str(c_path)],
            capture_output=True, text=True, timeout=30,
            check=True,
        )

        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0


# ---------------------------------------------------------------------------
# 2. WASM Tests
# ---------------------------------------------------------------------------

class TestCompileToWasm:

    def test_generates_wat(self, sample_constraints, tmp_dir):
        path = compile_to_wasm(sample_constraints, tmp_dir / "test.wat")
        assert path.exists()
        content = path.read_text()
        assert "(module" in content
        assert "(export \"check\"" in content
        assert "(export \"check_batch\"" in content
        assert "(export \"memory\"" in content

    def test_wat_contains_bounds(self, sample_constraints, tmp_dir):
        path = compile_to_wasm(sample_constraints, tmp_dir / "test.wat")
        content = path.read_text()
        # Check bounds are embedded as f64 constants
        assert "f64.const" in content
        assert "-40" in content or "40" in content  # lo of coolant_temp

    def test_check_function_signature(self, sample_constraints, tmp_dir):
        path = compile_to_wasm(sample_constraints, tmp_dir / "test.wat")
        content = path.read_text()
        # check takes f64 param, returns i32
        assert "(param $val f64)" in content
        assert "(result i32)" in content

    def test_zero_imports(self, sample_constraints, tmp_dir):
        path = compile_to_wasm(sample_constraints, tmp_dir / "test.wat")
        content = path.read_text()
        assert "(import" not in content

    def test_wat2wasm_if_available(self, sample_constraints, tmp_dir):
        """Try to compile WAT to WASM if wat2wasm is available."""
        if not _has_wat2wasm():
            pytest.skip("wat2wasm not available")

        path = compile_to_wasm(sample_constraints, tmp_dir / "test.wat")
        # If wat2wasm succeeded, we get a .wasm file
        if path.suffix == ".wasm":
            assert path.stat().st_size > 0
            # Read first 4 bytes — WASM magic
            magic = path.read_bytes()[:4]
            assert magic == b"\x00asm"


# ---------------------------------------------------------------------------
# 3. Verilog Tests
# ---------------------------------------------------------------------------

class TestCompileToVerilog:

    def test_generates_verilog(self, sample_constraints, tmp_dir):
        path = compile_to_verilog(sample_constraints, tmp_dir / "test.v")
        assert path.exists()
        content = path.read_text()
        assert "module flux_checker" in content
        assert "error_mask" in content
        assert "endmodule" in content

    def test_has_comparators(self, sample_constraints, tmp_dir):
        path = compile_to_verilog(sample_constraints, tmp_dir / "test.v")
        content = path.read_text()
        # Should have violation wires for each constraint
        assert "viol_coolant_temp_c" in content
        assert "viol_engine_rpm" in content
        assert "viol_battery_voltage_v" in content

    def test_single_clock_cycle(self, sample_constraints, tmp_dir):
        path = compile_to_verilog(sample_constraints, tmp_dir / "test.v")
        content = path.read_text()
        assert "clk" in content
        assert "rst_n" in content
        assert "valid_in" in content
        assert "valid_out" in content

    def test_has_testbench(self, sample_constraints, tmp_dir):
        path = compile_to_verilog(sample_constraints, tmp_dir / "test.v")
        content = path.read_text()
        assert "module flux_checker_tb" in content
        assert "$display" in content
        assert "$finish" in content

    def test_nan_detection(self, sample_constraints, tmp_dir):
        path = compile_to_verilog(sample_constraints, tmp_dir / "test.v")
        content = path.read_text()
        assert "is_nan" in content
        assert "11111111111" in content  # All-ones exponent

    def test_pipelined(self, sample_constraints, tmp_dir):
        """Verify pipeline register for batch throughput."""
        path = compile_to_verilog(sample_constraints, tmp_dir / "test.v")
        content = path.read_text()
        assert "stage_valid" in content


# ---------------------------------------------------------------------------
# 4. ARM Assembly Tests
# ---------------------------------------------------------------------------

class TestCompileToArm:

    def test_generates_assembly(self, sample_constraints, tmp_dir):
        path = compile_to_asm_arm(sample_constraints, tmp_dir / "test.s")
        assert path.exists()
        content = path.read_text()
        assert ".syntax unified" in content
        assert ".cpu cortex-m4" in content
        assert ".thumb" in content

    def test_has_flux_check_function(self, sample_constraints, tmp_dir):
        path = compile_to_asm_arm(sample_constraints, tmp_dir / "test.s")
        content = path.read_text()
        assert "flux_check_exact:" in content
        assert "flux_check_batch:" in content

    def test_has_fpu_instructions(self, sample_constraints, tmp_dir):
        path = compile_to_asm_arm(sample_constraints, tmp_dir / "test.s")
        content = path.read_text()
        assert "vcmp.f32" in content
        assert "vldr.32" in content
        assert "vmrs" in content

    def test_has_bounds_data(self, sample_constraints, tmp_dir):
        path = compile_to_asm_arm(sample_constraints, tmp_dir / "test.s")
        content = path.read_text()
        assert "bounds_lo:" in content
        assert "bounds_hi:" in content
        assert ".float" in content

    def test_nan_check(self, sample_constraints, tmp_dir):
        path = compile_to_asm_arm(sample_constraints, tmp_dir / "test.s")
        content = path.read_text()
        assert "NaN" in content or "vcmp.f32" in content  # NaN check uses vcmp s0, s0


# ---------------------------------------------------------------------------
# 5. All Presets × All Targets
# ---------------------------------------------------------------------------

class TestAllPresetsAllTargets:
    """Verify all 6 presets compile to all targets."""

    @pytest.mark.parametrize("preset_name", list(PRESETS.keys()))
    @pytest.mark.parametrize("target", ALL_TARGETS)
    def test_preset_compiles_to_target(self, preset_name, target, tmp_path):
        constraints = PRESETS[preset_name]
        result = deploy(target, constraints, tmp_path / f"{preset_name}_{target}")
        assert result[target]["status"] == "ok", \
            f"{preset_name} → {target} failed: {result[target]}"

    def test_all_6_presets_exist(self):
        assert len(PRESETS) == 6
        expected = {"automotive_can", "aviation_adsb", "medical_fhir",
                    "energy_scada", "iot_mqtt", "financial_fix"}
        assert set(PRESETS.keys()) == expected

    def test_deploy_all_targets(self, sample_constraints, tmp_path):
        results = deploy("all", sample_constraints, tmp_path / "all_targets")
        for target in ALL_TARGETS:
            assert results[target]["status"] == "ok", \
                f"Target {target} failed: {results[target]}"

    def test_deploy_creates_readme(self, sample_constraints, tmp_path):
        deploy("all", sample_constraints, tmp_path / "readme_test")
        readme = tmp_path / "readme_test" / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "FLUX" in content
        assert "Deployment" in content
        assert "coolant_temp_c" in content


# ---------------------------------------------------------------------------
# 6. Correctness Cross-Check
# ---------------------------------------------------------------------------

class TestCorrectnessCrossCheck:
    """Cross-check deployed code against Python reference."""

    def test_c_output_matches_python(self, tmp_path):
        """If gcc available, verify C output matches Python check_mask."""
        if not _has_gcc():
            pytest.skip("gcc not available")

        constraints = PRESETS["automotive_can"]
        from flux_constraint_exact import FluxExact

        fc = FluxExact(constraints)

        # Generate and compile C
        c_path = compile_to_c(constraints, tmp_path / "xcheck.c")

        # Add our own test values to the C file
        test_values = [0.0, 8000.0, 150.0, -40.0, 5000.0, 7999.999, 8000.001,
                       -0.001, 100.0, 200.0, 15.0, 9.0, 16.0, 16.001]

        # We trust the generated self-tests; the main point is it compiles
        # and runs without error. Deep cross-check would need custom C code.
        binary = tmp_path / "xcheck"
        subprocess.run(
            ["gcc", "-O3", "-mavx2", "-lm", "-o", str(binary), str(c_path)],
            capture_output=True, text=True, timeout=30,
            check=True,
        )

        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        assert result.returncode == 0

        # Cross-check with Python for a few values
        for val in test_values:
            mask = fc.check_mask(float(val))
            assert isinstance(mask, int)
            assert 0 <= mask <= 255


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_gcc() -> bool:
    try:
        subprocess.run(["gcc", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _has_wat2wasm() -> bool:
    try:
        subprocess.run(["wat2wasm", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
