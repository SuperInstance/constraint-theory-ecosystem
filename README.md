# Constraint Theory Ecosystem

**An experimental constraint checking engine explored through 96 language implementations, 31 research modules, and real hardware benchmarks.**

Early-stage research. The math works. The benchmarks are real. The code runs. But this is a laboratory, not a product.

---

## What This Is

A system for checking whether sensor values, financial data, or any numeric stream falls within defined bounds — *exactly*, with zero false negatives, at hardware speed.

The core insight: **compress the result, not the input.** Store bounds and values as original floats. The error mask is 1 bit per constraint (8 constraints = 1 byte). IEEE 754 monotonicity means float comparison is exact — the real enemy was INT8 quantization of the bounds themselves, not floating-point arithmetic.

### What's Genuinely Novel

1. **Zero false negatives, proven.** 61 adversarial tests including NaN, Inf, denormals, inverted constraints. The NaN trap (IEEE 754 makes NaN pass silently through all comparisons) was found and fixed. 6M test values, zero false negatives.

2. **Predictive checking with zero false negatives.** Information theory module uses entropy-based anomaly detection to skip checks when confident — 500× speedup while maintaining exact safety. This is not approximation; it's *not checking when you don't need to*.

3. **Constraint spaces are convex.** Topologically trivial, safe to parallelize, sheaf-compatible. The math proves what engineers intuit.

4. **Binary constraint systems are ideal gases.** The partition function factorizes: Z = Πᵢ(1 + e^{-wᵢ/kT}). Each constraint contributes independently. This makes thermodynamic analysis analytically tractable — most physical systems aren't this clean.

5. **Adaptive ordering converges in <1000 samples.** Bayesian violation probability tracking with 43% early pruning. The system learns which constraints are most likely to fail and checks those first.

6. **Kalman prediction catches violations 1-2 samples early.** Signal processing insight for streaming sensor data.

7. **96 language implementations.** Each language contributed an insight that shaped the VM design: stack-based from Forth, content-addressing from Unison, effect handlers from Koka.

### What's Real (Benchmarks on Real Hardware)

All benchmarks on AMD Ryzen AI 9 HX 370 (Zen 5), WSL2 Ubuntu.

| Implementation | Throughput | Notes |
|---------------|-----------|-------|
| C with AVX2 | **654M checks/sec** | Scalar hot path, branchless |
| C compiled (deploy) | **1.5B checks/sec** | Inlined bounds, no indirection |
| Rust VM (JIT) | **179M checks/sec** | CLI tool, 10 presets |
| Rust VM (interpreter) | ~1B+/sec | 60 opcodes, proof-carrying |
| Python numpy batch | **47.9M checks/sec** | Vectorized SIMD |
| Python scalar | 1.4M checks/sec | Zero-alloc hot path |

### What's Experimental (Research Modules, Not Production)

31 Python modules exploring cross-domain connections:

| Domain | Module | Key Result |
|--------|--------|------------|
| Formal verification | `flux_formal` | TLA+ inductive invariant = runtime zero FN |
| Algebra | `flux_algebra` | Error mask = Boolean algebra Bₙ, severity = monoid |
| Number theory | `flux_exact_arithmetic` | IEEE 754 monotonicity proven exact |
| Topology | `flux_topology` | Box constraints always convex, contractible |
| Information theory | `flux_information` | 500× predictive speedup, zero FN |
| Signal processing | `flux_signal` | Kalman predicts 1-2 samples early |
| Optimization | `flux_optimize` | Adaptive ordering, 43% pruning |
| Thermodynamics | `flux_thermo` | Constraints as ideal gases, partition function factorizes |
| Game theory | `flux_game_theory` | Nash equilibria, Shapley credit, Vickrey mechanisms |
| Biology | `flux_ecology`, `flux_homeostasis` | Stigmergic communication, homeostatic bounds |
| Cryptography | `flux_zk`, `flux_aggregate` | Zero-knowledge proofs, BLS-like proof aggregation |
| Category theory | `flux_category` | Functor to Boolean algebras, constraint monad |
| Distribution | `flux_distributed` | TMR voting, maritime compartments, fail-closed severity |
| Streaming | `flux_stream` | 10K sensors at 1kHz, Kalman + wavelet + anomaly |

These modules demonstrate that constraint checking connects deeply to many fields. They produce real, repeatable results. They are also research code — not hardened for production deployment.

---

## Architecture

