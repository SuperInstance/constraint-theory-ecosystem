# Cross-Realm Algebraic Structures in Constraint Satisfaction

> Synthesized from DeepSeek Reasoner analysis across five algebraic domains.
> Forgemaster ⚒️ — 2026-05-19

---

## 1. Error Mask Boolean Algebra

### Formal Definition

Given a constraint system with `n` constraints, each checking whether a value `v` falls within a range `[l_i, h_i]`, the **error mask** is a bitvector `e ∈ {0,1}^n` where `e_i = 1` if constraint `i` FAILS.

The set of all possible error masks forms a **Boolean algebra** under the operations:

| Operation | Definition | Meaning |
|-----------|-----------|---------|
| **Meet (∧)** | Bitwise AND | "Both fail simultaneously" |
| **Join (∨)** | Bitwise OR | "Either fails" |
| **Complement (¬)** | Bitwise NOT | "Invert pass/fail" |
| **Top (⊤)** | All 1s (`111...1`) | "Every constraint fails" |
| **Bottom (⊥)** | All 0s (`000...0`) | "Every constraint passes" |

### Proof Sketch

The power set `P({1,...,n})` is a Boolean algebra under union, intersection, complement. The error mask is isomorphic to a subset of `{1,...,n}` (the set of violated constraints). Therefore:

1. **Closure**: For any two masks `a, b ∈ {0,1}^n`, bitwise AND/OR/NOT produce elements in `{0,1}^n`
2. **Commutativity**: `a ∧ b = b ∧ a`, `a ∨ b = b ∨ a` (bitwise operations commute)
3. **Associativity**: Grouping doesn't matter for bitwise ops
4. **Distributivity**: `a ∧ (b ∨ c) = (a ∧ b) ∨ (a ∧ c)`
5. **Complements**: `a ∨ ¬a = ⊤`, `a ∧ ¬a = ⊥`
6. **Identity**: `a ∧ ⊤ = a`, `a ∨ ⊥ = a`

### Lattice Structure

The lattice of error masks is the **n-dimensional Boolean lattice** `B_n = {0,1}^n`:
- Atoms: masks with exactly one bit set (single constraint failure)
- Co-atoms: masks with exactly one bit clear
- Height: `n` (rank = number of failing constraints)
- The lattice is graded: `rank(e) = popcount(e)`

### Connection to Constraint Checking

The error mask Boolean algebra captures the **full information content** of a constraint check. When you run `n` constraints against a value, you're computing an element of this algebra. The lattice structure tells you:
- Which failures **imply** other failures (order relation)
- How to **combine** results from different checks
- When two checks are **independent** (orthogonal in the lattice)

### Practical Implications

