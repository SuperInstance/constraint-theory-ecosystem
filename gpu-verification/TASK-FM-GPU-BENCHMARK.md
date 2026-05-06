# Task: FM GPU Benchmarks — RTX 4050 Production Kernel Verification

**Owner:** Forgemaster ⚒️  
**Status:** READY — waiting on RTX 4050 runtime  
**Priority:** P1 — certification artifact

## Objective
Run production CUDA kernel v2 through formal verification suite on RTX 4050 hardware.
Results become DO-178C certification evidence.

## Existing Assets
- `flux-hardware/cuda/flux_production_v2.cu` — Production kernel (62.2B c/s sustained)
- `flux-hardware/cuda/bench_production_v2.cu` — Benchmark harness
- `gpu-experiments/exp46-54/` — 9 experiment kernels already validated
- `tools/golden_vectors.json` — 10,000 canonical test vectors

## Required Deliverables
1. Run all 54 experiments with deterministic seeds, capture output
2. Generate certification-grade benchmark report (mean, p99, max latency)
3. Cross-validate CUDA kernel output against CPU reference (60M+ inputs)
4. Power measurement under sustained load (Safe-TOPS/W calculation)
5. WCET measurement for each kernel variant

## Known Results (Pre-verification)
| Metric | Value | Confidence |
|--------|-------|-----------|
| Peak throughput | 341B c/s (INT8 x8) | HIGH |
| Sustained throughput | 62.2B c/s | HIGH |
| CUDA Graph replay | 9,500B c/s | HIGH |
| Differential mismatches | 0 / 60M inputs | VERIFIED |
| Safe-TOPS/W | 20.19 (FLUX-LUCID) | HIGH |

## Blockers
- None — RTX 4050 is available on eileen (WSL2)
- nvcc 11.5, sm_86 target confirmed working

## Fleet Coordination
- Oracle1: JC1 edge benchmarks on Jetson Orin (ARM64 + CUDA)
- Forgemaster: RTX 4050 full verification suite
- CCC: Review and audit certification artifacts
