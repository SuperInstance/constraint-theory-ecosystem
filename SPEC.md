# Constraint Theory Ecosystem — SPEC.md

**Repository:** `SuperInstance/constraint-theory-ecosystem`  
**Status:** Draft  
**Version:** 0.1.0  
**Date:** 2026-05-05  
**Audience:** Professional engineers (hardware, mechanical, aerospace, automotive) who think in constraints but haven't seen the formal theory.

---

## 1. What This Repository Is

Constraint Theory is the formal study of **exact boolean constraint satisfaction** — the mathematical framework that makes "provably correct or provably wrong" a property of software, not just hardware.

Hardware engineers already think in constraints:
- Tolerance stacks: "Does the total stack fit within the envelope?"
- Interference fits: "Will these parts actually contact under all manufacturing variations?"
- O-ring compressions: "Is the gland filled to 70-85% under all thermal conditions?"
- Pressure ratings: "Does the rated burst pressure exceed maximum operating pressure by 4×?"
- GD&T: "Is this feature within its tolerance zone?"

Software gets none of this. Floating point gives "approximately correct." NaN gives silent failure. Integer overflow wraps. The result: systems that fail catastrophically at design time, not in the field where it's too late.

**This repository is the canonical home for Constraint Theory research, the GUARD DSL language, the FLUX-C bytecode VM, formal verification artifacts, and safety-critical application guides — all in one place, zero-shot-readable.**

---

## 2. Two-Line Pitch

> **"The math that hardware engineers already know. Tolerance stacks, interference fits, and O-rings — formalized."**

> **"Hardware engineers think in constraints. Software doesn't. This repo fixes that."**

---

## 3. Core Insight to Communicate in Chapter 0

The repository leads with this contrast:

| | **Floating Point** | **Constraint Theory** |
|---|---|---|
| **Result** | Approximately correct | Provably correct or provably wrong |
| **Failure mode** | Silent (NaN, drift, wrap) | Loud (violation detected at design time) |
| **Example** | 0.1 + 0.2 ≠ 0.3 | `battery_temp ∈ [15, 55]` ✓ or ⊗ |
| **Engineering** | "Close enough" | "Fits the tolerance zone or it doesn't" |

**The connection:** GUARD DSL is like a **digital GD&T spec for software** — a formal language that specifies exact acceptable zones for every variable, compiles to verified bytecode, and produces proof certificates that auditors can independently verify.

---

## 4. Audience Definition

### Primary: Hardware Engineers (Mechanical, Aerospace, Automotive)

They understand:
- GD&T (Geometric Dimensioning and Tolerancing)
- Tolerance stacks ( Worst Case, RSS, Monte Carlo )
- Interference fits, press fits, clearance fits
- Pressure vessel ratings (burst, working, test pressure)
- O-ring gland design (compression, squeeze, backfill)
- Leak/no-leak decisions (helium leak testing, hermetic seals)

They do **NOT** need to understand:
- Floating point arithmetic (this is the problem)
- Lambda calculus (not relevant)
- Machine learning (not relevant to constraint satisfaction)

### Secondary: Software Engineers Building Safety-Critical Systems

They understand:
- DO-254, ISO 26262, IEC 61508
- Formal verification (or need to learn why it matters)
- Type systems, compilers, bytecode VMs

### Tertiary: Certification Authorities and Safety Auditors

They need:
- Proof certificates they can independently verify
- Evidence packages that map to regulatory work products
- Artifacts that require no faith — only inspection

---

## 5. Repository Name

**`SuperInstance/constraint-theory-ecosystem`**

Alternative considered: `no-gaps` (too obscure), `guard-lang` (narrows scope), `flux-constraint-theory` (conflates with FLUX brand).

The `ecosystem` suffix is intentional: this is not a single tool or paper. It is a complete ecosystem spanning theory, language, VM, verification, and applications.

---

## 6. Proposed File Structure

