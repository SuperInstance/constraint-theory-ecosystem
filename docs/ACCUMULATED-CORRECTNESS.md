# ACCUMULATED CORRECTNESS: What COBOL, MUMPS, and PLATO Teach Us About Systems That Must Be Right

## The Irreplaceability Problem

COBOL processes 95% of ATM transactions, $3 trillion per day. MUMPS (M) runs every VA hospital through VistA and backs Epic Systems. Neither language is elegant. Both are considered legacy, ugly, outdated.

**Replacement projects fail at 70-80%.** Not because the new teams are incompetent. Because you cannot extract 60 years of accumulated edge-case handling from running code into a clean specification.

The new system starts at correctness=0. The old system is at correctness=0.999999.

This is not a technology problem. It is a **structural epistemology** problem. The knowledge doesn't live in any person's head. It lives in the code. The code IS the specification — not by design, but by accumulation.

---

## The Five Structural Properties of Need-To-Be-Right Systems

### 1. The Specification IS the Running Code

After 60 years, no one at JPMorgan knows all the rules in their COBOL settlement system. The people who wrote the original code retired. The people who wrote the patches retired. The people who wrote patches on top of patches retired. What remains is a **sediment of correctness** — each layer deposited by a different generation, each responding to a crisis that no one remembers.

The COBOL code doesn't implement a specification. It IS the specification. There is no separate document that contains "what the system should do." The system does what it does, and what it does has been right for 60 years, and the proof that it's right is that the financial system hasn't collapsed.

This is not failure of documentation. This is the natural endpoint of any system that handles enough edge cases. The documentation becomes stale. The code stays current because it's what's running.

**PLATO analog:** A tile that has been refined through 100 cycles of execution and feedback embodies more correctness than any specification could capture. The tile IS the procedure. The procedure IS the knowledge. You don't need to understand WHY the tile checks for condition X — you just need to execute it.

### 2. Local Extension, Global Stability

COBOL's PICTURE clause and paragraph structure make it possible to add a new rule without touching existing rules. A new IF branch for a new regulatory requirement doesn't break the existing IF branches. The system is **supple against extension and brittle against breakage**.

MUMPS takes this further. Its sparse global arrays have no fixed schema. When Medicare adds a new billing code, you don't ALTER TABLE. You set a new node. The old nodes continue working. The new node handles the new case. **The data model doesn't fight back.**

This is the opposite of most modern architectures, where adding a new feature requires touching dozens of microservices, each with their own schema, each with their own deployment cycle, each capable of breaking the others.

**Design principle:** The cost of adding correct behavior must be low and LOCAL. The cost of breaking existing correct behavior must be high. This means: no hidden global state, no cascading dependencies, no "refactoring" that touches working code.

**PLATO analog:** A new tile in a PLATO room doesn't modify existing tiles. It adds new coverage. Old tiles continue operating. New tiles handle new cases. The room accumulates correctness monotonically.

### 3. The Hot Path Is Frozen

In both COBOL and MUMPS systems, the core transaction path hasn't changed in decades. The settlement logic, the patient record retrieval, the insurance claim processing — these are **frozen oracles**. They were right 40 years ago and they're still right.

All the change happens at the periphery: new regulations, new billing codes, new drug interactions. The hot path doesn't "learn." It **checks**. When something fails a check, the periphery handles it — a new rule, a new exception, a new branch.

**Design principle:** Separate the must-be-right core from the can-be-refined periphery. The core is a constraint engine — deterministic, verified, unchanged. The periphery is where accumulation happens. The core never approximates. It only enforces.

**Constraint theory analog:** This is exactly what FLUX does. The hot path is `check(values, bounds) → error_mask`. It's deterministic. It's frozen. It's right. Everything else — the presets, the severity classifiers, the deployment compilers — is periphery. The hot path never guesses. It only checks.

### 4. The Feedback Loop Is the System

VA hospitals don't just use VistA. They **improve** VistA through use. Every unusual patient case, every drug interaction that shouldn't have happened, every billing anomaly — it gets reported, and someone writes a patch. The patch handles the edge case. The edge case never happens again.

This is the hospital "science as you go" pattern: treat patient → observe outcome → refine protocol → codify into the system → next patient benefits.

The system doesn't have a separate "learning" phase. Learning IS the operation. Every execution is potentially a training event. The system is designed so that edge cases are captured, not just handled.

**Design principle:** Every execution must be capable of producing a refinement. The system must have a mechanism for: (1) detecting when something unexpected happened, (2) recording what happened, (3) creating or modifying a procedure to handle it, (4) deploying that procedure without breaking anything else.

**PLATO analog:** The collective inference loop: predict → observe → gap → learn → share. Every prediction that's wrong produces a gap. Every gap produces a learning. Every learning gets shared as a tile. The fleet gets smarter with every cycle.

