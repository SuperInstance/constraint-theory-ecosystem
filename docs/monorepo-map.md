# Navigating This Repository — A Map for Newcomers

**71 files. 78,000 words. 7 languages. Where do you start?**

Depends on who you are.

---

## I'm a Physical Engineer 🏗️

You design hydraulic fittings, O-ring seals, press-fit bearings. You think in tolerances.

| Order | Read | Time | What You'll Learn |
|-------|------|------|-------------------|
| 1 | [Physical Engineer's Guide](physical-engineers-guide.md) | 15 min | O-rings → constraints, rubber ruler → float, gauge blocks → INT8 |
| 2 | [Examples](examples.md) | 15 min | 6 worked examples from your world |
| 3 | [Quickstart](../QUICKSTART.md) | 10 min | Try it yourself (browser, no install) |
| 4 | [Constraint Theory Formalized](constraint-theory-formalized.md) | 30 min | Full theory paper (4,453 words) |
| 5 | [Ch08 GPU Architecture](../chapters/ch08-gpu-architecture.md) | 20 min | How we check 62B constraints/sec |

**Total: ~90 minutes to full understanding.**

## I'm a Software Engineer 💻

You write code. You want to integrate constraint checking.

| Order | Read | Time | What You'll Learn |
|-------|------|------|-------------------|
| 1 | [Quickstart](../QUICKSTART.md) | 10 min | 7 languages, copy-paste code |
| 2 | `src/python/flux_constraint.py` | 10 min | Python API (10 presets, 1.7M c/s) |
| 3 | `src/js/flux-constraint.js` | 10 min | JavaScript API (browser + Node) |
| 4 | [API Reference](api-reference.md) | 15 min | REST API spec (6 endpoints) |
| 5 | `src/rust/flux_constraint.rs` | 15 min | Rust implementation (16 tests) |
| 6 | `src/cuda/flux_production_v2.cu` | 20 min | CUDA kernel (62.2B c/s) |

**Total: ~80 minutes to integration.**

## I'm a Safety Engineer ⚠️

You certify systems. DO-178C, ISO 26262, IEC 61508.

| Order | Read | Time | What You'll Learn |
|-------|------|------|-------------------|
| 1 | [Standards Mapping](standards-mapping.md) | 20 min | Objective-by-objective evidence |
| 2 | [Certification Roadmap](chapters/ch11-certification-roadmap.md) | 20 min | 18-month DAL A plan |
| 3 | [Proofs Inventory](../proofs/INVENTORY.md) | 10 min | 15 Coq theorems catalogued |
| 4 | [Safe-TOPS/W Spec](specs/safe-tops-per-watt.md) | 10 min | Benchmark methodology |
| 5 | [INT8 Saturation Spec](specs/int8-saturation-semantics.md) | 10 min | Formal arithmetic properties |
| 6 | [GPU Results](../experiments/RESULTS.md) | 15 min | 54 experiments, 60M inputs, 0 mismatches |

**Total: ~85 minutes to evidence review.**

## I'm a Certification Authority 📋

You're a DER or assessor reviewing FLUX for tool qualification.

| Order | Read | Time | What You'll Learn |
|-------|------|------|-------------------|
| 1 | [Proofs Inventory](../proofs/INVENTORY.md) | 10 min | 15 Coq theorems |
| 2 | [Standards Mapping](standards-mapping.md) | 20 min | DO-178C objective mapping |
| 3 | [GPU Results](../experiments/RESULTS.md) | 15 min | Verification evidence |
| 4 | [Experiments Index](../experiments/INDEX.md) | 10 min | 54 experiment summaries |
| 5 | `src/rust/bytecode_validator.rs` | 15 min | 5-phase validation pipeline |
| 6 | `src/embedded/flux_embedded.h` | 15 min | WCET-bounded VM (42 opcodes) |
| 7 | [Certification Roadmap](chapters/ch11-certification-roadmap.md) | 20 min | Timeline and budget |

**Total: ~105 minutes to audit readiness.**

## I'm a Researcher 🔬

You study formal methods, GPU computing, or safety-critical systems.

| Order | Read | Time | What You'll Learn |
|-------|------|------|-------------------|
| 1 | [Constraint Theory Formalized](constraint-theory-formalized.md) | 30 min | Theory paper (4,453 words) |
| 2 | [EMSOFT Paper](papers/emsoft-flux-complete.md) | 30 min | Conference paper (8,366 words) |
| 3 | `proofs/coq/flux_saturation_coq.v` | 20 min | 7 Coq proofs |
| 4 | [GPU Results](../experiments/RESULTS.md) | 15 min | All benchmark data |
| 5 | [Blog Series](blog/) | 30 min | 5 posts, 8,635 words |

**Total: ~125 minutes to research depth.**

---

## Dependency Graph

```
Physical Engineer's Guide ──→ Examples ──→ Quickstart ──→ src/*
       │                          │
       └──→ Theory Paper ──→ Coq Proofs ──→ Standards Mapping ──→ Cert Roadmap
                                    │
                                    └──→ GPU Results ──→ Experiments Index

Quickstart ──→ Python ──→ REST API ──→ Dockerfile
            ──→ JavaScript
            ──→ Rust
            ──→ PHP
            ──→ C (embedded)
            ──→ CUDA
```

---

## File Counts by Category

| Category | Files | Words | Purpose |
|----------|-------|-------|---------|
| Chapters | 12 | ~28,000 | Book-length theory |
| Code (7 langs) | 14 | — | Integration kits |
| Tests | 6 | — | 85+ tests passing |
| Specs | 2 | ~1,500 | Formal specifications |
| Examples | 1 | ~1,000 | Worked walkthroughs |
| Papers | 1 | ~8,400 | EMSOFT paper |
| Blog | 5 | ~8,600 | Public posts |
| Benchmarks | 3 | — | GPU experiment data |
| Proofs | 2 | — | Coq theorems |
| Config | 4 | — | CI, Docker, git |

**Total: 71 files, 78,028 words, 20 commits**

---

*Pick your path. Start reading. Ship constraints.*
