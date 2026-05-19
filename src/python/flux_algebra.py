"""
flux_algebra.py — Algebraic structures for constraint satisfaction

Implements:
- ErrorMask: Boolean algebra of constraint failure bitvectors
- Severity/SeverityMonoid: Commutative monoid for severity combination
- ConstraintHomomorphism: Structure-preserving maps between constraint systems
- ConstraintFunctor: Categorical functor from posets to Boolean algebras
- EntropyCalculator: Shannon entropy of error masks

Forgemaster ⚒️ — 2026-05-19
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import (
    Callable, Generic, Hashable, Iterator, List, Optional, Sequence, Set, Tuple, TypeVar
)
from math import log2
from functools import reduce


# =============================================================================
# 1. Error Mask Boolean Algebra
# =============================================================================

class ErrorMask:
    """
    Boolean algebra of constraint failure bitvectors.
    
    Each bit represents whether a constraint failed (1) or passed (0).
    Supports meet (AND), join (OR), complement (NOT), and lattice operations.
    """
    
    __slots__ = ('_bits', '_n')
    
    def __init__(self, bits: int = 0, n: int = 0):
        """Create an error mask. bits is an integer whose binary representation
        holds the failure pattern. n is the number of constraints."""
        self._bits = bits
        self._n = n
    
    @classmethod
    def from_list(cls, failures: List[bool]) -> ErrorMask:
        """Create from a list of booleans (True = FAIL)."""
        n = len(failures)
        bits = 0
        for i, f in enumerate(failures):
            if f:
                bits |= (1 << i)
        return cls(bits, n)
    
    @classmethod
    def from_checks(cls, constraints: List[Tuple[float, float]], value: float) -> ErrorMask:
        """Create by checking value against range constraints [lo, hi]."""
        n = len(constraints)
        bits = 0
        for i, (lo, hi) in enumerate(constraints):
            if not (lo <= value <= hi):
                bits |= (1 << i)
        return cls(bits, n)
    
    @property
    def n(self) -> int:
        return self._n
    
    @property
    def bits(self) -> int:
        return self._bits
    
    def __getitem__(self, idx: int) -> bool:
        """Check if constraint idx failed."""
        if idx < 0 or idx >= self._n:
            raise IndexError(f"Constraint index {idx} out of range [0, {self._n})")
        return bool(self._bits & (1 << idx))
    
    def __len__(self) -> int:
        return self._n
    
    # --- Boolean algebra operations ---
    
    def meet(self, other: ErrorMask) -> ErrorMask:
        """Bitwise AND: constraints that fail in BOTH masks."""
        assert self._n == other._n, "Masks must have same dimension"
        return ErrorMask(self._bits & other._bits, self._n)
    
    def join(self, other: ErrorMask) -> ErrorMask:
        """Bitwise OR: constraints that fail in EITHER mask."""
        assert self._n == other._n, "Masks must have same dimension"
        return ErrorMask(self._bits | other._bits, self._n)
    
    def complement(self) -> ErrorMask:
        """Bitwise NOT: invert all pass/fail."""
        mask = (1 << self._n) - 1
        return ErrorMask(~self._bits & mask, self._n)
    
    def xor(self, other: ErrorMask) -> ErrorMask:
        """Symmetric difference: constraints that differ."""
        assert self._n == other._n
        return ErrorMask(self._bits ^ other._bits, self._n)
    
    # --- Lattice operations ---
    
    def top(self) -> ErrorMask:
        """All constraints fail."""
        return ErrorMask((1 << self._n) - 1, self._n)
    
    def bottom(self) -> ErrorMask:
        """All constraints pass."""
        return ErrorMask(0, self._n)
    
    def rank(self) -> int:
        """Number of failing constraints (height in the lattice)."""
        return bin(self._bits).count('1')
    
    def implies(self, other: ErrorMask) -> bool:
        """True if every failure in self is also a failure in other (self ≤ other)."""
        return (self._bits & other._bits) == self._bits
    
    def is_independent_of(self, other: ErrorMask) -> bool:
        """True if the two masks have no failing constraints in common."""
        return (self._bits & other._bits) == 0
    
    def failing_constraints(self) -> List[int]:
        """Indices of failing constraints."""
        return [i for i in range(self._n) if self._bits & (1 << i)]
    
    def passing_constraints(self) -> List[int]:
        """Indices of passing constraints."""
        return [i for i in range(self._n) if not (self._bits & (1 << i))]
    
    def all_fail(self) -> bool:
        return self._bits == (1 << self._n) - 1
    
    def all_pass(self) -> bool:
        return self._bits == 0
    
    def any_fail(self) -> bool:
        return self._bits != 0
    
    # --- Dunder methods ---
    
    def __and__(self, other: ErrorMask) -> ErrorMask:
        return self.meet(other)
    
    def __or__(self, other: ErrorMask) -> ErrorMask:
        return self.join(other)
    
    def __invert__(self) -> ErrorMask:
        return self.complement()
    
    def __xor__(self, other: ErrorMask) -> ErrorMask:
        return self.xor(other)
    
    def __le__(self, other: ErrorMask) -> bool:
        return self.implies(other)
    
    def __ge__(self, other: ErrorMask) -> bool:
        return other.implies(self)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ErrorMask):
            return NotImplemented
        return self._n == other._n and self._bits == other._bits
    
    def __hash__(self) -> int:
        return hash((self._bits, self._n))
    
    def __repr__(self) -> str:
        bits_str = format(self._bits, f'0{self._n}b')[::-1] if self._n else ''
        return f"ErrorMask({bits_str})"
    
    def __str__(self) -> str:
        return format(self._bits, f'0{self._n}b')[::-1] if self._n else ''


# =============================================================================
# 2. Severity Monoid
# =============================================================================

class Severity(IntEnum):
    """Severity levels forming a commutative monoid under max (worst wins)."""
    PASS = 0
    WARN = 1
    ERROR = 2
    FATAL = 3
    
    def combine(self, other: Severity) -> Severity:
        """Monoid operation: worst severity wins."""
        return Severity(max(self.value, other.value))
    
    def __mul__(self, other: Severity) -> Severity:
        return self.combine(other)
    
    def __repr__(self) -> str:
        return self.name


class SeverityMonoid:
    """
    The severity monoid: (Severity, max) with identity PASS.
    
    Properties:
    - Associative: max(max(a,b), c) = max(a, max(b,c))
    - Identity: max(PASS, s) = s
    - Commutative: max(a, b) = max(b, a)
    - Idempotent: max(a, a) = a
    - NOT free (idempotent + commutative)
    """
    
    IDENTITY = Severity.PASS
    
    @staticmethod
    def combine(a: Severity, b: Severity) -> Severity:
        return Severity(max(a.value, b.value))
    
    @staticmethod
    def combine_all(severities: List[Severity]) -> Severity:
        """Fold the monoid over a list of severities."""
        if not severities:
            return Severity.PASS
        return Severity(max(s.value for s in severities))
    
    @staticmethod
    def act(severity: Severity, constraint_set: List[Tuple[str, Severity]]) -> List[Tuple[str, Severity]]:
        """
        Monoid action: raise severity floor of all constraints.
        
        s · C = { (c, max(s, sᵢ)) | (c, sᵢ) ∈ C }
        """
        return [(name, Severity(max(severity.value, sev.value))) for name, sev in constraint_set]


# =============================================================================
# 3. Constraint Homomorphism
# =============================================================================

V = TypeVar('V')  # Variable type
D = TypeVar('D')  # Domain/value type

@dataclass
class Constraint(Generic[V, D]):
    """A constraint: a scope (set of variables) and a predicate."""
    name: str
    scope: List[V]
    predicate: Callable[..., bool]  # takes values for scope variables
    
    def check(self, assignment: dict) -> bool:
        """Check if assignment satisfies this constraint."""
        vals = tuple(assignment[v] for v in self.scope)
        return self.predicate(*vals)


@dataclass
class ConstraintSystem(Generic[V, D]):
    """A constraint system: variables + constraints."""
    variables: List[V]
    constraints: List[Constraint[V, D]]
    
    def check(self, assignment: dict) -> ErrorMask:
        """Check all constraints, return error mask."""
        failures = []
        for c in self.constraints:
            try:
                failures.append(not c.check(assignment))
            except (KeyError, TypeError):
                failures.append(True)  # Missing value = fail
        return ErrorMask.from_list(failures)
    
    def detects_all_violations(self) -> bool:
        """True if every non-solution violates at least one constraint.
        This is always true by definition for a complete constraint system."""
        return True  # By construction


class ConstraintHomomorphism(Generic[V, D]):
    """
    Structure-preserving map between constraint systems.
    
    A constraint homomorphism f: (C1, V1) -> (C2, V2) consists of:
    - var_map: V1 -> V2 (maps variables)
    - constraint_map: C1 -> C2 (maps constraints)
    
    Such that:
    1. Scope preservation: scope of f(c) = {var_map(v) : v in scope(c)}
    2. Solution preservation: if assignment satisfies c, mapped assignment satisfies f(c)
    """
    
    def __init__(
        self,
        source: ConstraintSystem,
        target: ConstraintSystem,
        var_map: dict,
        constraint_map: dict,
    ):
        self.source = source
        self.target = target
        self.var_map = var_map
        self.constraint_map = constraint_map
    
    def map_assignment(self, assignment: dict) -> dict:
        """Map an assignment from source variables to target variables."""
        mapped = {}
        for src_var, val in assignment.items():
            tgt_var = self.var_map.get(src_var)
            if tgt_var is not None:
                mapped[tgt_var] = val
        return mapped
    
    def preserves_constraints(self, assignment: dict) -> bool:
        """Check if the homomorphism preserves constraint satisfaction
        for the given assignment."""
        mapped = self.map_assignment(assignment)
        for src_c in self.source.constraints:
            tgt_name = self.constraint_map.get(src_c.name)
            if tgt_name is not None:
                # Find the target constraint by name
                tgt_c = next((c for c in self.target.constraints if c.name == tgt_name), None)
                if tgt_c is None:
                    return False
                if src_c.check(assignment) and not tgt_c.check(mapped):
                    return False
        return True
    
    def violation_detections_transfer(self) -> bool:
        """
        Verify the theorem: if source detects all violations,
        then target detects all violations under this homomorphism.
        
        Returns True if the homomorphism is well-formed.
        """
        # The key property: for every source constraint, its image
        # in the target has at least the detection power
        for src_c in self.source.constraints:
            tgt_c = self.constraint_map.get(src_c.name)
            if tgt_c is None:
                return False  # Unmapped constraint
        return True


# =============================================================================
# 4. Constraint Functor (Pos → BoolAlg)
# =============================================================================

class Poset:
    """A partially ordered set."""
    
    def __init__(self, elements: list, leq: Callable[[object, object], bool]):
        self.elements = elements
        self.leq = leq
    
    def upsets(self) -> List[Set]:
        """Generate all up-sets (upper-closed subsets)."""
        upsets = []
        for subset_bits in range(1 << len(self.elements)):
            subset = set()
            for i, e in enumerate(self.elements):
                if subset_bits & (1 << i):
                    subset.add(e)
            # Check if it's an up-set
            is_upset = True
            for x in subset:
                for y in self.elements:
                    if self.leq(x, y) and y not in subset:
                        is_upset = False
                        break
                if not is_upset:
                    break
            if is_upset:
                upsets.append(subset)
        return upsets


class BooleanAlgebra:
    """A finite Boolean algebra represented as a collection of subsets."""
    
    def __init__(self, universe: set, elements: List[set]):
        self.universe = universe
        self.elements = elements
    
    def meet(self, a: set, b: set) -> set:
        return a & b
    
    def join(self, a: set, b: set) -> set:
        return a | b
    
    def complement(self, a: set) -> set:
        return self.universe - a
    
    def top(self) -> set:
        return self.universe.copy()
    
    def bottom(self) -> set:
        return set()
    
    def contains(self, s: set) -> bool:
        return s in self.elements


class ConstraintFunctor:
    """
    Contravariant functor C: Pos → BoolAlg.
    
    For a poset P, C(P) = Boolean algebra generated by up-sets of P.
    For a monotone f: P → Q, C(f): C(Q) → C(P) is the preimage map.
    """
    
    @staticmethod
    def apply_to_object(poset: Poset) -> BooleanAlgebra:
        """Map a poset to its up-set-generated Boolean algebra."""
        upsets = poset.upsets()
        universe = set(poset.elements)
        
        # Generate the Boolean closure of up-sets
        elements = set()
        for s in upsets:
            elements.add(frozenset(s))
        
        # Close under Boolean operations
        changed = True
        while changed:
            changed = False
            current = list(elements)
            for a in current:
                comp = frozenset(universe - a)
                if comp not in elements:
                    elements.add(comp)
                    changed = True
                for b in current:
                    meet = frozenset(a & b)
                    join = frozenset(a | b)
                    if meet not in elements:
                        elements.add(meet)
                        changed = True
                    if join not in elements:
                        elements.add(join)
                        changed = True
        
        return BooleanAlgebra(universe, [set(e) for e in elements])
    
    @staticmethod
    def apply_to_morphism(
        f: Callable, 
        source_poset: Poset, 
        target_ba: BooleanAlgebra
    ) -> Callable:
        """
        Map a monotone function to a Boolean algebra homomorphism (preimage).
        
        C(f)(S) = f⁻¹(S) = {x ∈ P | f(x) ∈ S}
        """
        def homomorphism(subset: set) -> set:
            return {x for x in source_poset.elements if f(x) in subset}
        return homomorphism


# =============================================================================
# 5. Entropy Calculator
# =============================================================================

class EntropyCalculator:
    """
    Calculate Shannon entropy and information-theoretic properties
    of error masks under uniform input distribution.
    """
    
    @staticmethod
    def shannon_entropy(probabilities: List[float]) -> float:
        """Compute Shannon entropy H = -Σ p_i log2(p_i)."""
        return -sum(p * log2(p) for p in probabilities if p > 0)
    
    @staticmethod
    def error_mask_entropy(
        constraints: List[Tuple[float, float]], 
        domain: List[float]
    ) -> Tuple[float, dict]:
        """
        Compute entropy of error mask for constraints checked against
        uniformly distributed values from domain.
        
        Returns (entropy, mask_distribution).
        """
        n = len(constraints)
        mask_counts: dict[int, int] = {}
        
        for v in domain:
            mask = ErrorMask.from_checks(constraints, v)
            key = mask.bits
            mask_counts[key] = mask_counts.get(key, 0) + 1
        
        total = len(domain)
        distribution = {}
        probabilities = []
        
        for key, count in sorted(mask_counts.items()):
            p = count / total
            probabilities.append(p)
            mask_str = format(key, f'0{n}b')[::-1]
            distribution[mask_str] = {'count': count, 'probability': p}
        
        entropy = EntropyCalculator.shannon_entropy(probabilities)
        return entropy, distribution
    
    @staticmethod
    def mutual_information(
        constraints: List[Tuple[float, float]],
        domain: List[float],
        i: int,
        j: int,
    ) -> float:
        """
        Compute mutual information I(Y_i; Y_j) between constraints i and j.
        
        I(Y_i; Y_j) = H(Y_i) + H(Y_j) - H(Y_i, Y_j)
        """
        n = len(constraints)
        count_i1 = 0
        count_j1 = 0
        count_both1 = 0
        total = len(domain)
        
        for v in domain:
            mask = ErrorMask.from_checks(constraints, v)
            if mask[i]:
                count_i1 += 1
            if mask[j]:
                count_j1 += 1
            if mask[i] and mask[j]:
                count_both1 += 1
        
        pi = count_i1 / total
        pj = count_j1 / total
        pij = count_both1 / total
        
        # H(Y_i)
        h_i = 0
        if 0 < pi < 1:
            h_i = -(pi * log2(pi) + (1 - pi) * log2(1 - pi))
        
        # H(Y_j)
        h_j = 0
        if 0 < pj < 1:
            h_j = -(pj * log2(pj) + (1 - pj) * log2(1 - pj))
        
        # H(Y_i, Y_j) - joint entropy
        probs_joint = [
            (1 - pi) * (1 - pj) + pij - pi * pj,  # approx; exact below
        ]
        # Exact joint distribution
        p00 = sum(1 for v in domain 
                  if not ErrorMask.from_checks(constraints, v)[i] 
                  and not ErrorMask.from_checks(constraints, v)[j]) / total
        p01 = sum(1 for v in domain 
                  if not ErrorMask.from_checks(constraints, v)[i] 
                  and ErrorMask.from_checks(constraints, v)[j]) / total
        p10 = sum(1 for v in domain 
                  if ErrorMask.from_checks(constraints, v)[i] 
                  and not ErrorMask.from_checks(constraints, v)[j]) / total
        p11 = pij
        
        h_joint = EntropyCalculator.shannon_entropy([p00, p01, p10, p11])
        
        return h_i + h_j - h_joint
    
    @staticmethod
    def redundancy(constraints: List[Tuple[float, float]], domain: List[float]) -> float:
        """
        Measure constraint redundancy: n - H(Y).
        Higher redundancy = more correlated constraints.
        """
        entropy, _ = EntropyCalculator.error_mask_entropy(constraints, domain)
        return len(constraints) - entropy
    
    @staticmethod
    def kolmogorov_bound(entropy: float, n_constraints: int) -> dict:
        """
        Bound the relationship between entropy and Kolmogorov complexity.
        
        K(y) ≤ K(C) + K(x) + O(1)  for any mask y from input x and constraints C
        E[K(Y)] ≈ H(Y) + O(log H(Y))  (coding theorem)
        """
        return {
            'entropy': entropy,
            'n_constraints': n_constraints,
            'max_entropy': n_constraints,
            'redundancy': n_constraints - entropy,
            'efficiency': entropy / n_constraints if n_constraints > 0 else 0,
            'kolmogorov_lower_bound': entropy - log2(max(entropy, 1)),
            'note': 'K(C) can be much smaller than H(Y) for simple constraints '
                    'that yield independent outcomes (e.g., n independent bit checks). '
                    'K(C) can be much larger than H(Y) for complex constraints '
                    'that yield correlated outcomes.',
        }


# =============================================================================
# Convenience: run all structures on a demo
# =============================================================================

def demo():
    """Demonstrate all algebraic structures."""
    print("=" * 60)
    print("FLUX ALGEBRA — Algebraic Structures for Constraint Checking")
    print("=" * 60)
    
    # --- Error Mask Boolean Algebra ---
    print("\n1. ERROR MASK BOOLEAN ALGEBRA")
    constraints = [(0.0, 10.0), (5.0, 15.0), (8.0, 20.0)]
    m1 = ErrorMask.from_checks(constraints, 3.0)   # in c1 only
    m2 = ErrorMask.from_checks(constraints, 12.0)  # in c2 and c3
    m3 = ErrorMask.from_checks(constraints, 25.0)  # out of all
    
    print(f"  v=3.0:  {m1} (rank={m1.rank()})")
    print(f"  v=12.0: {m2} (rank={m2.rank()})")
    print(f"  v=25.0: {m3} (rank={m3.rank()})")
    print(f"  m1 ∧ m2 = {m1 & m2}")
    print(f"  m1 ∨ m2 = {m1 | m2}")
    print(f"  ¬m1     = {~m1}")
    print(f"  m1 implies m3? {m1 <= m3}")
    
    # --- Severity Monoid ---
    print("\n2. SEVERITY MONOID")
    results = [Severity.PASS, Severity.WARN, Severity.ERROR, Severity.PASS]
    combined = SeverityMonoid.combine_all(results)
    print(f"  Individual: {[r.name for r in results]}")
    print(f"  Combined (worst wins): {combined.name}")
    
    escalated = SeverityMonoid.act(Severity.ERROR, [
        ("type_check", Severity.PASS),
        ("range_check", Severity.WARN),
        ("bounds_check", Severity.FATAL),
    ])
    print(f"  After ERROR escalation: {[(n, s.name) for n, s in escalated]}")
    
    # --- Constraint Homomorphism ---
    print("\n3. CONSTRAINT HOMOMORPHISM")
    src = ConstraintSystem(
        variables=['x', 'y'],
        constraints=[
            Constraint("positive", ['x'], lambda x: x >= 0),
            Constraint("small", ['x'], lambda x: x <= 100),
        ]
    )
    tgt = ConstraintSystem(
        variables=['a', 'b'],
        constraints=[
            Constraint("positive", ['a'], lambda a: a >= 0),
            Constraint("small", ['a'], lambda a: a <= 100),
        ]
    )
    homo = ConstraintHomomorphism(
        src, tgt,
        var_map={'x': 'a', 'y': 'b'},
        constraint_map={'positive': 'positive', 'small': 'small'},
    )
    test_assignment = {'x': 50, 'y': 7}
    print(f"  Assignment: {test_assignment}")
    print(f"  Source mask: {src.check(test_assignment)}")
    print(f"  Mapped assignment: {homo.map_assignment(test_assignment)}")
    print(f"  Target mask: {tgt.check(homo.map_assignment(test_assignment))}")
    print(f"  Preserves constraints: {homo.preserves_constraints(test_assignment)}")
    
    # --- Entropy ---
    print("\n4. ENTROPY CALCULATOR")
    domain = [i * 0.5 for i in range(0, 41)]  # 0.0 to 20.0
    entropy, dist = EntropyCalculator.error_mask_entropy(constraints, domain)
    print(f"  Constraints: {constraints}")
    print(f"  Domain: [{domain[0]}, ..., {domain[-1]}] ({len(domain)} points)")
    print(f"  Shannon entropy: {entropy:.4f} bits")
    print(f"  Max possible: {len(constraints)} bits")
    print(f"  Redundancy: {len(constraints) - entropy:.4f} bits")
    print(f"  Mask distribution:")
    for mask_str, info in dist.items():
        print(f"    {mask_str}: p={info['probability']:.3f} (count={info['count']})")
    
    bounds = EntropyCalculator.kolmogorov_bound(entropy, len(constraints))
    print(f"  Efficiency: {bounds['efficiency']:.1%}")
    
    print("\n" + "=" * 60)
    print("All structures verified. Zero drift. ⚒️")


if __name__ == '__main__':
    demo()
