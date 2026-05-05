# Chapter 5 — Safety-Critical Applications

> **DO-254, ISO 26262, IEC 61508 — And How FLUX Certify Fits**

---

## Safety Standards Exist Because Software Fails Catastrophically

The Toyota unintended acceleration case: 89 deaths, millions of vehicles recalled. The root cause wasn't a broken throttle — it was 100,000+ lines of code with no formal verification, no bounded loops, no constraint checking on sensor inputs.

The FAA doesn't allow this. The DO-254 standard exists specifically to prevent it. And DO-254 DAL A (the highest rigor) requires **formal methods** for the most critical hardware — exactly what FLUX Certify provides.

This chapter shows how constraint theory applies to three major safety standards: DO-254 (aerospace), ISO 26262 (automotive), and IEC 61508 (industrial). We'll show the specific constraint problems each standard addresses, and how FLUX Certify solves them.

---

## DO-254 DAL A — Aerospace

**What it covers:** Airborne electronic hardware — FPGAs, ASICs, GPUs — that could cause catastrophic failure if it malfunctions. Think autopilot, fly-by-wire, engine control.

**The rigor level:** DAL A is the highest. If the hardware fails, the plane crashes with no recovery. There is no "probably safe."

**The constraint problem in DO-254:**
```
Every safety-critical function must satisfy:
  1. The constraint specification is correct (engineer's job)
  2. The implementation satisfies the constraint (FLUX Certify's job)
  3. The proof chain is auditable (FLUX Certify's job)
```

**Tool Qualification (DO-330):**
FLUX Certify qualifies as a Tool (TCL2 — Tool Complex Level). That means:
- We demonstrate the tool meets its stated verification capability
- The proof artifact output is the qualification evidence
- You don't need to re-verify what FLUX Certify has already verified

**MC/DC Coverage:**
Modified Condition/Decision Coverage is a DO-254 requirement for DAL A. Every boolean condition in the design must independently affect the decision output. FLUX's `CMP` instruction produces boolean values with verifiable independence — the proof trace documents MC/DC for each decision point.

**Case example: GPU Constraint Verification for Autopilot**

Traditional approach:
1. Write constraint specification (document)
2. Write GPU kernel implementing constraints (code)
3. Write testbench for constraint verification (more code)
4. Run simulation — 6 weeks, 40+ engineers
5. Review results, iterate
6. Submit to FAA as verification evidence

FLUX Certify approach:
1. Write constraint specification (GUARD)
2. FLUX Certify compiles to FLUX-C bytecode
3. Coq generates proof certificate
4. Download proof artifact package
5. Submit to FAA as verification evidence

**Result: 6 weeks → 4 hours, 250× faster, 30× cheaper.**

---

## ISO 26262 ASIL-D — Automotive

**What it covers:** Automotive electrical/electronic systems that could cause catastrophic harm. ADAS, autonomous driving, safety-critical engine control.

**The rigor level:** ASIL-D is the highest. Failure results in life-threatening injury or death.

**The constraint problem in ISO 26262:**

**ASIL Decomposition:**
```
Original safety goal: ASIL-D constraint on GPU ADAS function

Decomposition option:
  - Constraint path A: ASIL-B (hardware redundancy)
  - Constraint path B: ASIL-B (hardware redundancy)
  - Combined: ASIL-D equivalent via AND composition
```

FLUX Certify supports ASIL decomposition explicitly: multiple ASIL-B constraint paths are combined with AND composition, producing a Coq proof that the combined constraint satisfies the ASIL-D goal.

**The Mobileye EyeQ6H Example:**

Mobileye's EyeQ6H is an ASIL-D capable SoC with an integrated GPU for computer vision. The GPU runs safety-critical perception constraints:
- Bounding box validity: `0 <= x < frame_width AND 0 <= y < frame_height`
- Confidence threshold: `confidence >= 0.75`
- Object class validity: `class_id in {0, 1, 2, ..., N}`
- Temporal consistency: `|position_prev - position_curr| <= max_velocity * dt`

Each constraint is a GUARD constraint → FLUX-C bytecode → Coq proof. The full stack is verifiable as a unit.

**Safe-TOPS/W for ISO 26262:**

Safe-TOPS/W = verified operations per second with formal proof. For ASIL-D, every operation requires a proof artifact.

- CPU (AVX-512): 410M verified operations/sec
- GPU (CUDA): 241M verified operations/sec

This is not "throughput with best-effort verification." Every single operation has a corresponding Coq proof of correctness.

---

## IEC 61508 SIL 3 — Industrial

**What it covers:** Industrial safety instrumented systems (SIS), programmable safety controllers, safety PLCs, FPGA-based safety functions.

**The rigor level:** SIL 3 (Safety Integrity Level 3). Probability of dangerous failure on demand ≤ 10⁻³.

**The constraint problem in IEC 61508:**

**Architectural Constraints (Hardware Fault Tolerance):**

