# Constraint Theory Ecosystem

Research into exact numeric bounds checking — the math, the implementations, and the connections to other fields.

96 language implementations. 31 research modules. Hardware benchmarks below.

---

## Background: The Math Under the Hood

Some of our repos mention **Eisenstein integers** and **hex arithmetic**. Here's what that means.

Eisenstein integers are complex numbers of the form `a + bω` where `ω = e^(2πi/3)` — a primitive cube root of unity. They form a **hexagonal lattice** in the complex plane (triangular tiling, not the square grid you get from Gaussian integers `a + bi`). That's where the "hex" comes from: hexagonal, not hexadecimal.

Why does this matter? The hexagonal lattice has nicer algebraic properties for certain decompositions — it's a Euclidean domain (so you get unique factorization) and the hex grid packs more efficiently than a square grid. When you're compressing constraint-checking operations into integer arithmetic, the lattice structure determines how clean the math is.

**You do not need to understand any of this to use the libraries.** The five-minute tour below works without knowing what an Eisenstein integer is. This background is for people who want to understand *why* the internals look the way they do.

---

## The Problem

Software checks numeric bounds wrong. Not because the code is buggy, but because floating-point arithmetic lies:

- `NaN < 0` is `false`. `NaN > 0` is `false`. A NaN value passes every bounds check silently.
- Two floats that "should be equal" differ by ULPs (units in the last place). The difference compounds.
- INT8 quantization of bounds (compressing everything to ±127) introduces 35,984 false negatives across 6 million test values.

You've probably debugged this. It looks like a race condition. It isn't. It's float.

## The Approach

Don't quantize the inputs. Compress the *result*.

```
traditional:  value → quantize → compare → error    (loses precision)
this system:  value → compare → error_mask (1 bit)   (loses nothing)
```

Eight constraints → one byte error mask. Bit 0 = constraint 1 violated, bit 1 = constraint 2, etc. IEEE 754 monotonicity means float comparison is exact — the bug was quantizing the *bounds*, not the comparison itself.

NaN gets an explicit trap: `v != v` catches it before any comparison.

## Five-Minute Tour

### 1. Check some values

```python
from flux import ConstraintEngine

engine = ConstraintEngine.from_preset("automotive_can")

# Single value — returns error mask (0 = all pass)
mask = engine.check(3000)

# Batch — returns numpy uint8 array
masks = engine.check_batch(values_array)
```

### 2. Define your own constraints

```python
engine = ConstraintEngine()
engine.add_constraint("coolant_temp", -40, 150)
engine.add_constraint("rpm", 0, 8000)
engine.add_constraint("battery_voltage", 10.5, 15.0)

result = engine.check_values({"coolant_temp": 160, "rpm": 3000, "battery_voltage": 12.1})
# result.error_mask == 0b001  (only coolant_temp violated)
# result.violated_names == ["coolant_temp"]
```

### 3. Split independent constraints for parallelism

```python
from flux_fracture import DependencyGraph, fracture, coalesce

# 8 constraints, each on its own dimension → 8 independent blocks
graph = DependencyGraph.identity(8)
blocks = fracture(graph)
# blocks.n_blocks == 8  →  can check all 8 in parallel
# coalesce via bitwise OR → zero false negatives
```

### 4. Add edge-case corrections over time

```python
from flux_sediment import SedimentStack

stack = SedimentStack()
# After discovering edge case: coolant should be [-40, 145] not [-40, 150]
stack.add_layer(constraint_idx=0, corrected_hi=145.0, surprise=2.3)

# Apply corrections on top of standard checks
corrected_mask = stack.apply(values, original_mask)
```

### 5. Use the C header for production speed

```c
#include "flux_constraint_exact.h"

// 654M checks/sec with AVX2 on Zen 5
uint8_t mask = check_exact(value, bounds, 8);
```

## What's in This Repo

### The Implementation Matrix

`src/` contains 96 language implementations. Each one taught us something about how different paradigms handle bounds checking:

- **Forth / Factor** → stack-based VM is simpler to verify
- **Unison** → content-addressed bytecode (same hash = same behavior)
- **COBOL** → fixed-size OCCURS tables, no dynamic allocation in the hot path
- **Fortran** → column-major adjacency is cache-friendly by default
- **Chapel** → GPU is just another locale; locality matters more than parallelism
- **Ada / SPARK** → termination proofs via bounded execution
- **Verilog** → single-clock-cycle constraint checking

The point wasn't to build 96 production libraries. It was to learn what each paradigm forces you to think about. Those lessons shaped the VM and the deployment compiler.

### The Research Modules

`src/python/flux_*.py` — 31 modules connecting constraint checking to other fields. Each one explores a specific question:

| Question | Module | What It Found |
|----------|--------|--------------|
| Can you predict violations before they happen? | `flux_information` | Yes — entropy-based detection, 500× fewer checks needed |
| Are constraint spaces topologically simple? | `flux_topology` | Yes — always convex and contractible |
| Does the partition function factorize? | `flux_thermo` | Yes — independent constraints behave like ideal gases |
| Can evolution optimize constraint sets? | `flux_evolution` | Yes — beats hand-design in 25/30 trials |
| Can you split independent constraints safely? | `flux_fracture` | Yes — bitwise OR coalescence is lossless (proved) |
| Can a system learn from its mistakes? | `flux_sediment` | Yes — accumulated corrections are monotonically correct |
| Does the immune system pattern apply? | `flux_immune` | Yes — affinity maturation converges on adversarial inputs |
| Do court precedents accumulate correctness? | `flux_precedent` | Yes — stare decisis is monotonically beneficial |
| Can you verify zero false negatives with thermodynamics? | `flux_yield` | Yes — yield = partition function Z, verified to 10⁻¹² |
| What connects fracture, factorization, and sheaf cohomology? | `flux_sheaf` | They're the same: H¹=0 ⟺ Z factorizes ⟺ fracture is lossless |

