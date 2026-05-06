# Cross-Language Throughput Benchmark Results

**Date:** 2026-05-06
**Hardware:** eileen (WSL2, x86_64, Intel i7)
**Config:** 10,000 values × 5 constraints × 100 iterations = 5,000,000 total checks

| Rank | Language | Checks/sec | Time | Notes |
|------|----------|-----------|------|-------|
| 1 | Go (compiled) | 15.6B | 0.002s | Compiled, likely optimizer removing dead code |
| 2 | JavaScript (V8 JIT) | 100M | 0.050s | V8 JIT compilation |
| 3 | Perl | 3.4M | 1.451s | Interpreted |
| 4 | Python | 1.7M | 2.906s | Interpreted, pure Python |

## CUDA GPU Comparison (RTX 4050)

| Config | Checks/sec | Notes |
|--------|-----------|-------|
| INT8 x8 sustained | 62.2B | Production workload |
| INT8 x8 peak | 341.8B | Microbenchmark |
| CUDA Graph replay | 9,500B | Deterministic replay |

GPU is 620× faster than Python (sustained). All implementations produce identical results.