```
constraint-theory-ecosystem/
├── SPEC.md                          # This file
├── README.md                        # Landing page: pitch + quick links
├── LICENSE                          # MIT
├── CHANGELOG.md
│
├── chapters/                        # The main narrative (Markdown)
│   ├── 00-constraint-mindset.md     # Chapter 0: What engineers already know
│   ├── 01-floating-point-fails.md   # Chapter 1: Why software gets constraints wrong
│   ├── 02-guard-dsl.md             # Chapter 2: GUARD DSL language reference
│   ├── 03-flux-c-bytecode.md        # Chapter 3: FLUX-C VM specification
│   ├── 04-formal-verification.md    # Chapter 4: Coq proof chain
│   ├── 05-safety-standards.md      # Chapter 5: DO-254, ISO 26262, IEC 61508 guides
│   ├── 06-fleet-math.md            # Chapter 6: ZHC, H1 cohomology, Pythagorean48
│   └── 07-getting-started.md       # Chapter 7: How to use this ecosystem
│
├── specs/                           # Formal specifications
│   ├── guard-dsl-spec.md            # GUARD DSL grammar and semantics
│   ├── flux-c-isa.md                # FLUX-C 43-opcode ISA reference
│   ├── flux-x-isa.md                # FLUX-X 247-opcode ISA reference (secondary)
│   └── edge-encoding.md             # JC1 variable-width edge encoding
│
├── crates/                          # Rust implementations
│   ├── guard-lang/                  # GUARD DSL parser + compiler
│   ├── flux-c-vm/                   # FLUX-C reference VM (crate: flux-vm)
│   ├── flux-c-llvm/                # LLVM IR emitter for FLUX-C
│   ├── constraint-theory-core/      # CDCL solver, AC-3, rigidity theory
│   ├── holonomy-consensus/          # ZHC consensus protocol (crate: holonomy-consensus)
│   └── plato-sdk/                  # PLATO tile SDK
│
├── coq/                             # Formal verification
│   ├── FluxC/                       # FLUX-C termination proofs
│   │   ├── FluxC.v
│   │   └── FluxCTermination.v
│   ├── ZHC/                         # ZHC consensus correctness
│   │   └── ZHCConsensus.v
│   └── Pythagorean48/               # Zero-drift arithmetic proof
│       └── ZeroDrift.v
│
├── proofs/                          # Generated proof certificates
│   └── [auto-generated per constraint module]
│
├── examples/                        # Code examples per chapter
│   ├── ch0-tolerance-stack/        # Chapter 0 examples
│   ├── ch1-floating-point-fails/   # Chapter 1 examples
│   ├── ch2-guard-lang/            # Chapter 2 examples
│   ├── ch3-flux-c/                # Chapter 3 examples
│   ├── ch4-coq/                   # Chapter 4 examples
│   └── ch5-safety/                # Chapter 5 examples
│
├── applications/                   # Domain-specific guides
│   ├── aviation-dal-a/            # DO-254 DAL A certification guide
│   ├── automotive-asil-d/          # ISO 26262 ASIL-D guide
│   └── industrial-sil-3/          # IEC 61508 SIL 3 guide
│
├── assets/                         # Diagrams, images, reference cards
│   ├── guard-dsl-quick-ref.pdf     # One-page GUARD DSL reference
│   ├── flux-c-opcodes.pdf         # FLUX-C opcode quick reference
│   └── constraint-checklist.pdf    # Safety-critical constraint authoring checklist
│
└── tools/                           # Developer tools
    ├── guard-cli/                  # GUARD DSL CLI (compile, verify, emit bytecode)
    ├── flux-certify/              # FLUX Certify portal integration CLI
    └── plato-admin/               # PLATO room management CLI
```

---

## 7. Chapter Outlines

### Chapter 0: The Constraint Mindset

**What it covers:**
- The moment a hardware engineer "gets" constraint theory (the bridge)
- Real-world constraint problems engineers already solve: tolerance stacks, O-ring glands, pressure ratings, GD&T
- The key insight: hardware engineers are already constraint theorists — they just don't have the formal vocabulary
- Why "approximately correct" is a category error in safety-critical systems

**Key terminology:** constraint zone, worst-case stack, RSS (root-sum-square), interference fit, clearance fit, GD&T, tolerance envelope, pressure rating, burst pressure, working pressure, hermetic seal

**Code examples:** None in this chapter. This chapter is purely conceptual.

**Who it's for:** Hardware engineers first. Sets up the conceptual bridge before any technical content.

