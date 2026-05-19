# ACCUMULATED CORRECTNESS — Cross-Domain Evidence

## Synthesis of real-world systems that embody the five structural properties

*Research date: 2026-05-19*
*Cross-references: ACCUMULATED-CORRECTNESS.md (primary theory)*

---

## 1. Nuclear Power Plant Safety Systems — The Sediment of Operational Wisdom

### The Domain

Nuclear power plants are arguably the most safety-critical civilian systems ever built. A single failure can cascade into catastrophe (Chernobyl 1986, Fukushima 2011). The industry has responded by building layers of accumulated correctness into every aspect of operations — from reactor protection systems to operator procedures.

### The Sediment Analogy (Confirmed)

Nuclear plants literally embody geological-style sedimentation:

```
Layer 6 (2020s):  Fukushima lessons-learned patches, FLEX strategies, SEED equipment
Layer 5 (2010s):  Digital instrumentation upgrades, cybersecurity hardening
Layer 4 (2000s):  Security posture changes post-9/11 (B.5.b requirements)
Layer 3 (1990s):  Maintenance rule implementation, risk-informed regulation
Layer 2 (1980s):  Post-TMI operator training reforms, human factors engineering
Layer 1 (1970s):  Original plant design basis and safety analysis
```

Each layer was deposited by a different crisis. None is removed. The INPO (Institute of Nuclear Power Operations) and NRC maintain these layers through formal **Corrective Action Programs (CAPs)** that capture every operational event, evaluate its significance, and generate permanent procedural modifications.

### The Tacit Knowledge Crisis

- ~40% of US nuclear workers are projected to retire within the next decade (DOE, IAEA).
- Nearly a third of nuclear professionals globally are aged 55 or above.
- The workforce is older than any other energy sector, with a notable deficit of workers under 30.
- The generation-sized gap means operators who witnessed Three Mile Island aftermath, the INPO reforms, and decades of edge-case handling are leaving.

**This is exactly the COBOL problem in a different medium.** The accumulated knowledge lives in the procedures, the training programs, and the operators' mental models — not in any single document. When the operators retire, the sediment layers lose their interpreters.

### How the Industry Handles It

1. **Knowledge Transfer & Retention (KT&R) Plans** — Formal programs to identify critical tacit knowledge and capture it before retirees leave.
2. **INPO "Smart Planners"** — Tools that provide historical knowledge to work planners regardless of their experience level, effectively codifying tacit knowledge into executable procedures.
3. **Mentoring with overlap** — Requiring sufficient overlap between outgoing experts and incoming staff.
4. **Every event is a learning event** — The INPO principles state "Organizational learning is embraced." Every operational anomaly generates a formal report, root cause analysis, and procedural update.
5. **Fukushima lessons-learned** — INPO 11-005 Addendum (August 2012) systematically captured and distributed lessons from Fukushima. The accident revealed that operators at Fukushima Daiichi had limited experience with certain critical systems — the sediment had thinned.

### Structural Pattern: Feedback = Operation

The nuclear industry's CAP is the feedback loop made institutional. Every execution (every operational day) is potentially a learning event. The system is designed so that edge cases are captured, not just handled. This directly confirms Property 4 from ACCUMULATED-CORRECTNESS.md.

### Anti-Pattern Exposed: Fukushima

At Fukushima, the edge case (total station blackout + tsunami exceeding design basis) had been considered and dismissed decades earlier. The knowledge that it COULD happen existed in geological literature but had not been incorporated into the operational sediment. The failure was not a system failure — it was a sediment gap. A layer that should have been deposited was missing.

---

## 2. Air Traffic Control: ERAM and the HOST System — Replacing the Irreplaceable

### The Domain

The FAA's En Route Host Computer System ran US high-altitude air traffic control from the early 1970s through 2015. Originally written in JOVIAL (a contemporary of COBOL), it managed the National Airspace System (NAS) for approximately 40 years.

### The ERAM Replacement

ERAM (En Route Automation Modernization) was commissioned to replace the HOST system:
- **Original target date:** December 2010
- **Full operational date:** March 2015 (5 years late)
- **Cost overrun:** Exceeded $500 million above budget
- **Primary cause:** "Extensive software-related problems"

