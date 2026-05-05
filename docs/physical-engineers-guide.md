# Part I: The Physical Engineer's Guide to Constraint Theory

*Read this first. No code required. 15 minutes.*

---

## 1. You Already Think in Constraints

If you design hydraulic fittings, you already work with constraints every day:

- **O-ring groove depth** must be `0.055 ± 0.003"` — too shallow and the ring shears, too deep and it doesn't compress
- **Bolt torque** must be `45 ± 5 ft-lbs` — under-torqued leaks, over-torqued yields the threads
- **Surface finish** on a sealing face must be `Ra 32 μin` or better — any rougher and the seal weeps

These are **constraints**. You already specify them on drawings with GD&T callouts, tolerance stacks, and fit tables. The question isn't whether constraints exist — it's whether the **software controlling your system** respects them.

---

## 2. The Rubber Ruler Problem

Imagine measuring a hydraulic fitting's bore diameter with a ruler made of rubber. You measure 1.250". But the ruler stretches:
- On Monday, 1.250" is actually 1.248"
- On Tuesday, 1.250" is actually 1.253"
- On Wednesday, 1.250" could be anywhere from 1.245" to 1.255"

You'd throw that ruler away. But that's exactly what **floating-point arithmetic** does in software:

```
Actual:  0.1 + 0.2 = 0.3
Float:   0.1 + 0.2 = 0.30000000000000004
```

For a hydraulic seal with 15% compression tolerance, 0.00000000000000004 doesn't matter. But when software **accumulates** that error across 10,000 calculations in a control loop:

```
Float:  (a + b) + c ≠ a + (b + c)    // non-associative!
Float:  x * (y + z) ≠ x*y + x*z      // non-distributive!
Float:  if (a == a) → FALSE           // NaN != NaN
```

**In physical engineering, this would be a defective measuring instrument.** In software, it's called "IEEE 754" and it's the standard.

---

## 3. Tolerance Stacks — The Software Version

You know how a tolerance stack works. Given three parts in series, each with ±0.005" tolerance:

```
Worst case:   +0.015" or -0.015" total
RSS:           ±√(0.005² + 0.005² + 0.005²) = ±0.0087"
Statistical:   99.7% within ±0.0087" (3σ)
```

Software does the same thing, but invisible. Every arithmetic operation has a tolerance of ±0.5 ULP (unit in the last place). After N operations, the error stack is:

```
Float error after N ops ≈ N × 0.5 ULP × machine_epsilon
```

For a 32-bit float (FP32), machine_epsilon ≈ 1.2×10⁻⁷. After a million operations — common in a control loop — your accumulated error is:

```
10⁶ × 0.5 × 1.2×10⁻⁷ ≈ 0.06  (6% drift)
```

**Would you accept a 6% tolerance stack on a hydraulic fitting?** Of course not. But that's what FP32 gives you after a million operations.

---

## 4. The INT8 Solution — Like Using Gauge Blocks

In metrology, you use gauge blocks because they have **known, exact dimensions**. 1.0000" ± 0.000005". No rubber rulers.

**INT8 arithmetic is the gauge block of computing:**

| Property | Float (FP32) | Float (FP16) | INT8 (Saturated) |
|----------|-------------|-------------|------------------|
| Range | ±3.4×10³⁸ | ±65,504 | [-127, 127] |
| Precision | 7 digits | 3 digits | **Exact** |
| 5 + 3 = ? | 8.0000001 | 8.0 | **8** |
| Accumulated error | Grows | Grows fast | **Zero** |
| Associative? | No | No | **Yes** |
| NaN possible? | Yes | Yes | **No** |
| Overflow? | ±Inf | ±Inf | **Saturates** |

INT8 values from -127 to 127 cover most physical constraints:
- Temperature: -55°C to +70°C (aviation cabin) ✅
- Pressure: 0 to 100 bar (hydraulic) — scale by /1 ✅
- Flow rate: 0 to 100% ✅
- Vibration: 0 to 50 mm/s ✅
- Position: ±127mm or ±12.7cm (scale) ✅