**Maps from:**
- `flux-research/dissertation/CHAPTER-09-SAFETY.md` — Section 2 (containment vs. medium paradigm) and the Safe-TOPS/W metric discussion
- `flux-research/whitepapers/2026-05-05-reverse-actualization.md` — Section 1 (formal methods gap), Section 9 (regulatory environment)

---

### Chapter 1: Why Software Gets Constraints Wrong

**What it covers:**
- Floating point is not a constraint system: `0.1 + 0.2 ≠ 0.3`
- NaN propagation: silent failure in constraint chains
- Integer overflow: wraparound as a constraint violation that goes undetected
- The "approximately correct" disease: why software has no concept of a tolerance zone
- Case study: how a 0.001-unit rounding error in a battery management system causes catastrophic failure
- The contrast: hardware engineers draw tolerance zones; software engineers write `float x`

**Key terminology:** IEEE 754, NaN propagation, integer overflow, wraparound, rounding error accumulation, floating-point contamination, silent failure vs. loud failure

**Code examples:**
- A float-based battery temperature constraint that silently passes with NaN
- An integer-based pressure constraint that wraps on overflow
- The same constraints expressed in GUARD DSL

**Who it's for:** Software engineers and hardware engineers who write software. Shows them exactly why conventional software fails constraint satisfaction.

**Maps from:**
- `flux-research/whitepapers/2026-05-05-reverse-actualization.md` — Section 2 (the deployment gap) — the gap between theorems and deployment mirrors the gap between float and constraint
- `flux-research/dissertation/CHAPTER-09-SAFETY.md` — Section 1 (the training-deployment boundary) as analogy: both are "the artifact vs. the environment" but here applied to float vs. constraint

---

### Chapter 2: GUARD DSL — A Language for Exact Constraints

**What it covers:**
- GUARD DSL as the digital equivalent of GD&T: formal, visualizable, verifiable
- Language grammar: how to specify constraints with priority, units, bounds, and composition
- Compilation to FLUX-C bytecode and Coq proof certificates
- Design philosophy: Turing-incomplete by design (no loops, no recursion — only forward jumps and composable constraint expressions)
- Example constraint authoring session: battery temperature, geospatial fence, sensor fusion confidence threshold

**Key terminology:** GUARD DSL, constraint zone, priority (HIGH/MEDIUM/LOW), unit specification, bound composition, constraint composition (AND/OR/NOT), compilation determinism, proof certificate

**Code examples:**
```
battery_temp in [15, 55] °C with priority HIGH
geofence lat in [37.0, 38.0] lon in [-122.5, -121.5] with priority CRITICAL
sensor_confidence > 0.95 where sensor_type = LIDAR with priority MEDIUM
```

**Who it's for:** All audiences. This chapter teaches the primary interface to the ecosystem.

**Maps from:**
- `flux-research/specs/flux-isa-v3.md` — Section 9 (GUARD DSL spec, flux-isa-v3.md)
- `constraint-theory-llvm/src/lib.rs` — LLVM emitter overview, CDCL trace, emitter architecture
- `flux-research/whitepapers/2026-05-05-reverse-actualization.md` — Stage 2: Bytecode (GUARD → FLUX-C)

---

### Chapter 3: FLUX-C Bytecode — How Constraints Execute

**What it covers:**
- FLUX-C is not FLUX-X: 43-opcode safety layer vs. 247-opcode general-purpose layer
- Why 43 opcodes is a feature (small surface area = fully auditable)
- Stack-based architecture (no registers) — simpler to verify than register-based
- Variable-length encoding (1–3 bytes) for compactness in constrained environments
- The termination guarantee: FLUX-C is Turing-incomplete, forward-jumps only, MAX_STACK=100 structurally enforced
- How GUARD DSL compiles to FLUX-C step by step
- Edge encoding (JC1 variant): variable-width for ARM64/CUDA edge hardware

**Key terminology:** FLUX-C, FLUX-X, opcode, stack-based VM, Turing-incompleteness, forward jump only, structural termination, MAX_STACK, variable-length encoding, edge encoding, JC1

