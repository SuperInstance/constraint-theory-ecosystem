"""
FLUX Composition — Hierarchical and composed constraint systems.

Constraint systems aren't flat — they nest. A medical device has
constraints at every level: sensor → circuit → subsystem → device → patient.

This module provides:
1. ConstraintGroup — named group of constraints (AND/OR/MAJORITY semantics)
2. ConstraintHierarchy — tree of groups with severity escalation
3. ConstraintComposer — compose multiple constraint sets into one check
4. OverrideRules — runtime overrides that respect hierarchy

The key insight: constraint composition is MONOIDAL.
- empty set = identity (always passes)
- merge = binary operation (AND semantics)
- associative: (A ∘ B) ∘ C = A ∘ (B ∘ C)

This means we can compose arbitrarily deep hierarchies without
changing the checking semantics.

Forgemaster ⚒️ — 2026-05-19
"""

import math
import hashlib
import time
from typing import List, Dict, Tuple, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum, auto


# ── Composition Semantics ──

class Semantics(Enum):
    """How to combine results from multiple constraints in a group."""
    ALL = auto()       # AND: all must pass (strictest)
    ANY = auto()       # OR: at least one must pass (lenient)
    MAJORITY = auto()  # >50% must pass
    QUORUM = auto()    # configurable threshold
    NONE = auto()      # NAND: none must pass (inverted)


@dataclass
class ConstraintResult:
    """Result of checking a single constraint."""
    name: str
    passed: bool
    value: float
    lo: float
    hi: float
    mask_bit: int = 0
    
    @property
    def severity(self) -> float:
        """How far outside bounds, normalized to range width."""
        if self.passed:
            return 0.0
        width = self.hi - self.lo
        if width == 0:
            return float('inf')
        if self.value < self.lo:
            return (self.lo - self.value) / width
        return (self.value - self.hi) / width


@dataclass
class GroupResult:
    """Result of checking a constraint group."""
    group_name: str
    passed: bool
    semantics: Semantics
    results: List[ConstraintResult]
    mask: int = 0
    
    @property
    def n_passed(self) -> int:
        return sum(1 for r in self.results if r.passed)
    
    @property
    def n_failed(self) -> int:
        return sum(1 for r in self.results if not r.passed)
    
    @property
    def max_severity(self) -> float:
        return max((r.severity for r in self.results if not r.passed), default=0.0)


class Constraint:
    """A single constraint with bounds."""
    def __init__(self, lo: float, hi: float, name: str = "",
                 priority: float = 1.0, tags: Set[str] = None):
        self.lo = lo
        self.hi = hi
        self.name = name
        self.priority = priority
        self.tags = tags or set()
    
    def check(self, value: float) -> ConstraintResult:
        if value != value:  # NaN
            passed = False
        else:
            passed = self.lo <= value <= self.hi
        
        return ConstraintResult(
            name=self.name,
            passed=passed,
            value=value,
            lo=self.lo,
            hi=self.hi,
        )
    
    def check_mask(self, value: float, bit: int = 0) -> Tuple[bool, int]:
        """Zero-alloc: returns (passed, mask)."""
        if value != value:
            return False, 1 << bit
        passed = self.lo <= value <= self.hi
        return passed, 0 if passed else (1 << bit)


