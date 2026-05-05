# Coq Proof Inventory

15 Coq theorems formalizing FLUX constraint theory.

## flux_saturation_coq.v — INT8 Saturation Semantics (7 proofs)

Uses `Require Import ZArith Lia.` All proofs self-contained.

| # | Theorem | Statement | Significance |
|---|---------|-----------|--------------|
| 1 | `saturate_i8_correct` | ∀ x, -127 ≤ saturate(x) ≤ 127 | Range bound — saturate always returns valid INT8 |
| 2 | `negation_symmetry` | ∀ x ∈ [-127,127], -x ∈ [-127,127] | No wraparound on negation |
| 3 | `monotonicity` | a ≤ b → saturate(a) ≤ saturate(b) | Order preserved through saturation |
| 4 | `order_preservation` | In-range: a ≤ b ⟺ saturate(a) ≤ saturate(b) | Exact equivalence for normal values |
| 5 | `galois_preservation` | Saturate preserves GUARD ↔ FLUX-C Galois connection | Compiler correctness |
| 6 | `addition_saturation_closed` | a,b ∈ range → saturate(a+b) ∈ range | Arithmetic closure |
| 7 | `no_wraparound` | a+b representable → saturate(a+b) = a+b | Identity for in-range sums |

### The saturate function (defined in Coq):
```coq
Definition saturate (x : Z) : Z :=
  Z.max (-127) (Z.min 127 x).
```

### Why -127 not -128:
Standard INT8 range [-128, 127] has asymmetric negation: -(-128) = -128 (overflow).
By clamping to [-127, 127], negation is always correct: -(-127) = 127.

## flux_galois_coq.v — Galois Connection (4 proofs)

Formalizes the compiler correctness theorem: GUARD DSL ↔ FLUX-C bytecode.

| # | Theorem | Statement |
|---|---------|-----------|
| 8 | `guard_to_flux_monotone` | GUARD spec ordering preserved in FLUX-C |
| 9 | `flux_to_guard_monotone` | FLUX-C results reflect GUARD ordering |
| 10 | `galois_connection` | The adjoint pair (guard_to_flux, flux_to_guard) forms a Galois connection |
| 11 | `semantic_preservation` | Guard semantic meaning preserved through compilation |

## flux_wcet_coq.v — WCET Guarantees (4 proofs)

Formalizes worst-case execution time properties.

| # | Theorem | Statement |
|---|---------|-----------|
| 12 | `terminates_always` | All FLUX-C programs terminate (Turing-incomplete) |
| 13 | `bounded_iterations` | Program with deadline N executes at most N instructions |
| 14 | `wcet_linear` | WCET is linear in bytecode length |
| 15 | `sandbox_isolation` | SANDBOX_ENTER/EXIT pairs isolate untrusted code |

---

## Proof Strategy

1. **Arithmetic properties** (1-7): Direct proofs using `lia` (linear integer arithmetic)
2. **Galois connection** (8-11): Order theory with monotonicity lemmas
3. **WCET guarantees** (12-15): Structural induction on bytecode programs

## Compilation

```bash
coqc -Q . FluxResearch proofs/coq/flux_saturation_coq.v
```

Requires: Coq 8.16+, ZArith standard library.

---

## English Proofs (30 total)

In addition to the 15 Coq theorems, 30 English proofs cover:

- **Compiler correctness**: Galois connection between GUARD and FLUX-C
- **Arithmetic safety**: INT8 saturation prevents all overflow paths
- **Termination**: Turing-incomplete ISA guarantees finite execution
- **Bytecode validation**: 5-phase pipeline catches all malformed programs
- **GPU determinism**: CUDA Graphs ensure bit-identical replay
- **Error mask completeness**: All constraint violations are detected and localized
- **Severity monotonicity**: More violations → higher severity (never decreases)
- **Differential equivalence**: GPU and CPU produce identical results

---

*Total: 15 Coq + 30 English = 45 proof artifacts.*
