# THE APPLICATION-FIRST PRINCIPLE

## How ASVAB, Casting-Call, and FLUX Share the Same Deep Structure

### The Insight

The US military doesn't test recruits to find out what they're good at and then train them for it.

They have **jobs that need filling**. Specific roles with specific requirements. Nuclear submarine technicians. Crypto linguists. Aviation mechanics. Combat medics. They know exactly what they need. The ASVAB is the *instrument* they use to find who can fill those roles.

**Application defines the need. The test is the placement mechanism, not the purpose.**

This is the exact same deep structure as:

1. **Cocapn casting-call** — which AI model plays which role in the fleet
2. **FLUX constraint engine** — which implementation language serves which deployment target
3. **Any system that matches capability to purpose**

---

## The Military Pattern (ASVAB)

### History

Predecessors: Army Alpha/Beta tests (WWI), Armed Forces Qualification Test (AFQT, 1950). The ASVAB replaced AFQT in 1976 because the military needed *granular vocational placement*, not just "smart enough to serve."

The driving need: **the military has ~800 distinct occupational specialties** and needs to fill them all. They can't just take the smartest people and put them everywhere. They need the RIGHT person in the RIGHT role.

### How It Actually Works

10 subtests → composite scores → role-specific thresholds:

- **GT (General Technical)**: AR + VE → intelligence, admin, crypto
- **EL (Electronics)**: AR + MK + EI + GS → electronics, communications  
- **ST (Skilled Technical)**: GS + MK + MC + VE → engineering, medical
- **MM (Mechanical Maintenance)**: AS + MC + EI → vehicle, weapons maintenance
- **CL (Clerical)**: VE + AR + MK → administration, logistics

Each MOS (Military Occupational Specialty) defines minimum composite thresholds. **The job defines the requirements. The test identifies who meets them.**

### Application-First, Not Aptitude-First

The critical distinction:

| Approach | Question | Strategy |
|----------|----------|----------|
| **Aptitude-first** | "What can this person do?" | Test broadly, then find or create a role |
| **Application-first** | "Who can fill this role?" | Define the role, then find who qualifies |

The military is **application-first**. They know they need 3,000 crypto linguists this year. The ASVAB identifies who has the composite scores for that role. They don't discover linguists — they *manufacture* them by finding high-verbal, high-aptitude recruits and training them.

### The Feedback Loop

When a role is understaffed:
- Lower the composite threshold (expand the candidate pool)
- Increase recruiting targeting (more candidates in the pipeline)
- Increase training investment (upgrade near-qualifying candidates)

When a role is overstaffed:
- Raise the threshold (tighten admission)
- Redirect candidates to underfilled roles

**The system adapts the constraints to match supply and demand.**

---

## The Mathematical Structure

### It's Not Benchmarking

Benchmarking asks: "Rank all candidates, take the top N."
Placement asks: "Given M roles with specific requirements and N candidates with measured capabilities, assign candidates to roles to maximize system utility."

This is a **constrained assignment problem** — specifically, a **bipartite matching with capacity constraints and heterogeneous quality**:

```
maximize Σ v(i,r) · x(i,r)       # maximize total placement quality
subject to:
  Σ_r x(i,r) ≤ 1   for all i     # each candidate fills at most one role
  Σ_i x(i,r) = d(r) for all r     # each role gets exactly its demand
  c(i,r) = 1 if qualified          # candidate i meets role r's thresholds
```

### Adding Training = Adding Transformation Nodes

Candidates can be *upgraded* via training. This turns it into a **multi-commodity flow with transformation**:

```
Candidate (raw) → Training (cost, time) → Candidate (qualified)
```

The optimization now includes training investment decisions:
- Train candidate i for role r? Cost = training_time × salary
- Assign candidate i directly to role r they already qualify for? Cost = 0 but opportunity cost

### Adding Prediction = Dynamic Programming

Future needs are stochastic. The system must decide NOW whether to:
- Fill current roles with available candidates
- Reserve high-potential candidates for future, harder-to-fill roles
- Invest in training for anticipated future demand

This is a **two-stage stochastic program**:
- Stage 1: Decide training investments (before knowing exact future demand)
- Stage 2: Assign candidates given realized demand (with recourse)

### The Dual Decomposition Insight (from DeepSeek Reasoner)

The optimal strategy **separates**:
1. **Long-term**: What capabilities should we develop? (training portfolio)
2. **Short-term**: Which qualified candidate goes to which role? (assignment)

These decompose because training decisions have long lead times but assignment decisions are immediate. The constraint coupling is through the capability inventory: training determines what's available for assignment.

---

## The Cocapn Casting-Call Parallel

### Our Fleet Has Roles

| Role | What It Needs | Which Model Fills It |
|------|--------------|---------------------|
| Code generation | Fast, syntactically correct | GLM-5.1 (z.ai paid) |
| Context extraction | Cheap, fast, good enough | Seed-2.0-mini ($0.01) |
| Novel math | Deep reasoning | DeepSeek Reasoner |
| Cross-paradigm synthesis | World-class intelligence | Claude Opus |
| Second opinions | Different perspective | Hermes-70B |
| Quick routing | Fast classification | Qwen3.6-35B |

### Application-First

We don't benchmark all models on all tasks and rank them. We have **specific applications that need specific capabilities**:

