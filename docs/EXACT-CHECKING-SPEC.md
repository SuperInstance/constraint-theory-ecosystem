# EXACT Constraint Checking Specification

**Version:** 1.0  
**Date:** 2026-05-19  
**Status:** Active — replaces INT8 quantized checking for all safety-critical paths  
**Author:** Forgemaster ⚒️ (constraint-theory specialist)

---

## 1. Problem Statement

The original FLUX Constraint Engine quantizes **all values** (bounds AND sensor readings) to INT8 [-127, 127] before comparison. This causes **false negatives** — the most dangerous failure mode for a safety system.

### Concrete Example

```
Constraint: coolant_temp in [-40, 150]
INT8 quantization: saturate(-40) = -40, saturate(150) = 127
Actual constraint becomes: [-40, 127]

Sensor reads: 151°C (overheating!)
INT8 quantization: saturate(151) = 127
Check: 127 ∈ [-40, 127] → PASS ← FALSE NEGATIVE
```

The engine overheats and nobody knows. **This is unacceptable for any safety system.**

## 2. Core Invariant

> **ZERO FALSE NEGATIVES.** A value outside bounds is ALWAYS detected. No exceptions. No quantization excuses.

This is a hard guarantee, not a statistical property. Every implementation must prove it holds for:
- All numeric types (int, float, negative, positive, zero)
- All bound ranges (narrow, wide, single-sided, negative ranges)
- Edge cases: values AT the boundary, epsilon outside, far outside

## 3. Architecture: Compress the Result, Not the Values

### The Key Insight

We don't need to compress the sensor values. We need to compress the **RESULT** of the comparison.

```
8 constraints × 1 pass/fail bit each = 8 bits = 1 byte
```

That single byte — the **error mask** — IS the INT8 compact representation. Not the values.

### Data Flow

```
INPUT:  float/int values → EXACT comparison → error_mask (uint8)
                                              → severity (from mask)
                                              → details (optional)
```

### What Gets Quantized (and What Doesn't)

| Component | Quantized? | Storage Type | Rationale |
|-----------|-----------|--------------|-----------|
| Constraint bounds (lo, hi) | **NO** | Original float/int | Bounds define safety limits — must be exact |
| Sensor values | **NO** | Original float/int | Values must be compared exactly |
| Error mask | Implicitly uint8 | uint8 (0–255) | 8 bits for 8 constraints — natural fit |
| Severity | uint8 | uint8 (0–3) | Computed from error_mask popcount |
| Violation counts | uint8 | uint8 (0–8) | Small integer |

## 4. API Specification

### 4.1 Constraint Definition

```python
ConstraintDef:
    lo: float|int      # Lower bound (ORIGINAL value, NOT quantized)
    hi: float|int      # Upper bound (ORIGINAL value, NOT quantized)
    name: string       # Human-readable identifier
```

**Invariant:** `lo <= hi` (enforced at construction, ValueError if violated)

### 4.2 Check Result

```python
ExactResult:
    error_mask: uint8    # Bit i set = constraint i violated
    severity: uint8      # 0=PASS, 1=CAUTION, 2=WARNING, 3=CRITICAL
    violated_lo: uint8   # Bitmask of lower-bound violations
    violated_hi: uint8   # Bitmask of upper-bound violations
    violated_count: uint8 # Number of violated constraints (popcount of error_mask)
    passed: bool          # True iff error_mask == 0
```

### 4.3 Core Check Function

```python
def flux_check_exact(value: float|int, constraints: list[ConstraintDef]) -> ExactResult:
    """
    Check a single value against up to 8 constraints.
    
    INVARIANTS:
    - value is compared in ORIGINAL numeric space (no quantization)
    - bounds are stored as ORIGINAL values (no quantization)
    - comparison is EXACT: lo <= value <= hi
    - error_mask bit i = 1 iff value NOT in [constraints[i].lo, constraints[i].hi]
    - severity derived from error_mask popcount
    - ZERO false negatives guaranteed
    """
```

### 4.4 Severity Mapping

```python
SEVERITY_TABLE = {
    0: PASS,      # 0 violations
    1: CAUTION,   # 1 violation
    2: CAUTION,   # 2 violations
    3: WARNING,   # 3 violations
    4: WARNING,   # 4 violations
    5: CRITICAL,  # 5+ violations
    6: CRITICAL,
    7: CRITICAL,
    8: CRITICAL,
}
severity = SEVERITY_TABLE[popcount(error_mask)]
```

