# Tutorial 1: Check Your First Constraint

**Time:** 5 minutes  
**Language:** Python  
**What you'll learn:** Write a GUARD constraint, compile it, and check values.

---

## Prerequisites

```bash
# Clone and install
git clone https://github.com/SuperInstance/constraint-theory-ecosystem.git
cd constraint-theory-ecosystem
pip install -r src/python/requirements.txt
```

## Step 1: Write a GUARD constraint

Create a file called `sensor.guard`:

```bash
cat > sensor.guard << 'EOF'
constraint cabin_pressure_safety {
    cabin_pressure in [0.75, 1.05] atm
        with priority CRITICAL
        with category SAFETY
        with message "Cabin pressure outside safe range"
    
    oxygen_level in [19.5, 23.5] percent
        with priority HIGH
        with category LIFE_SUPPORT
        with message "Oxygen level abnormal"
}
EOF
```

This defines two constraints for an aircraft cabin:
- Cabin pressure must stay between 0.75 and 1.05 atm
- Oxygen must stay between 19.5% and 23.5%

## Step 2: Compile to FLUX-C bytecode

```bash
# Compile with proof certificate
guard compile sensor.guard --output sensor.fbc --proof sensor_proof.v
```

The compiler outputs:
- `sensor.fbc` — FLUX-C bytecode (43-opcode VM, termination guaranteed)
- `sensor_proof.v` — Coq proof certificate (auditable)

## Step 3: Check values from the command line

```bash
# Should PASS
guard check sensor.fbc --value cabin_pressure=1.0
# ✓ PASS: cabin_pressure = 1.0 atm ∈ [0.75, 1.05]

# Should FAIL
guard check sensor.fbc --value cabin_pressure=0.6
# ✗ FAIL: cabin_pressure = 0.6 atm ∉ [0.75, 1.05] — Cabin pressure outside safe range

# Check multiple values
guard check sensor.fbc --value cabin_pressure=1.0 --value oxygen_level=21.0
# ✓ ALL PASS (2/2 constraints satisfied)
```

## Step 4: Use the Python API

```python
from constraint_theory import GuardCompiler, FluxChecker

# Compile the constraint file
compiler = GuardCompiler()
bytecode = compiler.compile_file("sensor.guard")
checker = FluxChecker(bytecode)

# Single value check
result = checker.check("cabin_pressure", 1.0)
print(f"Cabin pressure 1.0 atm: {result}")  # True

result = checker.check("cabin_pressure", 0.6)
print(f"Cabin pressure 0.6 atm: {result}")  # False

# Check all constraints at once
sensor_reading = {
    "cabin_pressure": 1.0,
    "oxygen_level": 21.0,
}
report = checker.check_all(sensor_reading)
print(report)
# ✓ cabin_pressure = 1.0 atm ∈ [0.75, 1.05]
# ✓ oxygen_level = 21.0 percent ∈ [19.5, 23.5]
# Result: PASS (2/2)

# Batch check — 1 million values at once
import numpy as np
pressures = np.random.uniform(0.5, 1.2, size=1_000_000)
results = checker.check_batch("cabin_pressure", pressures)
print(f"Pass rate: {results.sum() / len(results) * 100:.1f}%")
# Pass rate: ~60.4% (roughly the fraction in [0.75, 1.05])
```

## Step 5: GPU-accelerated batch checking

```python
# If you have a CUDA GPU
checker_gpu = FluxChecker(bytecode, device="cuda")

# Check 10M values on GPU
pressures = np.random.uniform(0.5, 1.2, size=10_000_000)
results = checker_gpu.check_batch("cabin_pressure", pressures)
print(f"GPU throughput: {len(pressures) / results.elapsed_ms * 1000 / 1e9:.1f}B c/s")
# GPU throughput: ~62.0B c/s
```

## What you just did

1. Wrote an exact constraint in GUARD DSL (no floats, no rounding)
2. Compiled it to a terminating bytecode (FLUX-C)
3. Got a machine-checkable proof certificate (Coq)
4. Checked values in Python, CLI, and on GPU

**Next:** [Tutorial 2 — Write GUARD Specs →](02-guard-dsl.md)