### 5. The Data Model Is Open at the Edges

MUMPS doesn't have a schema. This is not a deficiency — it's the feature that enables 50 years of medical correctness accumulation. When a new type of medical record appears (genetic data, imaging metadata, telehealth vitals), you don't need a schema migration. You just store it.

COBOL's fixed-precision PICTURE clause is the complement: for financial data, the shape IS known and MUST be enforced. 9(7)V99 means exactly 7 digits before the decimal and 2 after. No floating point. No approximation. The data shape is the constraint.

**Design principle:** The data model must match the domain's certainty. For domains where the shape is known and must be exact (finance, constraints), enforce it at the structural level. For domains where the shape evolves (medicine, research), leave it open. Don't force one pattern on both.

**Constraint theory analog:** Bounds are known: lo ≤ value ≤ hi. The data shape is fixed: 8 values, 8 bounds, 8 error bits. This is PICTURE-clause territory — the shape is the correctness. But the PLATO tiles that wrap the constraint engine are schema-less — they accumulate new rules, new edge cases, new procedures over time. The engine is COBOL. The tiles are MUMPS.

---

## The Sediment Model of Correctness

A COBOL system is a geological formation:

```
Layer 5 (2020s): FinCEN anti-money-laundering rules
Layer 4 (2000s): Sarbanes-Oxley compliance patches
Layer 3 (1990s): Y2K fixes (the ones that worked)
Layer 2 (1980s): ATM network integration
Layer 1 (1970s): Core settlement logic
Layer 0 (1960s): Original implementation
```

Each layer was deposited by a different generation responding to a different crisis. The layers don't mix. The oldest layers are the densest and most stable. The newest layers are the most volatile but also the most valuable — they represent the most recently accumulated wisdom.

**The system is a stratified archive of correct behaviors.** It doesn't "learn" in the biological sense. It records and preserves every correct response to a real-world stimulus.

This is why replacement fails: you can't extract the sediment. You can't write a specification that captures "and then in 1987 there was a settlement crisis caused by a time zone boundary that required this specific IF statement." That IF statement IS the knowledge. Remove it and the system will fail in exactly that edge case, which will happen again, eventually.

---

## The Capability Ladder: Surgeons, Soldiers, and Small Models

### The Hospital Model

```
Johns Hopkins elite specialist (Claude Opus)
  → 2,000+ cases of tacit knowledge
  → discovers new technique, publishes protocol
  → the protocol IS the intelligence transfer

Mayo Clinic attending (GLM-5.1)
  → refines the protocol based on local outcomes
  → writes the version that gets deployed hospital-wide

Rural general surgeon (Seed-2.0-mini)
  → reads the protocol
  → executes it competently
  → reports outcomes back for refinement
  → doesn't need 2,000 cases — needs the protocol

The protocol (PLATO tile)
  → embodies 2,000+ cases of accumulated edge-case handling
  → versioned, refined, tested
  → gets better every cycle
  → outlives every surgeon who contributed to it
```

### The Military Model

```
Special Forces operator (Claude Opus)
  → develops CQB room-clearing technique in combat
  → technique gets codified into Field Manual

Ranger battalion (GLM-5.1)
  → trains on the technique, adapts to local conditions
  → writes the SOP that gets deployed brigade-wide

Regular infantry squad (Seed-2.0-mini)
  → reads the SOP
  → executes it with discipline
  → reports what worked and what didn't

The SOP (PLATO tile)
  → embodies combat experience the squad doesn't have
  → makes the squad more effective than their training alone
  → accumulates improvements from every execution
```

### The COBOL Model

```
1960s banking team (the original specialists)
  → wrote the core settlement logic
  → handled every edge case they knew about

1970s ATM integration team
  → added new layers for ATM network settlement
  → didn't touch the core — extended the periphery

1980s-2020s compliance teams
  → added regulatory patches, crisis responses, fraud detection
  → each layer sits on top of the last
  → none removes or replaces existing layers

The running code (the sediment)
  → embodies 60 years of accumulated financial correctness
  → every crisis deposited a layer
  → removing any layer risks the edge case it handles
  → the code IS the specification because the layers ARE the knowledge
```

### The PLATO Model

```
Large model (Claude/GPT-4 level — the specialist)
  → discovers novel insight, designs architecture, writes algorithm
  → codifies into a TILE

Medium model (GLM-5.1 level — the attending)
  → refines the tile based on execution results
  → adapts to new contexts, handles edge cases
  → creates improved versions

Small model (Seed-2.0-mini level — the general surgeon)
  → reads the tile, executes the procedure
  → reports results, identifies failures
  → doesn't need to understand the WHY — follows the protocol

The tile (the accumulated procedure)
  → embodies intelligence from every model that contributed
  → versioned, tested, provenance-tracked
  → gets better every cycle
  → survives compaction, restart, handoff
```

