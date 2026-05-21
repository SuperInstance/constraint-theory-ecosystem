# Constraint Theory Ecosystem

**Replace floating-point guesswork with provably correct constraint checks.**

Constraint theory treats every variable in your system as a dimension in a geometric space. Each constraint (`battery_temp ∈ [15, 55]`) carves out a valid region. If the intersection is non-empty, a solution exists — and you know at *design time*, not in production. No probabilities. No NaN. Just: in spec or out of spec.

This repo provides the full toolchain: a constraint DSL (GUARD), a terminating bytecode VM (FLUX-C), machine-checked proofs (Coq), GPU-accelerated checking (CUDA), and 248 real-world constraints across 10 industries.

---

## The 7 Key Results

| # | Result | Proof |
|---|--------|-------|
| 1 | **Laman rigidity** — E = 2V − 3 edges for exact structural rigidity | [`proofs/english/laman-rigidity.md`](proofs/english/laman-rigidity.md) |
| 2 | **GUARD DSL** — Exact bounds with zero rounding, compiles to verifiable bytecode | [`chapters/ch02-guard-dsl.md`](chapters/ch02-guard-dsl.md) |
| 3 | **FLUX-C VM** — 43 opcodes, termination guaranteed by construction (no infinite loops possible) | [`chapters/ch03-flux-c-bytecode.md`](chapters/ch03-flux-c-bytecode.md) |
| 4 | **Coq proof chain** — Machine-checked certificates auditors can verify independently | [`proofs/COQ-PROOF-INVENTORY.md`](proofs/COQ-PROOF-INVENTORY.md) |
| 5 | **ZHC consensus** — 38ms fleet-wide agreement, mathematically guaranteed | [`chapters/ch06-fleet-math.md`](chapters/ch06-fleet-math.md) |
| 6 | **Pythagorean48 encoding** — Zero-drift INT8 representation for 85% of industry constraints | [`docs/EXACT-ARITHMETIC-ANALYSIS.md`](docs/EXACT-ARITHMETIC-ANALYSIS.md) |
| 7 | **62.2B constraints/sec** — RTX 4050 sustained throughput with zero mismatches across 60M inputs | [`experiments/RESULTS.md`](experiments/RESULTS.md) |

---

## Quick Start

### Install

```bash
git clone https://github.com/SuperInstance/constraint-theory-ecosystem.git
cd constraint-theory-ecosystem
pip install -r src/python/requirements.txt   # Python bindings
```

### Write your first constraint (5 minutes)

```bash
# Create a GUARD constraint file
cat > battery.guard << 'EOF'
constraint battery_safety {
    battery_temp in [15.0, 55.0] degC
        with priority HIGH
        with category SAFETY
    battery_voltage in [2.8, 4.2] V
        with priority CRITICAL
        with category OPERATIONAL
}
EOF

# Compile to FLUX-C bytecode (with proof certificate)
guard compile battery.guard --output battery.fbc --proof battery_proof.v

# Check a value
guard check battery.fbc --value battery_temp=45.2
# ✓ PASS: battery_temp = 45.2 degC ∈ [15.0, 55.0]

guard check battery.fbc --value battery_temp=60.0
# ✗ FAIL: battery_temp = 60.0 degC ∉ [15.0, 55.0]
```

### Python API

```python
from constraint_theory import GuardCompiler, FluxChecker

# Compile and check in code
compiler = GuardCompiler()
checker = FluxChecker(compiler.compile("battery.guard"))

assert checker.check("battery_temp", 45.2) == True
assert checker.check("battery_temp", 60.0) == False

# Batch check 10M values on GPU
results = checker.check_batch_gpu(
    sensor="battery_temp",
    values=measurements,  # numpy array, 10M elements
    expected_throughput="62B c/s"
)
```

→ **Full tutorial:** [`tutorials/01-first-constraint.md`](tutorials/01-first-constraint.md)

---

## Architecture: GUARD → FLUX-C → CUDA

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐     ┌───────────┐
│  GUARD DSL  │────▶│  FLUX-C VM  │────▶│  CUDA Kernel v2  │────▶│  Coq Proof│
│  (.guard)   │     │  (.fbc)     │     │  (10M×8: 62B c/s)│     │  (.v)     │
└─────────────┘     └─────────────┘     └──────────────────┘     └───────────┘
   Human writes        Compiler           GPU checks 10M          Auditable
   exact bounds        guarantees         values in 1 pass        certificate
                       termination
