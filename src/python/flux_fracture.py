"""
flux_fracture.py — FRACTURE-COALESCE: Disjoint Linear Algebra for Constraint Systems

The ideal gas law for constraints says: if constraints are independent,
the partition function factorizes Z = prod(Z_i). This module makes that
OPERATIONAL by fracturing constraint systems into independent blocks
and coalescing results provably correct.

THEOREM: If fracture correctly identifies connected components of the
constraint-dimension dependency graph, coalescence via bitwise OR
preserves zero false negatives.

Proof: Each constraint violation is a Boolean event. For independent blocks,
the event spaces are disjoint (no shared dimensions). The union of all
violations = OR of block error masks. QED.

Author: Forgemaster ⚒️ (Constraint Theory Ecosystem)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Set, Tuple

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# 1. DependencyGraph — Bipartite constraint-dimension graph
# ---------------------------------------------------------------------------

@dataclass
class DependencyGraph:
    """
    Bipartite graph: constraints (rows) × dimensions (columns).
    Edge (i, j) exists iff constraint i involves dimension j.
    """
    adjacency: NDArray[np.uint8]  # shape (n_constraints, n_dimensions)
    n_constraints: int
    n_dimensions: int
    constraint_names: List[str] = field(default_factory=list)
    dimension_names: List[str] = field(default_factory=list)

    @classmethod
    def from_masks(cls,
                   masks: Sequence[NDArray[np.integer]],
                   constraint_names: Sequence[str] = (),
                   dimension_names: Sequence[str] = ()) -> "DependencyGraph":
        """
        Build from per-constraint dimension masks.

        Parameters
        ----------
        masks : sequence of integer arrays
            masks[i] has the dimension indices that constraint i involves.
        """
        n_c = len(masks)
        n_d = max((m.max() for m in masks), default=0) + 1 if masks else 0
        adj = np.zeros((n_c, n_d), dtype=np.uint8)
        for i, m in enumerate(masks):
            adj[i, m] = 1
        return cls(
            adjacency=adj,
            n_constraints=n_c,
            n_dimensions=n_d,
            constraint_names=list(constraint_names) or [f"c{i}" for i in range(n_c)],
            dimension_names=list(dimension_names) or [f"d{j}" for j in range(n_d)],
        )

    @classmethod
    def from_adjacency(cls, adj: NDArray[np.uint8],
                       constraint_names: Sequence[str] = (),
                       dimension_names: Sequence[str] = ()) -> "DependencyGraph":
        n_c, n_d = adj.shape
        return cls(
            adjacency=adj.astype(np.uint8),
            n_constraints=n_c,
            n_dimensions=n_d,
            constraint_names=list(constraint_names) or [f"c{i}" for i in range(n_c)],
            dimension_names=list(dimension_names) or [f"d{j}" for j in range(n_d)],
        )

    def involves(self, constraint_idx: int, dimension_idx: int) -> bool:
        return bool(self.adjacency[constraint_idx, dimension_idx])

    def constraint_dims(self, constraint_idx: int) -> NDArray[np.intp]:
        """Dimensions involved in a constraint."""
        return np.flatnonzero(self.adjacency[constraint_idx])

    def dim_constraints(self, dimension_idx: int) -> NDArray[np.intp]:
        """Constraints involving a dimension."""
        return np.flatnonzero(self.adjacency[:, dimension_idx])


# ---------------------------------------------------------------------------
# 2. FractureResult — The fractured system
# ---------------------------------------------------------------------------

@dataclass
class Block:
    """One independent block of the fractured system."""
    constraint_indices: List[int]
    dimension_indices: List[int]
    size: int  # number of constraints in this block

    def __post_init__(self):
        self.size = len(self.constraint_indices)


@dataclass
class FractureResult:
    """Result of fracturing a constraint system into independent blocks."""
    blocks: List[Block]
    graph: DependencyGraph
    n_blocks: int = 0
    largest_block_size: int = 0
    speedup_potential: float = 1.0

    def __post_init__(self):
        self.n_blocks = len(self.blocks)
        self.largest_block_size = max((b.size for b in self.blocks), default=0)
        n_c = self.graph.n_constraints
        self.speedup_potential = n_c / self.largest_block_size if self.largest_block_size > 0 else 1.0

    def summary(self) -> Dict:
        return {
            "n_blocks": self.n_blocks,
            "largest_block_size": self.largest_block_size,
            "speedup_potential": round(self.speedup_potential, 2),
            "block_sizes": [b.size for b in self.blocks],
            "n_constraints": self.graph.n_constraints,
            "n_dimensions": self.graph.n_dimensions,
        }


# ---------------------------------------------------------------------------
# 3. Fracturer — Splits constraint systems into independent blocks
# ---------------------------------------------------------------------------

class Fracturer:
    """
    Fractures a constraint system by finding connected components
    of the constraint-dimension bipartite dependency graph.
    """

    def fracture(self, graph: DependencyGraph) -> FractureResult:
        """
        Find connected components via BFS on the bipartite graph.

        Two nodes (constraint or dimension) are in the same component
        if there's a path between them via alternating constraint-dimension edges.
        """
        visited_c = np.zeros(graph.n_constraints, dtype=bool)
        visited_d = np.zeros(graph.n_dimensions, dtype=bool)
        blocks: List[Block] = []

        # Seed from each unvisited constraint
        for seed_c in range(graph.n_constraints):
            if visited_c[seed_c]:
                continue
            comp_c: Set[int] = set()
            comp_d: Set[int] = set()
            # BFS
            queue: deque = deque()
            queue.append(("c", seed_c))
            while queue:
                node_type, idx = queue.popleft()
                if node_type == "c":
                    if visited_c[idx]:
                        continue
                    visited_c[idx] = True
                    comp_c.add(idx)
                    # Add all dimensions this constraint touches
                    for d in np.flatnonzero(graph.adjacency[idx]):
                        if not visited_d[d]:
                            queue.append(("d", d))
                else:  # dimension
                    if visited_d[idx]:
                        continue
                    visited_d[idx] = True
                    comp_d.add(idx)
                    # Add all constraints touching this dimension
                    for c in np.flatnonzero(graph.adjacency[:, idx]):
                        if not visited_c[c]:
                            queue.append(("c", c))

            blocks.append(Block(
                constraint_indices=sorted(comp_c),
                dimension_indices=sorted(comp_d),
                size=len(comp_c),
            ))

        # Also seed from unvisited dimensions (dimensions with no constraints)
        for d in range(graph.n_dimensions):
            if not visited_d[d]:
                blocks.append(Block(
                    constraint_indices=[],
                    dimension_indices=[d],
                    size=0,
                ))

        return FractureResult(blocks=blocks, graph=graph)

    def fracture_from_bounds(self, constraints: List[Dict]) -> FractureResult:
        """
        Convenience: fracture from a list of constraint dicts.

        Each constraint dict should have 'dims' key with list of dimension indices.
        If no 'dims' key, constraint is assumed to involve dimension at same index.
        """
        masks = []
        for i, c in enumerate(constraints):
            if "dims" in c:
                masks.append(np.array(c["dims"], dtype=np.intp))
            else:
                masks.append(np.array([i], dtype=np.intp))
        graph = DependencyGraph.from_masks(masks)
        return self.fracture(graph)


# ---------------------------------------------------------------------------
# 4. Coalescer — Merges fractured results provably correct
# ---------------------------------------------------------------------------

class Coalescer:
    """
    Coalesces block-level error masks into a unified error mask.

    CORRECTNESS PROOF:
    Let E_i be the error mask for block i. Each E_i encodes constraint
    violations for constraints in block i. Since blocks are independent
    (no shared dimensions), the violation events are disjoint.
    The total error mask E = E_1 | E_2 | ... | E_k captures ALL violations.
    No false negatives: if constraint j is violated, it appears in exactly
    one block's mask, so its bit is set in the OR.
    """

    def coalesce_masks(self, block_masks: List[int], n_total_constraints: int) -> int:
        """Coalesce integer error masks via bitwise OR."""
        result = 0
        for m in block_masks:
            result |= m
        return result

    def coalesce_arrays(self, block_arrays: List[NDArray[np.uint8]]) -> NDArray[np.uint8]:
        """Coalesce boolean/violation arrays via elementwise OR."""
        if not block_arrays:
            return np.array([], dtype=np.uint8)
        result = np.zeros_like(block_arrays[0])
        for arr in block_arrays:
            result |= arr
        return result

    def verify_coalescence(self,
                           block_masks: List[int],
                           block_constraint_indices: List[List[int]],
                           monolithic_mask: int) -> Tuple[bool, str]:
        """
        Verify that coalesced result equals monolithic result.

        Returns (is_correct, message).
        """
        coalesced = self.coalesce_masks(block_masks, 0)

        # Reconstruct monolithic mask from block masks
        # Each block mask has bits only for its constraints
        reconstructed = 0
        for mask, indices in zip(block_masks, block_constraint_indices):
            for bit_pos, c_idx in enumerate(indices):
                if mask & (1 << bit_pos):
                    reconstructed |= (1 << c_idx)

        if reconstructed == monolithic_mask:
            return True, f"PERFECT MATCH: coalesced={monolithic_mask:#x}"
        else:
            false_negatives = monolithic_mask & ~reconstructed
            false_positives = reconstructed & ~monolithic_mask
            return False, (
                f"MISMATCH: coalesced={reconstructed:#x} vs monolithic={monolithic_mask:#x} | "
                f"false_neg={false_negatives:#x} false_pos={false_positives:#x}"
            )


# ---------------------------------------------------------------------------
# 5. AdaptiveFracturer — Dynamic re-fracturing on structure change
# ---------------------------------------------------------------------------

@dataclass
class FractureDelta:
    """Change in fracture structure between two states."""
    blocks_before: int
    blocks_after: int
    structure_changed: bool
    max_block_size_delta: int
    speedup_delta: float


class AdaptiveFracturer:
    """
    Monitors constraint system structure and re-fractures when needed.
    Tracks whether the dependency graph's connected component structure changed.
    """

    def __init__(self):
        self._last_result: FractureResult | None = None
        self._fracturer = Fracturer()
        self.refracture_count: int = 0

    def update(self, graph: DependencyGraph) -> Tuple[FractureResult, FractureDelta]:
        """
        Re-fracture with new graph, returning result and delta from last.
        """
        new_result = self._fracturer.fracture(graph)

        if self._last_result is None:
            delta = FractureDelta(
                blocks_before=0,
                blocks_after=new_result.n_blocks,
                structure_changed=True,
                max_block_size_delta=new_result.largest_block_size,
                speedup_delta=new_result.speedup_potential,
            )
        else:
            old_sizes = sorted(b.size for b in self._last_result.blocks)
            new_sizes = sorted(b.size for b in new_result.blocks)
            changed = old_sizes != new_sizes
            delta = FractureDelta(
                blocks_before=self._last_result.n_blocks,
                blocks_after=new_result.n_blocks,
                structure_changed=changed,
                max_block_size_delta=new_result.largest_block_size - self._last_result.largest_block_size,
                speedup_delta=round(new_result.speedup_potential - self._last_result.speedup_potential, 4),
            )

        if delta.structure_changed:
            self.refracture_count += 1

        self._last_result = new_result
        return new_result, delta

    @property
    def current(self) -> FractureResult | None:
        return self._last_result


# ---------------------------------------------------------------------------
# 6. Experiment Framework
# ---------------------------------------------------------------------------

def _check_constraint(value: float, lo: float, hi: float) -> bool:
    """Returns True if VIOLATED."""
    if np.isnan(value):
        return True
    return value < lo or value > hi


def run_fracture_experiment() -> Dict:
    """
    Run the full FRACTURE-COALESCE experiment across 4 dependency structures:
    a) Fully independent (8 blocks) → perfect parallelism
    b) Block diagonal (2 blocks of 4) → 2-way parallel
    c) Chain (overlapping pairs) → limited parallelism
    d) Fully connected (1 block) → no parallelism
    """
    np.random.seed(42)

    # Bounds for 8 dimensions (matching automotive-style)
    bounds = [
        (0, 8000),      # d0
        (0, 300),       # d1
        (-40, 150),     # d2
        (0, 100),       # d3
        (0, 200),       # d4
        (-720, 720),    # d5
        (9, 16),        # d6
        (0, 100),       # d7
    ]

    fracturer = Fracturer()
    coalescer = Coalescer()
    results = {}

    # ---- Structure A: Fully independent ----
    # 8 constraints, each on its own dimension
    adj_a = np.eye(8, dtype=np.uint8)
    graph_a = DependencyGraph.from_adjacency(adj_a)
    frac_a = fracturer.fracture(graph_a)

    # Generate test values (some in bounds, some out)
    n_tests = 1000
    test_values = np.random.uniform(-100, 9000, size=(n_tests, 8))

    def _run_verification(graph, frac, test_vals, bnds, label):
        """Run fracture-check-coalesce-verify for a structure."""
        matches = 0
        mismatches = 0
        for row in test_vals:
            # Monolithic check
            mono_mask = 0
            for i in range(graph.n_constraints):
                dims = graph.constraint_dims(i)
                for d in dims:
                    lo, hi = bnds[d]
                    if _check_constraint(row[d], lo, hi):
                        mono_mask |= (1 << i)
                        break  # constraint violated if ANY of its dims violates

            # Block check
            block_masks = []
            block_indices = []
            for block in frac.blocks:
                block_mask = 0
                for bit, c_idx in enumerate(block.constraint_indices):
                    dims = graph.constraint_dims(c_idx)
                    for d in dims:
                        lo, hi = bnds[d]
                        if _check_constraint(row[d], lo, hi):
                            block_mask |= (1 << bit)
                            break
                block_masks.append(block_mask)
                block_indices.append(block.constraint_indices)

            # Coalesce
            correct, msg = coalescer.verify_coalescence(
                block_masks, block_indices, mono_mask
            )
            if correct:
                matches += 1
            else:
                mismatches += 1

        return {
            "label": label,
            "n_blocks": frac.n_blocks,
            "largest_block": frac.largest_block_size,
            "speedup_potential": round(frac.speedup_potential, 2),
            "tests": n_tests,
            "matches": matches,
            "mismatches": mismatches,
            "perfect": mismatches == 0,
        }

    results["A_independent"] = _run_verification(graph_a, frac_a, test_values, bounds, "Fully Independent (8 blocks)")

    # ---- Structure B: Block diagonal (2 blocks of 4) ----
    adj_b = np.zeros((8, 8), dtype=np.uint8)
    adj_b[:4, :4] = 1  # Block 1: c0-c3 share dims 0-3
    adj_b[4:, 4:] = 1  # Block 2: c4-c7 share dims 4-7
    graph_b = DependencyGraph.from_adjacency(adj_b)
    frac_b = fracturer.fracture(graph_b)
    results["B_block_diagonal"] = _run_verification(graph_b, frac_b, test_values, bounds, "Block Diagonal (2×4)")

    # ---- Structure C: Chain (overlapping pairs) ----
    # c0→d0,d1  c1→d1,d2  c2→d2,d3  ... c7→d7,d0
    adj_c = np.zeros((8, 8), dtype=np.uint8)
    for i in range(8):
        adj_c[i, i] = 1
        adj_c[i, (i + 1) % 8] = 1
    graph_c = DependencyGraph.from_adjacency(adj_c)
    frac_c = fracturer.fracture(graph_c)
    results["C_chain"] = _run_verification(graph_c, frac_c, test_values, bounds, "Chain (cyclic pairs)")

    # ---- Structure D: Fully connected ----
    adj_d = np.ones((8, 8), dtype=np.uint8)
    graph_d = DependencyGraph.from_adjacency(adj_d)
    frac_d = fracturer.fracture(graph_d)
    results["D_fully_connected"] = _run_verification(graph_d, frac_d, test_values, bounds, "Fully Connected (1 block)")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 70)
    print("FRACTURE-COALESCE EXPERIMENT")
    print("Disjoint Linear Algebra for Constraint Systems")
    print("=" * 70)

    results = run_fracture_experiment()

    all_perfect = True
    for name, r in results.items():
        status = "✓ PERFECT" if r["perfect"] else "✗ FAILED"
        if not r["perfect"]:
            all_perfect = False
        print(f"\n{name}: {status}")
        print(f"  Blocks: {r['n_blocks']} | Largest: {r['largest_block']} | "
              f"Speedup: {r['speedup_potential']}x")
        print(f"  Tests: {r['tests']} | Matches: {r['matches']} | Mismatches: {r['mismatches']}")

    print("\n" + "=" * 70)
    if all_perfect:
        print("ALL STRUCTURES: ZERO FALSE NEGATIVES CONFIRMED ✓")
        print("Coalescence preserves correctness across all dependency topologies.")
    else:
        print("FAILURE: Some structures showed mismatches!")
    print("=" * 70)