---

## Why This Matters for PLATO

The COBOL/MUMPS lesson is: **the system that accumulates correctness eventually becomes irreplaceable.** Not because it's elegant, but because it contains knowledge that cannot be extracted and reconstructed.

PLATO tiles are designed to accumulate. Each cycle adds a layer. Each refinement captures an edge case. Each version is a sediment deposit. Over 100 cycles, a tile embodies more correctness than any single model could produce from scratch.

The design principles extracted from 60 years of COBOL and 50 years of MUMPS:

| Principle | COBOL | MUMPS | PLATO |
|-----------|-------|-------|-------|
| **Spec = Code** | Settlement logic IS the spec | VistA IS the medical protocol | Tile IS the procedure |
| **Local extension** | New IF branch, no breakage | New node, no schema change | New tile, no modification |
| **Frozen hot path** | Core unchanged for decades | Transaction engine unchanged | Constraint check is deterministic |
| **Feedback = operation** | Every transaction is a test | Every patient case is data | Every execution produces a gap |
| **Open data model** | PICTURE for known shapes | Schema-less for unknown | Tiles are open, constraints are fixed |
| **Accumulated sediment** | 60 years of crisis layers | 50 years of medical layers | N cycles of refinement layers |

---

## The Anti-Patterns: What Kills Accumulation

1. **Rewriting from scratch** — The cardinal sin. Every rewrite starts at correctness=0. The COBOL replacement disasters prove this.

2. **Premature abstraction** — Hiding edge cases behind "clean" interfaces makes them invisible to future maintainers. COBOL's verbosity is a feature — every rule is visible.

3. **Schema rigidity** — If the data model can't represent new kinds of information, edge cases get lost. MUMPS' schema-less design prevents this.

4. **Separating spec from code** — Documentation drifts. The code doesn't. If the spec and code diverge, you've lost the knowledge.

5. **Global refactoring** — Touching working code to "improve" it risks breaking accumulated correctness. Every line that hasn't been touched in 10 years is a line that's been RIGHT for 10 years. Don't fix what isn't broken.

6. **Removing the old layers** — The 1987 time zone IF statement looks unnecessary. It isn't. The edge case will recur. The old layers ARE the correctness.

**In PLATO terms:** Never delete tiles. Supersede them. The old tile remains in the record. The new tile handles the edge case the old one missed. Both are visible. Both contribute to the sediment. The fleet's knowledge is archaeological — every stratum tells a story.

---

## The Deeper Question: What Is a Procedure, Really?

A surgical procedure is not just a list of steps. It is:
- **Pre-conditions** — patient must be stable, imaging must be current
- **Steps** — cut here, clamp there, suture like this
- **Decision trees** — if bleeding, do X; if pressure drops, do Y
- **Contingencies** — if the aneurysm ruptures, emergency protocol Z
- **Post-conditions** — patient must be stable, vitals must be in range
- **Provenance** — developed by Dr. X, refined by Dr. Y, based on N cases

A military SOP is the same structure. A COBOL program is the same structure. A PLATO tile is the same structure.

The universal shape of a need-to-be-right procedure:

```
Procedure {
    pre_conditions:  [what must be true]
    steps:           [ordered actions with branching]
    post_conditions: [what must be true after]
    contingencies:   [what to do when things go wrong]
    provenance:      [who, when, why, based on what]
    version:         [v1 → v2 → v3, accumulating]
}
```

This is not a coincidence. It is the natural shape of accumulated operational knowledge in any domain where being wrong is unacceptable. Surgery, combat, finance, medicine, constraint checking.

**The procedure is the unit of accumulated correctness.** Systems that get better over time do so by accumulating procedures, not by getting smarter.

---

## Conclusion: The Goal Is Not Intelligence, It's Accumulation

A COBOL system is not intelligent. Neither is a surgical protocol. Neither is a Field Manual. They are **deposits of accumulated correctness** from thousands of executions, refined through cycles of failure and repair.

The goal for PLATO is not to build intelligent agents. It's to build a system where correctness accumulates. Where every execution can produce a refinement. Where every refinement is a new layer of sediment. Where the system gets better at being right, not because the models get smarter, but because the procedures get more comprehensive.

The models are surgeons. The tiles are the protocols. The fleet is the hospital.

The hospital doesn't get smarter. The protocols do. That's the architecture.

---

*"The good physician treats the disease. The great physician treats the patient who has the disease." — Osler*

*The good model answers the question. The great model writes the tile that lets any model answer it.*

*The irreplaceable model doesn't exist. The irreplaceable procedure does.*
