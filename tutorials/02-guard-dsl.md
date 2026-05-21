# Tutorial 2: Write GUARD Specs

**Time:** 10 minutes  
**What you'll learn:** The full GUARD DSL syntax for writing constraints.

---

## GUARD Constraint Anatomy

A GUARD file contains one or more constraints. Each constraint has:

```
constraint <name> {
    <variable> in [<min>, <max>] <unit>
        with priority <level>
        with category <type>
        with message "<description>"
}
```

## Step 1: Basic bounds constraint

```bash
cat > thermal.guard << 'EOF'
constraint thermal_management {
    core_temp in [0.0, 85.0] degC
        with priority CRITICAL
        with category SAFETY
}
EOF
```

Compile and verify:

```bash
guard compile thermal.guard --output thermal.fbc
guard check thermal.fbc --value core_temp=45.0   # ✓ PASS
guard check thermal.fbc --value core_temp=90.0   # ✗ FAIL
```

## Step 2: Multiple variables in one constraint

```bash
cat > motor.guard << 'EOF'
constraint motor_controller {
    winding_temp in [-40.0, 155.0] degC
        with priority CRITICAL
        with category THERMAL
        with message "Winding temperature exceeds class F insulation rating"
    
    rpm in [0.0, 12000.0] rev_per_min
        with priority HIGH
        with category MECHANICAL
        with message "RPM exceeds motor rating"
    
    current in [0.0, 45.0] A
        with priority HIGH
        with category ELECTRICAL
        with message "Overcurrent condition detected"
    
    vibration in [0.0, 4.5] mm_per_s
        with priority MEDIUM
        with category MECHANICAL
        with message "Vibration exceeds ISO 10816 threshold"
}
EOF
```

Check all variables at once:

```bash
guard compile motor.guard --output motor.fbc
guard check motor.fbc \
    --value winding_temp=120.0 \
    --value rpm=8000.0 \
    --value current=30.0 \
    --value vibration=2.1
# ✓ ALL PASS (4/4)
```

## Step 3: Priority levels and categories

GUARD supports these priority levels:

| Priority | Meaning |
|----------|---------|
| `CRITICAL` | System must halt immediately on violation |
| `HIGH` | Alert operator, system may continue with logging |
| `MEDIUM` | Log for maintenance scheduling |
| `LOW` | Informational, no action required |

Categories organize constraints for reporting:

```
SAFETY, OPERATIONAL, THERMAL, MECHANICAL, ELECTRICAL,
LIFE_SUPPORT, NAVIGATION, COMMUNICATION, STRUCTURAL
```

## Step 4: Constraint composition

Multiple constraints in one file are checked independently:

```bash
cat > system.guard << 'EOF'
constraint power_budget {
    total_power in [0.0, 500.0] W
        with priority CRITICAL
        with category ELECTRICAL
}

constraint thermal_envelope {
    ambient_temp in [-20.0, 55.0] degC
        with priority HIGH
        with category THERMAL
}

constraint structural_limits {
    vibration in [0.0, 7.1] mm_per_s
        with priority MEDIUM
        with category MECHANICAL
}
EOF
```

## Step 5: Python — Compile and introspect

```python
from constraint_theory import GuardCompiler

compiler = GuardCompiler()

# Compile from string
bytecode = compiler.compile("""
constraint battery {
    voltage in [2.8, 4.2] V
        with priority CRITICAL
        with category ELECTRICAL
    temp in [-20.0, 60.0] degC
        with priority HIGH
        with category THERMAL
}
""")

# Introspect the compiled constraint
print(f"Constraints: {bytecode.constraint_count}")     # 2
print(f"Variables: {bytecode.variables}")               # ['voltage', 'temp']
print(f"Bytecode size: {bytecode.size} bytes")
print(f"Opcodes: {bytecode.opcode_count}")              # <43 (termination guaranteed)

# Get the proof certificate
proof = bytecode.proof_certificate()
print(f"Proof: {proof[:200]}...")  # Coq source
```

## Step 6: Exact arithmetic — why this matters

```python
from constraint_theory import exact

# Float arithmetic lies
assert 0.1 + 0.2 != 0.3  # Standard Python

# GUARD uses exact arithmetic internally
val = exact.from_str("0.1") + exact.from_str("0.2")
assert val == exact.from_str("0.3")  # ✓ Exact

# This means constraint checks are never wrong due to rounding
checker = FluxChecker(compiler.compile("""
constraint test {
    x in [0.3, 0.3]
}
"""))
assert checker.check("x", exact.from_str("0.1") + exact.from_str("0.2"))  # ✓ PASS
```

## GUARD Syntax Reference

| Element | Syntax | Example |
|---------|--------|---------|
| Constraint block | `constraint <name> { ... }` | `constraint motor { ... }` |
| Variable bound | `<var> in [<min>, <max>] <unit>` | `temp in [0, 100] degC` |
| Priority | `with priority <level>` | `with priority CRITICAL` |
| Category | `with category <type>` | `with category SAFETY` |
| Message | `with message "<text>"` | `with message "Over temp"` |
| Comment | `// <text>` | `// Safety limit` |

Full spec: [`SPEC.md`](../SPEC.md)

**Next:** [Tutorial 3 — Industry Constraint Library →](03-industry-library.md)
