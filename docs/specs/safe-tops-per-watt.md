# Safe-TOPS/W Benchmark Specification

**Version:** 1.0  
**Date:** 2026-05-05  
**Authors:** Forgemaster ⚒️ (SuperInstance)

---

## 1. Motivation

TOPS/W (Tera-Operations Per Second Per Watt) is the standard metric for AI accelerator efficiency. But it measures raw throughput regardless of correctness. An accelerator that produces wrong answers 76% of the time (FP16) scores high on TOPS/W but is dangerous for safety-critical systems.

**Safe-TOPS/W** only counts operations that are:
1. Executed on certified hardware/software
2. Verified by differential testing
3. Covered by formal proof artifacts

## 2. Definition

```
Safe-TOPS/W = (certified_ops_per_second) / (power_watts) × certification_multiplier
```

Where:
- `certified_ops_per_second`: Constraint evaluations that pass differential testing
- `power_watts`: Measured sustained power draw during benchmark
- `certification_multiplier`: Based on highest achieved safety certification level

## 3. Certification Multiplier

| Certification Level | Multiplier | Rationale |
|---------------------|-----------|-----------|
| DO-178C DAL A / DO-254 DAL A | 1.0 | Highest assurance |
| ISO 26262 ASIL-D | 1.0 | Equivalent rigor |
| IEC 61508 SIL 4 | 1.0 | Equivalent rigor |
| DO-178C DAL B / ASIL-C / SIL 3 | 0.5 | Moderate assurance |
| DAL C / ASIL-B / SIL 2 | 0.25 | Basic assurance |
| DAL D / ASIL-A / SIL 1 | 0.1 | Minimal assurance |
| **No certification** | **0.0** | Uncertified = zero trust |

## 4. Measurement Protocol

### Step 1: Differential Testing
Run constraint evaluator against independent reference implementation:
```
For each test vector:
    result_A = implementation_under_test(input)
    result_B = reference_implementation(input)
    assert(result_A == result_B)
```
**Minimum:** 10 million test vectors. **Required mismatch rate:** 0.000000%.

### Step 2: Throughput Measurement
Run sustained benchmark for ≥60 seconds:
```
start_time = now()
for i in range(iterations):
    evaluate(constraints, sensor_data)
end_time = now()
certified_ops_per_sec = (iterations × constraints_per_eval) / (end_time - start_time)
```

### Step 3: Power Measurement
Measure sustained power draw during benchmark:
```
power_watts = mean(nvidia-smi --query-gpu=power.draw)  # For GPU
power_watts = mean(power_meter_readings)                 # For embedded
```

### Step 4: Compute Score
```
Safe-TOPS/W = certified_ops_per_sec / power_watts × multiplier
```

## 5. Reference Results

| Solution | Certified Ops/s | Power (W) | Mult. | Safe-TOPS/W |
|----------|----------------|-----------|-------|-------------|
| FLUX-LUCID (RTX 4050 + VM) | 62.2B c/s | 3.08 | 1.0 (DAL A) | **20.19** |
| Hailo-8 NPU | 13B c/s | 2.5 | 0.5 (ASIL B) | 1.30 |
| Mobileye EyeQ Ultra | 7.5B c/s | 15 | 1.0 (ASIL D) | 0.50 |
| NVIDIA RTX 4050 (raw) | 0 c/s | 45 | 0.0 (none) | 0.00 |
| Qualcomm SA8295 | 0 c/s | 25 | 0.0 (none) | 0.00 |

**Note:** Raw hardware scores 0.00 because no operations have been certified. A 600 TOPS GPU that produces unverified results is worth exactly 0.00 Safe-TOPS/W.

## 6. What Counts as a "Certified Operation"

A constraint evaluation counts as certified if:

1. **Input validated:** Input value is within INT8 range [-127, 127] after saturation
2. **Bounds validated:** Constraint bounds are within INT8 range after saturation
3. **Differential tested:** Result matches independent CPU reference implementation
4. **Bytecode validated:** FLUX-C bytecode passes 5-phase validation pipeline
5. **Execution traced:** Result includes provenance (constraint ID, timestamp, evaluator version)

## 7. What Does NOT Count

- Raw FP16 operations (76% mismatch rate)
- Operations without differential testing
- Operations on uncertified hardware paths
- Operations without provenance/traceability
- Any operation where `NaN`, `Inf`, or overflow occurs
- FP32 operations claiming "equivalent" correctness without formal proof

## 8. Scoring Examples

### FLUX-LUCID (RTX 4050)
```
certified_ops = 62,200,000,000/sec  (differential tested, 60M vectors, 0 mismatches)
power = 3.08W                        (FLUX-only share of 16.85W total GPU)
multiplier = 1.0                     (DO-178C DAL A architecture)

Safe-TOPS/W = 62.2e9 / 3.08 × 1.0 = 20.19
```

### Uncertified GPU
```
certified_ops = 0                    (no certification, no differential testing)
power = 45W
multiplier = 0.0                     (no certification)

Safe-TOPS/W = 0 / 45 × 0.0 = 0.00
```

## 9. Submitting Results

To submit a Safe-TOPS/W score:

1. Run the benchmark tool: `python3 tools/safe_tops_per_watt.py`
2. Provide evidence:
   - Differential test results (mismatch count = 0)
   - Power measurement logs
   - Certification documentation (or statement of none)
3. Submit PR to this repository with results in `benchmarks/` directory

## 10. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-05-05 | Initial specification |

---

*Safe-TOPS/W measures trust, not speed. The gap between 20.19 and 0.00 is the gap between verified and hope.*