class ConstraintGroup:
    """
    Named group of constraints with composition semantics.
    
    Groups can contain constraints or other groups (nesting).
    The semantics determine how results are combined.
    """
    
    def __init__(self, name: str, semantics: Semantics = Semantics.ALL,
                 quorum: float = 0.5, priority: float = 1.0,
                 tags: Set[str] = None):
        self.name = name
        self.semantics = semantics
        self.quorum = quorum
        self.priority = priority
        self.tags = tags or set()
        self._children: List = []  # Constraint or ConstraintGroup
    
    def add(self, child):
        """Add a constraint or subgroup."""
        self._children.append(child)
        return self
    
    @property
    def n_constraints(self) -> int:
        """Total leaf constraints."""
        total = 0
        for c in self._children:
            if isinstance(c, ConstraintGroup):
                total += c.n_constraints
            else:
                total += 1
        return total
    
    def check(self, values: Dict[str, float]) -> GroupResult:
        """
        Check all constraints against provided values.
        values maps constraint names to their values.
        """
        results = []
        
        for child in self._children:
            if isinstance(child, ConstraintGroup):
                sub_result = child.check(values)
                # Convert subgroup result to a single pass/fail
                results.append(ConstraintResult(
                    name=child.name,
                    passed=sub_result.passed,
                    value=0.0,
                    lo=0.0,
                    hi=0.0,
                ))
            else:
                value = values.get(child.name, float('nan'))
                results.append(child.check(value))
        
        passed = self._combine(results)
        mask = 0
        for i, r in enumerate(results):
            if not r.passed:
                mask |= (1 << i)
        
        return GroupResult(
            group_name=self.name,
            passed=passed,
            semantics=self.semantics,
            results=results,
            mask=mask,
        )
    
    def _combine(self, results: List[ConstraintResult]) -> bool:
        """Combine results according to semantics."""
        if not results:
            return True
        
        n_pass = sum(1 for r in results if r.passed)
        n_total = len(results)
        
        if self.semantics == Semantics.ALL:
            return n_pass == n_total
        elif self.semantics == Semantics.ANY:
            return n_pass > 0
        elif self.semantics == Semantics.MAJORITY:
            return n_pass > n_total / 2
        elif self.semantics == Semantics.QUORUM:
            return n_pass >= n_total * self.quorum
        elif self.semantics == Semantics.NONE:
            return n_pass == 0
        
        return n_pass == n_total  # default ALL
    
    def flatten(self) -> List[Constraint]:
        """Flatten to a list of all leaf constraints."""
        leaves = []
        for child in self._children:
            if isinstance(child, ConstraintGroup):
                leaves.extend(child.flatten())
            else:
                leaves.append(child)
        return leaves
    
    def hash(self) -> str:
        """Content hash of this group."""
        content = f"{self.name}:{self.semantics.name}:{self.quorum}:{self.priority}"
        for child in self._children:
            if isinstance(child, ConstraintGroup):
                content += f":G({child.hash()})"
            else:
                content += f":C({child.lo},{child.hi},{child.name})"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class ConstraintHierarchy:
    """
    Tree of constraint groups with severity escalation.
    
    When a constraint fails at a lower level, the hierarchy
    determines whether to escalate to higher levels.
    
    Example: medical device
    Level 0: sensor constraints (ambient temp, battery)
    Level 1: subsystem constraints (amplifier gain, filter bandwidth)
    Level 2: device constraints (measurement accuracy, safety limits)
    Level 3: patient constraints (vital signs, dosage)
    
    A level-0 failure might be recoverable.
    A level-3 failure is always critical.
    """
    
    def __init__(self):
        self.levels: Dict[int, ConstraintGroup] = {}
        self.level_names: Dict[int, str] = {}
        self.escalation_rules: Dict[int, Callable] = {}
    
    def add_level(self, level: int, group: ConstraintGroup, name: str = ""):
        """Add a constraint group at a hierarchy level."""
        self.levels[level] = group
        self.level_names[level] = name or group.name
    
    def set_escalation(self, from_level: int, rule: Callable[[GroupResult], bool]):
        """Set escalation rule: when does a failure at this level escalate up?"""
        self.escalation_rules[from_level] = rule
    
    def check(self, values: Dict[str, float]) -> Dict:
        """
        Check all levels bottom-up.
        Returns results per level with escalation status.
        """
        results = {}
        escalated = False
        
        for level in sorted(self.levels.keys()):
            group = self.levels[level]
            result = group.check(values)
            
            # Check escalation rule
            should_escalate = False
            if level in self.escalation_rules:
                should_escalate = self.escalation_rules[level](result)
            elif not result.passed:
                # Default: any failure escalates
                should_escalate = True
            
            results[level] = {
                "name": self.level_names.get(level, f"level_{level}"),
                "passed": result.passed,
                "n_constraints": result.n_passed + result.n_failed,
                "n_passed": result.n_passed,
                "n_failed": result.n_failed,
                "max_severity": result.max_severity,
                "mask": result.mask,
                "escalated": should_escalate,
            }
            
            if should_escalate:
                escalated = True
        
        return {
            "levels": results,
            "all_passed": all(r["passed"] for r in results.values()),
            "escalated": escalated,
            "total_constraints": sum(r["n_constraints"] for r in results.values()),
            "total_failed": sum(r["n_failed"] for r in results.values()),
        }
    
    def severity_at_level(self, level: int) -> float:
        """Base severity multiplier for a hierarchy level."""
        # Higher levels = more severe
        max_level = max(self.levels.keys()) if self.levels else 0
        if max_level == 0:
            return 1.0
        return (level + 1) / (max_level + 1)


