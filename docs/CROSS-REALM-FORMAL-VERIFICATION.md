# Cross-Realm Formal Verification: Lessons for Runtime Constraint Checking

**Date:** 2026-05-19  
**Author:** Forgemaster ⚒️ (Cross-domain research synthesis)  
**Status:** Research document

---

## Executive Summary

Formal verification systems (TLA+, Alloy, Coq, CBMC, control theory) have solved variants of our exact problem: **guaranteeing that no violation goes undetected.** Each system approaches this differently, and each offers concrete techniques we can port to runtime constraint checking.

**Key finding:** The "zero false negative" guarantee is not unique to us. It appears in:
- TLA+ as **inductive invariant proofs** (Init ⇒ Inv, Inv ∧ Next ⇒ Inv')
- Alloy as **bounded exhaustive search** (all instances within scope)
- Coq as **dependent types** (the proof IS the type)
- CBMC as **SAT/SMT unsatisfiability** (negated bounds = unsat)
- Control theory as **Violation Detection Lyapunov Functions** (monotone convergence to compliance)

---

## System-by-System Analysis

### 1. TLA+ (Temporal Logic of Actions)

**Core Technique: State-Space Exhaustion + Inductive Invariants**

TLA+ uses two complementary approaches:
1. **TLC model checker**: Explicitly enumerates ALL reachable states for finite specs, checking each against invariants. Fixed-point iteration until no new states emerge.
2. **Inductive invariant proofs**: For infinite-state systems, prove `Init ⇒ Inv` and `Inv ∧ Next ⇒ Inv'` — standard mathematical induction over the transition relation.

**Zero False Negative Guarantee:**
- Finite state: If any reachable state violates Inv, the counterexample trace is found by exhaustive search.
- Infinite state: If the inductive proof holds, no reachable state can violate Inv — this is a mathematical theorem, not a probabilistic claim.

**What We Can Port:**
- **Inductive invariant pattern**: We can define a constraint set's "well-formedness invariant" and prove it holds across all constraint operations. If `well_formed(C)` is true and we apply a valid operation `op`, then `well_formed(op(C))` is still true.
- **Fixed-point checking**: For finite value domains, we can exhaustively check all values in [lo, hi] to prove no misclassification exists.

**What Can't Be Done at Runtime:**
- Full state-space exploration (infeasible for continuous domains)
- Inductive proofs over arbitrary transition systems

**Concrete Adaptation:**
```python
def inductive_invariant_check(constraint_set, operation):
    """Prove well-formedness is preserved across operations."""
    assert well_formed(constraint_set), "Pre-condition: constraint set must be well-formed"
    result = operation(constraint_set)
    assert well_formed(result), "Post-condition: result must be well-formed"
    # If this holds for ALL operations, the invariant is inductive
    return result
```

---

### 2. Alloy Analyzer

**Core Technique: Bounded Exhaustive Search with SAT Solvers**

Alloy reduces first-order relational logic to a finite SAT problem:
1. Scope bounds the universe of atoms (e.g., `for 5` means at most 5 atoms per signature)
2. Every relational instance within scope is encoded as a propositional formula
3. SAT solver finds ALL solutions or proves none exist

**No Spurious Solutions Principle:**
- Alloy never abstracts the input constraints — only bounds the search space
- Every solution returned is a genuine model of the exact input constraints
- This is "compress the result, not the input" in action

**What We Can Port:**
- **Scope-bounded exhaustive verification**: For a constraint `C(x)` with domain `[lo, hi]`, we can exhaustively check every representable float value within the domain to prove no misclassification. This is Alloy's "bounded exhaustive search" adapted to continuous domains (using nextafter/epsilon-stepping).
- **Fact-based constraint composition**: Alloy facts are global constraints that must always hold. Our constraint sets should have "facts" — structural invariants that are checked once at setup time, not per-value.

**What Can't Be Done at Runtime:**
- SAT solver overhead per check (too slow for hot paths)
- Arbitrary relational logic (overkill for range checks)

**Concrete Adaptation:**
```python
def alloy_style_exhaustive_check(constraint, lo, hi, epsilon=1e-10):
    """Alloy-inspired: check EVERY value in the domain boundary."""
    # Check the boundary regions exhaustively
    x = lo
    while x <= hi:
        result = constraint.check(x)
        expected = lo <= x <= hi
        assert result == expected, f"Misclassification at x={x}"
        x = nextafter(x)  # smallest possible increment
    return True  # No misclassification in [lo, hi]
```

---

### 3. Coq (Dependent Type Theory)

**Core Technique: Proofs as Types (Curry-Howard Correspondence)**

In Coq, a proposition is a type, and a proof is a term inhabiting that type. The type checker IS the proof checker.

**Formal Type Signature for Proven Constraint Check:**
```coq
Record ProvenConstraintCheckResult {A : Type} : Type := {
  pccr_constraint : Constraint A;
  pccr_input : A;
  pccr_result : { pccr_constraint pccr_input } + { ~ pccr_constraint pccr_input };
  pccr_certificate : Certificate  (* SHA-256 hash chain *)
}.
```

The key insight: `pccr_result` is a **sum type** — it contains EITHER a proof that the constraint holds OR a proof that it doesn't. There is no "I don't know" option.

**What We Can Port:**
- **Proof certificates as types**: Our SHA-256 hash chains are analogous to Coq proof terms. We can make the certificate structure richer — not just "I checked" but "here's the evidence of what I found."
- **Well-formedness as a type-level guarantee**: Create a `WellFormedConstraintSet` type that can only be constructed if all structural invariants hold. This moves checking from runtime to construction time.

**What Can't Be Done at Runtime:**
- Full dependent type checking (requires theorem prover)
- Constructive proofs of arbitrary properties

**Concrete Adaptation:**
```python
from dataclasses import dataclass
from typing import TypeVar, Generic, Union

A = TypeVar('A')

@dataclass
class ProvenCompliance(Generic[A]):
    """Certificate that a constraint HOLDS for a value."""
    value: A
    constraint_id: str
    evidence: bytes  # serialized proof

@dataclass  
class ProvenViolation(Generic[A]):
    """Certificate that a constraint FAILS for a value."""
    value: A
    constraint_id: str
    violation_magnitude: float
    evidence: bytes

# The sum type: MUST be one or the other
ProvenResult = Union[ProvenCompliance, ProvenViolation]
```

---

### 4. CBMC (C Bounded Model Checker)

**Core Technique: Symbolic Execution + SAT/SMT Unsatisfiability**

CBMC verifies array bounds by:
1. Converting C code to a control-flow graph
2. Encoding all execution paths as symbolic constraints
3. Asserting the NEGATION of the safety property
4. If the solver returns UNSAT, the property holds for ALL executions

**The UNSAT Pattern:**
This is the most powerful technique for our use case. Instead of checking "does value x satisfy constraint C?" we check "does ANY value in the domain violate C and NOT get flagged?" If this is UNSAT, we have zero false negatives.

**What We Can Port:**
- **Negation-based verification**: To prove zero false negatives, encode `∃x: violates_constraint(x) ∧ NOT flagged(x)` and check for UNSAT. If UNSAT, no false negatives exist.
- **Path-sensitive analysis**: For compound constraints (AND/OR combinations), track which path was taken and verify each path independently.
- **Compile-time constraint set validation**: Before runtime, prove the constraint set is well-formed using symbolic methods.

**What Can't Be Done at Runtime:**
- Full symbolic execution (too expensive)
- SMT solving per value (too slow for hot paths)

**Concrete Adaptation:**
```python
def unsat_false_negative_check(constraint_set, domain_lo, domain_hi):
    """CBMC-inspired: prove no value is misclassified."""
    # For each constraint in the set:
    for c in constraint_set.constraints:
        # Check boundary regions (where misclassification is most likely)
        boundary_points = c.boundary_points()
        for x in boundary_points:
            result = c.check(x)
            # If x is in the valid region, result should be COMPLIANT
            # If x is outside, result should be VIOLATION
            # Any mismatch = false negative or false positive
            assert result.is_correct(x), f"Misclassification at boundary {x}"
    
    # Check epsilon neighborhoods of boundaries
    for c in constraint_set.constraints:
        for boundary in c.boundaries():
            for eps in [-1e-15, -1e-10, -1e-5, 0, 1e-5, 1e-10, 1e-15]:
                x = boundary + eps
                result = c.check(x)
                expected = c.classify(x)
                assert result == expected, f"Epsilon misclassification at {boundary}±{eps}"
```

---

### 5. Control Theory (Lyapunov Functions)

**Core Technique: Violation Detection Lyapunov Functions (VDLF)**

A VDLF is a function W(x) that:
1. W(x) > 0 ⟺ at least one constraint is violated
2. W(x) = h(v(x)) where h is strictly monotone on the violation lattice
3. Ẇ(x) ≤ 0 (non-increasing along trajectories)
4. The only invariant set where Ẇ=0 is the compliant set

**The Violation Lattice:**
- V^∞ = ℝ≥0^m (non-negative violation vectors)
- Product partial order: a ≤ b ⟺ aᵢ ≤ bᵢ for all i
- Join: max componentwise; Meet: min componentwise
- Complete lattice with Knaster-Tarski fixed point theorem

**What We Can Port:**
- **Violation vectors**: Instead of binary pass/fail, compute a violation magnitude per constraint. This gives us a position in the violation lattice.
- **Monotone violation detection**: If violation detection is monotone (more violation → more detection), then by lattice theory, we have guaranteed convergence to detection.
- **VDLF as a diagnostic tool**: Compute a "detection energy" that must decrease as violations are resolved.

**What Can't Be Done at Runtime:**
- Continuous-time dynamics (our system is discrete)
- Trajectory analysis (we check individual values, not sequences)

**Concrete Adaptation:**
```python
class ViolationVector:
    """Position in the violation lattice."""
    def __init__(self, violations: list[float]):
        self.components = violations  # v_i = max(0, constraint_i(x))
    
    def __le__(self, other) -> bool:
        """Product partial order on violation lattice."""
        return all(a <= b for a, b in zip(self.components, other.components))
    
    def join(self, other) -> 'ViolationVector':
        """Least upper bound."""
        return ViolationVector([max(a, b) for a, b in zip(self.components, other.components)])
    
    def magnitude(self) -> float:
        """VDLF: strictly monotone function on violation lattice."""
        return sum(v**2 for v in self.components) ** 0.5
    
    @property
    def is_compliant(self) -> bool:
        return all(v == 0 for v in self.components)
```

---

## Cross-Pollination Matrix

| Technique ↓ From → | TLA+ | Alloy | Coq | CBMC | Control Theory |
|---------------------|------|-------|-----|------|----------------|
| **Inductive Invariants** | ✅ SOURCE | Can verify scope bounds | Type-level guarantees | Loop invariants | LaSalle invariance |
| **Bounded Exhaustive Search** | TLC does this | ✅ SOURCE | Small-scale reflection | Bounded unrolling | Grid search |
| **Proofs as Data** | Temporal formulas | Instance models | ✅ SOURCE | Counterexample traces | VDLF values |
| **Negation/UNSAT** | Negation of safety | UNSAT = no model | Decidability | ✅ SOURCE | Contradiction |
| **Monotone Convergence** | Fixed-point iteration | Scope monotonicity | Termination proofs | Convergence of refinement | ✅ SOURCE |
| **SHA-256 Certificates** | Not native | Not native | Possible via axioms | Not native | Not native |
| **Violation Lattice** | State ordering | Instance ordering | Type hierarchy | Constraint ordering | ✅ SOURCE |

### Key Cross-Pollinations

1. **TLA+ → Runtime**: Inductive invariant pattern for constraint set well-formedness
2. **Alloy → Runtime**: Bounded exhaustive search near constraint boundaries
3. **Coq → Runtime**: Proof certificates as structured sum types (not just hashes)
4. **CBMC → Runtime**: UNSAT-based verification of zero false negatives at setup time
5. **Control Theory → Runtime**: Violation vectors + monotone detection guarantee

---

## What's Unique to Static/Compile-Time

These cannot be fully replicated at runtime:
1. **Full state-space exploration** (TLA+, Alloy) — exponential in system size
2. **Constructive proofs** (Coq) — require theorem prover, not a constraint checker
3. **Symbolic execution** (CBMC) — path explosion makes it infeasible per-value
4. **Continuous trajectory analysis** (Control theory) — we check discrete points

## What We CAN Do at Runtime

These are viable adaptations:
1. **Setup-time verification**: Prove constraint set well-formedness once, not per-check
2. **Boundary exhaustive testing**: Test all boundary + epsilon neighborhoods at setup
3. **Rich certificates**: Include structured evidence, not just pass/fail hashes
4. **UNSAT-inspired validation**: Encode false-negative-freedom and check at setup
5. **Violation magnitude tracking**: Lattice-positioned violation vectors for diagnostics

---

## Implementation Priority

| Priority | Technique | From | Effort | Impact |
|----------|-----------|------|--------|--------|
| 1 | Setup-time well-formedness proofs | TLA+ + Coq | Medium | Catches config errors early |
| 2 | Boundary exhaustive testing | Alloy + CBMC | Low | Proves no boundary misclassification |
| 3 | Structured proof certificates | Coq | Medium | Richer audit trail |
| 4 | Violation vectors | Control Theory | Low | Better diagnostics |
| 5 | UNSAT-based validation | CBMC | High | Mathematical guarantee |

---

*Research conducted via Seed-2.0-mini cross-domain analysis, synthesized by Forgemaster ⚒️*
