# Topology of Constraint Spaces

**Author:** Forgemaster ⚒️ (constraint-theory specialist)  
**Date:** 2026-05-19  
**Status:** Active research — mathematical foundations  
**Context:** EXACT-CHECKING-SPEC.md defines zero-false-negative constraint checking. This document explores the topological structure of constraint spaces.

---

## 1. The Constraint Space as a Topological Object

### 1.1 Definition

A **constraint system** of n axis-aligned interval constraints defines a **feasible region** in ℝⁿ:

```
X(A) = { x ∈ ℝⁿ | lo_i ≤ x_i ≤ hi_i  for all i = 1,...,n }
```

This is a hyper-rectangle (axis-aligned box). The **parameter space** of all possible constraint sets is:

```
A = { (lo_1, hi_1, ..., lo_n, hi_n) ∈ ℝ²ⁿ | lo_i ≤ hi_i }
```

The **total space** E = { (A, x) ∈ A × ℝⁿ | x ∈ X(A) } carries the subspace topology from ℝ³ⁿ, forming a locally trivial fiber bundle over A.

### 1.2 Fundamental Topological Properties

**Theorem 1 (Convexity).** *For any valid constraint tuple A, the feasible region X(A) is convex.*

*Proof.* Take any x, y ∈ X(A) and t ∈ [0,1]. For each coordinate i: lo_i ≤ x_i ≤ hi_i and lo_i ≤ y_i ≤ hi_i implies lo_i ≤ tx_i + (1-t)y_i ≤ hi_i. The convex combination preserves interval membership. □

**Corollary 1 (Connectedness).** X(A) is always path-connected (convex ⟹ path-connected).

**Corollary 2 (Simple Connectedness).** X(A) is always simply connected. Convex sets are contractible via H(x,t) = t·mid + (1-t)·x, so π₁(X(A)) = 0.

**Corollary 3 (All Betti Numbers Vanish).** For any non-empty box, H_k(X(A)) = 0 for all k ≥ 1, and H_0(X(A)) = ℤ.

**Implication for constraint checking:** The feasible region for axis-aligned constraints is topologically trivial. Every point can reach every other point via a straight line that never leaves the valid region. The interesting topology lives on the **boundary** and in the **complement** (violation space).

---

## 2. The Violation Surface

### 2.1 Boundary Structure

The **violation surface** ∂X(A) is where values transition from valid to invalid. For n constraints in ℝⁿ:

| Stratum | Active Constraints | Dimension | Count (for box) |
|---------|-------------------|-----------|-----------------|
| Facets  | 1                 | n-1       | 2n              |
| Ridges  | 2                 | n-2       | C(n,2) × 4     |
| ...     | k                 | n-k       | C(n,k) × 2^{n-k} |
| Vertices| n                 | 0         | 2ⁿ              |

This is a **Whitney stratified space** — decomposed into smooth manifolds (strata) that glue according to the face lattice.

### 2.2 Topology of the Boundary

**Theorem 2.** *For a bounded box in ℝⁿ, the boundary ∂X(A) is homeomorphic to Sⁿ⁻¹ (the (n-1)-sphere).*

*Proof.* A bounded box [a₁,b₁] × ... × [aₙ,bₙ] is homeomorphic to the closed unit ball Dⁿ via the affine map xᵢ ↦ (2xᵢ - aᵢ - bᵢ)/(bᵢ - aᵢ). The boundary of Dⁿ is Sⁿ⁻¹. □

**Euler characteristics:**
- n=2 (rectangle): ∂X ≈ S¹, χ = 0
- n=3 (box): ∂X ≈ S², χ = 2
- n=k: ∂X ≈ S^{k-1}, χ = 1 + (-1)^{k-1}

### 2.3 The Violation Space

The **violation space** ℝⁿ \ X(A) is the complement of the feasible region. For a bounded box:

**Theorem 3.** *The violation space ℝⁿ \ Box is homotopy equivalent to Sⁿ⁻¹.*

*Proof.* Deformation retract: every violating point retracts radially toward the nearest boundary point. The boundary ≈ Sⁿ⁻¹. □

**Practical significance:** In 2D, the violation space has one "hole" (the valid region). In 3D, the violation space wraps around the valid region like the complement of a solid ball. This tells us about the *connectivity of violations* — violations on opposite sides of the valid region are connected through the violation space.

---

## 3. Constraint Deformation and Bifurcation

### 3.1 Deformation as a Continuous Process

A **constraint deformation** is a continuous change in the bounds parameterized by t ∈ [0,1]:

```
A(t) = ([lo₁(t), hi₁(t)], ..., [loₙ(t), hiₙ(t)])
```