class ConstraintComposer:
    """
    Compose multiple constraint sets into a unified check.
    
    The monoidal structure:
    - identity: empty constraint set (always passes)
    - merge: AND of all constraint sets
    - associative: composition order doesn't matter
    """
    
    def __init__(self):
        self.groups: List[ConstraintGroup] = []
    
    def add(self, group: ConstraintGroup) -> 'ConstraintComposer':
        """Add a constraint group to the composition."""
        self.groups.append(group)
        return self
    
    def check(self, values: Dict[str, float]) -> Dict:
        """
        Check all groups. Returns combined result.
        AND semantics: all groups must pass.
        """
        group_results = []
        
        for group in self.groups:
            result = group.check(values)
            group_results.append({
                "group": group.name,
                "passed": result.passed,
                "n_failed": result.n_failed,
                "mask": result.mask,
            })
        
        return {
            "passed": all(g["passed"] for g in group_results),
            "groups": group_results,
            "total_groups": len(group_results),
            "total_failed": sum(g["n_failed"] for g in group_results),
        }
    
    def merge(self) -> ConstraintGroup:
        """Merge all groups into a single flat group with ALL semantics."""
        merged = ConstraintGroup("merged", Semantics.ALL)
        for group in self.groups:
            for leaf in group.flatten():
                merged.add(leaf)
        return merged


class OverrideRules:
    """
    Runtime constraint overrides that respect hierarchy.
    
    Overrides can:
    - Widen bounds (emergency tolerance)
    - Narrow bounds (stricter safety)
    - Disable specific constraints
    - Change composition semantics
    
    Every override is logged with reason and expiry.
    """
    
    def __init__(self):
        self.overrides: Dict[str, Dict] = {}
        self.log: List[Dict] = []
    
    def override(self, name: str, new_lo: Optional[float] = None,
                 new_hi: Optional[float] = None, reason: str = "",
                 expiry: Optional[float] = None, disable: bool = False):
        """
        Register an override for a named constraint.
        
        Args:
            name: constraint name
            new_lo: new lower bound (None = keep original)
            new_hi: new upper bound (None = keep original)
            reason: why the override exists (audit trail)
            expiry: timestamp when override expires (None = permanent)
            disable: if True, constraint is disabled entirely
        """
        self.overrides[name] = {
            "lo": new_lo,
            "hi": new_hi,
            "reason": reason,
            "expiry": expiry,
            "disable": disable,
            "timestamp": time.time(),
        }
        self.log.append({
            "action": "override",
            "name": name,
            "new_lo": new_lo,
            "new_hi": new_hi,
            "reason": reason,
            "disable": disable,
        })
    
    def apply(self, constraints: List[Constraint]) -> List[Constraint]:
        """Apply overrides to a list of constraints."""
        now = time.time()
        result = []
        
        for c in constraints:
            if c.name in self.overrides:
                ovr = self.overrides[c.name]
                
                # Check expiry
                if ovr["expiry"] is not None and now > ovr["expiry"]:
                    self.log.append({"action": "expired", "name": c.name})
                    result.append(c)
                    continue
                
                if ovr["disable"]:
                    # Disabled constraint: replace with one that always passes
                    new_c = Constraint(float('-inf'), float('inf'), c.name + "_disabled",
                                       c.priority, c.tags)
                    result.append(new_c)
                else:
                    new_lo = ovr["lo"] if ovr["lo"] is not None else c.lo
                    new_hi = ovr["hi"] if ovr["hi"] is not None else c.hi
                    new_c = Constraint(new_lo, new_hi, c.name, c.priority, c.tags)
                    new_c._override_reason = ovr["reason"]
                    result.append(new_c)
            else:
                result.append(c)
        
        return result
    
    def clear(self, name: str = None):
        """Clear override(s)."""
        if name:
            self.overrides.pop(name, None)
            self.log.append({"action": "clear", "name": name})
        else:
            self.overrides.clear()
            self.log.append({"action": "clear_all"})
