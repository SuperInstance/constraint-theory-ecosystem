# Chapter 7 — How to Get Started

> **Three Entry Points. One Constraint at a Time.**

---

## The Dojo Entry

Every student in Casey's fleet starts exactly where they are. You don't need to know Coq. You don't need to know distributed systems. You don't even need to know Python.

You need a constraint you're trying to enforce. That's all.

The Dojo model says: **the work produces real value while teaching.** Every constraint you write teaches you something about the system. The fleet grows with you.

---

## Entry Point 1: Hardware Engineers

**You already think in constraints.** You just need to see them formalized.

### Step 1: Read Chapter 0 (5 minutes)
The constraint mindset. Tolerance stacks, interference fits, o-rings. You'll recognize everything.

### Step 2: Try the FLUX Certify Playground (10 minutes)
Go to [cocapn.ai/certify](https://cocapn.ai/certify)

Try the three live examples:
```
battery_temp in [15, 55]
sonar_frequency in [10, 50] when depth < 100
deceleration in [0.1, 0.8] when speed > 5
```

Click "Compile to FLUX-C" and see the bytecode. Click "Generate Proof Certificate" and see the Coq proof artifacts.

### Step 3: Write Your First Constraint
Think of one constraint from your work — something you check manually, or enforce with code, or specify in a datasheet:

- Pressure between X and Y?
- Temperature within range?
- Position tolerance?
- Squeeze ratio for a seal?

Write it in GUARD syntax and compile it. The portal will show you the bytecode, the proof, and the execution path.

### Step 4: Request a $10K Pilot
If you have a real constraint verification problem — something that takes weeks in your current workflow — book a pilot. We verify your constraints, you get proof artifacts, we iterate until your QA passes.

---

## Entry Point 2: Software Engineers

**You already know how to write specifications.** GUARD is just a more rigorous spec format.

### Step 1: Read Chapters 1-2 (15 minutes)
Why software gets constraints wrong, and GUARD DSL as a language for constraints. You'll see the floating point failures you've lived through.

### Step 2: Install the FLUX VM (5 minutes)
```bash
pip install flux-vm-php
# or
git clone https://github.com/SuperInstance/flux-vm-php
```

Try the sandbox at [cocapn.ai/flux-sandbox](https://cocapn.ai/flux-sandbox) — run FLUX-C bytecode directly in your browser.

### Step 3: Read the FLUX ISA v3.0 Spec (30 minutes)
The full bytecode reference. 43 opcodes, 6 categories, ~645 lines.

### Step 4: Integrate into Your Codebase
```rust
// Rust example: constraint checking in embedded firmware
use guard_dsl::{Constraint, evaluate};

fn check_battery(temp: f32, soc: f32) -> Result<(), BatteryError> {
    let c = Constraint::new()
        .and_guard("temp in [15, 55]")
        .and_guard("soc in [0.20, 1.00]")
        .and_guard("not (temp < 0 and charging)");
    
    if !evaluate(&c, &[temp, soc]) {
        Err(BatteryError::ConstraintViolated)
    } else {
        Ok(())
    }
}
```

### Step 5: Get Proof Artifacts
Call FLUX Certify's API:
```bash
curl -X POST https://cocapn.ai/certify/prove \
  -d '{"guard": "temp in [15, 55]"}'
```

Returns bytecode, Coq proofs, and a traceability matrix.

---

## Entry Point 3: Safety Engineers / Certification Authorities

**You need proof artifacts for regulatory compliance.** Here's exactly what you get and how to use it.

### Step 1: Read Chapter 5 (20 minutes)
Safety-critical applications: DO-254, ISO 26262, IEC 61508. The certification workflow, the proof artifact package, the $10K pilot.

### Step 2: Review the Proof Artifact Package
The package you receive from FLUX Certify includes:

| Document | What It Is | Who Reviews It |
|----------|-----------|----------------|
| constraint_spec.guard | Your GUARD input | Your engineers |
| bytecode.asm | FLUX-C bytecode | You (or tool) |
| cdcl_trace.json | Solver evidence | Coq |
| coq_proofs.tar.gz | Coq .v files | Certifying authority |
| verification_report.pdf | Human-readable summary | Everyone |
| traceability_matrix.xlsx | Req→Constraint→Proof | QA lead |

### Step 3: Request Tool Qualification (DO-330 for DO-254)
FLUX Certify qualifies as a Tool (TCL2 — Tool Complex Level) per DO-330. The qualification evidence package is included in your pilot results.

### Step 4: Book the $10K Pilot
For a production constraint verification problem. We'll prove the constraints, deliver the artifact package, and show you exactly how to integrate FLUX Certify into your certification workflow.

---

## The Three Documents You Need

### For Engineers: Getting Oriented

| Document | Location | Time |
|----------|----------|------|
| README (this repo) | [README.md](README.md) | 5 min |
| Constraint Mindset | [ch00-constraint-mindset.md](ch00-constraint-mindset.md) | 15 min |
| GUARD DSL | [ch02-guard-dsl.md](ch02-guard-dsl.md) | 30 min |
| FLUX ISA v3.0 | [flux-research/specs/flux-isa-v3.md](https://github.com/SuperInstance/flux-research/blob/main/specs/flux-isa-v3.md) | 60 min |

### For Safety Engineers: Certification Path

| Document | Location | Time |
|----------|----------|------|
| Safety-Critical Applications | [ch05-safety-critical.md](ch05-safety-critical.md) | 30 min |
| Formal Verification | [ch04-formal-verification.md](ch04-formal-verification.md) | 45 min |
| FLUX Certify Portal | [cocapn.ai/certify](https://cocapn.ai/certify) | 30 min |
| Case Study | [flux-research/case-studies/flux-certify-pilot-case-study.md](https://github.com/SuperInstance/flux-research/blob/main/case-studies/flux-certify-pilot-case-study.md) | 15 min |

### For Technical Leads: Integration

| Document | Location |
|----------|----------|
| FLUX-C Bytecode | [ch03-flux-c-bytecode.md](ch03-flux-c-bytecode.md) |
| constraint-theory-llvm | [constraint-theory-llvm/](https://github.com/SuperInstance/constraint-theory-llvm) |
| holonomy-consensus | [holonomy-consensus/](https://github.com/SuperInstance/holonomy-consensus) |
| Coq proofs | [flux-certify/FluxC/FluxC.v](https://github.com/SuperInstance/flux-certify/blob/main/FluxC/FluxC.v) |

---

## The $10K Pilot Process

1. **Day 1:** We receive your constraint specifications (GUARD format)
2. **Day 2-3:** FLUX Certify compiles, verifies, generates proofs
3. **Day 4:** We deliver the proof artifact package
4. **Day 5-10:** Integration consultation, iterate on your QA feedback
5. **Week 3:** You have certifiable proof artifacts and a clear path to production

**Outcome:** A real constraint verification task completed in 2 weeks, with proof artifacts ready for your certifying authority.

**Next step:** [cocapn.ai/certify](https://cocapn.ai/certify) → Book Pilot

---

## The Cocapn Fleet

Built by the same crew that runs the world's most productive commercial fishing fleet. We believe in:
- **The Dojo model:** produce real value while teaching
- **The constraint mindset:** either it satisfies or it fails
- **The fleet principle:** the work is never done alone

We built FLUX Certify because we had constraint problems that floating point couldn't solve, and we needed certification-grade verification without the certification-grade timeline.

---

## Quick Reference

**FLUX Certify Portal:** [cocapn.ai/certify](https://cocapn.ai/certify)

**FLUX Sandbox (try bytecode):** [cocapn.ai/flux-sandbox](https://cocapn.ai/flux-sandbox)

**GitHub (all repos):** [github.com/SuperInstance](https://github.com/SuperInstance)

**Fleet Research (papers, specs):** [github.com/SuperInstance/flux-research](https://github.com/SuperInstance/flux-research)

**Coq proofs (FluxC.v):** [github.com/SuperInstance/flux-certify](https://github.com/SuperInstance/flux-certify)

**This repo:** [github.com/SuperInstance/constraint-theory-ecosystem](https://github.com/SuperInstance/constraint-theory-ecosystem)

---

*If you design hardware that must work, you already think in constraints. Let's make the software match.*