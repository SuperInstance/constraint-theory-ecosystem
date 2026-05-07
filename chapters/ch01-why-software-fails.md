# Chapter 1 — Why Software Gets Constraints Wrong

> **The Floating Point Problem**

---

## Quick Start

**You need:** 5 minutes, Python

The problem: floating point has special values (NaN, ±∞) that bypass normal comparisons. See it fail:

```python
import math

temp = float('nan')
if 15 < temp < 55:
    print("Charging enabled")  # NEVER runs — NaN comparisons always return False
else:
    print("Charging blocked")  # Runs — but NaN doesn't mean "cold"!

# Another failure mode:
temp = -40.0  # frozen sensor reads -40, passes the check silently
```

The fix: use constraint DSL that validates inputs before comparison (Chapter 2).

---

## The Story Every Engineer Has

You're writing code for an industrial controller. Temperature sensor reads `temp = 23.4567`. You write:

```c
if (temp > 15.0 && temp < 55.0) {
    enable_charging();
}
```

Looks fine. Works fine. Until one day in January in Minnesota, the sensor freezes, returns `-40.0`, and the charger tries to charge a frozen battery. Or the sensor fails short, returns `0.0`, and the charger tries to charge a dead battery. Or the sensor fails open and returns `NaN` — and every comparison with `NaN` is false, so charging never enables even with a perfect battery at room temperature.

What happened? The code **assumed** `temp` was a real number. It wasn't. It was a floating point approximation of a real number — with special values for error states.

---

## The Four Failure Modes of Floating Point

### 1. NaN — Not a Number

`NaN` is the result of invalid operations:
- `sqrt(-1.0)` → NaN
- `0.0 / 0.0` → NaN
- `inf - inf` → NaN

**The critical property:**
```c
NaN != NaN  // This is TRUE
```

Every comparison with NaN returns **false**, including `NaN != NaN` — which is true, but not in the way you want.

```c
if (temp > 15.0 && temp < 55.0) {
    enable_charging();  // Never runs if temp is NaN
}
// temp is NaN: (NaN > 15.0) is false
// (NaN < 55.0) is false
// false && false = false
```

**In constraint terms:** NaN violates the constraint `temp ∈ ℝ`. But instead of failing loudly, it propagates silently until the system does something unexpected.

### 2. Integer Overflow — The Wraparound

```c
int32_t speed = 2147483647;  // INT_MAX
speed += 1;                  // speed = -2147483648 (INT_MIN)
// If speed controls throttle, the engine suddenly goes full reverse
```

C and Rust define integer overflow as **undefined behavior** in release mode. The compiler is allowed to assume it never happens — and optimize accordingly. Sometimes it wraps. Sometimes it traps. Sometimes it does nothing. The C standard says "undefined" means exactly that.

**Constraint theory says:** The variable has a bounded domain. If the bound is violated, the system must fail — not wrap, not trap, not silently corrupt.

```
GUARD speed >= 0 AND speed <= 200
// If speed reaches INT_MAX and overflows:
// the constraint is violated → system fails predictably
// NOT: speed wraps to -2147483648 → throttle goes full reverse
```

### 3. Floating Point Non-Transitivity

```python
>>> a, b, c = 0.1, 0.2, 0.3
>>> (a + b) + c == a + (b + c)
False
>>> a + b + c
0.5999999999999999
>>> a + (b + c)
0.6
```

This isn't a bug in Python. It's the nature of IEEE 754 floating point: `(a ⊕ b) ⊕ c ≠ a ⊕ (b ⊕ c)` in general, where `⊕` is floating point addition.

For constraint systems, this means:
```python
# Constraint: x + y + z <= 100
# Implementation:
constraint = (x + y) + z <= 100   # False sometimes
constraint = x + (y + z) <= 100   # True sometimes (different result!)
```

**The constraint is not well-defined under floating point.** The order of operations changes whether it's satisfied.

### 4. The Comparison Trap — Why `==` Is Dangerous

```python
# Everyone's favorite interview problem
result = 0.1 + 0.2
print(result)  # 0.30000000000000004
print(result == 0.3)  # False
print(abs(result - 0.3) < 1e-10)  # True (but requires knowing the tolerance)
```

**In constraint terms:** The constraint `result == 0.3` is **provably unsatisfiable under floating point**, even though the intent was `result ≈ 0.3`.

---

## The Root Cause: Continuous Approximation for Discrete Constraints

Floating point was designed to approximate **continuous quantities** — lengths, temperatures, pressures — where "close enough" is acceptable. That's the right tool for physics simulations and graphics.

But constraint satisfaction is **discrete**. The battery temperature either is in [15°C, 55°C] or it isn't. The throttle position either is in [0, 100]% or it isn't. The o-ring squeeze either is in [15%, 25%] or it isn't.

**There is no "close enough."** Either the constraint is satisfied or the system fails.