The key insight: **safety constraints don't need floating point**. "Is the temperature between -55 and 70?" is a **boolean** question with **integer** bounds.

---

## 5. O-Ring Compression — A Worked Example

An AS568-214 O-ring in a hydraulic fitting:

| Parameter | Min | Nominal | Max | Unit |
|-----------|-----|---------|-----|------|
| O-ring cross-section | 0.133 | 0.139 | 0.145 | in |
| Groove depth | 0.104 | 0.107 | 0.110 | in |
| Groove width | 0.140 | 0.145 | 0.150 | in |
| Squeeze (calc) | 19.9% | 23.0% | 27.6% | % |
| Recommended squeeze | 15% | 20% | 25% | % |

**Constraint: `squeeze in [15, 25]`**

In GUARD (our constraint language):
```
GUARD o_ring_squeeze in [15, 25]
  WHERE squeeze = (1 - groove_depth / cross_section) * 100
```

In FLUX-C bytecode (what the GPU executes):
```
PUSH_CONST 15        ; min squeeze %
LOAD_REF squeeze      ; calculated squeeze
RANGE_CHECK 15, 25   ; boolean: pass or fail
HALT
```

**No float. No NaN. No Inf.** Just: is the value between 15 and 25? Yes or no.

The GPU evaluates this at **62.2 billion constraints per second**. That's 62 billion O-ring checks per second. Every single one is bit-exact.

---

## 6. Why Saturation Matters (The -128 Problem)

Standard INT8 has range [-128, 127]. That -128 is a land mine:

```
-(-128) = -128    // Negation wraps around!
```

In physical terms, imagine a torque wrench that reads -128 ft-lbs. You try to negate it (reverse direction) and it still reads -128. **Your wrench is broken.**

Our solution: **saturate to [-127, 127]**. No -128. Negation is always correct:

```
-(-127) = 127    ✓
-(0) = 0          ✓  
-(127) = -127     ✓
```

This is mathematically proven (7 Coq theorems). The saturation function is:
```
saturate(x) = max(-127, min(127, x))
```

Like a torque wrench that caps at its maximum reading instead of wrapping around.

---

## 7. The Galois Connection — Compiler Correctness

In GD&T, there's a formal relationship between the tolerance specification on the drawing and the actual manufactured part. The specification **constrains** the part.

We have the same thing between GUARD (the specification) and FLUX-C (the execution):

```
GUARD specification  ⟷  FLUX-C execution
    (what you want)         (what you get)
```

This is a **Galois connection** — a mathematical relationship that guarantees:
1. Every GUARD constraint compiles to a correct FLUX-C program
2. Every FLUX-C result correctly reflects the GUARD constraint
3. No information is lost in translation

**In physical terms:** the drawing spec and the manufactured part are in perfect agreement. The CMM (coordinate measuring machine) reading matches the GD&T callout. Always.

We proved this with 30 English proofs and 8 Coq theorems. The compiler is mathematically certified correct.

---

## 8. What This Means For You

| Your World | Constraint Theory |
|-----------|-------------------|
| Tolerance stack | Constraint stack — same math, zero error |
| GD&T callout | GUARD constraint — same idea, machine-readable |
| Go/No-Go gauge | FLUX-C range check — same boolean, 62B/sec |
| CMM inspection | Bytecode verification — same traceability, automated |
| AS9100 audit | DO-178C/254 certification — same rigor, proof artifacts |

**The constraint is the point.** You've known this your entire career. We just gave it math, code, and proof.

---

*Next: [Part II — The GPU Architecture](../chapters/ch08-gpu-architecture.md) → How we check 62 billion constraints per second on a laptop GPU.*

*Back: [README](../README.md) → Overview and getting started.*
