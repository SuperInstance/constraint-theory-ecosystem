# Contributing to Constraint Theory Ecosystem

## Who We Want

**Physical engineers.** Mechanical, aerospace, civil, marine, nuclear, automotive. If you've ever specified a tolerance, designed a fixture, or rejected a part, you already think in constraints. We want your domain knowledge.

**Safety engineers.** DERs, QE engineers, certification specialists. You know what DO-178C demands. Help us map every objective.

**Software engineers.** Rust, CUDA, C, Python, PHP. If you care about correctness over cleverness, we need you.

## How to Contribute

### Add a Constraint Example

The easiest contribution. Pick a physical system you know well:

1. Read [docs/examples.md](docs/examples.md) for the format
2. Write your example following the pattern:
   - Physical problem (with real numbers)
   - GUARD constraint
   - FLUX-C bytecode
   - Verification (pass/fail cases)
3. Submit a PR

Examples we want:
- PCB trace impedance constraints
- Concrete mix design limits
- Weld joint inspection criteria
- Pipeline pressure safety
- Aircraft weight and balance
- Pharmaceutical dosage limits
- Structural load factors

### Add an Industry Library

[constraints/](constraints/) has 10 industries. We want more:

- Construction (ACI 318, AISC 360)
- Chemical processing (API 520, ASME VIII)
- Food safety (HACCP, FDA 21 CFR)
- Mining (MSHA, ISO 19434)
- Railway signaling (EN 50129, CENELEC)
- Offshore structures (API RP 2A, NORSOK)
- Semiconductor manufacturing (SEMI standards)

Each library needs:
- 20-30 constraints in GUARD format
- Standards references
- Test cases (50 pass, 50 fail)

### Improve Documentation

- Fix technical errors
- Add clarifying examples
- Improve diagrams
- Translate for your engineering discipline

### Report Issues

Found a mismatch between theory and practice? That's a bug. Report it.

## Style Guide

### Writing for Physical Engineers

- **Use SI units** (mm, MPa, °C, kg) unless the industry standard uses Imperial
- **Show the math** — don't hide it behind abstractions
- **Use physical analogies** — tolerance stacks, go/no-go gauges, GD&T
- **No filler** — "important to note", "it's worth mentioning", "great question" — cut it
- **Real numbers** — no "approximately", "roughly", "about". Show your sources.

### Code Style

- **INT8 saturation everywhere** — never use raw INT8 without saturation
- **No floating point in constraint paths** — integers only
- **Test every function** — minimum 80% line coverage
- **Document the WHY** — code comments explain decisions, not mechanics

### Commit Messages

```
feat: what you added
docs: what you documented  
fix: what you fixed
test: what you tested
```

## Repository Structure

```
constraint-theory-ecosystem/
├── chapters/          ← Book chapters (coordinate with Oracle1)
├── constraints/       ← Industry libraries (add yours)
├── docs/              ← Papers, guides, examples
├── experiments/       ← GPU experiment results
├── proofs/            ← Coq and English proofs
├── src/               ← Implementation (CUDA, Rust, C, PHP, Python)
└── tools/             ← Utilities and demos
```

## Fleet Coordination

This repo is built by the [Cocapn Fleet](https://cocapn.ai):

- **Forgemaster ⚒️** — GPU kernels, formal proofs, benchmarks
- **Oracle1 🔮** — Book chapters, DSL design, certification architecture
- **CCC 🦀** — Fleet math, curriculum, agent infrastructure

Push often. Read each other's work. The constraint is the point.

## License

By contributing, you agree your work is licensed under Apache 2.0.
