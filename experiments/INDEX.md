# GPU Experiments Index

54 experiments on NVIDIA RTX 4050 Laptop GPU (CUDA 11.5, sm_86).

## Phase 1: Foundation (Exp01-10)
- **Exp01-03:** Memory layout, access patterns, cache behavior
- **Exp04-06:** Warp-level primitives, shuffle operations, cooperative groups
- **Exp07:** VRAM scaling (1M to 100M sensors)
- **Exp08-10:** Precision analysis — **KEY FINDING: FP16 has 76% mismatches, INT8 has zero**

## Phase 2: Optimization (Exp11-20)
- **Exp11-13:** INT8 warp-cooperative 256 constraints/element, CUDA Graphs (51× launch speedup)
- **Exp14-16:** Async pipeline, multi-stream, power measurement
- **Exp17-18:** Mixed constraint types, adaptive ordering
- **Exp19-20:** Production kernel v1 — 101.7B c/s sustained

## Phase 3: Architecture (Exp21-30)
- **Exp21-25:** Struct vs flat bounds, error masks, cold start behavior
- **Exp26-28:** Error localization, flat bounds 1.45× faster, masked evaluation
- **Exp29-30:** Hot-swap bounds (1.07ms, <1kHz capable), streaming patterns

## Phase 4: Production v2 (Exp31-45)
- **Exp31-40:** Saturation semantics, edge case coverage, INT8 boundary validation
- **Exp41-45:** Space/time constraints, cross-platform validation, production hardening

## Phase 5: Advanced R&D (Exp46-54)
- **Exp46:** Multi-industry fusion (aviation + maritime + energy + medical simultaneous)
- **Exp47:** WCET determinism (10K iterations, jitter measurement)
- **Exp48:** Cascade propagation (1M sensor grid, 3-hop cascade detection in 0.193ms)
- **Exp49:** Power efficiency (10M/20M/50M linear scaling, 100% efficiency)
- **Exp50:** 60-second stability (zero drift, zero memory errors)
- **Exp51:** GPU-accelerated CSP solver (BitmaskDomain, N-Queens, graph coloring)
- **Exp52:** Temporal constraints (rate-of-change, deadband, persistence — 22.8B c/s)
- **Exp53:** Streaming incremental (77.3× faster at 0.1% change rate)
- **Exp54:** Multivariate cross-sensor (AND/OR compound logic — 14.8B c/s)

## Key Results Summary

| Metric | Value |
|--------|-------|
| Peak throughput | 341B c/s (INT8 × 8, ideal) |
| Sustained production | 62.2B c/s (10M × 8c) |
| CUDA Graph speedup | 152× launch |
| Precision (INT8) | Zero mismatches, 60M inputs |
| Precision (FP16) | 76% mismatches, values >2048 |
| Streaming incremental | 77.3× at 0.1% change rate |
| Temporal constraints | 22.8B c/s with 4 constraint types |
| Cross-sensor | 14.8B c/s with AND/OR logic |
| 60s stability | Zero drift, zero memory errors |
| Safe-TOPS/W | 20.19 (FLUX-LUCID DAL A) |

---

*All experiments use real hardware, real timing, real data. No simulation.*
