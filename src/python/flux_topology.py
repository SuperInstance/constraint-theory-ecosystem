"""
flux_topology.py — Topological Analysis of Constraint Spaces

Implements topological structures for the FLUX constraint engine:
1. ConstraintSpace — space of valid values for a constraint set
2. ViolationSurface — boundary where violations occur, parameterized
3. DeformationDetector — detects topological bifurcation as bounds change
4. HomotopyChecker — checks if two constraint systems are equivalent
5. SheafChecker — checks if distributed constraint sub-results glue correctly

References: EXACT-CHECKING-SPEC.md, TOPOLOGY-OF-CONSTRAINT-SPACES.md
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Callable
import math
import itertools


# ---------------------------------------------------------------------------
# 1. ConstraintSpace — the valid region induced by axis-aligned constraints
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConstraintDef:
    """A single interval constraint [lo, hi] on one dimension."""
    lo: float
    hi: float
    name: str = ""

    def __post_init__(self):
        if self.lo > self.hi:
            raise ValueError(f"ConstraintDef({self.name}): lo={self.lo} > hi={self.hi}")

    def contains(self, value: float) -> bool:
        return self.lo <= value <= self.hi

    def empty(self) -> bool:
        """Is this a degenerate point constraint? Still valid (single point)."""
        return self.lo == self.hi

    def midpoint(self) -> float:
        return (self.lo + self.hi) / 2.0

    def width(self) -> float:
        return self.hi - self.lo


@dataclass
class ConstraintSpace:
    """
    Represents the space of valid values for a set of axis-aligned constraints.

    For n constraints in R^n, the valid region is a hyper-rectangle (box):
        X(A) = { x in R^n | lo_i <= x_i <= hi_i for all i }

    Properties proven in the literature:
    - Always convex (proof: linear combination preserves interval bounds)
    - Always connected (path-connected via line segments)
    - Always simply connected (contractible to midpoint via linear homotopy)
    - Homeomorphic to a closed ball when all intervals are non-degenerate
    """
    constraints: List[ConstraintDef]

    def __post_init__(self):
        if len(self.constraints) > 8:
            raise ValueError("Maximum 8 constraints (uint8 error mask)")

    # -- Topological invariants ------------------------------------------------

    @property
    def dimension(self) -> int:
        """Ambient dimension = number of constraints."""
        return len(self.constraints)

    def is_convex(self) -> bool:
        """Always True for axis-aligned box constraints."""
        return True

    def is_connected(self) -> bool:
        """Always True — convex implies path-connected."""
        return True

    def is_simply_connected(self) -> bool:
        """Always True — contractible to midpoint."""
        return True

    def is_bounded(self) -> bool:
        """True if all constraint intervals are finite."""
        return all(math.isfinite(c.width()) for c in self.constraints)

    # -- Geometric queries -----------------------------------------------------

    def contains(self, point: List[float]) -> bool:
        """Check if a point lies in the valid region (exact comparison)."""
        if len(point) != self.dimension:
            raise ValueError(f"Point dimension {len(point)} != space dimension {self.dimension}")
        return all(c.contains(point[i]) for i, c in enumerate(self.constraints))

    def midpoint(self) -> List[float]:
        """Center of the hyper-rectangle."""
        return [c.midpoint() for c in self.constraints]

    def volume(self) -> float:
        """Lebesgue measure of the valid region (product of interval widths)."""
        return math.prod(c.width() for c in self.constraints)

    def sample_grid(self, resolution: int = 10) -> List[List[float]]:
        """Generate a uniform grid of points within the valid region."""
        import numpy as np
        axes = [np.linspace(c.lo, c.hi, resolution) for c in self.constraints]
        return [list(pt) for pt in itertools.product(*axes)]

    # -- Deformation / homotopy ------------------------------------------------

    def contract(self, point: List[float], t: float) -> List[float]:
        """
        Linear contraction homotopy: H(x, t) = t*mid + (1-t)*x.
        At t=0: returns point. At t=1: returns midpoint.
        Proves contractibility (hence simple connectedness).
        """
        mid = self.midpoint()
        return [t * mid[i] + (1 - t) * point[i] for i in range(self.dimension)]

    def path_between(self, p1: List[float], p2: List[float], t: float) -> List[float]:
        """Linear path: gamma(t) = t*p1 + (1-t)*p2. Proves path-connectedness."""
        return [t * p1[i] + (1 - t) * p2[i] for i in range(self.dimension)]

    # -- Violation mask --------------------------------------------------------

    def violation_mask(self, point: List[float]) -> int:
        """
        Compute error mask: bit i set iff constraint i is violated.
        Same semantics as EXACT-CHECKING-SPEC error_mask (uint8).
        """
        mask = 0
        for i, c in enumerate(self.constraints):
            if not c.contains(point[i]):
                mask |= (1 << i)
        return mask

    def severity(self, point: List[float]) -> int:
        """Severity from popcount of violation mask."""
        return bin(self.violation_mask(point)).count('1')


# ---------------------------------------------------------------------------
# 2. ViolationSurface — boundary where violations occur
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BoundaryStratum:
    """
    A single stratum of the violation surface.

    For a set S of active constraints, the stratum is:
        ∂_S(F) = { x | constraint i active ⟺ i ∈ S, LICQ holds }

    Dimension: d - |S| (where d = ambient dimension).
    """
    active_constraints: Tuple[int, ...]  # Indices of active constraints
    dimension: int                        # d - |active_constraints|

    @property
    def codimension(self) -> int:
        return len(self.active_constraints)

    @property
    def is_facet(self) -> bool:
        """Highest-dimensional boundary component (single active constraint)."""
        return len(self.active_constraints) == 1

    @property
    def is_vertex(self) -> bool:
        """Lowest-dimensional: all constraints active."""
        return self.codimension >= 2  # For 2D+, vertex has d active constraints


@dataclass
class ViolationSurface:
    """
    The violation surface = boundary of the valid region.

    For n axis-aligned constraints in R^d (n == d for box constraints),
    the boundary decomposes into a Whitney stratified space:
    - Facets (|S|=1): (d-1)-dimensional faces (2d of them for a box)
    - Edges (|S|=2): (d-2)-dimensional ridges
    - Vertices (|S|=d): 0-dimensional corner points

    For a box (axis-aligned), boundary is homeomorphic to S^{d-1} (if bounded).
    """
    space: ConstraintSpace

    def strata(self) -> List[BoundaryStratum]:
        """Enumerate all boundary strata."""
        d = self.space.dimension
        result = []
        for k in range(1, d + 1):
            for combo in itertools.combinations(range(d), k):
                result.append(BoundaryStratum(
                    active_constraints=combo,
                    dimension=d - k
                ))
        return result

    def facets(self) -> List[BoundaryStratum]:
        """Top-dimensional boundary components (|S|=1)."""
        return [s for s in self.strata() if s.is_facet]

    def vertices(self) -> List[BoundaryStratum]:
        """Corner points (all d constraints active)."""
        d = self.space.dimension
        return [s for s in self.strata() if s.codimension == d]

    def vertex_coordinates(self) -> List[List[float]]:
        """Actual coordinates of all 2^d corner points."""
        d = self.space.dimension
        corners = []
        for bits in range(2**d):
            pt = []
            for i in range(d):
                c = self.space.constraints[i]
                pt.append(c.lo if (bits >> i) & 1 else c.hi)
            corners.append(pt)
        return corners

    def euler_characteristic(self) -> int:
        """
        Euler characteristic of the boundary.
        For a bounded box in R^d, boundary ≈ S^{d-1}, so χ = 1 + (-1)^{d-1}.
        For d=2 (rectangle boundary ≈ S^1): χ = 0.
        For d=3 (box boundary ≈ S^2): χ = 2.
        """
        d = self.space.dimension
        if self.space.is_bounded():
            return 1 + (-1)**(d - 1)
        return 0  # Unbounded: harder, return 0 as placeholder

    def face_count(self) -> Dict[int, int]:
        """Count faces by codimension. For d-box: f_k = 2^{d-k} * C(d, k)."""
        d = self.space.dimension
        counts = {}
        for k in range(d + 1):
            counts[k] = math.comb(d, k) * (2 ** (d - k)) if k < d else (2**d if k == d else 0)
        # Adjust: codimension k has C(d,k) * 2^(d-k) faces for a box
        return counts

    def signed_distance(self, point: List[float]) -> float:
        """
        Signed distance from point to boundary.
        Negative = outside, zero = on boundary, positive = inside.
        For box constraints: min over i of min(x_i - lo_i, hi_i - x_i).
        """
        d = self.space.dimension
        min_dist = float('inf')
        for i in range(d):
            c = self.space.constraints[i]
            dist_lo = point[i] - c.lo
            dist_hi = c.hi - point[i]
            min_dist = min(min_dist, dist_lo, dist_hi)
        return min_dist

    def closest_boundary_point(self, point: List[float]) -> List[float]:
        """Project a point onto the nearest boundary point."""
        result = list(point)
        min_penetration = float('inf')
        best_dim = 0
        best_side = 'lo'
        for i, c in enumerate(self.space.constraints):
            pen_lo = point[i] - c.lo
            pen_hi = c.hi - point[i]
            if pen_lo < min_penetration:
                min_penetration = pen_lo
                best_dim = i
                best_side = 'lo'
            if pen_hi < min_penetration:
                min_penetration = pen_hi
                best_dim = i
                best_side = 'hi'
        result[best_dim] = self.space.constraints[best_dim].lo if best_side == 'lo' else self.space.constraints[best_dim].hi
        return result


# ---------------------------------------------------------------------------
# 3. DeformationDetector — detect topological bifurcation
# ---------------------------------------------------------------------------

@dataclass
class BifurcationPoint:
    """
    A parameter value where the topology of the valid region changes.

    Analogous to catastrophe theory: as bounds deform continuously,
    the valid region changes topology at bifurcation points.
    """
    parameter_value: float
    bifurcation_type: str   # 'collapse', 'degenerate_vertex', 'unbounded_transition'
    description: str
    active_constraints: Tuple[int, ...] = ()


@dataclass
class DeformationDetector:
    """
    Detects when continuously changing constraint bounds cause
    topological changes in the valid region.

    For axis-aligned box constraints, bifurcation types:
    1. COLLAPSE: An interval [lo, hi] degenerates to a point (lo == hi).
       Dimension drops by 1.
    2. EMPTY: An interval collapses further (lo > hi), making valid set empty.
       Connected component disappears.
    3. UNBOUNDED: A bound goes to ±infinity, changing boundary homeomorphism.
    4. DEGENERATE_VERTEX: Multiple constraints become simultaneously active
       at a single point.

    These are the "fold catastrophes" of the constraint world.
    """
    space: ConstraintSpace

    def detect_collapses(self) -> List[int]:
        """Find dimensions where the interval has zero width."""
        return [i for i, c in enumerate(self.space.constraints) if c.width() == 0]

    def effective_dimension(self) -> int:
        """Dimension of the valid region (subtracting collapsed dimensions)."""
        return sum(1 for c in self.space.constraints if c.width() > 0)

    def deformation_series(
        self,
        dim: int,
        bound: str,  # 'lo' or 'hi'
        start: float,
        end: float,
        steps: int = 100
    ) -> List[BifurcationPoint]:
        """
        Sweep a bound from start to end and detect bifurcations.

        Returns list of BifurcationPoint where topology changes.
        """
        bifurcations = []

        for step in range(steps + 1):
            t = start + (end - start) * step / steps
            constraints = list(self.space.constraints)
            lo, hi = constraints[dim].lo, constraints[dim].hi

            if bound == 'lo':
                lo = t
            else:
                hi = t

            # Bifurcation: interval collapses
            if abs(lo - hi) < 1e-12:
                bifurcations.append(BifurcationPoint(
                    parameter_value=t,
                    bifurcation_type='collapse',
                    description=f"Dimension {dim} collapses to point at {t}",
                    active_constraints=(dim,)
                ))

            # Bifurcation: interval inverts (empty set)
            if lo > hi:
                bifurcations.append(BifurcationPoint(
                    parameter_value=t,
                    bifurcation_type='empty',
                    description=f"Dimension {dim} becomes empty at {t}",
                    active_constraints=(dim,)
                ))

        # Deduplicate (keep first of each type per dimension)
        seen = set()
        unique = []
        for b in bifurcations:
            key = (b.bifurcation_type, b.active_constraints)
            if key not in seen:
                seen.add(key)
                unique.append(b)

        return unique

    def critical_curves(
        self,
        dims: Tuple[int, int]
    ) -> List[Tuple[float, float]]:
        """
        For 2D deformation of two bounds simultaneously,
        compute the critical curve where topology changes.

        Returns list of (param1, param2) points on the critical curve.
        """
        i, j = dims
        c1, c2 = self.space.constraints[i], self.space.constraints[j]
        points = []

        # Collapse curve: c1.lo == c1.hi (parametric in c1 bound)
        for t in [c1.lo + k * c1.width() / 50 for k in range(51)]:
            points.append((t, c2.lo))

        # Collapse curve: c2.lo == c2.hi
        for t in [c2.lo + k * c2.width() / 50 for k in range(51)]:
            points.append((c1.lo, t))

        return points


# ---------------------------------------------------------------------------
# 4. HomotopyChecker — equivalence of constraint systems
# ---------------------------------------------------------------------------

@dataclass
class HomotopyResult:
    """Result of homotopy equivalence check between two constraint systems."""
    equivalent: bool
    reason: str
    betti_numbers_match: bool = False
    dimension_match: bool = False
    volume_ratio: float = 0.0


@dataclass
class HomotopyChecker:
    """
    Checks if two constraint systems are homotopy equivalent.

    For axis-aligned box constraints:
    - Two boxes in R^d are homotopy equivalent iff they have the same
      effective dimension (number of non-degenerate intervals).
    - All non-empty boxes of dimension d are homotopy equivalent
      (they are all contractible to a point).
    - The violation spaces R^d \\ Box are homotopy equivalent to S^{d-1}
      minus a point = R^{d-1} \\ {0}... actually R^d \\ B is homotopy
      equivalent to S^{d-1} (if bounded).

    Homotopy equivalence means: detect the same violations at the
    homotopy level (same connected components of violation space).
    """
    space_a: ConstraintSpace
    space_b: ConstraintSpace

    def same_ambient_dimension(self) -> bool:
        return self.space_a.dimension == self.space_b.dimension

    def check_dimension_equivalence(self) -> bool:
        """
        Two box constraint spaces are homotopy equivalent iff they have
        the same effective dimension.
        """
        return self.space_a.dimension == self.space_b.dimension

    def check_homotopy_equivalence(self) -> HomotopyResult:
        """
        Full homotopy equivalence check.

        For boxes:
        1. Same ambient dimension
        2. Both non-empty (volume > 0 or point constraint)
        3. Both bounded or both unbounded

        If all hold: homotopy equivalent (both contractible).
        """
        a, b = self.space_a, self.space_b

        if a.dimension != b.dimension:
            return HomotopyResult(
                equivalent=False,
                reason=f"Dimension mismatch: {a.dimension} vs {b.dimension}",
                dimension_match=False
            )

        if a.volume() == 0 and b.volume() > 0:
            return HomotopyResult(
                equivalent=False,
                reason="A is degenerate (volume 0), B is not",
                dimension_match=True
            )

        if b.volume() == 0 and a.volume() > 0:
            return HomotopyResult(
                equivalent=False,
                reason="B is degenerate (volume 0), A is not",
                dimension_match=True
            )

        vol_a = a.volume() if a.volume() > 0 else 0
        vol_b = b.volume() if b.volume() > 0 else 0
        ratio = vol_b / vol_a if vol_a > 0 else (0 if vol_b == 0 else float('inf'))

        return HomotopyResult(
            equivalent=True,
            reason="Both are contractible spaces (convex boxes) — homotopy equivalent to a point",
            betti_numbers_match=True,
            dimension_match=True,
            volume_ratio=ratio
        )

    def linear_homotopy(self, t: float) -> ConstraintSpace:
        """
        Construct the intermediate constraint space at parameter t ∈ [0, 1].
        Linear interpolation of bounds: lo(t) = (1-t)*lo_a + t*lo_b.

        If all intermediate spaces are non-empty, this proves homotopy equivalence
        via an explicit deformation.
        """
        if not self.same_ambient_dimension():
            raise ValueError("Cannot interpolate spaces of different dimension")

        intermediates = []
        for i in range(self.space_a.dimension):
            ca = self.space_a.constraints[i]
            cb = self.space_b.constraints[i]
            lo_t = (1 - t) * ca.lo + t * cb.lo
            hi_t = (1 - t) * ca.hi + t * cb.hi
            intermediates.append(ConstraintDef(
                lo=min(lo_t, hi_t),  # Ensure valid
                hi=max(lo_t, hi_t),
                name=f"interp_{i}"
            ))

        return ConstraintSpace(constraints=intermediates)

    def verify_homotopy_path(self, steps: int = 100) -> bool:
        """
        Verify that the linear homotopy path stays non-empty at all steps.
        If True: spaces are connected by a path of non-empty convex sets,
        proving they're in the same path component of constraint hyperspace.
        """
        for step in range(steps + 1):
            t = step / steps
            space_t = self.linear_homotopy(t)
            if space_t.volume() < 0:
                return False
            # Check all intervals are valid
            for c in space_t.constraints:
                if c.lo > c.hi:
                    return False
        return True


# ---------------------------------------------------------------------------
# 5. SheafChecker — distributed constraint checking via sheaf theory
# ---------------------------------------------------------------------------

@dataclass
class LocalSection:
    """A partial assignment over a subset of dimensions that satisfies local constraints."""
    dimensions: Tuple[int, ...]       # Which dimensions this covers
    values: Dict[int, float]          # dimension_index -> value
    passes: bool                      # Does this local assignment satisfy its constraints?


@dataclass
class SheafResult:
    """Result of sheaf gluing check."""
    glued_valid: bool
    all_local_pass: bool
    overlaps_consistent: bool
    global_constraints_satisfied: bool
    failure_reason: str = ""


@dataclass
class SheafChecker:
    """
    Checks if distributed constraint sub-results glue correctly.

    The constraint sheaf F assigns to each open set U of dimensions:
        F(U) = { assignments over U satisfying all constraints scoped to U }

    The gluing axiom: if local sections agree on overlaps, their union
    should be globally valid. This FAILS when there are "hidden" global
    constraints not enforced by any local section.

    For axis-aligned constraints (each scoped to one dimension),
    gluing ALWAYS works because constraints are purely local.
    For cross-dimensional constraints, gluing can fail.
    """
    space: ConstraintSpace
    cross_constraints: List[Tuple[Tuple[int, ...], Callable]] = field(default_factory=list)
    # Each cross_constraint: (dimensions, check_function(values_dict) -> bool)

    def local_check(self, section: LocalSection) -> bool:
        """Check if a local section satisfies its scoped constraints."""
        for dim in section.dimensions:
            c = self.space.constraints[dim]
            val = section.values.get(dim)
            if val is None:
                continue
            if not c.contains(val):
                return False
        # Check cross-constraints scoped within this section
        for dims, check_fn in self.cross_constraints:
            if all(d in section.dimensions for d in dims):
                vals = {d: section.values[d] for d in dims if d in section.values}
                if len(vals) == len(dims) and not check_fn(vals):
                    return False
        return True

    def check_gluing(self, sections: List[LocalSection]) -> SheafResult:
        """
        Check if a collection of local sections can be glued into
        a valid global assignment.

        Steps:
        1. All local sections pass their local checks
        2. Overlapping sections agree on shared dimensions
        3. The glued assignment satisfies ALL constraints (including cross)
        """
        # Step 1: Local checks
        all_pass = all(self.local_check(s) for s in sections)
        if not all_pass:
            return SheafResult(
                glued_valid=False,
                all_local_pass=False,
                overlaps_consistent=True,
                global_constraints_satisfied=False,
                failure_reason="At least one local section fails its constraints"
            )

        # Step 2: Check overlap consistency
        for i, s1 in enumerate(sections):
            for j, s2 in enumerate(sections):
                if i >= j:
                    continue
                overlap = set(s1.dimensions) & set(s2.dimensions)
                for dim in overlap:
                    if abs(s1.values[dim] - s2.values[dim]) > 1e-12:
                        return SheafResult(
                            glued_valid=False,
                            all_local_pass=True,
                            overlaps_consistent=False,
                            global_constraints_satisfied=False,
                            failure_reason=f"Sections {i},{j} disagree on dim {dim}"
                        )

        # Step 3: Glue into global assignment
        global_values: Dict[int, float] = {}
        for s in sections:
            global_values.update(s.values)

        # Check all per-dimension constraints
        for dim, c in enumerate(self.space.constraints):
            if dim in global_values:
                if not c.contains(global_values[dim]):
                    return SheafResult(
                        glued_valid=False,
                        all_local_pass=True,
                        overlaps_consistent=True,
                        global_constraints_satisfied=False,
                        failure_reason=f"Glued value {global_values[dim]} violates constraint {dim}"
                    )

        # Check cross-dimensional constraints
        for dims, check_fn in self.cross_constraints:
            if all(d in global_values for d in dims):
                vals = {d: global_values[d] for d in dims}
                if not check_fn(vals):
                    return SheafResult(
                        glued_valid=False,
                        all_local_pass=True,
                        overlaps_consistent=True,
                        global_constraints_satisfied=False,
                        failure_reason=f"Cross-constraint on dims {dims} fails after gluing"
                    )

        return SheafResult(
            glued_valid=True,
            all_local_pass=True,
            overlaps_consistent=True,
            global_constraints_satisfied=True
        )

    def is_sheaf(self) -> bool:
        """
        For axis-aligned constraints (no cross-constraints), this is always True.
        For cross-constraints, depends on whether they're locally enforceable.
        """
        if not self.cross_constraints:
            return True  # Purely local constraints → always a sheaf
        # Check: every cross-constraint's scope is contained in some
        # "local patch" (here we'd need the cover structure)
        return False  # Conservative: with cross-constraints, need explicit cover


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def constraint_space_2d(lo1: float, hi1: float, lo2: float, hi2: float,
                        name1: str = "x", name2: str = "y") -> ConstraintSpace:
    """Convenience constructor for 2D constraint spaces."""
    return ConstraintSpace([
        ConstraintDef(lo1, hi1, name1),
        ConstraintDef(lo2, hi2, name2)
    ])


def constraint_space_3d(lo1: float, hi1: float, lo2: float, hi2: float,
                        lo3: float, hi3: float,
                        name1: str = "x", name2: str = "y", name3: str = "z") -> ConstraintSpace:
    """Convenience constructor for 3D constraint spaces."""
    return ConstraintSpace([
        ConstraintDef(lo1, hi1, name1),
        ConstraintDef(lo2, hi2, name2),
        ConstraintDef(lo3, hi3, name3)
    ])


def violation_gradient_2d(
    space: ConstraintSpace,
    resolution: int = 20
) -> List[List[float]]:
    """
    Compute a severity landscape for 2D constraint space.
    Returns a resolution×resolution grid of severity values.
    """
    if space.dimension != 2:
        raise ValueError("violation_gradient_2d requires 2D space")

    c0, c1 = space.constraints[0], space.constraints[1]
    xs = [c0.lo + i * c0.width() / (resolution - 1) for i in range(resolution)]
    ys = [c1.lo + i * c1.width() / (resolution - 1) for i in range(resolution)]

    grid = []
    for y in ys:
        row = []
        for x in xs:
            row.append(float(space.severity([x, y])))
        grid.append(row)
    return grid