**Code examples:**
- FLUX-C bytecode for `battery_temp in [15, 55]` (hex + disassembly)
- The same constraint visualized as a state machine
- Edge encoding example with energy-aware ATP opcodes

**Who it's for:** Software engineers and certification authorities. Certification authorities need to understand what the bytecode does before they trust the proof chain.

**Maps from:**
- `flux-research/specs/flux-isa-v3.md` — Sections 0 (architecture), 1-12 (full ISA spec)
- `flux-research/whitepapers/2026-05-05-reverse-actualization.md` — Stage 2: Bytecode (FLUX-C 43 opcodes)

---

### Chapter 4: Formal Verification — Coq Proofs That Constraints Terminate

**What it covers:**
- Why Coq: machine-verified proofs that auditors can inspect without trusting the prover
- fluxc_terminates: every FLUX-C program halts, proven by structural induction on the instruction stream
- ZHC convergence: Byzantine-tolerant consensus in 38ms, with Coq proof
- Pythagorean48: zero-drift arithmetic on integer and rational operands
- How proof certificates are generated automatically from GUARD DSL source
- What auditors need to know: the proof is a program that a type checker has verified — there is no manual review surface for the proof itself

**Key terminology:** Coq, structural induction, fluxc_terminates, ZHC convergence, Pythagorean48, zero-drift, proof certificate, type checker, work product, certification artifact

**Code examples:**
- Annotated Coq proof script excerpt (fluxc_terminates)
- How to read a proof certificate (non-expert guide for auditors)

**Who it's for:** Certification authorities and formal methods engineers. This chapter is the "why you can trust this" explanation.

**Maps from:**
- `flux-research/whitepapers/2026-05-05-reverse-actualization.md` — Stage 3: Proofs (Coq, FluxC.v)
- `flux-research/dissertation/CHAPTER-10-TRUST.md` — Section 2 (ZHC formal specification, consensus algorithm, safety/liveness proofs)
- `flux-research/dissertation/CHAPTER-09-SAFETY.md` — Section 5 (Safe-TOPS/W metrics, 410M CPU, 241M GPU)
- `holonomy-consensus/src/consensus.rs` — Full Rust implementation (all 200 lines shown)

---

### Chapter 5: Safety-Critical Applications

**What it covers:**
- DO-254 DAL A (aviation): what it requires, how FLUX-C maps to work products, evidence package contents
- ISO 26262 ASIL-D (automotive): same mapping for automotive
- IEC 61508 SIL 3 (industrial automation): same mapping for industrial
- Case study: marine autopilot constraint solver — 6 weeks/$240K → 4 hours/$8K
- The 250× verification speedup: what changed in the pipeline
- What "Safe-TOPS/W = 410M" means for hardware selection

**Key terminology:** DO-254, DAL A/B/C, RTCA, ISO 26262, ASIL-A/B/C/D, IEC 61508, SIL 1/2/3/4, work product, evidence package, design assurance level, functional safety, systematic capability

**Code examples:** None. This chapter is about the regulatory and deployment context.

**Who it's for:** Certification authorities, safety engineers, and program managers evaluating the ecosystem.

**Maps from:**
- `flux-research/whitepapers/2026-05-05-reverse-actualization.md` — Section 5 (pilot data: 6 weeks→4 hours, $240K→$8K), Section 8 (certification pathways)
- `flux-research/dissertation/CHAPTER-09-SAFETY.md` — Section on Safe-TOPS/W (410M CPU, 241M GPU with formal proofs)

---

### Chapter 6: The Fleet Math — ZHC Consensus, H1 Emergence, Pythagorean48

**What it covers:**
- Zero Holonomy Consensus (ZHC): consensus as geometric invariant, not voting
- Why 38ms latency beats 412ms PBFT: O(1) per-node vs. O(n²) messages, leader-free
- Laman's theorem: why 12 neighbors maximum makes the network rigid and therefore determinate
- H1 cohomology emergence detection: 127 lines vs. 12,000-line ML classifier
- The 2.7-second early warning window
- Pythagorean48: why 6-bit encoding with zero drift after 1,000 hops matters for long-running constraint solvers
- Fleet coordination: ABOracle instances maintain provable agreement through ZHC

