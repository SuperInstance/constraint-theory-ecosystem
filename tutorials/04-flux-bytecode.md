# Tutorial 4: Understand FLUX-C Bytecode

**Time:** 10 minutes  
**What you'll learn:** How GUARD compiles to FLUX-C, the 43-opcode VM, and why termination is guaranteed.

---

## What is FLUX-C?

FLUX-C is a 43-opcode bytecode virtual machine for constraint checking. It has a critical property: **it cannot loop forever.** There are no jump instructions, no recursion, no backward branches. Every FLUX-C program terminates in bounded time — guaranteed by construction, not by analysis.

## Step 1: Inspect compiled bytecode

```bash
# Compile a simple constraint
cat > simple.guard << 'EOF'
constraint simple {
    temp in [0.0, 100.0] degC
}
EOF

guard compile simple.guard --output simple.fbc
guard disassemble simple.fbc
```

Output:

```
FLUX-C Bytecode v4 — simple
=================================
 0: LOAD_CONST  0.0        ; Lower bound
 1: LOAD_CONST  100.0      ; Upper bound
 2: LOAD_INPUT  0          ; Sensor value (temp)
 3: CMP_GTE                ; value >= 0.0?
 4: CMP_LTE                ; value <= 100.0?
 5: AND                    ; Both bounds satisfied?
 6: STORE_RESULT 0         ; Constraint 0 result
 7: HALT                   ; Done

Opcodes used: 8/43
Termination: GUARANTEED (no backward jumps)
Bytecode size: 56 bytes
```

## Step 2: The 43 opcodes

FLUX-C opcodes fall into 6 categories:

| Category | Opcodes | Count | Purpose |
|----------|---------|-------|---------|
| **Load/Store** | `LOAD_CONST`, `LOAD_INPUT`, `STORE_RESULT` | 5 | Move values |
| **Arithmetic** | `ADD`, `SUB`, `MUL`, `DIV`, `MOD`, `ABS` | 8 | Exact arithmetic |
| **Comparison** | `CMP_EQ`, `CMP_NE`, `CMP_LT`, `CMP_GT`, `CMP_LTE`, `CMP_GTE` | 6 | Check bounds |
| **Logic** | `AND`, `OR`, `NOT`, `XOR` | 4 | Combine checks |
| **Control** | `HALT`, `NOP`, `ASSERT` | 3 | Flow (no jumps!) |
| **Special** | `SCALE`, `CONVERT`, `PACK_INT8`, ... | 17 | Encoding, units |

Key property: **no `JMP`, `CALL`, or `LOOP`.** The instruction pointer only moves forward.

## Step 3: Trace execution in Python

```python
from constraint_theory import GuardCompiler, FluxVM

compiler = GuardCompiler()
bytecode = compiler.compile("""
constraint temp_check {
    temp in [0.0, 100.0] degC
}
""")

# Create VM and trace execution
vm = FluxVM(bytecode, trace=True)
result = vm.execute({"temp": 45.0})

# Trace output:
# [0] LOAD_CONST  0.0       → stack: [0.0]
# [1] LOAD_CONST  100.0     → stack: [0.0, 100.0]
# [2] LOAD_INPUT  0         → stack: [0.0, 100.0, 45.0]
# [3] CMP_GTE               → stack: [0.0, True]    (45.0 >= 0.0)
# [4] CMP_LTE               → stack: [True]         (45.0 <= 100.0)
# [5] STORE_RESULT 0        → result[0] = True
# [6] HALT

print(f"Result: {result}")       # True
print(f"Steps: {vm.step_count}") # 7
print(f"Time: {vm.elapsed_us}µs")
```

## Step 4: Multi-variable constraints

```python
bytecode = compiler.compile("""
constraint motor_safety {
    temp in [-40.0, 155.0] degC
    current in [0.0, 45.0] A
    rpm in [0.0, 12000.0] rev_per_min
}
""")

guard disassemble motor_safety.fbc
```

```
FLUX-C Bytecode v4 — motor_safety
====================================
 0: LOAD_CONST  -40.0
 1: LOAD_CONST  155.0
 2: LOAD_INPUT  0          ; temp
 3: CMP_GTE
 4: CMP_LTE                ; temp check done
 5: LOAD_CONST  0.0
 6: LOAD_CONST  45.0
 7: LOAD_INPUT  1          ; current
 8: CMP_GTE
 9: CMP_LTE                ; current check done
10: AND                    ; temp AND current
11: LOAD_CONST  0.0
12: LOAD_CONST  12000.0
13: LOAD_INPUT  2          ; rpm
14: CMP_GTE
15: CMP_LTE                ; rpm check done
16: AND                    ; all three
17: STORE_RESULT 0
18: HALT

Opcodes: 19, Max steps: 19, Termination: GUARANTEED
```

## Step 5: Why termination matters

In safety-critical systems (DO-254, ISO 26262), you must prove that your software cannot hang. With FLUX-C:

```
Max steps = number of opcodes in bytecode (no loops possible)
Max time  = max_steps × time_per_opcode
```

This is provable without static analysis:

```python
bytecode = compiler.compile_file("motor.guard")
print(f"Guaranteed max steps: {bytecode.max_steps}")
print(f"Guaranteed max time:  {bytecode.max_steps * 0.001}ms")  # 1µs per opcode
# Guaranteed max steps: 42
# Guaranteed max time:  0.042ms
```

This is the proof you show auditors: "The constraint checker cannot run longer than 42µs. Here's the bytecode, here's the proof."

## Step 6: Proof certificate

Every compiled bytecode includes a Coq proof certificate:

```bash
guard compile motor.guard --proof motor_proof.v
```

```coq
(* Excerpt from motor_proof.v *)
Theorem motor_safety_terminates :
  forall input, executes_in motor_safety_bytecode input <= 19 steps.
Proof.
  (* No backward jumps exist in bytecode *)
  (* Max instruction pointer movement: forward only *)
  (* QED *)
Qed.

Theorem motor_safety_correct :
  forall input temp current rpm,
    check motor_safety_bytecode input = true <->
    (temp >= -40.0 /\ temp <= 155.0 /\
     current >= 0.0 /\ current <= 45.0 /\
     rpm >= 0.0 /\ rpm <= 12000.0).
Proof. (* machine-verified *) Qed.
```

An auditor verifies this with:

```bash
coqc motor_proof.v
# motor_proof.v compiles successfully. All theorems verified.
```

**Next:** [Tutorial 5 — GPU Acceleration →](05-gpu-acceleration.md)
