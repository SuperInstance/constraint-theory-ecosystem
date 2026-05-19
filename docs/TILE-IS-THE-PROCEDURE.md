# THE TILE IS THE PROCEDURE

## How Mayo Clinic, Military Field Manuals, and PLATO Tiles Share the Same Deep Structure

### The Medical Pattern

At Mayo Clinic or Johns Hopkins, an elite specialist — say, a neurosurgeon who has done 2,000+ clipping procedures for cerebral aneurysms — develops a refined technique. She discovers that a specific angle of approach reduces complications by 15%. She publishes. The procedure gets codified into a step-by-step protocol with decision trees, contraindications, and contingency branches.

A general surgeon in rural Alaska reads that protocol. She is not an elite neurosurgeon. But she is competent, trained, and capable of following a well-specified procedure. When the patient arrives, she executes the protocol.

**The intelligence transfer happened through the procedure, not the person.**

The elite specialist's 2,000 cases of tacit knowledge — the "feel" for when the aneurysm is about to rupture, the angle that works 15% better — got codified into explicit, repeatable steps. The general surgeon doesn't need 2,000 cases of experience. She needs the distilled procedure and the competence to execute it.

### The Military Pattern

Same structure. Special Forces operators develop close-quarters battle (CQB) tactics through real operations. They discover that a specific stack formation when entering a room reduces friendly casualties. The technique gets written into a Field Manual (FM). Regular infantry units train on it. The knowledge scales.

The original operators might have developed the technique through intuition honed by combat. The Field Manual doesn't capture the intuition — it captures the *result* of the intuition. The "why" is implicit in the steps. A squad leader doesn't need combat experience to execute the formation. He needs the manual and the discipline to follow it.

### The Hospital Science Pattern

Large research hospitals don't just treat patients — they *do science as they go*. Every treatment is also data. Every outcome refines the protocol. This is the feedback loop:

```
Treat patient → observe outcome → refine protocol → codify update → publish
     ↑                                                        |
     └────────────── next patient gets better care ───────────┘
```

The protocol is a living document. It gets better with every cycle. The current version of a surgical procedure at Mayo Clinic embodies 50+ years of accumulated outcomes. A surgeon executing it today benefits from every patient who came before — not because they're a genius, but because the *procedure is the accumulated intelligence*.

### The PLATO Tile Pattern

PLATO tiles are the same thing:

```
Large model (Claude Opus, GLM-5.1 — the "specialist")
  → discovers an insight, designs an architecture, writes an algorithm
  → codifies it into a TILE (the "procedure")
  → tile includes: the code, the reasoning, the constraints, the tests
  → small model (Seed-2.0-mini — the "general surgeon")
  → reads the tile, executes the procedure, verifies the result
```

The tile IS the intelligence transfer. The small model doesn't need to be a genius. It needs:
1. The competence to read and understand the tile
2. The ability to execute the specified steps
3. The discipline to follow the protocol (not improvise)

### What This Means for Tile Construction

Tiles are NOT just data. They are **executable procedures** with:

1. **Pre-conditions** — what must be true before execution (like surgical contraindications)
2. **Steps** — the ordered procedure (like a surgical protocol)
3. **Decision trees** — branching logic based on observations (like intraoperative decisions)
4. **Post-conditions** — what must be true after execution (like surgical outcome criteria)
5. **Contingencies** — what to do when things go wrong (like surgical complication management)
6. **Provenance** — who developed this procedure, when, based on what evidence

### The Capability Ladder

```
Tier 3: Elite Specialist (Claude Opus, GPT-4)
  → Creates NEW procedures from scratch
  → Novel synthesis, cross-domain insight
  → Expensive, rare, reserved for genuinely new territory

Tier 2: Senior Practitioner (GLM-5.1, DeepSeek Reasoner)
  → Refines existing procedures
  → Adapts protocols to new contexts
  → Writes tiles that smaller models can execute
  → The workhorse — "the attending physician"

Tier 1: General Practitioner (Seed-2.0-mini, Hermes-70B, Qwen)
  → Reads and executes procedures from tiles
  → Competent, fast, cheap
  → Follows the protocol — doesn't improvise
  → Reports results back for refinement
```

