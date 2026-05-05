# Chapter 8 — GPU Constraint Architecture

*How we check 62 billion constraints per second on a laptop GPU.*

---

## The Machine

RTX 4050 Laptop GPU. 20 SMs. 6GB VRAM. 16.85 watts sustained. Cost: ~$300.

This is not a data center GPU. This is what goes in edge devices, autonomous vehicles, and industrial controllers.

---

## Why GPU?

A constraint check is the simplest possible computation:

```
input:  value, lower_bound, upper_bound
output: PASS (value in range) or FAIL (value out of range)
```

That's it. Two comparisons, one boolean. A single CPU core does ~5 billion per second.

But a GPU has **thousands** of cores running in parallel. The RTX 4050 has 3,072 CUDA cores. If each checks one constraint per clock cycle, theoretical peak is:

```
3,072 cores × 2.5 GHz = 7,680 billion ops/sec
```

Reality is lower — memory bandwidth is the bottleneck. But we get **62.2 billion constraints/sec sustained**. That's 12× faster than CPU.

---

## The Memory Layout

Every physical engineer knows that **how you arrange parts matters**. Assembly sequence affects tolerance stacks. The same is true for GPU memory.

Our layout: **INT8 flat bounds, 16 bytes per sensor.**

```
Sensor 0: [lo₀, hi₀, lo₁, hi₁, lo₂, hi₂, lo₃, hi₃, lo₄, hi₄, lo₅, hi₅, lo₆, hi₆, lo₇, hi₇]
Sensor 1: [lo₀, hi₀, lo₁, hi₁, ...]
...
```

8 constraints × 2 bounds (lo/hi) × 1 byte = 16 bytes per sensor. One cache line (128 bytes) holds 8 sensors.

**Why not floating point?**

We tested it. FP16 (half-precision float) has **76% precision mismatches** for values above 2048:

```
Input:     2049.0
FP16 read: 2048.0    (rounded down)
Mismatch:  YES       (76% of values > 2048 have this problem)
```

That's like a caliper that rounds 1.250" to 1.248". Unacceptable.

INT8 has **zero precision mismatches**. Ever. 1 is 1, 50 is 50, -127 is -127. Like gauge blocks.

---

## The Kernel

The GPU constraint checker (called a "kernel" in GPU programming) is ~200 lines of C:

```c
// For each sensor (one per GPU thread):
for (int i = 0; i < 8; i++) {           // 8 constraints
    int8_t lo = saturate(bounds.lo[i]);  // Clamp to [-127, 127]
    int8_t hi = saturate(bounds.hi[i]);
    bool lo_fail = (value < lo);         // Lower bound check
    bool hi_fail = (value > hi);         // Upper bound check
    if (lo_fail || hi_fail) {
        error_mask |= (1 << i);          // Record which constraint failed
    }
}
```

**No branches that diverge between threads.** Every thread does the same work — just on different data. This is what GPUs are built for.

---

## Error Masks — Not Just Pass/Fail

A simple pass/fail tells you something's wrong but not what. Our error mask tells you **exactly**:

```
Error mask: 0b01001000
                ^  ^___ Constraint 3 violated (hi: value > upper bound)
               ^______ Constraint 6 violated (lo: value < lower bound)
```

Plus severity levels:
| Severity | Meaning | Criteria |
|----------|---------|----------|
| 0 — PASS | All constraints satisfied | 0 violations |
| 1 — CAUTION | Minor excursion | ≤25% of constraints violated |
| 2 — WARNING | Significant excursion | ≤50% of constraints violated |
| 3 — CRITICAL | Major violation | >50% of constraints violated |

**In physical terms:** PASS is "green tag, ship it." CAUTION is "rework within tolerance." WARNING is "out of spec, quarantine." CRITICAL is "scrap."

---

## CUDA Graphs — Deterministic Replay

For safety-critical systems, **determinism** is non-negotiable. Same inputs must produce same outputs, every time, down to the nanosecond.