- "I need to extract context from 5 files for a Claude prompt" → Seed-2.0-mini
- "I need to synthesize category theory + constraint theory into a new architecture" → Claude Opus
- "I need to write a 500-line Python module" → GLM-5.1 subagent
- "I need a second opinion on this design" → Hermes-70B

**The task defines the model. The model doesn't define the task.**

### The ASVAB Composite Analogy

The ASVAB has composites (GT, EL, ST, MM, CL) that are *combinations* of subtest scores. Our model evaluation has similar composites:

- **Reasoning depth**: Can it handle multi-step logic? (DeepSeek > GLM > Seed)
- **Speed**: How fast does it respond? (Seed-mini > GLM > DeepSeek > Claude)
- **Cost efficiency**: Quality per dollar? (Seed-mini >>> GLM >> Claude)
- **Novelty**: Can it produce genuinely new ideas? (Claude > DeepSeek > GLM > Seed)
- **Code quality**: Does the code work first try? (GLM-5.1 > Seed-code > Hermes)

Each application needs a different *composite profile*:
- Routine code: high speed + high code quality + high cost efficiency → GLM-5.1
- Research prompt: high reasoning + high novelty → DeepSeek Reasoner
- File distillation: high speed + high cost efficiency → Seed-2.0-mini

---

## The FLUX Language Parallel

### 96 Languages, Each With Strengths

We implemented constraint checking in 96 languages. Not to find "the best language" — but because each language serves a **specific deployment target**:

| Application Need | Best Language | Why |
|-----------------|---------------|-----|
| Embedded (ARM Cortex-M) | C / Assembly | Zero overhead, no runtime |
| Web browser | JavaScript / WASM | Runs everywhere, sandboxed |
| Data pipeline | Python / NumPy | Rich ecosystem, vectorized |
| Safety-critical | Rust / Ada | Memory safety, provable |
| Research | Haskell / OCaml | Type-level proofs |
| Quick prototype | Python / Node | Fast iteration |
| FPGA | Verilog / VHDL | Hardware parallelism |
| Bare metal | C / Assembly | No OS dependency |

**The deployment target defines the language.** We don't pick Python because it's "best" — we pick it because the application is a data pipeline. We don't pick C because it's "fastest" — we pick it because the target is a 16KB microcontroller.

### The FLUX JIT is ASVAB Placement

The JIT compiler takes a constraint specification and *places* it on the optimal execution substrate:
- Few constraints, simple bounds → tight scalar loop
- Many constraints → SIMD vectorized
- Known deployment target → AOT compile to that target's native code

**Application-first**: The deployment context defines the compilation strategy.

---

## The Unified Principle

```
APPLICATION (need) → CAPABILITY INVENTORY (what's available) → PLACEMENT (optimal match)
     ↑                        ↑                                        |
     |                        |                                        |
     └──── FEEDBACK LOOP ─────┘ ←── PREDICTION (future needs) ────────┘
```

1. **Application defines the need** — what job, what target, what role
2. **Capability inventory catalogs assets** — test scores, model evaluations, language benchmarks
3. **Placement algorithm matches** — constrained optimization, not greedy ranking
4. **Feedback loop corrects** — wrong placement detected → adjust thresholds/retraining
5. **Prediction anticipates** — future needs → pre-position capability

### Why This Matters

Power for power's sake is waste. The ASVAB doesn't exist to find the smartest recruit — it exists to fill the military's roles. Casting-call doesn't exist to rank AI models — it exists to put the right model in the right task. FLUX doesn't exist to benchmark languages — it exists to serve deployment targets.

**We are building solutions waiting for problems that are predicted to come later.**

The ASVAB pre-positions human capability. Casting-call pre-positions model capability. FLUX pre-positions implementation capability. All three solve the same structural problem: **heterogeneous capability allocation to heterogeneous demand with stochastic futures**.

---

## The Mathematical Framework

Let:
- **A** = set of applications (roles, targets, tasks)
- **C** = set of candidates (recruits, models, languages)
- **φ(c)** = capability vector of candidate c
- **τ(a)** = threshold vector for application a
- **v(c,a)** = value of placing c in a
- **d(a)** = demand for application a
- **T(c,a)** = training/adaptation cost

The placement problem:

```
maximize  Σ_{c,a} v(c,a) · x(c,a) - Σ_{c,a} T(c,a) · y(c,a)
subject to:
  Σ_a x(c,a) ≤ 1              ∀c ∈ C       (each candidate placed once)
  Σ_c x(c,a) = d(a)           ∀a ∈ A       (each application filled)
  φ(c) + Δφ(c)·y(c,a) ≥ τ(a) ∀(c,a)∈x     (qualification after training)
  x(c,a) ∈ {0,1}, y(c,a) ∈ {0,1}
```

Adding prediction:

```
Stage 1 (now):     decide y(c,a) — training investments
Stage 2 (future):  observe d̃(a) — realized demand
                   decide x(c,a) — actual placement
```

The optimal policy maintains a **capability buffer** — a reserve of flexible candidates who can be deployed to multiple roles as demand materializes.

This is the Cocapn fleet strategy. This is the ASVAB strategy. This is the FLUX deployment strategy.

**Same structure, different substrate.**