The key insight: **Tier 1 models can do Tier 2 work IF the tile is good enough.** The tile is the capability amplifier. A general surgeon executing a perfect Mayo Clinic protocol produces better outcomes than a mediocre specialist winging it.

### The Accumulation Effect

Like medical knowledge, tile quality compounds over time:

```
Cycle 1: Specialist creates tile v1 (good but rough)
Cycle 2: Practitioner executes, reports edge cases
Cycle 3: Specialist refines → tile v2 (better)
Cycle 4: Another practitioner executes, finds more edge cases
Cycle 5: Specialist refines → tile v3 (refined)
...
Cycle N: Tile vN embodies N iterations of accumulated intelligence
```

After 100 cycles, a Seed-2.0-mini executing tile v100 produces better results than GLM-5.1 working from scratch. **The procedure has absorbed the intelligence.** This is why medical protocols get better — not because surgeons get smarter, but because the procedures accumulate.

### The Military Analog: Standing Operating Procedures (SOPs)

The military calls these SOPs. Every unit has them:
- How to clear a room
- How to call in artillery
- How to set up a checkpoint
- How to treat a gunshot wound under fire

An SOP is a tile. It was written by someone with deep experience. It's executed by someone who may have none. The quality of the SOP determines the quality of the outcome, not the experience level of the executor.

**In PLATO, every room should accumulate SOPs — tiles that encode the best-known procedures for that room's domain.**

### Practical Implications

1. **Tile construction is the highest-value activity.** Like writing a surgical protocol, writing a tile captures intelligence permanently. Every hour spent refining a tile pays dividends forever.

2. **Tiles should include the "why", not just the "what".** A surgical protocol explains why you cut at this angle. A tile should explain why this algorithm was chosen. The "why" enables the executor to handle edge cases the author didn't anticipate.

3. **Small models + good tiles > large models + no tiles.** This is the core economic insight. We can't afford Claude Opus for every fleet decision. But we CAN afford to have Claude Opus write tiles that Seed-2.0-mini executes.

4. **Tiles should get versioned and refined.** Like medical protocols, tiles should have version history, change logs, and outcome tracking. The lineage tracker in plato-types (v1 → v2 → v3) is exactly this.

5. **The feedback loop is essential.** Medical procedures improve because outcomes are tracked. PLATO tiles should track execution outcomes — did the procedure work? What were the edge cases? This feeds back into tile refinement.

### The Delegation Pyramid Revisited

```
Casey (CEO) — "we need X"
  │
  Forgemaster (senior partner) — designs the procedure, writes the tile
    │
    ├── GLM-5.1 agents — refine procedures, adapt to new contexts
    │     They are the "residents" — learning by executing and refining
    │
    ├── Seed-2.0-mini ($0.01) — execute procedures from tiles
    │     They are the "nurses" — competent, follow protocol, report results
    │
    └── Tiles — the accumulated intelligence that makes the system work
          They are the "medical protocols" — getting better every cycle
```

The system's intelligence is NOT in any single model. It's in the tiles. The models are surgeons of varying skill. The tiles are the protocols. A system with mediocre models and excellent tiles will outperform a system with excellent models and no tiles.

This is why PLATO rooms matter. They are the institutional memory — the medical library, the field manual collection, the accumulated wisdom of the fleet. Every tile written is a procedure that any model can execute. Every tile refined is intelligence that compounds.

---

*"The good physician treats the disease. The great physician treats the patient who has the disease." — William Osler, founder of Johns Hopkins*

*The good model answers the question. The great model writes the tile that lets any model answer it.*