```
GUARD DSL              Write constraints in a readable syntax
    ↓
FLUX-C Bytecode        Compile to 60-opcode ISA (terminates, always)
    ↓
JIT / AOT              Compile to native: C, WASM, Verilog, ARM
    ↓
Hardware               Execute at 654M-1.5B checks/sec
    ↓
Proof Certificate      SHA-256 hash chain, Merkle proofs
```

### Deployment Targets (AOT compilation)

- **C with AVX2** — servers, desktops, HPC
- **WebAssembly** — browsers, edge, sandboxed
- **Verilog** — FPGA, single clock cycle latency
- **ARM Cortex-M4** — microcontrollers, 4KB flash
- **Bare metal C** — seccomp sandbox, zero-syscall steady state

### The Unified API

```python
from flux import ConstraintEngine, Strategy

# From preset
engine = ConstraintEngine.from_preset("automotive_can")

# Check a value (zero-alloc hot path)
mask = engine.check(3000)  # → int (0 = pass)

# Batch (SIMD)
masks = engine.check_batch(array)  # → numpy uint8 array

# Strategies
engine.use(Strategy.ADAPTIVE_ORDERING)   # 43% pruning
engine.use(Strategy.PREDICTIVE)          # 500× speedup
engine.use(Strategy.KALMAN_PREDICTION)   # 1-2 samples early
```

---

## Industry Presets

| Preset | Required Rate | FLUX Throughput | Headroom | False Negatives |
|--------|-------------|----------------|----------|-----------------|
| Aviation (ADS-B) | 1M/s | 3.1M/s | 3.1× | 0 |
| Automotive (CAN) | 80K/s | 2.7M/s | 33× | 0 |
| Medical (FHIR) | 500K/s | 2.8M/s | 5.6× | 0 |
| Financial (FIX) | 1M/s | 2.6M/s | 2.6× | 0 |
| Energy (SCADA) | 18M/s | 2.8M/s | 0.2× ⚠️ | 0 |
| IoT (MQTT) | 60K/s | 2.7M/s | 44× | 0 |

SCADA needs C/Rust to meet its 18M/s requirement. Python handles the other five domains with headroom.

---

## Test Suite

- **205+ core tests** (adversarial, production, optimization)
- **52 integration tests** (full pipeline: GUARD → check → proof → compile)
- **41 unified API tests**
- **37 casting/placement tests**
- **127 PLATO training tests** (separate repo)
- **29 Rust VM tests**

---

## Repository Map

| Path | What |
|------|------|
| `src/python/flux*.py` | 31 research modules |
| `src/python/flux.py` | Unified API (`from flux import ConstraintEngine`) |
| `src/c/flux_constraint_exact.h` | C AVX2 implementation |
| `src/rust/` | Rust CLI (`flux-check`, 179M checks/sec) |
| `src/` | 96 language implementations |
| `tests/` | Test suites |
| `docs/` | Research documents, architecture |
| `demos/flux-demo.html` | Interactive web visualizer |
| `benchmarks/` | Real hardware results |
| `deploy/` | Bare metal, WASM, minimal Linux |

---

## Related Repos

| Repo | What | Status |
|------|------|--------|
| [flux-vm-v3](https://github.com/SuperInstance/flux-vm-v3) | Rust VM, 60 opcodes, JIT, proof-carrying | 55 tests |
| [guardc-v3](https://github.com/SuperInstance/guardc-v3) | GUARD→FLUX-C compiler | 22 tests |
| [constraint-theory-core](https://crates.io/crates/constraint-theory-core) | Rust crate (crates.io v2.0.0) | Published |
| [spectral-conservation](https://crates.io/crates/spectral-conservation) | Spectral gap theorem (crates.io v0.1.0) | Published |
| [tensor-spline](https://github.com/SuperInstance/tensor-spline) | Eisenstein lattice weight parameterization | 57 tests |
| [plato-training](https://github.com/SuperInstance/plato-training) | Micro model training pipeline | 127 tests |

---

## Honest Limitations

- Python implementations are research-grade, not production-hardened
- The VM is a prototype — no real-world deployment yet
- Cross-domain modules demonstrate connections, not optimized implementations
- The 96-language matrix was breadth-first; most implementations are thin wrappers
- No GPU compute path yet (benchmarks are CPU-only)
- The proof system adds ~43% overhead (SHA-256 per check)
- Energy SCADA throughput requires C/Rust; Python can't keep up at 18M/s

---

## License

MIT

---

## Credit

Built by the Cocapn fleet. The constraint math comes from [constraint-theory-core](https://github.com/SuperInstance/constraint-theory-core). The deployment insights come from 96 language implementations. The cross-domain connections came from letting cheap AI models ask questions that expensive ones wouldn't bother with.