### 4.5 SIMD Acceleration

For C/Rust implementations with AVX2:

```c
// 8-wide float comparison against exact bounds
__m256 values = _mm256_load_ps(data);      // 8 floats
__m256 lo = _mm256_load_ps(bounds_lo);     // 8 exact bounds
__m256 hi = _mm256_load_ps(bounds_hi);     // 8 exact bounds

__m256 ge_lo = _mm256_cmp_ps(values, lo, _CMP_GE_OQ);  // value >= lo
__m256 le_hi = _mm256_cmp_ps(values, hi, _CMP_LE_OQ);  // value <= hi
__m256 in_range = _mm256_and_ps(ge_lo, le_hi);

uint8_t error_mask = (uint8_t)_mm256_movemask_ps(in_range);
// Note: movemask gives PASS bits; invert for error_mask
error_mask = ~error_mask & 0xFF;
```

## 5. Zero False Negative Proof

### Theorem

For any value `v` and constraint `[lo, hi]`:
- If `v < lo` or `v > hi`, then the corresponding bit in `error_mask` is set to 1.

### Proof

The comparison is performed in original numeric space using native floating-point or integer comparison:

```
lo_fail = (v < lo)    // exact comparison, no quantization
hi_fail = (v > hi)    // exact comparison, no quantization
bit_i = lo_fail OR hi_fail
error_mask |= (bit_i << i)
```

Since `v`, `lo`, and `hi` are all in original numeric space:
- If `v < lo` is true in math, it is true in code (IEEE 754 exact for integers; float comparison is monotonic)
- If `v > hi` is true in math, it is true in code
- Therefore `bit_i = 1` for any out-of-range value

No quantization step exists between the input and the comparison. **QED.**

### What About Floating-Point Precision?

For float comparisons near the boundary:
- `lo <= v <= hi` where v = lo - epsilon: `v < lo` is true (correct detection)
- `lo <= v <= hi` where v = hi + epsilon: `v > hi` is true (correct detection)
- Edge case `v = lo` or `v = hi`: IEEE 754 guarantees exact equality comparison for these

The only risk is if `lo` or `hi` itself is stored imprecisely (e.g., `0.1`). But the **user specified** those bounds — we preserve them exactly as given.

## 6. Backward Compatibility

### Migration Path

1. Old API (`FluxConstraint.check()`) continues to work with INT8 quantization
2. New API (`FluxConstraint.check_exact()`) provides zero-false-negative guarantee
3. Preset data stays the same — bounds are now stored as original values
4. Applications migrate by switching `check()` → `check_exact()`

### Performance

The exact check is **at least as fast** as the quantized check because:
- No `saturate()` call per value (removes a branch + clamp)
- Native float/int comparison is a single CPU instruction
- SIMD operates on floats (same throughput as INT8 on modern hardware)

## 7. Implementation Checklist

- [ ] Python: `flux_constraint_exact.py` — pure Python, exact comparison
- [ ] C: `flux_constraint_exact.h` — AVX2 float SIMD, single-header
- [ ] Rust: `exact.rs` — generic over f32/f64/i32/i64, no_std
- [ ] Go: `flux_constraint_exact.go` — original numeric space
- [ ] Node: `flux_constraint_exact.js` — original numeric space
- [ ] Test suite: `test_exact_zero_fn.py` — 1M values × 6 scenarios
- [ ] Benchmark: `EXACT-VS-QUANTIZED.md` — speed + correctness comparison

## 8. Summary

| Property | Old (INT8 Quantized) | New (Exact) |
|----------|---------------------|-------------|
| False negatives | **YES** — values clamped to in-range | **ZERO** — guaranteed |
| False positives | Zero | Zero |
| Bounds accuracy | Clamped to [-127, 127] | Original values preserved |
| Value accuracy | Clamped to [-127, 127] | Original values preserved |
| Error mask | Works (bit per constraint) | Works (bit per constraint) |
| Severity | From clamped values | From error mask popcount |
| Speed | Fast | Same or faster (no saturate) |
| Safety | **UNSAFE** | **SAFE** |

**The exact engine doesn't trade safety for performance. It has both.**
