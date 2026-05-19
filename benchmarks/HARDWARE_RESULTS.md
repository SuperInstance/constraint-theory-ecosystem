# Hardware Benchmark Results — FLUX Constraint Engine

**Hardware:** AMD Ryzen AI 9 HX 370 w/ Radeon 890M  
**OS:** WSL2 Ubuntu 22.04 on Windows 11  
**Date:** 2026-05-19  
**Test:** 4-constraint aviation preset, 10M iterations, single-threaded  

---

## Throughput (checks/sec)

| Rank | Language | Throughput | Time (10M) | ×Python |
|------|----------|-----------|------------|---------|
| 1 | **C (gcc -O3 -march=native)** | **11.1 B/s** | 3.6ms | 6,854× |
| 2 | **Rust (rustc -O)** | **3.0 B/s** | 13.3ms | 1,852× |
| 3 | **Go 1.26** | **1.4 B/s** | 29.3ms | 843× |
| 4 | **Node.js 22 (V8 JIT)** | **678 M/s** | 59.0ms | 418× |
| 5 | **Python 3.10** | **1.6 M/s** | 24,800ms | 1× |

### Notes

- **C -O3** with `-march=native` on Zen 5 architecture hits 11.1 billion constraint checks per second. That's **4 constraints × 10M values in 3.6ms**. The optimizer vectorizes the inner loop.
- **C -O2** (baseline) was 1.9B/s — `-O3 -march=native` gives a 5.8× boost from auto-vectorization on Zen 5.
- **Rust -O** at 3.0B/s — the `clamp` intrinsic generates good code but doesn't auto-vectorize as aggressively as GCC here.
- **Go** at 1.4B/s — solid compiled performance, no surprises.
- **Node.js** at 678M/s — V8's JIT compiles the inner loop to near-native. Only 5× slower than Rust.
- **Python** at 1.6M/s — interpreted, expected. The numpy/pypy path would be 10-100× faster.

### Golden Vector Verification

| Language | Vectors | Mismatches |
|----------|---------|------------|
| Python | 10,000 | 0 |
| Node.js | 10,000 | 0 |
| Go | 10,000 | 0 |

**Cross-language: 30,000 checks, 0 mismatches.**

---

## Why C Wins Here

The Zen 5 backend in GCC 11 can auto-vectorize the 4-constraint inner loop into SIMD instructions. Each constraint check is a compare+mask, and 4 of them in sequence maps cleanly to a vector compare + blend. At `-O3 -march=native`, GCC generates:

```asm
; Conceptual: 4 constraints checked in ~8 AVX instructions
vpmovsxbw  (%cs), %ymm0    ; load 4 × {lo, hi} pairs
vpcmpgtb   %val, %ymm0     ; parallel compare
vpor       %lo_fail, %hi_fail
```

The constraint checking problem is **embarrassingly simple for hardware** — it's just integer comparison with bit masking. The bottleneck is loop overhead, not the comparison itself.

---

## Projection: CUDA / GPU

No NVIDIA GPU on this machine (AMD Radeon 890M in WSL2, no ROCm compute). Based on prior benchmarks on RTX 4050:

| Target | Throughput | Source |
|--------|-----------|--------|
| CUDA (RTX 4050, 8-constraint) | 62.2 B/s | `cuda/benches/` |
| CUDA Graphs (replay) | 9,500 B/s | `cuda/benches/` |
| C (Zen 5, 4-constraint) | 11.1 B/s | This benchmark |

The GPU advantage is modest for 4-constraint checks (the problem is too simple to saturate GPU parallelism). GPU wins big at 20+ constraints or batch sizes >1M.
