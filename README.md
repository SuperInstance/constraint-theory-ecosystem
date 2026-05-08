# constraint-theory-ecosystem

54 GPU experiments. 47 language ports. 60M differential test inputs with zero mismatches. CUDA benchmarks on real hardware. Coq proofs of core semantics.

This is the lab notebook — the numbers, the code, and the honest negative results.

---

## The idea

Software verification uses floating-point. Float lies — NaN, Inf, rounding drift, ULP errors. Constraint theory uses integer range checks instead. Same math hardware engineers use for tolerance stacks and go/no-go gauges, but compiled to a 43-opcode bytecode that can't loop forever and runs at hardware speed.

```
GUARD DSL          ← Write constraints (like GD&T for software)
    ↓
FLUX-C Bytecode    ← Compile to 43-opcode ISA (terminates, always)
    ↓
GPU / ARM / FPGA   ← Execute at hardware speed
    ↓
Coq Proofs         ← 15 theorems cover core semantics
```

New here? Read the [Physical Engineer's Guide](docs/physical-engineers-guide.md). Fifteen minutes, no code, just O-rings and tolerance stacks.

---

## The numbers

All benchmarks on RTX 4050. Real hardware, not paper estimates.

| Configuration | Throughput | Precision loss |
|--------------|-----------|---------------|
| INT8 × 8 parallel | **62.2 B checks/sec** | Zero |
| CUDA Graphs (replay) | 9,500 B c/s | Zero |
| Temporal (rate + persistence) | 22.8 B c/s | Zero |
| Cross-sensor (AND/OR) | 14.8 B c/s | Zero |
| Streaming incremental (0.1% Δ) | 4,699 B c/s amortized | Zero |
| CPU scalar (Rust, single core) | 7.6 B c/s | Zero |
| FP16 (half-precision float) | ~50 B c/s | **76% mismatches** |

That last row is the whole argument. INT8 constraints are gauge blocks. Float is a rubber ruler.

---

## What's been verified

| What | Count | Status |
|------|-------|--------|
| English proofs | 30 | Done |
| Coq theorems | 15 (8 original + 7 saturation) | Proven |
| Differential test inputs | 60,000,000 | Zero mismatches |
| Industry constraint libraries | 248 across 10 industries | 100% pass |
| GPU experiments | 54 | All completed |
| VM tests (Rust + C) | 29 | All passing |

---

## What you can use

**47 language implementations** in `src/` — Ada, Assembly, C, C++, C#, CUDA, Clojure, COBOL, Crystal, Dart, Elixir, Erlang, F#, Fortran, Gleam, Go, Haskell, Java, JavaScript, Julia, Kotlin, Lua, MATLAB, Nim, Objective-C, OCaml, Pascal, Perl, PHP, PowerShell, Python, R, Ruby, Rust, Scala, Scheme, Shell, Swift, SystemVerilog, TypeScript, V, VBA, VHDL, WebGPU/WGSL, Zig.

**10 industry constraint libraries** (248 constraints): Aviation, Automotive, Maritime, Energy, Medical, Nuclear, Railway, Robotics, Space, Autonomous Underwater.

**CUDA kernels** — production-ready, benchmarked.

**Embedded runtime** (`flux_embedded.h`) — ARM Cortex-R, 42 opcodes, deterministic.

**REST API** — Docker container, deploy in minutes.

Example:

```
// GUARD constraint
GUARD o_ring_squeeze in [15, 25]

// FLUX-C bytecode
PUSH 15
PUSH squeeze_val
RANGE_CHECK
HALT
```

```python
from flux import guard_check
result = guard_check("o_ring_squeeze", value=22, lo=15, hi=25)
```

---

## What doesn't work

Honest negative results, because that's how science works:

- **FP16 fails.** 76% mismatch rate on the same workloads INT8 handles cleanly. This isn't fixable — float semantics are fundamentally wrong for exact constraints.
- **We are not certified.** Not DO-178C, not ISO 26262, not anything. The architecture is designed for certification, proof artifacts exist, the bytecode validator is complete. But certification takes time and money we haven't spent yet.
- **Coq proofs cover core semantics only.** 15 theorems. The GPU kernels are verified by differential testing (60M inputs), not formal proof.

---

## Certification path (future, not achieved)

| Standard | Domain | Status |
|----------|--------|--------|
| DO-178C DAL A | Aviation | Architecture designed, proof artifacts ready |
| DO-254 DAL A | Avionics hardware | FPGA SystemVerilog started |
| ISO 26262 ASIL-D | Automotive | Bytecode validator complete |
| IEC 61508 SIL 3 | Industrial control | Constraint libraries validated |
| IEC 62304 | Medical device | Medical constraints validated |

These are milestones on a path. Not achievements on a wall.

---

## Repo layout

```
constraint-theory-ecosystem/
├── src/              ← 47 language implementations
│   ├── cuda/         ← Production CUDA kernels
│   ├── embedded/     ← ARM Cortex-R (42 opcodes)
│   ├── rust/         ← Rust integration (571 lines, 16 tests)
│   ├── python/       ← Python + REST API
│   └── ...           ← 42 more languages
├── proofs/
│   └── coq/          ← 15 Coq theorems
├── constraints/      ← 10 industry libraries (248 total)
├── experiments/      ← 54 GPU experiments
├── chapters/         ← Book chapters (ch00–ch11)
├── docs/
│   ├── physical-engineers-guide.md  ← Start here
│   ├── constraint-theory-formalized.md
│   └── examples.md
└── tools/
    ├── safe_tops_per_watt.py
    └── playground.html
```

---

## Fleet

Built by [Forgemaster ⚒️](https://github.com/SuperInstance/forgemaster) and [Oracle1 🔮](https://github.com/SuperInstance/oracle1-vessel) of the [Cocapn Fleet](https://cocapn.ai).

## License

Apache-2.0