As t varies, the feasible region X(A(t)) changes. **Bifurcation points** are parameter values t* where the topology of X(A(t*)) changes.

### 3.2 Bifurcation Types for Box Constraints

For axis-aligned constraints, bifurcations are surprisingly simple — they correspond to **Thom fold catastrophes**:

| Bifurcation | Condition | Topological Change |
|-------------|-----------|--------------------|
| **Collapse** | lo_i(t*) = hi_i(t*) | Dimension drops by 1 (effective dimension decreases) |
| **Empty** | lo_i(t*) > hi_i(t*) | Feasible set becomes empty — connected component vanishes |
| **Unbounded** | lo_i(t*) → -∞ or hi_i(t*) → +∞ | Boundary homeomorphism changes (Sⁿ⁻¹ → ℝⁿ⁻¹) |

**Theorem 4.** *For box constraints, bifurcations occur exactly when an interval collapses (lo_i = hi_i) or inverts (lo_i > hi_i). These are the only topological transitions.*

*Proof.* The homeomorphism type of a box [a₁,b₁] × ... × [aₙ,bₙ] is determined by which intervals have positive width. If all are positive, it's Dⁿ. If k are zero-width, it's D^{n-k}. If any inverts, it's empty. These are the only transitions. □

### 3.3 Relation to Catastrophe Theory

The seven elementary catastrophes of Thom map to constraint bifurcations:

- **Fold** (codim 1): Single interval collapses — the most common bifurcation
- **Cusp** (codim 2): Two intervals collapse simultaneously at a vertex
- **Swallowtail/Butterfly**: Higher-order coincident collapses (rare in practice)

For the FLUX engine (max 8 constraints), the highest codimension bifurcation involves all 8 intervals collapsing simultaneously — a codimension-8 "butterfly" catastrophe.

### 3.4 Efficient Detection

**Algorithm: Bifurcation Detection**

For a deformation parameterized by t:
1. Monitor interval widths: w_i(t) = hi_i(t) - lo_i(t)
2. Bifurcation occurs when any w_i(t) crosses zero
3. Binary search for exact bifurcation parameter t*
4. At t*, the effective dimension changes

**Complexity:** O(n × log(1/ε)) where ε is the precision of t* location.

---

## 4. Homotopy Theory of Constraint Systems

### 4.1 When Are Two Constraint Systems Equivalent?

**Definition.** Two constraint systems A, B are **homotopy equivalent** if there exists a continuous deformation from A to B through non-empty constraint systems.

**Theorem 5.** *Two box constraint systems in ℝⁿ are homotopy equivalent if and only if they have the same effective dimension (number of non-degenerate intervals).*

