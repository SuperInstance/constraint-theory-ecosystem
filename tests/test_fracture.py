"""
tests/test_fracture.py — FRACTURE-COALESCE test suite

Tests for:
- DependencyGraph construction and queries
- Fracturer connected component detection
- Coalescer bitwise OR correctness
- AdaptiveFracturer delta tracking
- Full experiment verification
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

import numpy as np
import pytest

from flux_fracture import (
    DependencyGraph,
    FractureResult,
    Block,
    Fracturer,
    Coalescer,
    AdaptiveFracturer,
    FractureDelta,
    run_fracture_experiment,
)


# ===================================================================
# DependencyGraph tests
# ===================================================================

class TestDependencyGraph:

    def test_from_adjacency_identity(self):
        adj = np.eye(4, dtype=np.uint8)
        g = DependencyGraph.from_adjacency(adj)
        assert g.n_constraints == 4
        assert g.n_dimensions == 4
        assert g.involves(0, 0)
        assert not g.involves(0, 1)

    def test_from_masks(self):
        masks = [
            np.array([0, 1]),
            np.array([2, 3]),
            np.array([4]),
        ]
        g = DependencyGraph.from_masks(masks)
        assert g.n_constraints == 3
        assert g.n_dimensions == 5
        assert g.involves(0, 0)
        assert g.involves(0, 1)
        assert g.involves(1, 2)
        assert not g.involves(0, 2)

    def test_constraint_dims(self):
        adj = np.array([[1, 1, 0], [0, 1, 1]], dtype=np.uint8)
        g = DependencyGraph.from_adjacency(adj)
        assert list(g.constraint_dims(0)) == [0, 1]
        assert list(g.constraint_dims(1)) == [1, 2]

    def test_dim_constraints(self):
        adj = np.array([[1, 1, 0], [0, 1, 1]], dtype=np.uint8)
        g = DependencyGraph.from_adjacency(adj)
        assert list(g.dim_constraints(1)) == [0, 1]
        assert list(g.dim_constraints(0)) == [0]

    def test_empty_graph(self):
        adj = np.zeros((0, 0), dtype=np.uint8)
        g = DependencyGraph.from_adjacency(adj)
        assert g.n_constraints == 0
        assert g.n_dimensions == 0


# ===================================================================
# Fracturer tests
# ===================================================================

class TestFracturer:

    def setup_method(self):
        self.fracturer = Fracturer()

    def test_fully_independent(self):
        """8 constraints, each on its own dimension → 8 blocks."""
        adj = np.eye(8, dtype=np.uint8)
        g = DependencyGraph.from_adjacency(adj)
        result = self.fracturer.fracture(g)
        assert result.n_blocks == 8
        assert result.largest_block_size == 1
        assert result.speedup_potential == pytest.approx(8.0)

    def test_block_diagonal(self):
        """2 blocks of 4 constraints sharing dims within each block."""
        adj = np.zeros((8, 8), dtype=np.uint8)
        # Block 1: constraints 0-3 all share dims 0-3
        adj[:4, :4] = 1
        # Block 2: constraints 4-7 all share dims 4-7
        adj[4:, 4:] = 1
        g = DependencyGraph.from_adjacency(adj)
        result = self.fracturer.fracture(g)
        assert result.n_blocks == 2
        assert result.largest_block_size == 4
        assert result.speedup_potential == pytest.approx(2.0)

    def test_chain_cyclic(self):
        """Chain: c0→d0,d1, c1→d1,d2, ... c7→d7,d0 → 1 block (cycle)."""
        adj = np.zeros((8, 8), dtype=np.uint8)
        for i in range(8):
            adj[i, i] = 1
            adj[i, (i + 1) % 8] = 1
        g = DependencyGraph.from_adjacency(adj)
        result = self.fracturer.fracture(g)
        assert result.n_blocks == 1
        assert result.largest_block_size == 8
        assert result.speedup_potential == pytest.approx(1.0)

    def test_fully_connected(self):
        """All constraints touch all dimensions → 1 block."""
        adj = np.ones((8, 8), dtype=np.uint8)
        g = DependencyGraph.from_adjacency(adj)
        result = self.fracturer.fracture(g)
        assert result.n_blocks == 1
        assert result.largest_block_size == 8

    def test_chain_open(self):
        """Open chain: c0→d0,d1, c1→d1,d2, ... c6→d6,d7 → 1 block."""
        adj = np.zeros((7, 8), dtype=np.uint8)
        for i in range(7):
            adj[i, i] = 1
            adj[i, i + 1] = 1
        g = DependencyGraph.from_adjacency(adj)
        result = self.fracturer.fracture(g)
        assert result.n_blocks == 1
        assert result.largest_block_size == 7

    def test_two_independent_chains(self):
        """Two independent 4-chains → 2 blocks."""
        adj = np.zeros((8, 8), dtype=np.uint8)
        # Chain 1: c0→d0,d1, c1→d1,d2, c2→d2,d3, c3→d3,d0
        for i in range(4):
            adj[i, i] = 1
            adj[i, (i + 1) % 4] = 1
        # Chain 2: c4→d4,d5, c5→d5,d6, c6→d6,d7, c7→d7,d4
        for i in range(4, 8):
            adj[i, i] = 1
            adj[i, 4 + (i - 4 + 1) % 4] = 1
        g = DependencyGraph.from_adjacency(adj)
        result = self.fracturer.fracture(g)
        assert result.n_blocks == 2
        assert result.largest_block_size == 4

    def test_empty_system(self):
        g = DependencyGraph.from_adjacency(np.zeros((0, 0), dtype=np.uint8))
        result = self.fracturer.fracture(g)
        assert result.n_blocks == 0

    def test_single_constraint_single_dim(self):
        g = DependencyGraph.from_adjacency(np.array([[1]], dtype=np.uint8))
        result = self.fracturer.fracture(g)
        assert result.n_blocks == 1
        assert result.largest_block_size == 1

    def test_fracture_from_bounds(self):
        constraints = [
            {"lo": 0, "hi": 100, "dims": [0]},
            {"lo": -10, "hi": 10, "dims": [1]},
        ]
        result = self.fracturer.fracture_from_bounds(constraints)
        assert result.n_blocks == 2


# ===================================================================
# Coalescer tests
# ===================================================================

class TestCoalescer:

    def setup_method(self):
        self.coalescer = Coalescer()

    def test_coalesce_masks_basic(self):
        # Block 0: constraint 0 violated (bit 0)
        # Block 1: constraint 2 violated (bit 2)
        # Block 2: no violations
        masks = [0b001, 0b100, 0b000]
        result = self.coalescer.coalesce_masks(masks, 3)
        assert result == 0b101

    def test_coalesce_masks_empty(self):
        result = self.coalescer.coalesce_masks([], 0)
        assert result == 0

    def test_coalesce_masks_all_zero(self):
        result = self.coalescer.coalesce_masks([0, 0, 0, 0], 4)
        assert result == 0

    def test_coalesce_arrays(self):
        arrs = [
            np.array([1, 0, 0], dtype=np.uint8),
            np.array([0, 1, 0], dtype=np.uint8),
            np.array([0, 0, 1], dtype=np.uint8),
        ]
        result = self.coalescer.coalesce_arrays(arrs)
        np.testing.assert_array_equal(result, [1, 1, 1])

    def test_verify_correct(self):
        # Monolithic: constraints 0 and 5 violated → mask = 0b100001 = 33
        mono = 0b100001
        # Block 0 handles constraints [0,1,2,3]: bit 0 set → 0b0001
        # Block 1 handles constraints [4,5,6,7]: bit 1 set (constraint 5 = local bit 1) → 0b0010
        block_masks = [0b0001, 0b0010]
        block_indices = [[0, 1, 2, 3], [4, 5, 6, 7]]
        ok, msg = self.coalescer.verify_coalescence(block_masks, block_indices, mono)
        assert ok
        assert "PERFECT MATCH" in msg

    def test_verify_incorrect(self):
        mono = 0b11  # both constraints violated
        block_masks = [0b01]  # only block 0 reports
        block_indices = [[0, 1]]
        ok, msg = self.coalescer.verify_coalescence(block_masks, block_indices, mono)
        assert not ok
        assert "MISMATCH" in msg


# ===================================================================
# AdaptiveFracturer tests
# ===================================================================

class TestAdaptiveFracturer:

    def test_first_update(self):
        af = AdaptiveFracturer()
        adj = np.eye(4, dtype=np.uint8)
        g = DependencyGraph.from_adjacency(adj)
        result, delta = af.update(g)
        assert delta.structure_changed is True
        assert delta.blocks_before == 0
        assert delta.blocks_after == 4
        assert af.refracture_count == 1

    def test_no_change(self):
        af = AdaptiveFracturer()
        adj = np.eye(4, dtype=np.uint8)
        g = DependencyGraph.from_adjacency(adj)
        af.update(g)
        result, delta = af.update(g)
        assert delta.structure_changed is False
        assert af.refracture_count == 1

    def test_structure_change(self):
        af = AdaptiveFracturer()
        # Start with 4 independent blocks
        adj1 = np.eye(4, dtype=np.uint8)
        g1 = DependencyGraph.from_adjacency(adj1)
        af.update(g1)
        assert af.refracture_count == 1

        # Now connect them all → 1 block
        adj2 = np.ones((4, 4), dtype=np.uint8)
        g2 = DependencyGraph.from_adjacency(adj2)
        result, delta = af.update(g2)
        assert delta.structure_changed is True
        assert delta.blocks_after == 1
        assert af.refracture_count == 2

    def test_current_property(self):
        af = AdaptiveFracturer()
        assert af.current is None
        adj = np.eye(2, dtype=np.uint8)
        g = DependencyGraph.from_adjacency(adj)
        af.update(g)
        assert af.current is not None
        assert af.current.n_blocks == 2


# ===================================================================
# Full experiment test
# ===================================================================

class TestExperiment:

    def test_experiment_all_perfect(self):
        results = run_fracture_experiment()
        assert len(results) == 4
        for name, r in results.items():
            assert r["perfect"], f"{name} had {r['mismatches']} mismatches"
            assert r["matches"] == r["tests"]

    def test_independent_8_blocks(self):
        results = run_fracture_experiment()
        assert results["A_independent"]["n_blocks"] == 8
        assert results["A_independent"]["speedup_potential"] == 8.0

    def test_block_diagonal_2_blocks(self):
        results = run_fracture_experiment()
        assert results["B_block_diagonal"]["n_blocks"] == 2
        assert results["B_block_diagonal"]["speedup_potential"] == 2.0

    def test_chain_1_block(self):
        results = run_fracture_experiment()
        assert results["C_chain"]["n_blocks"] == 1
        assert results["C_chain"]["speedup_potential"] == 1.0

    def test_fully_connected_1_block(self):
        results = run_fracture_experiment()
        assert results["D_fully_connected"]["n_blocks"] == 1
        assert results["D_fully_connected"]["speedup_potential"] == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
