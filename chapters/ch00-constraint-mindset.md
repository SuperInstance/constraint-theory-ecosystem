# Chapter 0 — The Constraint Mindset

> **You are already a constraint theorist. You just haven't called it that.**

---

## The One Idea That Makes This Whole Thing Click

Every time you've calculated a **tolerance stack**, you've composed constraints.  
Every time you've specified an **interference fit**, you've written a constraint inequality.  
Every time you've watched an **O-ring seat** and decided yes or no — you've performed a constraint satisfaction check.

The math is the same. The language is different.

---

## Quick Start

**You need:** 5 minutes  
**You need to know:** nothing new — just recognize what you already do

---

## Example 1: The Tolerance Stack

You have three components:
- A: 10.000 ±0.005 mm
- B: 5.000 ±0.005 mm
- C: 5.000 ±0.005 mm

They stack into a housing: **20.000 ±0.020 mm**

**The constraint check:**

```
Min(A+B+C) = 19.985 mm  ✓  (≥ 19.980 minimum)
Max(A+B+C) = 20.015 mm  ✓  (≤ 20.020 maximum)
```

The stack **always** fits. Not "probably." Not "usually." Either yes or no.

This is **constraint satisfaction.** No probabilities. No "close enough."

---

## Example 2: The Interference Fit

Shaft: Ø10.000 mm. Bore: Ø9.995 mm.

```
Interference = 9.995 − 10.000 = −0.005 mm  (PRESS fit)
```

If the spec says "interference must be between −0.010 and −0.002 mm":
- −0.005 is **within spec** → use hydraulic press
- −0.015 is **out of spec** → machined wrong, reject it

**Either the fit works or it doesn't.** There's no "maybe."

---

## Example 3: The O-Ring Gland

O-ring free height: 3.0 mm. Gland depth: 2.30 mm.

```
Squeeze = (3.0 − 2.30) / 3.0 = 23.3%
```

If the spec says "squeeze must be 15–25%":
- 23.3% is **within spec** → good seal
- 10% is **out of spec** → leak risk
- 30% is **out of spec** → O-ring extrusion risk

**The constraint is the spec.** The math tells you whether you meet it.

---

## The Floating Point Problem

Software doesn't work this way. It uses floating point:

```python
temp = sensor.read()  # might be 0.0, NaN, or -40.0
if 15 < temp < 55:
    enable_charging()
```

- `temp = NaN` → comparison returns **false** → charging never enables
- `temp = -40.0` (frozen sensor) → no alert, frozen battery tries to charge
- `temp = inf` → no alert, overflow propagates silently

**Hardware engineer response:** "That sensor is reading out of its valid range — it should be rejected before the check."

**Software engineer response:** "Works on my machine."

---

## The Constraint Mindset — Defined

| Hardware Engineer | Constraint Theorist |
|---|---|
| "Does it fit the tolerance zone?" | "Does it satisfy the constraint?" |
| O-ring squeeze 15–25% | `squeeze ∈ [0.15, 0.25]` |
| Interference fit −0.010 to −0.002 | `interference ∈ [-0.010, -0.002]` |
| Pressure rating 4× working | `burst_pressure ≥ 4 × working_pressure` |

**Same thinking. Same math. Software just never got the formal vocabulary.**

---

## What This Book Gives You

1. **The vocabulary** — formal names for what you already do
2. **The language** — GUARD DSL (write constraints in code, the way you specify them on paper)
3. **The proof** — Coq machine-checked certificates that your constraints are satisfied
4. **The math** — Laman's theorem, H¹ cohomology, Pythagorean48 (fleet coordination from geometry, not voting)

---

## Key Insight

The gap between hardware and software constraint thinking is not intelligence. It's that hardware engineers learned to work with **hard boundaries** — parts either fit or they don't. Software learned to work with **approximations** — results are "close enough" until they're catastrophically wrong.

**Constraint theory makes software engineering as rigorous as hardware engineering.** The tolerance zones are the same. The math is the same. Now the language is too.

---

## Next: Why Software Gets Constraints Wrong

Chapters 1–3 show exactly why floating point fails constraint satisfaction — and how GUARD DSL fixes it. Start wherever you want. Chapters are independent.