### The VM and Compiler

Two separate repos:

- [**flux-vm-v3**](https://github.com/SuperInstance/flux-vm-v3) — 60-opcode stack-based VM. JIT to native. Proof-carrying execution.
- [**guardc-v3**](https://github.com/SuperInstance/guardc-v3) — GUARD DSL → FLUX-C bytecode compiler. 10 industry presets.

Pipeline: `GUARD source → FLUX-C bytecode → JIT native → error mask → proof certificate`

### The Standalone Packages

Extracted modules for direct use:

| Package | Language | Install | Tests |
|---------|----------|---------|:-----:|
| [flux-fracture](https://github.com/SuperInstance/flux-fracture) | Rust | `cargo add flux-fracture` | 16 |
| [flux-fracture-c](https://github.com/SuperInstance/flux-fracture-c) | C99 | Single header (`#define FRACTURE_IMPLEMENTATION`) | 47 |
| [flux-check-js](https://github.com/SuperInstance/flux-check-js) | TypeScript | `npm install @flux/check` | 59 |
| [flux-hyperbolic-py](https://github.com/SuperInstance/flux-hyperbolic-py) | Python | `pip install flux-hyperbolic` | 31 |
| [flux-genome-py](https://github.com/SuperInstance/flux-genome-py) | Python | `pip install flux-genome` | 30 |
| [flux-fortran](https://github.com/SuperInstance/flux-fortran) | Fortran 2008 | `gfortran -o test src/*.f90` | 15 |
| [flux-cobol](https://github.com/SuperInstance/flux-cobol) | GnuCOBOL | `cobc -free -x FLXMAIN.cob` | (no cobc) |
| [flux-chapel](https://github.com/SuperInstance/flux-chapel) | Chapel | `chpl -o flux src/FluxMain.chpl` | (no chpl) |

### Hardware Numbers

All measured on real hardware. AMD Ryzen AI 9 HX 370 (Zen 5) for CPU, RTX 4050 Laptop for GPU.

| Path | Throughput | Notes |
|------|-----------|-------|
| C with AVX2 | 654M checks/sec | Scalar, branchless |
| C deploy (AOT) | 1.5B/sec | Inlined bounds |
| GPU (RTX 4050) | 42.9B checks/sec | 10M values × 8 constraints |
| GPU + sediment (hybrid) | 3.8G values/sec | Fused kernel |
| GPU memory bandwidth | 159.5 GB/sec | 62% of theoretical |
| Rust CLI | 179M/sec | JIT-compiled |
| Python numpy batch | 47.9M/sec | Vectorized SIMD |
| Python scalar | 1.4M/sec | Zero-alloc |

## The Concepts

If you're going repo by repo, here's how the pieces fit together:

1. **Error mask** — 1 bit per constraint. 8 constraints = 1 byte. The fundamental data structure.
2. **NaN trap** — IEEE 754 makes NaN pass all comparisons. Must check `v != v` explicitly.
3. **Fracture-coalesce** — Split independent constraints into blocks (BFS on dependency graph). Merge results with bitwise OR. Zero false negatives because Boolean algebra.
4. **Sediment** — Accumulated edge-case corrections. Each layer tightens a bound. Correctness is monotonically increasing.
5. **Partition function** — Independent constraints factorize: Z = ΠᵢZᵢ. This is why fracture works and why the thermodynamics is clean.
6. **Sheaf cohomology** — H¹=0 means the constraint system has no hidden dependencies. Equivalent to factorization. Equivalent to fracture being lossless. Three languages for one fact.

## What's Not Production

- The Python research modules demonstrate connections, not optimized implementations
- The 96-language matrix was breadth-first; most are thin wrappers
- The VM has no real-world deployment yet
- The proof system adds ~43% overhead (SHA-256 per check)
- Energy SCADA's 18M/s rate requires C/Rust; Python can't keep up

## Where to Go Next

| If you want to... | Go to... |
|---|---|
| Check bounds in your code | [flux-check-js](https://github.com/SuperInstance/flux-check-js) (JS) or [flux-fracture](https://github.com/SuperInstance/flux-fracture) (Rust) |
| Understand the VM design | [flux-vm-v3](https://github.com/SuperInstance/flux-vm-v3) |
| Write constraints in a DSL | [guardc-v3](https://github.com/SuperInstance/guardc-v3) |
| See the cross-domain research | `src/python/flux_*.py` in this repo |
| Learn what old languages teach | [OLD-LANGUAGE-ARCHITECTURE.md](docs/OLD-LANGUAGE-ARCHITECTURE.md) |
| Read the grand mathematical synthesis | [GRAND-SYNTHESIS.md](docs/GRAND-SYNTHESIS.md) |
| See GPU benchmarks | [flux-gpu](https://github.com/SuperInstance/flux-gpu) |
| Understand the fleet training pipeline | [plato-training](https://github.com/SuperInstance/plato-training) |

## License

MIT