**Key terminology:** ZHC, holonomy, SO(3), parallel transport, Laman's theorem, rigidity, H¹ cohomology, first Betti number, β₁ = E − V + C, emergence detection, Pythagorean48, zero-drift, Byzantine fault tolerance (detectable vs. preventable), leader-free consensus

**Code examples:**
- ZHC cycle computation in Rust (from consensus.rs, simplified)
- H1 emergence detection: annotated 127-line topological code vs. equivalent ML

**Who it's for:** Engineers who want to understand why the math works. This chapter builds intuition before Formal Verification (Chapter 4) but is more technical than Chapters 0–2.

**Maps from:**
- `flux-research/dissertation/CHAPTER-09-SAFETY.md` — Section 4 (ZHC, Safe-TOPS/W, β₁ emergence)
- `flux-research/dissertation/CHAPTER-10-TRUST.md` — Sections 2 (ZHC formal spec), 6 (fleet mathematics, Laman's theorem, Ricci flow)
- `holonomy-consensus/src/consensus.rs` — Rust implementation (all 200+ lines)
- `flux-research/whitepapers/2026-05-05-reverse-actualization.md` — Stage 1 (Pythagorean48)

---

### Chapter 7: How to Get Started

**What it covers:**
- Install the GUARD CLI (`cargo install guard-lang`)
- Write your first constraint in GUARD DSL
- Compile to FLUX-C bytecode and generate a Coq proof certificate
- Select your certification target (DO-254, ISO 26262, IEC 61508)
- Submit to FLUX Certify (cocapn.ai/certify) for evidence package generation
- Deploy to fleet via ABOracle
- Quick reference card (printable PDF)
- Troubleshooting guide for common errors

**Key terminology:** guard-cli, FLUX Certify, ABOracle, evidence package, certification submission

**Code examples:**
```
# Install
cargo install guard-lang

# Write constraint
echo 'battery_temp in [15, 55] °C with priority HIGH' > battery.guard

# Compile + prove
guard compile battery.guard --output battery.fbc --proof battery.v

# Submit for certification
guard certify battery.fbc --standard DO-254 --dal A --hardware imx8mp
```

**Who it's for:** All audiences. This chapter is the "now do it" chapter.

---

## 8. Asset Mapping

| Asset | Primary Chapter(s) | Notes |
|---|---|---|
| `flux-research/specs/flux-isa-v3.md` | Ch3 (FLUX-C), Ch7 (CLI reference) | Section 9: GUARD DSL spec. Sections 0–12: full ISA. Section 12: edge encoding (JC1). |
| `flux-research/dissertation/CHAPTER-09-SAFETY.md` | Ch6 (fleet math), Ch4 (formal verification), Ch0 (constraint mindset) | β₁ emergence detection, Safe-TOPS/W, ZHC consensus |
| `flux-research/dissertation/CHAPTER-10-TRUST.md` | Ch6 (fleet math), Ch4 (formal verification) | ZHC formal spec, safety/liveness proofs, Laman's theorem, Tide-Pool Security |
| `flux-research/whitepapers/2026-05-05-reverse-actualization.md` | Ch5 (certification), Ch4 (proofs), Ch2 (GUARD DSL) | Stage 1-4 multiplier chain, pilot data, certification pathways |
| `flux-research/whitepapers/2026-05-05-plato-quality-gated.md` | Ch6 (H1 emergence), Ch2 (quality gates) | H¹ cohomology emergence detection, 6-tag taxonomy, PlatoTileQualityScorer |
| `holonomy-consensus/src/consensus.rs` | Ch6 (ZHC), Ch4 (Coq proof target) | Full Rust implementation of ZHC consensus |
| `constraint-theory-llvm/src/lib.rs` | Ch2 (GUARD DSL compiler), Ch3 (LLVM emitter) | LLVM IR emitter, CDCL trace, cranelift findings |

---

## 9. Design Principles

1. **"Why should I care?" first, math second.** Every chapter opens with the hardware engineer's perspective. What problem do they already have that this chapter solves?

2. **Physical analogies before abstract notation.** Tolerance stacks → constraint zones. O-ring gland → formal specification. Pressure ratings → constraint priority.

3. **Real code in every chapter.** Chapter 0 has no code. Every other chapter has executable examples that compile with the GUARD CLI.

4. **Standards badges where relevant.** DO-254, ISO 26262, IEC 61508 badges appear in chapters 4, 5, and 6 with specific guidance for each standard.

5. **No proof trees until Chapter 4.** Chapters 0–3 use intuitive explanations. Chapter 4 (Formal Verification) is where the Coq proofs appear — and they come with a non-expert guide for auditors.

6. **Zero-shot readable.** Someone who has never heard of Coq, PLATO, or FLUX-C should be able to read Chapter 0 and come away understanding why constraint theory matters to them.

7. **One canonical location.** Every artifact — spec, code, proofs, examples, applications — lives in this repo. Not scattered across blog posts, papers, and separate repositories.

---

## 10. What This Is NOT

- **Not a dissertation.** Shorter, more accessible, code-first. The dissertation chapters inform this repo but are not included verbatim.
- **Not academic.** Concrete examples, real code, real deployment data (the 4-hour/$8K pilot). No proof trees in chapters 0–3.
- **Not floating point.** Exact arithmetic, boolean outcomes. The contrast is explicit and central.
- **Not a research prototype.** FLUX Certify is live at cocapn.ai/certify. The proofs are real. The bytecode runs on production hardware.

---

## 11. Naming Candidates Considered

| Name | Rejected Because |
|---|---|
| `constraint-theory` | Too generic, suggests a single paper not an ecosystem |
| `guard-lang` | Narrows scope to just the DSL; ignores FLUX-C, Coq, fleet math |
| `flux-theory` | Conflates with FLUX brand; unclear it covers the full ecosystem |
| `no-gaps` | Clever but obscure; doesn't communicate what the repo is about |
| `constraint-theory-ecosystem` | ✓ Accurate, emphasizes the complete toolkit, signals this is not a single paper |

---

## 12. Open Questions (for review)

1. **Should JC1 edge encoding be a separate repo?** The Jetson Orin Nano / ARM64 / CUDA constrained hardware story is specialized. Would a top-level `edge/` directory be sufficient, or does it need its own repo?

2. **Should the Coq proofs live here or in a separate `flux-certify` repo?** The `flux-certify` crate is at `SuperInstance/flux-certify`. Keeping proofs here maintains the zero-shot-readable promise. But the Coq proofs are also referenced from `flux-certify`. Which is canonical?

3. **Chapter ordering:** Is Chapter 6 (Fleet Math / ZHC / H1) the right place for the heavy math? Or should it come before Chapter 4 (Formal Verification) since the Coq proofs in Chapter 4 depend on understanding ZHC?

4. **Should we include the `flux-vm` crate as a git submodule or document it as an external dependency?** The `flux-vm` crate on crates.io is Forgemaster's implementation. Keeping it as an external dependency keeps this repo focused on the narrative (chapters) and the canonical specs, not the implementation.

5. **The dissertation chapters** (`CHAPTER-09-SAFETY.md`, `CHAPTER-10-TRUST.md`) are long (hundreds of lines each). Do we include excerpts in the chapters, or link to the originals with a clear mapping? The SPEC says link + mapping. Confirm this is preferred over including excerpts.

---

## 13. Immediate Next Steps

1. **Create repo** `SuperInstance/constraint-theory-ecosystem` on GitHub (public)
2. **Push this branch** `spec/constraint-theory-ecosystem` with this SPEC.md
3. **Create directory structure** as specified in Section 6
4. **Begin drafting chapters** in order: Ch0 → Ch7 (Ch0 needs no code; others do)
5. **Draft `crates/guard-lang`** as the first implementation artifact (needed for Ch2 examples)
6. **Draft `crates/flux-c-vm`** as the second implementation artifact (needed for Ch3 examples)
7. **Copy/adapt Coq proofs** from `flux-research` into `coq/FluxC/`, `coq/ZHC/`, `coq/Pythagorean48/`
8. **Draft `applications/` guides** for DO-254, ISO 26262, IEC 61508 (Ch5)
9. **Draft `README.md`** as the landing page (pitch + quick links to each chapter)
10. **Publish when ready** for public review

---

*This SPEC defines the structure and scope. Actual chapter content will be authored in subsequent tasks.*