The HOST system embodied 40 years of accumulated edge-case handling: air traffic rules, sector boundary logic, conflict detection heuristics, weather rerouting, special-use airspace management. No specification document captured all of it. The code WAS the specification.

### Why It Took 15+ Years and Billions

1. **Underestimated technical complexity** — The FAA consistently underestimated how complex it would be to replicate HOST's accumulated behavior in new code.
2. **Every edge case was a potential disaster** — Air traffic control has no "acceptable failure rate" for loss of separation. The new system had to be correct on day one at a level the old system had taken 40 years to reach.
3. **Workarounds became requirements** — The HOST system had accumulated workarounds for edge cases that were never documented. These surfaced during ERAM testing as failures in scenarios no one remembered encoding.
4. **Controller knowledge was in the system** — Air traffic controllers had adapted their workflows to HOST's quirks. ERAM changed the interface, requiring retraining that didn't account for the tacit knowledge embedded in old workflows.
5. **The LA Center failure (April 2014)** — ERAM system failure at Los Angeles ARTCC caused a ground stop, demonstrating the risks of running a new system that hasn't accumulated the HOST's correctness.

### The Current State (2025-2026)

A 2023 FAA assessment found:
- **51 of 138** air traffic control systems are "unsustainable"
- **54 more** are "potentially unsustainable"
- Some modernization projects are 6-10 years away
- Some have no planned investment at all

The FAA is now planning a new $30+ billion modernization to replace ERAM itself (along with STARS) with a unified "Common Automation Platform (CAP)." They are essentially repeating the replacement cycle — trying to extract accumulated correctness from ERAM into a new system.

**This confirms the COBOL replacement failure pattern.** The HOST → ERAM transition cost billions and took years beyond schedule. Now ERAM → CAP faces the same challenge, with ERAM itself becoming the new "legacy" containing 10+ years of its own accumulated edge cases.

### Structural Pattern: Spec = Code (Confirmed)

The HOST system operated for decades without a complete specification. The JOVIAL code was the specification. ERAM teams had to reverse-engineer requirements from running behavior, which is exactly what happens in every COBOL replacement project.

---

## 3. Space Shuttle Flight Software — The Gold Standard of Accumulated Correctness

### The Domain

NASA's Space Shuttle flight software (developed primarily by Loral (formerly IBM Federal Systems) in Houston) is widely considered the most reliable software ever built. The shuttle flew 135 missions over 30 years (1981-2011) with software that never caused a mission failure.

### The Numbers

- **420,000 lines of code** in the primary flight software
- **17 errors across 11 major versions** (as of 1996 reporting)
- Some versions had a total bug count of approximately **one** for the entire codebase
- A 6,300-line GPS update required a **2,500-page specification document**
- **Zero mission failures** attributable to software across the entire program

### The "Code Is the Spec" Approach (Confirmed — With Nuance)

The shuttle team didn't literally skip specifications. They did the opposite: they wrote specifications so detailed that the code and spec were nearly isomorphic. A 6,300-line code change required 2,500 pages of specification. The spec was so precise that the gap between "what was specified" and "what was coded" was nearly zero.

This is a different route to the same destination:
- **COBOL path:** No separate spec; code IS the spec (by accumulation)
- **Shuttle path:** Spec IS the code (by exhaustive specification)

Both arrive at the same structural property: there is no gap between specification and implementation.

### How They Achieved Zero Production Bugs

1. **The "Power of 10" Rules** — Strict coding standards that limit control flow complexity, loop bounds, memory allocation, and function length. These constraints make bugs structurally difficult to write.
2. **Independent Verification & Validation (IV&V)** — A separate team at NASA's IV&V facility in Fairmont, West Virginia, independently verified every line of shuttle software.
3. **Process over heroism** — The culture valued rigorous process over individual brilliance. No "clever" code. Everything had to be understandable by the IV&V team.
4. **Change review boards** — Every modification went through multiple review stages. The cost of change was high, which meant changes were rare and carefully considered.
5. **Version accumulation** — The shuttle flew with 11 major software versions across 30 years. Each version was a sediment layer. Old code wasn't removed; it was extended.

### Structural Pattern: Frozen Hot Path (Confirmed)

The shuttle's primary flight control loop — the guidance, navigation, and control (GNC) software — was essentially frozen for most of the program. Changes to the GNC core were extraordinarily rare. All modifications happened at the periphery: new navigation modes, updated landing sequences, GPS integration. The hot path was deterministic, verified, and unchanged. The periphery accumulated.