The mismatch is fundamental:
- Floating point: "What's the approximate value of π?" → 3.141592653589793
- Constraint theory: "Is x in [0, 1]?" → TRUE or FALSE, exactly

---

## What Constraint Theory Provides Instead

### Exact Arithmetic

Constraint theory uses **bounded integer arithmetic** or **exact rational arithmetic**. No NaN. No infinity. No overflow (bounds checked explicitly).

```
GUARD battery_temp in [15, 55]
GUARD shaft_diameter in [9.999, 10.020]
GUARD squeeze_ratio in [0.15, 0.25]
```

Every variable has an explicit domain. Every constraint has a precise satisfiability condition. No approximation.

### Boolean Outcomes

Constraint satisfaction is **boolean**: SATISFIED or UNSATISFIED. No "probably satisfied." No "approximately violated."

```coq
Theorem constraint_satisfied:
  forall (c: constraint) (v: valuation),
    sat c v = true \/ sat c v = false
```
"There is no third option. The constraint is either satisfied or violated."

### Explicit Failure Modes

When a constraint is violated, the system fails **predictably and loudly**. No silent corruption. No NaN propagation. No wraparound.

```
Constraint violation:
  battery_temp = 56 → constraint "battery_temp in [15, 55]" violated
  → FAIL: battery_temp_exceeded → safe state → diagnostic logged
  → NOT: silent charging continues → battery thermal runaway
```

---

## The Constraint-Theoretic Fix

### Floating Point Version (Broken)

```python
def check_battery_temp(temp: float) -> None:
    if temp > 15 and temp < 55:
        enable_charging()
    else:
        disable_charging()
# NaN: never enables (NaN > 15 is False)
# Overflow: unpredictable
# Non-transitivity: not applicable here but other operations fail
```

### Constraint-Theoretic Version (Correct)

```python
from guard_dsl import *

def check_battery_temp(temp: float) -> None:
    constraint = AND(
        GTE(temp, 15),   # temp >= 15
        LTE(temp, 55)    # temp <= 55
    )
    
    if is_satisfied(constraint, {"temp": temp}):
        enable_charging()
    else:
        disable_charging()
        log_violation("battery_temp", temp, "15 <= temp <= 55")

# NaN: is_satisfied returns False (NaN violates GTE constraint)
# Overflow: would require temp to exceed explicit bounds → already fails
# Non-transitivity: GTE and LTE are transitive by definition
```

### The Real FLUX-C Version (Verified)

```c
; FLUX-C bytecode for battery temperature constraint
; Generated by: guard compile "battery_temp in [15, 55]"
; Verified by: Coq/FLUXC.v theorem fluxc_terminates

section .text

check_battery_temp:
    vxorpd   %xmm0, %xmm0        ; zero xmm0
    vcmpgtd  .lower_15(%rip), %xmm1, %xmm2    ; temp >= 15? (all lanes)
    vcmpgtd  .upper_55(%rip), %xmm1, %xmm3   ; temp <= 55? (all lanes)
    vpand    %xmm2, %xmm3, %xmm4            ; both satisfied?
    vmovd    %xmm4, %eax
    test     %eax, %eax
    jz       constraint_violated
    ret

constraint_violated:
    ; Coq-verified safe shutdown sequence
    call     safe_shutdown
    ud2       ; invalid instruction — forces crash, not continue
```

The `ud2` at the end is intentional. If the constraint is violated, the program **crashes predictably** rather than continuing in an invalid state. For safety-critical systems, continuing with invalid state is never an option.

---

## Summary: The Four Properties

| Property | Floating Point | Constraint Theory |
|----------|---------------|------------------|
| NaN handling | Propagates silently | Explicit domain violation → FALSE |
| Overflow | Undefined behavior | Explicit bounds check → FAIL |
| Approximation | "Close enough" | Boolean satisfaction |
| Failure mode | Silent corruption | Predictable crash with diagnostic |

---

## When Floating Point Is Fine

Floating point is the right tool when:
- The quantity is inherently continuous (position, velocity, temperature)
- Approximation is acceptable (graphics, physics simulation, signal processing)
- Probability distributions are involved (Monte Carlo, statistics)
- "Close enough" is acceptable and the failure mode is benign

Floating point is the **wrong tool** when:
- The quantity has a hard physical boundary (pressure > burst = catastrophic failure)
- The failure mode is silent (battery overcharge → thermal runaway)
- The system must be provably correct for regulatory compliance

---

## Key Takeaway

The floating point model — "approximate the real numbers, hope for no NaN, check for overflow occasionally" — is incompatible with safety-critical constraint satisfaction. Hardware engineers already know this. They specify tolerances, not "approximately this value." They design for catastrophic failure modes, not graceful degradation.

Constraint theory brings the same rigor to software. The math is the same. The stakes are the same. The only difference is the notation.

---

*Next: [Chapter 2 — GUARD DSL: A Language for Exact Constraints](ch02-guard-dsl.md)*