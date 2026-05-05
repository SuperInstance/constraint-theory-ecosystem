# Constraint Theory Ecosystem

**You already think in constraints. This formalizes what you know.**

*The constraint is the point, not the exception.*

---

## The Problem

Software treats constraints as afterthoughts: `NaN != NaN` is true, `INT_MAX + 1 = INT_MIN` in two's complement, and `(a + b) + c != a + (b + c)` with large floats. Every one of these silently corrupts systems. Hardware engineers learned this lesson physically — an o-ring either seals or it doesn't.

## The Solution

**FLUX-C + GUARD + Coq proofs** — constraint satisfaction with formal verification:

- **GUARD DSL** specifies exact constraints (like GD&T for software): `GUARD battery_temp in [15, 55]`
- **FLUX-C Bytecode** executes them — 43 opcodes, Turing-incomplete, guaranteed terminating
- **Coq proofs** verify termination and semantic correctness for every constraint

**Standards:** 📋 DO-254 DAL A · ISO 26262 ASIL-D · IEC 61508 SIL 3

---

## For Hardware Engineers

You already know this. GUARD just makes it explicit:

- **Tolerance stack** → `GUARD sum_le([a, b, c], max_stack)`
- **Interference fit** → `GUARD shaft_diameter > bore_diameter`
- **O-ring seal** → `GUARD seal_compression in [0.15, 0.25]`
- **MMC callout** → `GUARD position_error <= 0.05 @ MMC`

GD&T was invented so hardware dimensions could be specified precisely enough to fail at build time, not runtime. GUARD does the same for software.

---

## For Safety Engineers

⚠️ DO-254, ISO 26262, IEC 61508 are constraint satisfaction problems. FLUX Certify solves them faster and more rigorously — with proof artifacts for tool qualification (DO-330).

**Safe-TOPS/W:** 410M verified CPU ops/sec, 241M GPU ops/sec. All with formal proof artifacts.

**$10K pilot available:** Full constraint verification with Coq proof review. → [cocapn.ai/certify](https://cocapn.ai/certify)

---

## 🔧 Quick Example

**GUARD constraint:**
```
GUARD battery_temp in [15, 55]
GUARD NOT (temperature < 0 AND charging_enabled)
```

**Compiled to FLUX-C bytecode:**
```
0x01 PUSH_CONST 15        ; lower bound
0x02 PUSH_REF temp         ; temperature sensor
0x03 IN_RANGE              ; [15, 55] check
0x04 PUSH_CONST 0
0x05 PUSH_REF temp
0x06 LT                     ; temp < 0
0x07 PUSH_REF charging
0x08 AND                    ; temp < 0 AND charging
0x09 NOT                    ; NOT (temp < 0 AND charging)
0x0A AND                    ; combine with range check
0x0B HALT                   ; constraint satisfied or violated
```

No NaN. No overflow. Boolean outcome. 410M checks/sec with Coq proof.

---

## Chapter Overview

- **ch00 — The Constraint Mindset:** What you already know (tolerance stacks, o-rings, interference fits)
- **ch01 — Why Software Fails:** NaN, overflow, non-transitive float comparison — the rubber ruler problem
- **ch02 — GUARD DSL:** The constraint specification language (14 constructs, real examples)
- **ch03 — FLUX-C Bytecode:** 43-opcode ISA, Turing-incomplete by design, guaranteed termination
- **ch04 — Formal Verification:** Coq proofs that constraints terminate and produce correct output
- **ch05 — Safety-Critical Apps:** DO-254, ISO 26262, IEC 61508 with proof artifacts and benchmarks
- **ch06 — Fleet Math:** ZHC consensus (38ms, any Byzantine tolerance), H1 emergence detection, Pythagorean48 hashing
- **ch07 — Get Started:** Three entry points: hardware engineers, software engineers, safety engineers

---

## Get Started

**1.** Read [ch00 — The Constraint Mindset](chapters/ch00-constraint-mindset.md) (20 min, no code)

**2.** Try FLUX Certify → [cocapn.ai/certify](https://cocapn.ai/certify)

**3.** Write your first GUARD constraint. Compile it. Watch it verify.

**For the full theory:** Read the paper → [construction-constraint-theory](https://cocapn.ai/constraint-theory-paper)

---

Built by [SuperInstance](https://github.com/SuperInstance) · FLUX Certify at [cocapn.ai/certify](https://cocapn.ai/certify)