### The Key Insight for PLATO

The shuttle achieved accumulated correctness through **constrained expressiveness**. The Power of 10 rules made certain classes of bugs structurally impossible. This is exactly what FLUX does with constraints: the hot path (`check(values, bounds) → error_mask`) has constrained expressiveness. It can only do one thing, and it does it deterministically. Bugs in the hot path are structurally difficult because the hot path has no degrees of freedom.

---

## 4. Railway Signalling (ERTMS/ETCS) — Correctness by Specification Hierarchy

### The Domain

ERTMS (European Rail Traffic Management System) is the standard for railway signalling across Europe. Its core component, ETCS (European Train Control System), is an automatic train protection (ATP) system that continuously monitors train speed and automatically applies brakes if the permitted speed is exceeded.

### The Accumulated Correctness Challenge

ETCS faces a unique version of the sediment problem:
- **Multi-vendor implementations** — Different suppliers (Siemens, Alstom, Bombardier, Hitachi) implement the same specification
- **National values** — Each country has country-specific parameters that modify behavior
- **Ambiguous requirements** — Early ETCS specifications had ambiguities that led to conflicting implementations by different vendors. Specifically: operational mode transitions and braking curve computations (safety-critical functions) were interpreted differently.
- **Version coexistence** — During migration, old and new versions must coexist on the same track. A train with ETCS v2.x must safely interact with trackside equipment running v1.x.

### How They Maintain Correctness Across Versions

1. **ERA Change Control Board** — The European Union Agency for Railways manages a formal Change Control Board (CCB) that evaluates every modification request. Changes are globally assessed before implementation.
2. **Subset 026 (SRS)** — The System Requirements Specification explicitly manages ERTMS/ETCS system versions. The SRS version number is incremented with each system version change.
3. **Formal methods** — Formal specification languages and model checking are used to validate ETCS concepts and verify safety properties. This catches ambiguities before they become conflicting implementations.
4. **Test sequence validation** — Rigorous rules for evaluating test results and defining validation ranges for on-board equipment.
5. **Configuration data verification** — Specialized services verify consistency between design documentation, trackside configuration data, and operational requirements BEFORE integration testing.

### Structural Pattern: Local Extension, Global Stability (Confirmed)

ETCS version management is designed so that:
- Trackside equipment is versioned independently of on-board equipment
- The system version defines the mandatory functions for interoperability
- New versions can add functionality without breaking old implementations
- The braking curve computation (the hot path) is frozen across versions — only parameters change

### The Anti-Pattern: Ambiguous Specifications

The early ETCS rollout failures demonstrate what happens when the specification is NOT the code. Different vendors interpreted ambiguous requirements differently, leading to interoperability failures. The fix was to make the specification more precise (moving toward the shuttle model) and to add formal verification (making the spec mathematically checkable).

**For PLATO:** This confirms that tile specifications must be unambiguous. If two agents can interpret a tile differently, the tile is underspecified.

---

## 5. Medical Device Firmware — Living With Legacy

### The Domain

Pacemakers, infusion pumps, ventilators, and implantable defibrillators run firmware that must operate correctly for 10-30+ years. A software bug can kill a patient. The FDA regulates these devices under IEC 62304 (medical device software lifecycle) and 21 CFR Part 820 (quality system regulation).

### The "Can't Rewrite From Scratch" Problem (Confirmed)

Medical device firmware faces the same accumulated correctness problem as COBOL:

- **Code older than its developers** — Firmware for devices like the CADD infusion pump family (Smiths Medical/CADD-Solis) traces lineage back to the 1990s. Current developers inherited code written by people who have retired.
- **Regulatory barriers to rewriting** — FDA requires that any change to a Class III medical device go through a full design control process. Rewriting from scratch means re-proving safety from scratch. The regulatory cost of a rewrite often exceeds the cost of maintaining the legacy system.
- **IEC 62304 legacy provisions** — The standard explicitly addresses "legacy software" (software developed before the standard existed), recognizing that it cannot be brought into full compliance without risking the accumulated correctness.
- **Therac-25 (1985-1987)** — The canonical medical device software failure. A radiation therapy machine's software had a race condition that delivered lethal radiation doses, killing 6 patients. The root cause: the software replaced hardware interlocks, but the accumulated correctness of the hardware safety system was not replicated in the software. The new system started at correctness=0.

