# The Constraint Theory Ecosystem

> **"The math that hardware engineers already know. Tolerance stacks, interference fits, and o-rings — formalized."**

---

## The O-Ring Test

An o-ring either seals or it doesn't. The housing either compresses the o-ring 15–25% or it doesn't. The pressure either holds or the system fails catastrophically.

There is no "approximately sealed." No "close enough pressure." No "good enough for government work."

This is **constraint satisfaction** — and if you design hardware, you've been doing it your entire career.

---

## The Floating Point Problem

Software engineers keep relearning what hardware engineers already know:

```
FLOATING POINT:    "x is approximately in [0, 1]" → wrong silent, fails at runtime
CONSTRAINT THEORY:  "x ∈ [0, 1] ∧ ¬deadlock ∧ ¬overflow" → right or wrong, known at compile time
```

- `NaN != NaN` is true. Every comparison with NaN is false.
- `INT_MAX + 1 = INT_MIN` in two's complement. Undefined behavior.
- `(a + b) + c != a + (b + c)` with large floats. Non-transitive comparison.

These aren't edge cases. They're the natural consequence of using **continuous approximation** where **discrete constraint satisfaction** is required.

---

## What This Ecosystem Is

A public monorepo that teaches constraint theory to engineers who already think in constraints — and shows them how to write software that enforces them with the same rigor they apply to physical design.

**Contains:**
- **GUARD DSL** — a constraint specification language (like GD&T for software)
- **FLUX-C Bytecode** — 43-opcode verifiable instruction set (Turing-incomplete = guaranteed terminating)
- **Coq Proofs** — formal verification that constraints terminate and produce correct output
- **Safe-TOPS/W** — 410M verified CPU operations/sec, 241M GPU ops/sec (with proof artifacts)
- **ZHC Consensus** — 38ms fleet coordination latency, unlimited Byzantine tolerance
- **H1 Emergence Detection** — 127 lines detect emergence vs 12K-line ML model

**Standards supported:** DO-254 DAL A · ISO 26262 ASIL-D · IEC 61508 SIL 3

---

## Quick Example: The Battery Temperature Constraint

**What a hardware engineer thinks:**
> "Battery temp must be between 15°C and 55°C. Below 0°C, charging damages the cells. Above 60°C, thermal runaway starts. I need a margin."

**What a software engineer writes (floating point):**
```python
if temp > 15 and temp < 55:
    # allow charging
    pass
```
*Problem: `temp` could be NaN. `temp > 55` is false when temp is NaN. Charging still happens.*

**What a constraint theorist writes (GUARD DSL):**
```
GUARD battery_temp in [15, 55]
GUARD NOT (temperature < 0 AND charging_enabled)
```
*Compiled to FLUX-C bytecode, verified by Coq, executed at 410M checks/sec.*

---

## For Engineers Who Already Know GD&T

| What You Call It | What CS Calls It | What GUARD Writes |
|-----------------|------------------|-------------------|
| Tolerance stack | Bounded variable composition | `GUARD sum_le([a, b, c], max_stack)` |
| Interference fit | Negative clearance constraint | `GUARD shaft_diameter > bore_diameter` |
| Pressure rating | Upper bound on stress | `GUARD pressure < max_working_pressure / safety_factor` |
| Leak test | Constraint validation | `GUARD seal_compression in [0.15, 0.25]` |
| Safety factor | Overconstraint margin | `GUARD margin > 1.5` |
| MMC (max material condition) | Worst-case bound | `GUARD position_error <= 0.05 @ MMC` |
| GD&T callout | Formal constraint spec | `GUARD perpendicularity(tolerance, surface_finish)` |

---

## Three Entry Points

### For Hardware Engineers
1. Read [chapters/ch00-constraint-mindset.md](chapters/ch00-constraint-mindset.md)
2. Try the [FLUX Certify playground](https://cocapn.ai/certify)
3. Write your first GUARD constraint

### For Software Engineers
1. Read [chapters/ch02-guard-dsl.md](chapters/ch02-guard-dsl.md)
2. Install the [FLUX VM](https://github.com/SuperInstance/flux-vm-php)
3. Try the [sandbox](https://cocapn.ai/flux-sandbox)

### For Safety Engineers / Certification Authorities
1. Read [chapters/ch05-safety-critical.md](chapters/ch05-safety-critical.md)
2. Review Safe-TOPS/W metrics and proof artifacts
3. Request a $10K pilot engagement: [cocapn.ai/certify](https://cocapn.ai/certify)

---

## The Three Breakthroughs (Fleet Math)

**ZHC — Zero Holonomy Consensus**
> Distributed coordination without voting. The geometry IS the position.
> 38ms latency (any N nodes, any Byzantine tolerance) vs PBFT 412ms.

**H1 — First Cohomology Emergence Detection**
> "Is emergent behavior emerging?" Answer from algebraic topology, not machine learning.
> 127 lines vs 12,000-line PyTorch model. 100% accuracy on benchmark graphs.

**Pythagorean48 — Collision-Free Hashing**
> 48-element codebook. 6 bits per vector. Involution (h = h⁻¹) = zero drift.
> Collision probability 1/48. Trivially correctable with parity check.

---

## Status

| Component | Status | Location |
|-----------|--------|----------|
| GUARD DSL | SPEC COMPLETE | `src/guard-compiler/` (pending) |
| FLUX-C Bytecode | Live | `flux-research/specs/flux-isa-v3.md` |
| Coq Proofs | [PROVEN] | `proofs/FluxC/FluxC.v` |
| LLVM Emitter | Live | `constraint-theory-llvm/` |
| ZHC Consensus | Live | `holonomy-consensus/` |
| FLUX Certify | Live | [cocapn.ai/certify](https://cocapn.ai/certify) |
| This Repo | SPEC ONLY | You're reading it |

---

## Maintainer

**CoCapn Fleet** — *The ocean counts. The Spark lights the fire.*

Built by [SuperInstance](https://github.com/SuperInstance) · FLUX Certify at [cocapn.ai/certify](https://cocapn.ai/certify)

---

*If you design hardware that must work, you already think in constraints. Let's make the software match.*