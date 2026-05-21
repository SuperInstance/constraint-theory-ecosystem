# Constraint Theory Ecosystem

## What is constraint theory?

You have a system of equations. You need exactly enough constraints for a unique solution. Not too few — that's underconstrained, and the system drifts. Not too many — that's overconstrained, and you get conflicts. The math tells you the exact number.

Think about an O-ring seal. The gland depth constrains the O-ring's compression. If the squeeze is between 15% and 25%, you get a seal. Too loose (10%) and fluid leaks. Too tight (30%) and the ring extrudes through the gap. The constraint *is the spec*, and the math tells you whether you meet it — yes or no, not "probably."

This is what hardware engineers do every day. Tolerance stacks, interference fits, pressure ratings — all constraint checks. The answer is always binary: in spec or out of spec. No probabilities.

Software doesn't work this way. Software writes `float x` and hopes.

## The floating point problem

```python
>>> 0.1 + 0.2 == 0.3
False
```

Floating point arithmetic is approximate by design. That's fine for graphics, dangerous for safety-critical systems. When `battery_temp` drifts by 0.001°C due to rounding, you don't know if you're inside or outside the safe operating range.

Constraint theory replaces "approximately correct" with "provably correct or provably wrong."

## The key equation

```
E = 2V − 3
```

This is Laman's theorem (1970). For V vertices in a 2D structure, you need exactly 2V−3 edges for rigidity. Think of a bridge truss: too few beams and it flexes. Too many and internal stresses build up. Exactly 2V−3 and it's rigid — it cannot deform without a beam breaking.

Applied to software: V agents in a fleet need exactly 2V−3 trust relationships. Too few and they drift silently. Too many and sub-coalitions form unpredictably. Exactly right and the fleet is provably consistent.

## What's actually happening?

Constraint theory treats every variable in your system as a dimension in a geometric space. Each constraint (`battery_temp ∈ [15, 55]`) carves out a valid region. If the intersection of all regions is non-empty, a solution exists. If it's empty, no solution is possible — and you find out at *design time*, not in production.

The approach works because it's geometric, not statistical. You're not estimating probabilities. You're checking whether a point falls inside a polytope. The answer is exact.

## What this repository contains

| Layer | What it does |
|-------|-------------|
| **GUARD DSL** | Write constraints like `battery_temp ∈ [15, 55]` — a domain-specific language for exact bounds |
| **FLUX-C bytecode** | 43-opcode virtual machine that *cannot loop forever* (termination guaranteed by construction) |
| **Coq proofs** | Machine-checked proof certificates that auditors can verify independently |
| **Fleet math** | ZHC consensus (38ms), H¹ emergence detection, Pythagorean48 zero-drift encoding |
| **Industry guides** | DO-254, ISO 26262, IEC 61508 — mapping constraint checks to safety standards |

## Quick example

```bash
# Write a constraint
echo 'battery_temp in [15, 55] °C with priority HIGH' > battery.guard

# Compile and generate a proof certificate
guard compile battery.guard --output battery.fbc --proof battery.v
```

The compiler doesn't just check your constraint — it produces a machine-verifiable proof that the check is correct. An auditor can verify `battery.v` without trusting your toolchain.

## Contrast with floating point

| Property | Floating point | Constraint theory |
|----------|---------------|-------------------|
| Result | Approximately correct | Provably correct or provably wrong |
| Failure mode | Silent (NaN, drift, wrap) | Loud (violation at design time) |
| Example | `0.1 + 0.2 ≠ 0.3` | `battery_temp ∈ [15, 55]` ✓ or ✗ |
| Audit trail | None | Coq proof certificate |

## Chapters

The `chapters/` directory contains a full textbook:

- **Ch 0** — The Constraint Mindset (you're already doing this)
- **Ch 1** — Why Software Gets Constraints Wrong (floating point is the problem)
- **Ch 2** — GUARD DSL (the language for exact constraints)
- **Ch 3** — FLUX-C Bytecode (43 opcodes, termination guaranteed)
- **Ch 4** — Formal Verification (Coq proof chain)
- **Ch 5** — Safety-Critical Applications (DO-254, ISO 26262, IEC 61508)
- **Ch 6** — Fleet Math (ZHC, H¹, Pythagorean48)
- **Ch 7** — Getting Started (install, write, certify)
- **Ch 8** — GPU Architecture (62 billion checks/sec on a $300 GPU)

## Why does this work?

Because constraints are geometry, and geometry is exact. When you write `x ∈ [a, b]`, you're not approximating — you're defining a region in space. Either a point is inside it or it isn't. No rounding, no drift, no "approximately." The Coq proofs make this machine-checkable: the theorem prover verifies that your constraints are satisfiable, that the check covers all cases, and that the compiled bytecode faithfully implements the check.

## License

MIT
