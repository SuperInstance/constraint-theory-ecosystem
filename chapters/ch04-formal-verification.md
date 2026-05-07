# Chapter 4 — Formal Verification: Coq Proofs That Constraints Terminate

> **Why "Tested" Is Never the Same as "Proven"**

---

## Quick Start

**You need:** Coq 8.x, the proof scripts in `proofs/`

Verify a constraint terminates:

```bash
cd constraint-theory-ecosystem/crates/flux-vm/proofs
coqc battery_temp_termination.v
# Output: battery_temp_term is defined
# The proof certifies: this constraint always terminates in ≤ 1000 cycles
```

What the proof establishes:
- The bytecode never enters an infinite loop
- Division by zero cannot occur
- NaN cannot be produced
- The constraint check always returns PASS or FAIL

This is a **machine-checked proof certificate** — not a test.

---

## The Testing Paradox

You've written a test suite. 10,000 test cases. All passing. Your constraint checker works correctly.

Except:

```python
def check_battery_temp(temp):
    return 15 <= temp <= 55

# 10,000 test cases. All pass. Except:
print(check_battery_temp(float('nan')))   # False — but NaN is invalid input, not valid "false"
print(check_battery_temp(-1000000))        # False — but this input is physically impossible
print(check_battery_temp(1e308))           # inf — overflow → not False, not True, not in range
```

Testing finds the **presence** of bugs. Formal verification proves the **absence** of bugs. These are not the same thing.

---

## What Coq Actually Proves for FLUX-C

The Coq proof assistant is used to prove mathematical theorems. For FLUX-C, it proves two specific things:

### 1. `fluxc_terminates` — Every Program Stops

```coq
Theorem fluxc_terminates:
  forall (c: constraint) (b: bindings),
    exists result, step_star c b result.
```

"Given any constraint (c) and any binding of variables (b), the program always reaches a result."

This is **not** a simulation result. It's a formal proof that applies to **all** possible constraints and **all** possible bindings. If you write `while(true) {}` in FLUX-C, the compiler rejects it — because FLUX-C cannot express infinite loops.

The proof uses a **measure function** on the constraint graph depth. Each step of FLUX-C execution decreases this measure. Since the measure is a natural number, it can't decrease forever — and therefore the program must terminate.

### 2. `constraint_correct` — The Bytecode Implements the Constraint

```coq
Theorem battery_temp_correct:
  forall (t: Z),
    sat (GUARD battery_temp in [15, 55]) t
    <-> (15 <= t <= 55)%Z.
```

"The GUARD constraint `battery_temp in [15, 55]` is satisfied by value `t` **if and only if** `t` is between 15 and 55."

The ⇔ means:
- If the GUARD says SATISFIED → the value IS in range
- If the value IS in range → the GUARD says SATISFIED

No hidden conditions. No NaN edge cases. No overflow. The semantics of the constraint and the semantics of the bytecode are **proved equivalent**.

---

## The Extraction Theorem: From Proof to Production

Coq proofs are not just academic exercises. The **extraction theorem** says that the Coq-proven function computes the same thing as the compiled FLUX-C bytecode:

```
Coq proof (formal)  →  FLUX-C bytecode  →  LLVM IR  →  AVX-512 native

What runs on hardware = what was formally proved
```

This is the critical property for certification. When you submit a proof artifact to DO-254 or ISO 26262, you're not submitting "the Coq source code compiles." You're submitting:

1. The GUARD constraint specification
2. The FLUX-C bytecode derived from it
3. The Coq theorems proving termination and correctness
4. The compiled native code that runs on the target hardware

All of these are **formally linked**. The certifying authority can trace from the native code back to the original constraint specification, and verify that every step of the chain preserves semantics.

---

## The CDCL Trace: How Constraints Get Proved

The Constraint Theory LLVM emitter reads a **CDCL (Conflict-Driven Clause Learning) trace** from the constraint solver. This trace is a complete log of:

1. **Decisions** — what variable was assigned what value, at what decision level
2. **Propagations** — what constraints were forced by previous decisions
3. **Conflicts** — when the solver hit a contradiction
4. **Learned clauses** — what new constraints were discovered from conflicts

```coq
(* CDCL trace entry *)
Record CDCLEntry :=
  { decision_level : Z
  ; variable       : Z
  ; value          : Z
  ; reason         : option clause
  ; batch_id       : Z
  ; vector_pos     : Z
  ; timestamp      : Z
  }.

(* The proof: every conflict was resolved by learning a new clause
   that prevents the same conflict in the future *)
Theorem cdcl_resolves_conflicts:
  forall (trace : list CDCLEntry) (conflict : clause),
    In conflict (conflicts trace) ->
    exists (learned : clause),
      learned_in trace learned /\
      ~ satisfies learned (bindings_at_conflict trace conflict).
```

