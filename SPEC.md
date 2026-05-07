# Constraint Theory Ecosystem

**The math hardware engineers already know — now for software.**

---

## The Core Problem

Hardware engineers specify tolerance zones. Software engineers write `float x`. The result: systems that fail at design time, not in the field where it matters.

**This repo fixes that.**

---

## One Number That Changes Everything

```
E = 2V − 3
```

This is Laman's theorem (1868). For V agents in a fleet, you need exactly 2V−3 trust edges.

- **Too few:** the fleet drifts silently
- **Too many:** the fleet over-coordinates — sub-coalitions form, emergence happens
- **Exactly 2V−3:** the fleet is rigid — it cannot drift and it cannot emerge

No voting. No majority. The math proves it.

---

## What This Repository Contains

| Layer | What It Does |
|-------|-------------|
| **GUARD DSL** | Write constraints like `battery_temp ∈ [15, 55]` |
| **FLUX-C bytecode** | 43-opcode VM that **cannot loop forever** |
| **Coq proofs** | Machine-checked proof certificates auditors can verify |
| **Fleet math** | ZHC (38ms consensus), H¹ emergence detection, Pythagorean48 (zero-drift trust encoding) |
| **Industry guides** | DO-254, ISO 26262, IEC 61508 mapping |

---

## The Contrast

| | Floating Point | Constraint Theory |
|---|---|---|
| Result | Approximately correct | Provably correct or provably wrong |
| Failure mode | Silent (NaN, drift, wrap) | Loud (violation at design time) |
| Example | `0.1 + 0.2 ≠ 0.3` | `battery_temp ∈ [15, 55]` ✓ or ⊗ |

---

## Quick Start

```bash
# Install the GUARD CLI
cargo install guard-lang

# Write your first constraint
echo 'battery_temp in [15, 55] °C with priority HIGH' > battery.guard

# Compile + generate proof
guard compile battery.guard --output battery.fbc --proof battery.v
```

Try it live at [cocapn.ai/certify](https://cocapn.ai/certify)

---

## Chapters

- **Ch 0** — The Constraint Mindset *(you're already doing this)*
- **Ch 1** — Why Software Gets Constraints Wrong *(floating point is the problem)*
- **Ch 2** — GUARD DSL *(the language for exact constraints)*
- **Ch 3** — FLUX-C Bytecode *(43 opcodes, termination guaranteed)*
- **Ch 4** — Formal Verification *(Coq proof chain)*
- **Ch 5** — Safety-Critical Applications *(DO-254, ISO 26262, IEC 61508)*
- **Ch 6** — Fleet Math *(ZHC, H¹, Pythagorean48)*
- **Ch 7** — Getting Started *(install, write, certify)*
- **Ch 8** — GPU Architecture *(62B checks/sec on a $300 GPU)*

---

## The Insight in One Sentence

> GUARD DSL is **digital GD&T for software** — a formal language that specifies exact acceptable zones, compiles to verified bytecode, and produces proof certificates that auditors can independently verify.

---

## Status

- **SPEC.md** — This document (canonical description of the ecosystem)
- **chapters/** — 7 chapters, all drafted
- **crates/guard-lang** — GUARD DSL parser + compiler
- **crates/flux-vm** — FLUX-C reference VM
- **Live at:** [cocapn.ai/certify](https://cocapn.ai/certify)