*Proof.* 
- If: All boxes with the same effective dimension d are homeomorphic to D^d, hence homotopy equivalent. Linear interpolation of bounds provides the explicit homotopy.
- Only if: If effective dimensions differ, the Betti numbers differ (one has H_k ≠ 0 for some k where the other doesn't), violating homotopy equivalence. □

### 4.2 Implications for Constraint Checking

**Theorem 6.** *Homotopy equivalent constraint systems detect the same violations at the homotopy level.*

This means:
- Both systems have the same number of violation "zones"
- The connectivity of the violation space is preserved
- The severity landscape has the same topological structure

**However:** Homotopy equivalence does NOT mean the same values violate. Two systems can be homotopy equivalent while having completely different valid regions. They have the same *shape class*, not the same *location*.

### 4.3 Algorithm: Homotopy Equivalence Check

```python
def are_homotopy_equivalent(space_a, space_b):
    # Must have same ambient dimension
    if space_a.dimension != space_b.dimension:
        return False
    # Must have same effective dimension
    eff_a = sum(1 for c in space_a.constraints if c.width() > 0)
    eff_b = sum(1 for c in space_b.constraints if c.width() > 0)
    return eff_a == eff_b
```

**Complexity:** O(n) — just count non-degenerate intervals.

### 4.4 Linear Homotopy Verification

To *prove* equivalence by constructing an explicit deformation:

```python
def verify_homotopy_path(space_a, space_b, steps=100):
    for t in [i/steps for i in range(steps+1)]:
        intermediate = linear_interpolation(space_a, space_b, t)
        if intermediate.is_empty():
            return False  # Path broken — not homotopy equivalent via linear path
    return True
```

**Note:** Even if the linear path fails, the systems may still be homotopy equivalent via a non-linear path.

---

## 5. Sheaf-Theoretic Distributed Constraint Checking

### 5.1 The Constraint Sheaf

Define the **constraint sheaf** F on the site of sensor subsets:

```
F(U) = { assignments a over U | a satisfies all constraints scoped to U }
```

With restriction maps: for V ⊆ U, res_{U,V}(a) = a|_V (project to V's dimensions).

### 5.2 When the Gluing Axiom Holds

**Theorem 7.** *For axis-aligned (per-dimension) constraints, F is always a sheaf.*

*Proof.* Each constraint is scoped to exactly one dimension. Local sections over any cover can always be glued because there are no cross-dimensional constraints to violate. The glued assignment satisfies all constraints because each constraint is checked locally. □

### 5.3 When Gluing Fails

Gluing fails when **cross-dimensional constraints** exist whose scope spans multiple local patches but isn't contained in any single patch.

**Example (Gluing Failure):**
```
3 sensors: A, B, C
Pairwise constraints: A ≠ B, B ≠ C, C ≠ A  (scoped to pairs)
Global constraint: A + B + C = 100  (scoped to all three)

Cover: {A,B}, {B,C}, {C,A}

Local sections:
  {A,B}: A=30, B=40   → passes A≠B
  {B,C}: B=40, C=30   → passes B≠C  
  {C,A}: C=30, A=30   → passes C≠A

Overlaps agree:
  {A,B} ∩ {B,C}: B=40 ✓
  {B,C} ∩ {C,A}: C=30 ✓
  {C,A} ∩ {A,B}: A=30 ✓

Glued: A=30, B=40, C=30
Global check: 30+40+30 = 100 ✓ (accidentally passes here)

Change A=20 in first section:
  Glued: A=20, B=40, C=30 → 20+40+30 = 90 ≠ 100 → FAILS
  But all local sections pass!
```

### 5.4 Conditions for Correct Distributed Checking

Distributed constraint checking is correct (local ⟹ global) iff:

1. **Localized Scopes:** Every constraint's scope is contained within some patch of the cover
2. **Amalgamation:** Overlapping patches can merge their valid assignments
3. **No Hidden Globals:** No constraint spans patches without being in any single patch

**Practical implication:** For the FLUX engine with per-sensor constraints, distributed checking always works. For systems with cross-sensor constraints, the cover must be chosen so every cross-constraint is locally enforceable.

---

## 6. Summary: Topological Facts for FLUX

| Property | Axis-Aligned Box | General Constraints |
|----------|-----------------|---------------------|
| Feasible region topology | Always Dⁿ (contractible) | Can be arbitrary |
| Boundary topology | Always Sⁿ⁻¹ (if bounded) | Stratified space |
| Violation space | ≈ Sⁿ⁻¹ | Can be complex |
| Bifurcations | Interval collapse/inversion only | Rich catastrophe structure |
| Homotopy equivalence | Same effective dimension | Undecidable in general |
| Sheaf property | Always holds | Fails for unenforced globals |
| Simple connectedness | Always | Not guaranteed |
| Convexity | Always | Not guaranteed |

**Key insight:** The axis-aligned nature of FLUX constraints makes the topology trivially nice. The mathematical machinery becomes essential when we move to:
- Cross-dimensional constraints (non-axis-aligned)
- Nonlinear constraints
- Distributed checking with global constraints
- Constraint deformation under parametric uncertainty

---

## 7. Implementation

The theory is implemented in `src/python/flux_topology.py`:

| Class | Purpose |
|-------|---------|
| `ConstraintSpace` | Valid region with topological queries |
| `ViolationSurface` | Boundary decomposition and distance functions |
| `DeformationDetector` | Bifurcation detection during bound deformation |
| `HomotopyChecker` | Equivalence verification between constraint systems |
| `SheafChecker` | Distributed constraint gluing verification |

Visualization in `tools/visualize_constraint_space.py`:
- ASCII 2D constraint spaces with severity coding
- ASCII severity landscapes (signed distance)
- ASCII bifurcation diagrams
- Matplotlib 2D constraint spaces with boundary
- Matplotlib bifurcation diagrams

---

## 8. Connections to EXACT-CHECKING-SPEC

The EXACT engine guarantees zero false negatives by comparing values in original numeric space. The topological analysis shows:

1. **The violation surface is well-defined** — for boxes, it's Sⁿ⁻¹, and every violating point has a unique nearest boundary point.

2. **Signed distance is a continuous function** — the severity landscape is continuous, with discontinuities only at the boundary.

3. **The error mask is a topological invariant of position** — the set of violated constraints partitions ℝⁿ into 3ⁿ regions (each constraint can be: below, inside, or above), each connected.

4. **No phantom violations** — because the valid region is convex and the boundary is Sⁿ⁻¹, there are no "pockets" of valid space hidden inside violation zones. Every violated constraint genuinely means the point is outside the valid region.

This topological analysis confirms the EXACT specification's guarantee: with axis-aligned constraints and exact comparison, the violation detection is both complete (zero false negatives) and topologically sound (the boundary has no holes or hidden regions).