### How the Industry Handles Decades-Old Firmware

1. **Incremental refactoring, never rewriting** — Internal structure is improved without changing external behavior. The regulatory path for "no change to device function" is far simpler than "new device function."
2. **Unit testing legacy code** — Adding tests to unmodified legacy code to verify functionality and generate evidence for regulatory audits. This is sediment archaeology — writing tests that capture what the code actually does, not what it was specified to do.
3. **Modular decomposition** — Breaking monolithic firmware into modules that can be independently maintained, tested, and updated. This is the "local extension" principle applied retroactively.
4. **Post-market surveillance (PMS)** — Every device in the field generates data. Anomalies trigger investigations. Every investigation can generate a firmware patch. The patch handles the edge case. The edge case never happens again.
5. **Software Bill of Materials (SBOMs)** — New regulatory requirement to track every software component, creating a literal sediment map of the firmware's composition.

### Structural Pattern: Frozen Hot Path (Confirmed)

Medical device firmware typically has a safety-critical core (e.g., the drug delivery rate calculation in an infusion pump, or the pacing algorithm in a pacemaker) that is frozen for the device's lifetime. All changes happen at the periphery: communication protocols, user interfaces, telemetry. The core delivery/pacing algorithm doesn't change because it was proven correct at design time and any change requires full re-validation.

### The Therac-25 Lesson

Therac-25 is the ultimate anti-pattern for accumulated correctness:
1. **Replacing a safety system with software that had zero accumulated correctness**
2. **Removing hardware interlocks** (the frozen hot path) and replacing them with software checks
3. **The software started at correctness=0** — it had not accumulated any edge-case handling
4. **The result was lethal**

For PLATO: Never replace a tile's constraint check with a "smarter" version unless the new version has accumulated at least as much correctness as the old one. The constraint check IS the hardware interlock.

---

## Cross-Domain Structural Patterns

### Patterns That Repeat Everywhere

| Pattern | Nuclear | ATC (ERAM) | Shuttle | Railway (ETCS) | Medical Devices | COBOL/MUMPS | PLATO |
|---------|---------|------------|---------|-----------------|-----------------|-------------|-------|
| **Spec = Code** | Procedures ARE the knowledge | HOST code was the spec | Spec was so detailed it WAS the code | SRS versions ARE the system | Firmware IS the validated behavior | Running code IS the spec | Tile IS the procedure |
| **Local Extension** | Regulatory patches don't touch core | ERAM added capabilities, didn't modify HOST behavior | Periphery changes only | National values don't modify core ATP | Modular updates | New IF branch | New tile, no modification |
| **Frozen Hot Path** | Reactor protection system | Conflict detection | GNC core | Braking curve computation | Drug delivery rate calc | Settlement logic | Constraint check |
| **Feedback = Operation** | CAP captures every anomaly | Controllers report system issues | Every mission generates data | PMS + incident reports | Post-market surveillance | Every transaction is a test | Every execution produces a gap |
| **Sediment Accumulation** | Crisis layers since 1970s | 40 years of HOST edge cases | 11 versions over 30 years | SRS version increments | Firmware version lineage | 60 years of layers | N cycles of refinement |

### Anti-Patterns That Lead to Failures