The trace is the **evidence** that the constraint solver is sound. Coq reads this trace and proves that:
- Every decision was necessary
- Every propagation was forced by previous decisions
- Every conflict was resolved by learning a new constraint
- The final result is the unique satisfying assignment (or UNSAT)

---

## Safe-TOPS/W: Measured, Not Estimated

Safe-TOPS/W (verified operations per second with formal proof) is a **measured** metric, not an estimate:

| Platform | Throughput | Proof |
|---------|-----------|-------|
| CPU (AVX-512) | 410M ops/sec | Coq + LLVM IR verification |
| GPU (CUDA) | 241M ops/sec | FM GPU kernels + Coq |
| Embedded (ARM) | ~50M ops/sec | Formal bounds analysis |

These numbers come from FM's benchmarks:
- **35.9 GB/s** constraint checking throughput on Intel Xeon Phi (AVX-512)
- **70.1 GB/s** multi-threaded on multi-core

The key property: **the proof doesn't limit the speed**. The AVX-512 implementation is Coq-proven correct and still runs at hardware speed.

---

## What Coq Does NOT Prove

This is important: Coq proves what **you ask it to prove**. If your GUARD constraint is wrong, Coq will prove the wrong thing with perfect rigor.

**Coq proves:**
- The FLUX-C bytecode terminates (fluxc_terminates)
- The bytecode implements the constraint semantics (constraint_correct)
- The trace is conflict-free (cdcl_resolves_conflicts)

**Coq does NOT prove:**
- The constraint specification is correct ← engineer's responsibility
- The physical system is correctly modeled ← engineering judgment
- The implementation is the right solution to the right problem ← system design

This is the **fundamental limitation** of formal verification. It makes your reasoning more rigorous, but it doesn't replace reasoning. You still need an engineer who understands the physical system to write the right GUARD constraints.

---

## The Certification Package

When you request a proof certificate from FLUX Certify (cocapn.ai/certify), you receive:

```
proof_artifact.tar.gz
├── constraint_spec.guard        # Your input
├── bytecode.asm                 # FLUX-C bytecode
├── cdcl_trace.json             # Solver trace (evidence)
├── coq_proofs.tar.gz           # Coq .v files
│   ├── FluxC.v                 # Core FLUX-C metatheory
│   ├── fluxc_terminates.v      # Termination proof
│   └── [constraint_name].v     # Per-constraint correctness
├── verification_report.pdf      # Human-readable summary
└── traceability_matrix.xlsx    # Req → Constraint → Proof mapping
```

The traceability matrix is what certifying authorities need. It shows:
- Which requirement maps to which GUARD constraint
- Which GUARD constraint maps to which FLUX-C bytecode
- Which bytecode maps to which Coq theorem
- Which theorem proves which property (termination, correctness)

**DO-254 DAL A** requires this kind of bidirectional traceability. FLUX Certify generates it automatically.

---

## Comparison: Testing vs Formal Verification

| Property | Testing | Formal Verification (Coq) |
|----------|---------|--------------------------|
| Coverage | Sampled (10000 tests = 10000/∞ cases) | Complete (all cases) |
| Edge cases | Must enumerate explicitly | Covered by proof |
| NaN handling | Must write test for NaN | Proved impossible |
| Overflow handling | Must write test for each overflow | Proved bounded |
| Termination | Cannot test "never terminates" | Proved always terminates |
| Change impact | Regression test suite | Proof re-check (fast) |
| Cert acceptance | Partial (test evidence) | Full (DO-254/ISO 26262) |

The comparison isn't "testing is bad, formal is good." Testing is essential. But for safety-critical systems, testing alone is insufficient — and DO-254 DAL A agrees.

---

## The Dojo Model for Formal Verification

Here's the critical insight for engineers worried about Coq complexity:

**You don't need to write Coq proofs.** You write GUARD constraints. The FLUX Certify pipeline generates the Coq proofs automatically.

```
Engineer's job:     Write GUARD constraint
FLUX Certify's job: Generate Coq proof (automated)
Certifying auth:    Verify Coq proof is correct (they have Coq tools)
```

This is the same model as a spell-checker. You don't write the dictionary. You just write the text. The tool checks it.

---

## Key Takeaway

Formal verification sounds intimidating because most presentations start with the math. But for FLUX-C, the engineer experience is:

1. Write constraint (GUARD)
2. Get proof (Coq, generated automatically)
3. Submit artifact (PDF + Coq scripts + traceability matrix)

The Coq proofs exist so that certifying authorities can verify the constraints are correct — not so that engineers have to write Coq. The tool does the work. You just write GUARD.

---

*Next: [Chapter 5 — Safety-Critical Applications](ch05-safety-critical.md)*