```

1. **GUARD** — You write constraints in a readable DSL: `battery_temp in [15, 55] degC`
2. **FLUX-C** — Compiler produces 43-opcode bytecode; termination is guaranteed by construction (no loops, no recursion)
3. **CUDA Kernel v2** — Batch constraint checking at 62.2B constraints/sec on consumer hardware
4. **Coq Proof** — Every compiled constraint comes with a machine-checkable proof certificate

---

## Cross-Language Support

98 language implementations in `src/`. Core bindings:

| Language | Status | Location | Notes |
|----------|--------|----------|-------|
| **Python** | ✅ Production | [`src/python/`](src/python/) | Primary API, GPU bindings |
| **Rust** | ✅ Production | [`src/rust/`](src/rust/) | Zero-cost abstractions |
| **C** | ✅ Production | [`src/c/`](src/c/) | Embedded-friendly |
| **C++** | ✅ Production | [`src/cpp/`](src/cpp/) | Industry interop |
| **CUDA** | ✅ Production | [`src/cuda/`](src/cuda/) | 62.2B c/s kernel |
| **Zig** | ✅ Complete | [`src/zig/`](src/zig/) | Comptime checks |
| **Go** | ✅ Complete | [`src/go/`](src/go/) | Service integration |
| **JavaScript** | ✅ Complete | [`src/js/`](src/js/) | Web/Node.js |
| **Haskell** | ✅ Complete | [`src/haskell/`](src/haskell/) | Type-level proofs |
| **Lean** | ✅ Complete | [`src/lean/`](src/lean/) | Formal verification |

[Full list of 98 languages →](docs/monorepo-map.md)

---

## Industry Coverage

10 industries, 248 constraints, 85% INT8-compatible:

| Industry | Constraints | Standard | File |
|----------|------------|----------|------|
| Aerospace | 25 | DO-254 | [`constraints/aviation.md`](constraints/aviation.md) |
| Automotive | 28 | ISO 26262 | [`constraints/automotive.md`](constraints/automotive.md) |
| Medical | 22 | IEC 62304 | [`constraints/medical.md`](constraints/medical.md) |
| Nuclear | 30 | IEC 61508 | [`constraints/nuclear.md`](constraints/nuclear.md) |
| Railway | 18 | EN 50128 | [`constraints/railway.md`](constraints/railway.md) |
| Maritime | 24 | IACS | [`constraints/maritime.md`](constraints/maritime.md) |
| Energy | 35 | IEEE 1547 | [`constraints/energy.md`](constraints/energy.md) |
| Robotics | 25 | ISO 10218 | [`constraints/robotics.md`](constraints/robotics.md) |
| Space | 28 | ECSS-E-ST-10C | [`constraints/space.md`](constraints/space.md) |
| Autonomous Underwater | 13 | IMCA | [`constraints/autonomous-underwater.md`](constraints/autonomous-underwater.md) |

---

## Experiment Results

All benchmarks run on real hardware (RTX 4050 Laptop, WSL2). No simulation.

| Benchmark | Throughput | Notes |
|-----------|-----------|-------|
| Production Kernel v2 | **62.2 B c/s** | 10M × 8c, INT8 saturated |
| CUDA Graph replay | 9,500 B c/s | Kernel replay speedup |
| Streaming incremental (0.1% change) | 77.3× faster than full sweep | Real-time sensor feeds |
| Temporal constraints (window=4) | 44.1 B c/s | Rate-of-change + deadband |
| Multivariate cross-sensor | 14.8 B c/s | AND/OR combinations |
| Differential correctness | **ZERO mismatches** | 60M inputs verified |

→ [`experiments/RESULTS.md`](experiments/RESULTS.md) for full data

---

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** — 15-minute setup guide
- **[COOKBOOK.md](COOKBOOK.md)** — 40+ constraint recipes
- **[SPEC.md](SPEC.md)** — GUARD/FLUX-C language specification
- **[chapters/](chapters/)** — Full textbook (10 chapters, constraint theory from first principles)
- **[docs/](docs/)** — Technical deep dives (category theory, thermodynamics, topology of constraint spaces)
- **[tutorials/](tutorials/)** — Hands-on guides with working code

---

## Contributing

We want your domain expertise. Physical engineers, safety engineers, software engineers — if you've ever specified a tolerance, you already think in constraints.

→ [`CONTRIBUTING.md`](CONTRIBUTING.md) for guidelines

## License

MIT — see [`LICENSE`](LICENSE)
