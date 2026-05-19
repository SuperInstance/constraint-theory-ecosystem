"""
Tests for flux_ecology.py — Ecological Succession, Stigmergy, Physarum Optimizer
"""

import sys
import os
import pytest
import random
import time

sys.path.insert(0, os.path.dirname(__file__) + "/../src/python")

from flux_ecology import (
    SuccessionStage,
    ConstraintOrganism,
    ConstraintSuccession,
    SuccessionEvent,
    PheromoneMarker,
    StigmergicDataItem,
    StigmergicField,
    PhysarumTube,
    PhysarumOptimizer,
    OrderingResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def always_pass(v):
    return (True, 0.0)

def always_fail(v):
    return (False, 1.0)

def fail_if_negative(v):
    return (v >= 0, 0.8 if v < 0 else 0.0)

def fail_if_over_100(v):
    return (v <= 100, 0.5 if v > 100 else 0.0)


# ===========================================================================
# ConstraintSuccession Tests
# ===========================================================================

class TestConstraintOrganism:
    def test_check_pass(self):
        org = ConstraintOrganism("test", always_pass, SuccessionStage.PIONEER)
        passed, sev = org.check(42)
        assert passed is True
        assert sev == 0.0
        assert org.checks_run == 1
        assert org.violations_caught == 0

    def test_check_fail(self):
        org = ConstraintOrganism("test", always_fail, SuccessionStage.PIONEER)
        passed, sev = org.check(42)
        assert passed is False
        assert sev == 1.0
        assert org.violations_caught == 1

    def test_fitness_updates(self):
        org = ConstraintOrganism("test", always_fail, SuccessionStage.PIONEER)
        for _ in range(5):
            org.check(1)
        assert org.fitness == 1.0

    def test_established_after_enough_checks(self):
        org = ConstraintOrganism("test", always_fail, SuccessionStage.PIONEER)
        for _ in range(10):
            org.check(1)
        assert org.established is True

    def test_not_established_if_no_violations(self):
        org = ConstraintOrganism("test", always_pass, SuccessionStage.PIONEER)
        for _ in range(20):
            org.check(1)
        assert org.established is False


class TestConstraintSuccession:
    def test_initial_state_is_disturbed(self):
        s = ConstraintSuccession()
        assert s.stage == SuccessionStage.DISTURBED

    def test_disturb_resets_state(self):
        s = ConstraintSuccession()
        pioneer = ConstraintOrganism("range", fail_if_over_100, SuccessionStage.PIONEER)
        s.add_organism(pioneer)
        s.stage = SuccessionStage.PIONEER
        s.disturb("test")
        assert s.stage == SuccessionStage.DISTURBED
        assert pioneer.checks_run == 0
        assert pioneer.established is False

    def test_pioneer_colonization(self):
        """After disturbance, pioneers colonize and advance stage."""
        s = ConstraintSuccession(stability_window=3)
        pioneer = ConstraintOrganism("range", fail_if_over_100, SuccessionStage.PIONEER)
        s.add_organism(pioneer)
        s.disturb("test")

        # First check triggers disturbed->pioneer
        s.check(50)
        assert s.stage == SuccessionStage.PIONEER

    def test_succession_progression(self):
        """Full progression: disturbed -> pioneer -> intermediate -> climax."""
        s = ConstraintSuccession(stability_window=3)
        s.add_organism(ConstraintOrganism("p1", always_fail, SuccessionStage.PIONEER))
        s.add_organism(ConstraintOrganism("i1", always_fail, SuccessionStage.INTERMEDIATE))
        s.add_organism(ConstraintOrganism("c1", always_fail, SuccessionStage.CLIMAX))

        s.disturb("test")

        # Should go to pioneer
        s.check(1)
        assert s.stage == SuccessionStage.PIONEER

        # Run enough checks to establish pioneer
        for _ in range(15):
            s.check(1)

        # Should have advanced to intermediate or further
        assert s.stage in (SuccessionStage.INTERMEDIATE, SuccessionStage.CLIMAX)

    def test_active_organisms_includes_current_and_earlier(self):
        s = ConstraintSuccession()
        p = ConstraintOrganism("p", always_pass, SuccessionStage.PIONEER)
        i = ConstraintOrganism("i", always_pass, SuccessionStage.INTERMEDIATE)
        c = ConstraintOrganism("c", always_pass, SuccessionStage.CLIMAX)
        s.add_organism(p)
        s.add_organism(i)
        s.add_organism(c)

        s.stage = SuccessionStage.INTERMEDIATE
        active = s.active_organisms
        names = {o.name for o in active}
        assert "p" in names
        assert "i" in names
        assert "c" not in names

    def test_statistics(self):
        s = ConstraintSuccession()
        s.add_organism(ConstraintOrganism("p", always_pass, SuccessionStage.PIONEER))
        stats = s.statistics()
        assert stats["stage"] == "disturbed"
        assert stats["community_size"] == 1
        assert stats["pioneers"] == 1

    def test_events_recorded(self):
        s = ConstraintSuccession()
        s.disturb("test event")
        assert len(s.events) == 1
        assert s.events[0].trigger == "test event"


# ===========================================================================
# StigmergicField Tests
# ===========================================================================

class TestPheromoneMarker:
    def test_uid_generated(self):
        m = PheromoneMarker(checker_name="test", intensity=0.5, timestamp=1.0)
        assert len(m.uid) == 10

    def test_custom_uid(self):
        m = PheromoneMarker(checker_name="test", intensity=0.5, timestamp=1.0, uid="custom")
        assert m.uid == "custom"


class TestStigmergicDataItem:
    def test_total_intensity_empty(self):
        item = StigmergicDataItem(key="x", value=42)
        assert item.total_intensity == 0.0

    def test_total_intensity(self):
        item = StigmergicDataItem(key="x", value=42, markers=[
            PheromoneMarker("a", 0.5, 1.0),
            PheromoneMarker("b", 0.3, 1.0),
        ])
        assert abs(item.total_intensity - 0.8) < 1e-10

    def test_strongest_marker(self):
        item = StigmergicDataItem(key="x", value=42, markers=[
            PheromoneMarker("a", 0.5, 1.0),
            PheromoneMarker("b", 0.8, 1.0),
        ])
        strongest = item.strongest_marker()
        assert strongest.checker_name == "b"

    def test_strongest_marker_empty(self):
        item = StigmergicDataItem(key="x", value=42)
        assert item.strongest_marker() is None


class TestStigmergicField:
    def test_add_and_get_item(self):
        f = StigmergicField()
        f.add_item("x", 42)
        item = f.get_item("x")
        assert item is not None
        assert item.value == 42

    def test_get_nonexistent(self):
        f = StigmergicField()
        assert f.get_item("missing") is None

    def test_place_marker(self):
        f = StigmergicField()
        f.add_item("x", 42)
        f.place_marker("x", "checker1", severity=0.8)
        item = f.get_item("x")
        assert len(item.markers) == 1
        assert item.markers[0].intensity == 0.8

    def test_reinforce_existing_marker(self):
        f = StigmergicField(reinforcement_boost=0.2)
        f.add_item("x", 42)
        f.place_marker("x", "checker1", severity=0.5)
        f.place_marker("x", "checker1", severity=0.7)
        item = f.get_item("x")
        assert len(item.markers) == 1  # Still one marker
        assert item.markers[0].intensity == pytest.approx(0.7, abs=0.01)

    def test_evaporation(self):
        f = StigmergicField(evaporation_rate=0.5, min_intensity=0.01)
        f.add_item("x", 42)
        f.place_marker("x", "checker1", severity=1.0, timestamp=1.0)
        f.evaporate(ticks=1)
        item = f.get_item("x")
        assert item.markers[0].intensity == pytest.approx(0.5, abs=0.01)

    def test_evaporation_removes_weak_markers(self):
        f = StigmergicField(evaporation_rate=0.5, min_intensity=0.3)
        f.add_item("x", 42)
        f.place_marker("x", "checker1", severity=0.4, timestamp=1.0)
        f.evaporate(ticks=1)  # 0.4 * 0.5 = 0.2 < 0.3
        item = f.get_item("x")
        assert len(item.markers) == 0

    def test_select_for_checking(self):
        f = StigmergicField()
        f.add_item("a", 1)
        f.add_item("b", 2)
        f.add_item("c", 3)
        f.place_marker("a", "chk", severity=1.0)
        f.place_marker("b", "chk", severity=0.01)

        selected = f.select_for_checking(count=2)
        assert len(selected) == 2

    def test_select_empty_field(self):
        f = StigmergicField()
        assert f.select_for_checking() == []

    def test_field_intensity(self):
        f = StigmergicField()
        f.add_item("a", 1)
        f.add_item("b", 2)
        f.place_marker("a", "chk", severity=0.5)
        intensities = f.field_intensity()
        assert intensities["a"] == pytest.approx(0.5)
        assert intensities["b"] == pytest.approx(0.0)

    def test_statistics(self):
        f = StigmergicField()
        f.add_item("a", 1)
        f.place_marker("a", "chk", severity=0.5)
        stats = f.statistics()
        assert stats["items"] == 1
        assert stats["total_markers"] == 1

    def test_marker_on_nonexistent_item(self):
        f = StigmergicField()
        f.place_marker("missing", "chk", severity=0.5)  # Should not raise


# ===========================================================================
# PhysarumOptimizer Tests
# ===========================================================================

class TestPhysarumOptimizer:
    def test_basic_optimization(self):
        """Optimizer should find a reasonable ordering."""
        constraints = ["a", "b", "c"]
        call_count = {"n": 0}

        def evaluate(ordering):
            call_count["n"] += 1
            # Prefer alphabetical ordering
            score = 0.0
            for i, c in enumerate(sorted(ordering)):
                if i < len(ordering) and ordering[i] == c:
                    score += 1.0
            return score

        opt = PhysarumOptimizer(constraints, evaluate, seed=42)
        best = opt.run(iterations=50)
        assert best is not None
        assert best.quality > 0
        assert call_count["n"] == 50

    def test_single_step(self):
        constraints = ["x", "y"]
        opt = PhysarumOptimizer(constraints, lambda o: 1.0, seed=42)
        result = opt.step()
        assert result is not None
        assert len(result.ordering) == 2
        assert set(result.ordering) == {"x", "y"}

    def test_best_updates(self):
        constraints = ["a", "b", "c"]
        qualities = [0.5, 0.8, 0.3, 0.9, 0.2]
        idx = [0]

        def evaluate(ordering):
            q = qualities[idx[0] % len(qualities)]
            idx[0] += 1
            return q

        opt = PhysarumOptimizer(constraints, evaluate, seed=42)
        opt.step()
        opt.step()
        opt.step()
        opt.step()
        opt.step()
        assert opt.best_result is not None
        assert opt.best_result.quality == pytest.approx(0.9)

    def test_tube_thickness_updates(self):
        constraints = ["a", "b"]
        opt = PhysarumOptimizer(
            constraints, lambda o: 1.0,
            learning_rate=0.5, decay_rate=0.0, seed=42
        )
        initial_thickness = opt.tubes["a->b"].thickness
        opt.step()
        # Tube in the ordering should thicken
        # (depending on the ordering, at least one tube should be thicker)
        any_thicker = any(t.thickness > initial_thickness for t in opt.tubes.values())
        assert any_thicker

    def test_statistics(self):
        constraints = ["a", "b", "c"]
        opt = PhysarumOptimizer(constraints, lambda o: 1.0, seed=42)
        opt.run(iterations=10)
        stats = opt.statistics()
        assert stats["iterations"] == 10
        assert stats["constraints"] == 3
        assert stats["tubes"] == 6  # 3*2 ordered pairs

    def test_tube_matrix(self):
        constraints = ["a", "b"]
        opt = PhysarumOptimizer(constraints, lambda o: 1.0, seed=42)
        matrix = opt.get_tube_matrix()
        assert "a" in matrix
        assert "b" in matrix
        assert "a" not in matrix["a"]  # No self-connections
        assert isinstance(matrix["a"]["b"], float)

    def test_convergence(self):
        """Running many iterations should stabilize the best ordering."""
        constraints = ["a", "b", "c", "d"]

        def evaluate(ordering):
            # Prefer reversed alphabetical
            return sum(1.0 / (i + 1) for i, c in enumerate(ordering)
                      if c == sorted(ordering, reverse=True)[i])

        opt = PhysarumOptimizer(constraints, evaluate, seed=42)
        opt.run(iterations=200)
        # Should have found a non-zero quality solution
        assert opt.best_result.quality > 0

    def test_exploration(self):
        """With high exploration probability, should produce varied orderings."""
        constraints = ["a", "b", "c"]
        orderings = set()

        def evaluate(o):
            orderings.add(tuple(o))
            return 1.0

        opt = PhysarumOptimizer(
            constraints, evaluate,
            exploration_prob=0.9, seed=42
        )
        opt.run(iterations=20)
        # Should have explored multiple orderings
        assert len(orderings) > 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