1. **Fast detection**: If you know `e₁ ≤ e₂` (failures of e₁ are a subset of e₂'s), you can skip checking e₂
2. **Partial evaluation**: Check constraints in order of severity; early failure masks later checks
3. **Compositional reasoning**: Combining constraint systems is join in this algebra

### Code

See `ErrorMask` class in `flux_algebra.py`.

---

## 2. Constraint Homomorphism

### Formal Definition

A **constraint homomorphism** `f: (C₁, V₁) → (C₂, V₂)` is a structure-preserving map between two constraint systems consisting of:

- A variable map `φ: V₁ → V₂`
- A constraint map `ψ: C₁ → C₂`

Such that for every constraint `c ∈ C₁` with scope `S ⊆ V₁`:
1. **Scope preservation**: `ψ(c)` has scope `φ(S) ⊆ V₂`
2. **Solution preservation**: If assignment `α: V₁ → D` satisfies `c`, then the induced assignment `β: V₂ → D` (defined by `β(φ(x)) = α(x)`) satisfies `ψ(c)`

### Required Properties

| Property | Definition | Why |
|----------|-----------|-----|
| **Monotonicity** | `α ≤ α' ⟹ f(α) ≤ f(α')` | Order preservation |
| **Constraint preservation** | `α ⊨ c ⟹ f(α) ⊨ ψ(c)` | Solutions map to solutions |
| **Violation propagation** | `f(α) violates ψ(c) ⟹ α violates c` | Contrapositive of above |

### Theorem: Violation Detection Transfer

**Statement**: If `f` is a constraint homomorphism and `C₁` detects all violations (every non-solution violates at least one constraint), then `C₂` detects all violations under `f`.

**Proof**:

1. Let `β: V₂ → D` be an assignment that is **not** a solution of `C₂`.
2. Then `β` violates some constraint `c₂ ∈ C₂`.
3. If `c₂ = ψ(c₁)` for some `c₁ ∈ C₁`, then `β` is the image of some `α` under `f`.
4. Since `f` preserves constraint satisfaction: `α satisfies c₁ ⟹ β satisfies ψ(c₁) = c₂`.
5. By contrapositive: `β violates c₂ ⟹ α violates c₁`.
6. Since `C₁` detects all violations, `α` is detected as a non-solution.
7. Therefore `β` is detected as a non-solution of `C₂`. ∎

### Practical Implications

1. **Safe refactoring**: If you can build a homomorphism from old constraints to new, detection is preserved
2. **Abstraction**: Coarser constraint systems that admit a homomorphism from finer ones inherit detection
3. **Testing**: Test the simpler system, get guarantees about the complex one

### Code

See `ConstraintHomomorphism` class in `flux_algebra.py`.

---

## 3. Severity Monoid

### Formal Definition

Let `S = {PASS, WARN, ERROR, FATAL}` with ordering `PASS < WARN < ERROR < FATAL`. Define the **severity monoid** `(S, ⊕)` where:

```
s₁ ⊕ s₂ = max(s₁, s₂)    // worst severity wins
```

### Proof of Monoid Properties

1. **Associativity**: `max(a, max(b, c)) = max(max(a, b), c)` — maximum of a totally ordered set is associative ✓
2. **Identity**: `max(PASS, s) = s` — PASS is the least element ✓
3. **Commutativity**: `max(a, b) = max(b, a)` ✓

Therefore `(S, ⊕)` is a **commutative monoid**.

### Is This a Free Monoid?

**No.** A free monoid over a set X consists of all finite strings over X with concatenation. The severity monoid is:
- **Idempotent**: `s ⊕ s = s` (not true for free monoid strings)
- **Commutative** (free monoids are not, except |X|=1)

These properties are incompatible with freeness.

### Monoid Action on Constraint Sets

The severity monoid acts on constraint sets `C` via:

```
s · C = { (c, max(s, sᵢ)) | (c, sᵢ) ∈ C }
```

This satisfies the action axioms:
- `(s₁ ⊕ s₂) · C = s₁ · (s₂ · C)` (associativity of action)
- `PASS · C = C` (identity action)

**Interpretation**: Raising the severity floor of all constraints. If you escalate a system's severity level, every constraint inherits at least that severity.

### Practical Implications

1. **Severity escalation**: Elevating system state escalates all constraint severities uniformly
2. **Compositional severity**: Combining results from independent checks is monoid multiplication
3. **Parallel checking**: Independent checks can be combined in any order (commutativity)

### Code

See `Severity`, `SeverityMonoid` in `flux_algebra.py`.

---

## 4. Constraint Functor (Category Theory)

### Definition

Define a **contravariant functor** `C: Pos → BoolAlg`:

- **Objects**: For a poset `(P, ≤)`, `C(P)` = Boolean algebra generated by the up-sets of P (subsets `U ⊆ P` such that `x ∈ U ∧ x ≤ y ⟹ y ∈ U`)
- **Morphisms**: For a monotone map `f: P → Q`, `C(f): C(Q) → C(P)` is the preimage `C(f)(S) = f⁻¹(S)`

### Why This Works

1. **Well-defined on objects**: The up-sets of a poset form a distributive lattice; their Boolean closure is a Boolean algebra
2. **Well-defined on morphisms**: Preimage under a monotone map sends up-sets to up-sets, and preserves all Boolean operations
3. **Functoriality**: `C(id) = id` and `C(g ∘ f) = C(f) ∘ C(g)` (contravariant)

### Objects and Morphisms

| Category | Objects | Morphisms |
|----------|---------|-----------|
| **Pos** | Partially ordered sets | Monotone (order-preserving) maps |
| **BoolAlg** | Boolean algebras | Boolean homomorphisms |

The functor maps:
- Ordered set → Boolean algebra of order-definable constraints
- Monotone map → Constraint translation (pullback)

### Natural Transformations

A natural transformation `η: C ⇒ D` between two such functors assigns to each poset `P` a Boolean homomorphism `η_P: C(P) → D(P)` such that for every monotone `f: P → Q`:

```
η_P ∘ C(f) = D(f) ∘ η_Q
```

For the identity functor, the only natural endomorphism is the identity (by Yoneda: the functor is representable by the 2-element Boolean algebra, and `Hom(2, 2)` as Boolean algebras has only the identity map).

### Practical Implications

1. **Constraint translation**: Mapping between constraint domains is functorial
2. **Compositionality**: Stacking constraint layers composes naturally
3. **Universality**: The functor construction gives a canonical way to generate constraint algebras from ordered structures

### Code

See `ConstraintFunctor` in `flux_algebra.py`.

---

## 5. Entropy of the Error Mask

### Shannon Entropy

For `n` constraints with uniformly distributed input values over domain `D`:

- Each constraint produces 1 bit (pass/fail)
- The error mask `Y = (Y₁, ..., Yₙ)` is a random variable over `{0,1}^n`

**Individual entropies**: `H(Yᵢ) ≤ 1`, with equality iff `Pr(Yᵢ = 1) = 1/2`

**Joint entropy**:
```
H(Y) = H(Y₁, ..., Yₙ) ≤ Σᵢ H(Yᵢ) ≤ n
```

Equality holds iff the constraint outcomes are **independent** (mutual information `I(Yᵢ; Yⱼ) = 0` for all i ≠ j).

For **uniform input** over domain `D` of size `|D|`:
```
H(Y) ≤ min(n, log₂|D|)
```

The entropy is bounded by both the number of constraints and the information content of the input.

### Relation to Kolmogorov Complexity

The **Kolmogorov complexity** `K(C)` of the constraint set is the length of the shortest program that outputs the constraints.

Key relationships:

1. **Expected complexity bounds entropy**: For computable distributions, `E[K(Y)] ≈ H(Y) + O(log H(Y))` (coding theorem)
2. **Complexity of constraints bounds complexity of masks**: Since `Y = F(X)` where `F` is determined by `C`:
   ```
   K(y | C) ≤ K(x) + O(1)    // mask computable from input + constraints
   K(y) ≤ K(C) + K(x) + O(1) // mask computable from constraints + input
   ```
3. **Entropy vs. constraint complexity**: No direct inequality between `H(Y)` and `K(C)` — simple constraints can yield high-entropy masks (e.g., n independent bit-checks), and complex constraints can yield low-entropy masks (e.g., all constraints identical)

**The fundamental insight**: The Shannon entropy of the error mask measures the **average information gained** from constraint checking. The Kolmogorov complexity of the constraint set measures the **algorithmic information required to describe** the checking procedure. They are complementary:
- `H(Y)`: How much you *learn* from checking
- `K(C)`: How much you *need to know* to check

### Practical Implications

1. **Optimal constraint ordering**: Check high-entropy constraints first (they reveal the most)
2. **Redundancy detection**: `n - H(Y)` measures constraint redundancy
3. **Compression**: If `K(C) << n`, the constraint system has exploitable structure

### Code

See `EntropyCalculator` in `flux_algebra.py`.

---

## Summary Table

| Structure | Algebra | Operation | Key Property | Practical Win |
|-----------|---------|-----------|-------------|---------------|
| Error Mask | Boolean algebra | ∧, ∨, ¬ | Complemented distributive lattice | Combine checks compositionally |
| Constraint Homo. | Homomorphism | Structure-preserving map | Violation detection transfers | Safe abstraction/refactoring |
| Severity | Commutative monoid | max (worst wins) | Idempotent, commutative | Parallel check composition |
| Constraint Functor | Contravariant functor | Preimage on up-sets | Functorial constraint translation | Canonical constraint generation |
| Entropy | Information theory | Shannon entropy | H(Y) ≤ n, bounded by K(C) | Optimal check ordering |

---

*"The glitches ARE the research agenda. The gaps ARE the work."*