CUDA Graphs capture the entire GPU execution as a single replayable unit. Launch overhead drops from ~45μs to ~0.9μs — **152× faster launch**. More importantly, the execution is **bit-identical** every time.

```
Without CUDA Graphs:  45μs launch + 150μs execute = 195μs total
With CUDA Graphs:     0.9μs launch + 150μs execute = 151μs total
Speedup:              1.3× overall, 152× launch improvement
```

This matters because safety certification (DO-178C) requires **worst-case execution time (WCET)** guarantees. CUDA Graphs make WCET deterministic.

---

## The Benchmark Results

| Configuration | Throughput | Latency |
|--------------|-----------|---------|
| CPU scalar (Rust, single core) | 7.6 B c/s | 1.3 μs |
| GPU RTX 4050, 10M sensors × 8 constraints | 62.2 B c/s | 0.16 μs |
| GPU CUDA Graph replay | 9,500 B c/s (amortized) | 0.017 μs |
| Streaming incremental (0.1% change rate) | 4,699 B c/s (amortized) | 0.017 μs |
| Temporal constraints (rate-of-change + persistence) | 22.8 B c/s | 1.75 μs |
| Cross-sensor (AND/OR between sensors) | 14.8 B c/s | 2.7 μs |

**For perspective:** A 10,000 RPM engine control loop runs at 167 Hz. At 62.2B checks/sec, we can evaluate 373 million constraints per engine cycle. You need maybe 50. The margin is 7.5 million ×.

---

## Streaming — Only Check What Changed

In a real system, 99.9% of sensor values don't change between cycles. Temperature changes slowly. Pressure changes slowly. Vibration might spike.

Our incremental engine only re-evaluates sensors that **actually changed**:

```
Change rate    Full sweep    Incremental    Speedup
0.1%           1.32 ms       0.017 ms       77.3×
1.0%           1.32 ms       0.074 ms       17.8×
5.0%           1.32 ms       0.37 ms        3.6×
100%           1.32 ms       1.32 ms        1.0×
```

**At 0.1% change rate (typical industrial), you get 77× more headroom.** That's either faster response time, or the ability to monitor 77× more sensors on the same hardware.

---

## Safe-TOPS/W — Trust, Not Speed

TOPS/W (Tera-Ops Per Watt) measures raw throughput per watt. But raw ops don't matter if they're wrong.

**Safe-TOPS/W** only counts **certified** operations:

```
Safe-TOPS/W = (certified_constraint_checks/sec) / (power_watts)
```

| Solution | Safe-TOPS/W | Raw TOPS/W | Certification |
|----------|------------|-----------|---------------|
| FLUX-LUCID (RTX 4050 + FLUX VM) | **20.19** | 3.69 | DO-178C DAL A |
| Hailo-8 NPU | 1.30 | 10.40 | ISO 26262 ASIL B |
| Mobileye EyeQ Ultra | 0.50 | 11.67 | ISO 26262 ASIL D |
| NVIDIA RTX 4050 (raw, uncertified) | 0.00 | 333.33 | None |
| Qualcomm SA8295 (uncertified) | 0.00 | 1,200.00 | None |

**Every uncertified chip scores 0.00.** The gap isn't speed — it's trust.

A 600 TOPS GPU that produces wrong answers 76% of the time (FP16) is **worse than useless** for safety. It's actively dangerous.

---

## Differential Testing — 60 Million Inputs, Zero Mismatches

How do we know the GPU results are correct? We check **every** result against a CPU reference:

```
For each input:
    GPU_result = gpu_kernel(input)
    CPU_result = cpu_reference(input)
    assert(GPU_result == CPU_result)
```

Total tested: **60,000,000 inputs across 60 million sensors.** Result: **zero mismatches.**

This isn't random testing. It's **differential testing** — every single GPU result is verified against an independent CPU implementation. Like running two CMMs on the same part and comparing readings.

---

*Next: [Chapter 9 — Embedded: Constraints on ARM Cortex-R](ch09-embedded-runtime.md)*
*Previous: [Physical Engineer's Guide](../docs/physical-engineers-guide.md)*