| Anti-Pattern | Nuclear | ATC | Shuttle | Railway | Medical | Lesson for PLATO |
|-------------|---------|-----|---------|---------|---------|-----------------|
| **Rewrite from scratch** | Never attempted (wisely) | ERAM: $500M overrun, 5 years late | N/A (they didn't rewrite) | Version coexistence required | Regulatory barrier prevents it | Never replace accumulated tiles with "clean" versions |
| **Premature abstraction** | Fukushima: tsunami dismissed | HOST workarounds became undocumented requirements | Avoided by Power of 10 rules | Ambiguous specs → vendor conflicts | Therac-25: race condition hidden by UI | Don't hide edge cases behind clean interfaces |
| **Schema rigidity** | Flexible (procedures evolve) | Fixed ATC data formats | Extremely rigid (correctly) | National values as escape valve | IEC 62304 accommodates legacy | Tiles must be open, constraints must be fixed |
| **Separating spec from code** | Procedures live with operations | HOST had no separate spec | Spec and code were isomorphic | SRS diverged from implementations | Firmware diverges from original specs | Tile = procedure, never separate them |
| **Removing old layers** | INPO preserves all CAP entries | HOST decommissioned only after ERAM matched its behavior | Old versions preserved in archives | Backward compatibility required | Legacy code preserved under IEC 62304 | Never delete tiles; supersede them |
| **Global refactoring** | Plant modifications are isolated | ERAM changed everything at once (risky) | Changes reviewed by board | CCB evaluates changes globally | Incremental refactoring only | Room-level changes only, never fleet-wide refactors |

---

## Testable Hypotheses for PLATO

Based on cross-domain evidence, these hypotheses should be testable within the PLATO system:

### H1: Tile Correctness Accumulates Monotonically
**If** a tile is never deleted but only superseded, **then** the tile's correctness (measured by successful executions / total executions) should increase monotonically over cycles.
- **Nuclear evidence:** CAP entries only add constraints, never remove them. Correctness accumulates.
- **Medical evidence:** Firmware patches only add safety checks. Correctness accumulates.
- **Test:** Track per-tile success rate over 100+ cycles. Verify monotonic increase.

### H2: The Frozen Hot Path Enables Periphery Innovation
**If** the constraint check (FLUX hot path) is frozen and deterministic, **then** periphery components (presets, classifiers, compilers) can be modified freely without risking core correctness.
- **Shuttle evidence:** GNC core frozen → 11 major peripheral versions without core failure.
- **Medical evidence:** Delivery algorithm frozen → UI/communication updates without safety regression.
- **Test:** Modify periphery tiles aggressively while measuring hot path correctness. Hot path error rate should be zero regardless of periphery changes.

### H3: Specification Ambiguity Causes Tile Divergence
**If** a tile's specification is ambiguous enough for two agents to interpret differently, **then** the tile's behavior will diverge across agents, causing correctness loss.
- **Railway evidence:** ETCS spec ambiguities → vendor implementation conflicts.
- **Test:** Give the same tile to two different models. Compare execution traces. Divergence indicates underspecification.

### H4: Knowledge Loss Follows Operator Retirement Curves
**If** experienced agents are replaced by new agents without tile-based knowledge transfer, **then** the system's correctness will drop proportionally to the departing agents' accumulated edge-case handling.
- **Nuclear evidence:** 40% workforce retirement → knowledge gap → safety risk.
- **COBOL evidence:** Retiring programmers → irreplaceable knowledge in code.
- **Test:** Replace a model that has been refining tiles with a fresh model. Measure correctness drop in subsequent cycles.

### H5: Every Execution Should Be Capable of Producing a Refinement
**If** the system captures gaps from every execution, **then** the refinement rate (new tiles per cycle) should correlate with the novelty of inputs, and the fleet should handle previously-novel inputs correctly on subsequent encounters.
- **Nuclear evidence:** CAP generates a procedure update for every anomaly.
- **Medical evidence:** PMS generates firmware patches for every field anomaly.
- **Test:** Feed novel inputs to the fleet. Measure: (a) gap detection rate, (b) refinement creation rate, (c) correctness on re-encounter.

### H6: Rewriting a Tile From Scratch Is Riskier Than Extending It
**If** a tile with 50+ cycles of refinement is replaced by a "clean" implementation, **then** the new tile will fail on edge cases the old tile handled, and the failure rate will be proportional to the number of cycles the old tile had accumulated.
- **COBOL evidence:** 70-80% replacement failure rate.
- **ATC evidence:** ERAM $500M overrun, 5-year delay.
- **Therac-25 evidence:** Lethal failures from replacing proven interlocks with new software.
- **Test:** Take a tile with 50+ cycles. Create a "clean" version from spec only. Run both against the same test corpus. The clean version should fail on cases the old version handles.

---

## What This Means for PLATO Tile Design

### 1. Tiles Must Be Append-Only
The nuclear CAP, COBOL sediment, and shuttle version history all demonstrate that correctness accumulates by addition, never by deletion. PLATO tiles should be superseded, never deleted. The old tile remains in the sediment.

### 2. Tile Specifications Must Be Unambiguous
The ETCS vendor divergence shows what happens when specifications are ambiguous. PLATO tiles need the shuttle's level of specification precision, especially for the hot path (constraint checks). If two agents can interpret a tile differently, the tile is broken.

### 3. The Constraint Check Is the Frozen Core
Every domain confirms: the safety-critical core is frozen. For PLATO, the FLUX constraint check (`check(values, bounds) → error_mask`) is the reactor protection system, the conflict detection algorithm, the braking curve computation, the drug delivery rate calculation. It must never be "improved" — only extended.

### 4. Every Execution Produces a Gap (or Confirms Correctness)
The nuclear CAP, medical PMS, and shuttle mission data all show that the feedback loop IS the system. PLATO's collective inference loop (predict → observe → gap → learn → share) must fire on every execution, not just on failures. Confirmations are as important as gaps — they verify that accumulated layers are still correct.

### 5. Agent Retirement = Knowledge Loss = Tile Dependency
When nuclear operators retire, the industry loses tacit knowledge. When AI models are replaced (compaction, new model releases), the fleet loses tacit knowledge unless it's encoded in tiles. The tile IS the knowledge. The model is the operator. Operators come and go; the procedures remain.

### 6. Regulatory Analog: Tile Certification
Medical devices require IEC 62304 compliance. Nuclear plants require NRC oversight. Railway systems require ERA certification. PLATO needs an analogous "tile certification" process — a formal verification that a tile meets its specification before it enters the fleet's active sediment.

---

## Citations and Sources

### Nuclear Power
- OECD Nuclear Energy Agency, "Knowledge Management in the Context of an Ageing Workforce" (nea.fr)
- IAEA, "Knowledge Loss Risk Management in Nuclear Organizations" (iaea.org, pubs 10921)
- INPO, "Lessons Learned from the Nuclear Accident at Fukushima Daiichi" (INPO 11-005 Addendum, August 2012)
- US DOE, "5 Workforce Trends in Nuclear Energy" (energy.gov)
- ResearchGate, "The Role of Tacit Knowledge and the Challenges in Transferring It in the Nuclear Power Plant Context" (2013)

### Air Traffic Control (ERAM)
- FAA, En Route Automation Modernization program documentation (faa.gov)
- US DOT OIG, "FAA ERAM Final Report" (oig.dot.gov, 07-29-2020)
- GAO, "Air Traffic Control: FAA Needs to Improve Its Approach to Modernizing Systems" (gao.gov, GAO-25-108162, 2025)
- US DOT, "Brand New Air Traffic Control System Plan" (transportation.gov, May 2025)
- Wikipedia, "En Route Automation Modernization" (en.wikipedia.org)

### Space Shuttle Flight Software
- National Academies, "The Role of Flight Software in Spacecraft" (nationalacademies.org)
- NASA, "Software Assurance and Safety Standard" (NASA-STD-8719.13)
- BugSplat, "Why NASA Code Doesn't Crash" (bugsplat.com)
- Perforce, "NASA Rules for Developing Safety-Critical Code" (perforce.com)
- NASA SMA, "STS-126 Software Anomaly" (sma.nasa.gov, 2009)

### Railway Signalling (ERTMS/ETCS)
- European Union Agency for Railways, "ERTMS/ETCS System Requirements Specification" (Subset 026)
- ERA, "ERTMS/ETCS System Version Management" (era.europa.eu)
- Railway Signalling, "ERTMS Safety" (railwaysignalling.eu)
- HASLab, "Formal Modelling and Verification of ETCS" (ABZ 2018 conference)

### Medical Device Firmware
- IMDRF, "Principles and Practices of Cybersecurity for Legacy Medical Devices" (N70, 2023)
- MITRE, "Managing Legacy Medical Device Cybersecurity Risks" (PR-23-3695, 2023)
- FDA, 21 CFR Part 820 (Quality System Regulation)
- IEC 62304 (Medical Device Software Lifecycle)
- Therac-25 case study (widely documented; see Leveson & Turner, "An Investigation of the Therac-25 Accidents," IEEE Computer, 1993)

---

*The evidence is clear: accumulated correctness is not a theory. It is the dominant pattern in every domain where systems must be right. The systems that survive are the ones that accumulate. The systems that fail are the ones that try to start over.*

*The sediment is the system.*