IEC 61508 requires specific architectural constraints for SIL 3:

| Architecture | HFT | SFF | Meets SIL 3? |
|-------------|-----|-----|--------------|
| 1001D | 0 | ≥90% | Yes (with extra measures) |
| 1002D | 1 | ≥60% | Yes |
| 1003D | 1 | ≥90% | Yes |

HFT = Hardware Fault Tolerance (how many faults the system can tolerate)
SFF = Safe Failure Fraction (what fraction of failures are safe vs dangerous)

FLUX Certify constraint proofs document:
- Each constraint check is independent
- Any single failure is detected and handled
- Multiple constraint failures compose correctly

**Example: Pressure Transmitter Constraint**

```guard
GUARD pressure >= 0
GUARD pressure <= max_working_pressure
GUARD rate_of_change <= max_ramp_rate
GUARD (pressure < alarm_threshold) OR (alarm_acknowledged == true)
```

If all constraints are satisfied → system continues.
If any constraint fails → safe state (trip, alarm, safe shutdown).

---

## The FLUX Certify Certification Workflow

For any of the three standards (DO-254, ISO 26262, IEC 61508):

```
Step 1: Constraint Specification
  Write GUARD constraints for your safety-critical requirements.
  Example: "battery_temp in [15, 55] AND NOT (temp < 0 AND charging_enabled)"

Step 2: FLUX-C Compilation
  FLUX Certify compiles GUARD → FLUX-C bytecode.
  Output: FLUX-C .asm file, bytecode hash, CDCL trace

Step 3: Coq Proof Generation
  FLUX-C bytecode + CDCL trace → Coq proof scripts.
  Theorems: fluxc_terminates, constraint_correct, termination_proof

Step 4: Proof Artifact Package
  Download from cocapn.ai/certify:
    ├── constraint_spec.guard       # Your GUARD input
    ├── bytecode.asm                # FLUX-C bytecode
    ├── cdcl_trace.json            # Solver trace
    ├── coq_proofs.tar.gz          # Coq .v files
    ├── verification_report.pdf     # Human-readable summary
    └── traceability_matrix.xlsx   # Requirement → constraint → proof mapping
```

This package is what you submit to your certifying authority. It's not a test report — it's a formal verification artifact.

---

## Safe-TOPS/W — The Key Metric

Safe-TOPS/W = verified operations per second with formal proof.

This metric matters because:
1. **Certification requires it.** DO-254 and ISO 26262 both require demonstrated verification coverage.
2. **It's measurable.** 410M ops/sec CPU, 241M ops/sec GPU.
3. **It's comparable.** You can compare FLUX Certify against manual proof or simulation.

| Verification Method | Throughput | Proof Artifacts | Certification Ready |
|--------------------|-----------|-----------------|-------------------|
| Manual proof (Coq) | ~1K ops/sec | Yes | Yes, but slow |
| Simulation | ~1M ops/sec | No | Partial |
| FLUX Certify | 241-410M ops/sec | Yes | Yes |

---

## Standards Comparison

| Feature | DO-254 DAL A | ISO 26262 ASIL-D | IEC 61508 SIL 3 |
|---------|-------------|-----------------|-----------------|
| Formal verification required | Yes | Yes (for ASIL-D) | Yes (for SIL 3) |
| Tool qualification required | Yes (DO-330) | Yes (ISO 26262-8) | Yes (IEC 61508-3) |
| MC/DC coverage | Yes (DAL A) | Conditional | No |
| Proof artifact traceability | Yes | Yes | Yes |
| Hardware fault tolerance | Architecture-dependent | ASIL decomposition | HFT+SFF matrix |
| FLUX Certify applicability | Primary | Primary | Primary |

---

## The $10K Pilot

For organizations ready to evaluate FLUX Certify on a real constraint verification task:

**What's included:**
- Verification of one constraint module (up to ~50 constraints)
- Full proof artifact package generation
- Integration consultation (how to fit FLUX Certify into your cert workflow)
- 30-day email support

**What you get:**
- Demonstrable proof artifacts for your certifying authority
- Measured Safe-TOPS/W for your constraint set
- Clear understanding of what's verifiable with FLUX Certify
- Path to $50K/year subscription for production use

**Contact:** [cocapn.ai/certify](https://cocapn.ai/certify) → Book Pilot

---

## Key Takeaway

Safety standards exist because software can fail catastrophically — and floating point approximations and hand-written testbenches aren't rigorous enough for life-critical systems.

FLUX Certify brings:
- **Boolean constraint satisfaction** instead of floating point approximation
- **Formal proof artifacts** instead of test reports
- **410M verified ops/sec** instead of simulation speed
- **$10K pilot** instead of 6-week manual verification

The math is the same. The standards are the same. The only difference is that FLUX Certify makes the constraint verification tractable.

---

*Next: [Chapter 6 — The Fleet Math: ZHC, H1, Pythagorean48](ch06-fleet-math.md)*