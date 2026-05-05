# Chapter 0 — The Constraint Mindset

> **What You Already Know**

---

## You Are Already a Constraint Theorist

You've been doing constraint theory your entire career. You just haven't called it that.

Every time you've calculated a **tolerance stack**, you've composed constraints. Every time you've specified an **interference fit**, you've written a constraint inequality. Every time you've watched an **o-ring seat** and decided yes or no — you've performed a constraint satisfaction check.

The math is the same. The language is different.

---

## Example 1: The Tolerance Stack

You have three components with dimensions:
- A: 10.000 ±0.005 mm
- B: 5.000 ±0.005 mm
- C: 5.000 ±0.005 mm

They stack into a housing with a specification:
- Total length: 20.000 ±0.020 mm

**The constraint:** Does the stack fit?

**Math:**
```
Min(A+B+C) = (10.000-0.005) + (5.000-0.005) + (5.000-0.005) = 19.985 mm
Max(A+B+C) = (10.000+0.005) + (5.000+0.005) + (5.000+0.005) = 20.015 mm

Acceptable range: [19.980, 20.020] mm

Is 19.985 >= 19.980? Yes.
Is 20.015 <= 20.020? Yes.

Therefore: the stack ALWAYS fits, regardless of component variation.
```

This is **compositional constraint satisfaction**. The constraint (total length within tolerance) is satisfied if and only if all sub-constraints (individual dimensions within tolerance) are satisfied. No probabilities. No "probably fits." Either the answer is yes or the answer is no.

---

## Example 2: The Interference Fit

You want to press a steel shaft into a housing bore. You specify:
- Shaft diameter: 10.000 mm
- Bore diameter: 9.995 mm
- Interference: 0.005 mm (5 micrometers)

**The constraint:** Will the assembly hold without additional fasteners?

**Engineering decision:**
- Friction coefficient (steel-on-steel, dry): μ ≈ 0.15–0.25
- Contact pressure from interference: P = 2Eδ/(d × (1 - ν²)) × (d/d_inner)... [formula from machinery's handbook]
- Clamping force must exceed operating torque

**The constraint check:**
```
GUARD interference_fit(
    shaft_diameter >= bore_diameter,        # must be interference
    shaft_diameter <= bore_diameter + 0.020, # cannot be too tight
    clamping_force > operating_torque / (μ * contact_radius)  # must not slip
)
```

If all three constraints are satisfied simultaneously → the fit holds. If any one fails → catastrophic failure (shaft slips under load).

There is no floating point tolerance here. The o-ring either seals or it doesn't. The shaft either holds or it slips.

---

## Example 3: The O-Ring Seal

You have a hydraulic fitting with an o-ring groove:
- O-ring nominal ID: 10.0 mm
- Groove diameter: 11.0 mm
- O-ring cross-section: 2.0 mm
- Specified squeeze: 15–25%

**The constraint:**
```
squeeze = (groove_width - o_ring_cs) / o_ring_cs
GUARD squeeze in [0.15, 0.25]
```

Below 15% squeeze: the o-ring leaks (not enough compression to fill the groove geometry).
Above 25% squeeze: the o-ring extrudes (over-compression damages the seal material).

15–25% is not a recommendation. It's a **hard constraint boundary**. Outside the boundary → catastrophic hydraulic failure.

This is what safety engineers call a **catastrophic failure mode** — the system doesn't degrade gracefully, it fails suddenly and completely.

Software engineers would call this an **assertion failure**. Except most software doesn't have assertions for physical failure modes.

---

## Example 4: The Pressure Rating

A hydraulic cylinder has:
- Working pressure: 3,000 psi (207 bar)
- Proof pressure (test): 1.5× working = 4,500 psi
- Burst pressure: 4× working = 12,000 psi (theoretical minimum — actual parts burst higher)

**The constraints:**
```
GUARD working_pressure <= 3000 psi * 0.80      # 80% derating factor
GUARD proof_pressure <= 4500 psi * 0.90       # 90% of test pressure
GUARD pressure_fatigue_cycles < max_cycles    # no infinite cycling
```

Notice the **safety factor** in the constraint specification. The 80% derating isn't "to make the engineer feel safe." It's an **over-constraint margin** that accounts for:
- Measurement uncertainty (pressure gauge error ±2%)
- Material property variation (heat treatment lot differences)
- Dynamic pressure spikes (valve transient, pump surge)
- Temperature effects (thermal expansion changes clearance)

**Safety factor is a constraint margin.** It exists because we know our constraints are wrong — we just don't know by how much.

---

## The Bridge to Software

Here is what all four examples have in common:

1. **Bounded variables** — Every value has a physically meaningful range. A shaft can't be negative diameter. Pressure can't be below vacuum (well, it can, but you know what we mean).

2. **Boolean outcomes** — Either the constraint is satisfied or it isn't. Either the o-ring seals or it doesn't. Either the stack fits or it doesn't.

3. **Catastrophic failure modes** — Constraint violations don't produce "close enough" results. They produce **failure**. The o-ring doesn't "mostly seal."

4. **Composition** — Complex constraints are built from simple ones. The tolerance stack is a SUM of bounded variables. The interference fit is an AND of geometric and force constraints.

5. **No approximation** — Real engineering uses exact tolerances. The hole is 10.000mm ±0.005mm. Not "approximately 10mm." The tolerance IS the specification.

Software has none of these properties by default:
- Integers overflow silently
- Floats propagate NaN and lose precision
- Booleans don't compose cleanly (null, undefined, three-valued logic)
- Failure modes are often silent or poorly defined

**This is the gap that constraint theory fills.** It brings the rigor of physical engineering to software.

---

## What Comes Next

The rest of this ecosystem explains how to bring that rigor to software:

- **Chapter 1:** Why software gets constraints wrong (and why floating point is the root cause)
- **Chapter 2:** GUARD DSL — a constraint language as precise as GD&T
- **Chapter 3:** FLUX-C bytecode — how constraints execute as verifiable machine code
- **Chapter 4:** Formal verification — Coq proofs that constraints terminate and produce correct results
- **Chapter 5:** Safety-critical applications — DO-254, ISO 26262, IEC 61508
- **Chapter 6:** The fleet math — ZHC, H1, Pythagorean48

---

## Key Takeaway

If you've ever said any of the following, you already think in constraints:

- "The tolerance stack won't close unless we use a tighter spec on B"
- "That interference is too tight — the housing will crack during assembly"
- "The o-ring squeeze is wrong — it'll leak at 5,000 psi"
- "The safety factor is too thin for a safety-critical application"
- "We need a burst pressure of 3× working pressure"

**Constraint theory is formalizing the math you already do in your head.** The rest of this ecosystem shows you how to make software do the same.

---

*Next: [Chapter 1 — Why Software Gets Constraints Wrong](ch01-why-software-fails.md)*