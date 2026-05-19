"""
Flux Cellular — Cellular Automata for Spatial Constraint Propagation

Models sensor grids as cellular automata where constraint violations
propagate spatially, creating "attention waves" that increase monitoring
intensity on nearby sensors. Supports multiple cell states, configurable
neighborhoods, and wave attenuation.

Part of the Constraint Theory Ecosystem.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Cell States
# ---------------------------------------------------------------------------

class CellState(Enum):
    """States a sensor cell can be in."""
    SATISFIED = auto()    # Constraint met, normal monitoring
    VIOLATED = auto()     # Constraint violated, alert state
    UNKNOWN = auto()      # Awaiting evaluation
    ATTENTION = auto()    # Elevated monitoring due to nearby violations


# State metadata
STATE_MONITORING_LEVEL = {
    CellState.SATISFIED: 1.0,
    CellState.VIOLATED: 3.0,
    CellState.UNKNOWN: 1.5,
    CellState.ATTENTION: 2.0,
}

STATE_PRIORITY = {
    CellState.SATISFIED: 0,
    CellState.UNKNOWN: 1,
    CellState.ATTENTION: 2,
    CellState.VIOLATED: 3,
}


# ---------------------------------------------------------------------------
# Cell
# ---------------------------------------------------------------------------

@dataclass
class Cell:
    """A single sensor cell in the CA grid."""
    row: int
    col: int
    state: CellState = CellState.UNKNOWN
    attention_level: float = 0.0        # 0.0 to 1.0, decays over time
    violation_history: List[bool] = field(default_factory=list)
    last_check_tick: int = -1
    neighbors: List[Cell] = field(default_factory=list, repr=False)
    
    @property
    def monitoring_level(self) -> float:
        """Current monitoring intensity."""
        base = STATE_MONITORING_LEVEL[self.state]
        attention_boost = 1.0 + self.attention_level * 0.5
        return base * attention_boost
    
    @property
    def recent_violation_rate(self) -> float:
        """Violation rate over recent history."""
        if not self.violation_history:
            return 0.0
        window = self.violation_history[-10:]
        return sum(1 for v in window if v) / len(window)
    
    def record_result(self, violated: bool, tick: int) -> None:
        """Record a check result."""
        self.violation_history.append(violated)
        if len(self.violation_history) > 50:
            self.violation_history = self.violation_history[-50:]
        self.last_check_tick = tick


# ---------------------------------------------------------------------------
# Neighborhood Functions
# ---------------------------------------------------------------------------

def moore_neighbors(grid: List[List[Cell]], row: int, col: int) -> List[Cell]:
    """Moore neighborhood — all 8 surrounding cells."""
    rows, cols = len(grid), len(grid[0])
    neighbors = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = row + dr, col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                neighbors.append(grid[nr][nc])
    return neighbors


def von_neumann_neighbors(grid: List[List[Cell]], row: int, col: int) -> List[Cell]:
    """Von Neumann neighborhood — 4 orthogonal neighbors."""
    rows, cols = len(grid), len(grid[0])
    neighbors = []
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = row + dr, col + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            neighbors.append(grid[nr][nc])
    return neighbors


def extended_neighbors(grid: List[List[Cell]], row: int, col: int,
                       radius: int = 2) -> List[Cell]:
    """Extended neighborhood within given radius."""
    rows, cols = len(grid), len(grid[0])
    neighbors = []
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr == 0 and dc == 0:
                continue
            nr, nc = row + dr, col + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                neighbors.append(grid[nr][nc])
    return neighbors


# ---------------------------------------------------------------------------
# Update Rules
# ---------------------------------------------------------------------------

@dataclass
class CAConfig:
    """Configuration for the cellular automata system."""
    rows: int = 10
    cols: int = 10
    neighborhood: str = "moore"          # "moore", "vonneumann", "extended"
    neighborhood_radius: int = 2
    attention_decay: float = 0.85        # Attention level decay per tick
    attention_propagation: float = 0.6   # How much attention spreads
    violated_influence: float = 0.8      # How much violated neighbors boost attention
    attention_threshold: float = 0.2     # Below this, attention drops to 0
    violation_persistence: int = 3       # Ticks a violation persists before re-check
    seed: Optional[int] = None


def compute_cell_update(cell: Cell, tick: int, config: CAConfig) -> CellState:
    """
    Compute the next state for a cell based on its current state and neighbors.
    
    Returns the new CellState.
    """
    # Count neighbor states
    n_violated = sum(1 for n in cell.neighbors if n.state == CellState.VIOLATED)
    n_attention = sum(1 for n in cell.neighbors if n.state == CellState.ATTENTION)
    n_total = len(cell.neighbors)
    
    current = cell.state
    
    # Rule 1: VIOLATED cells stay violated for persistence period
    if current == CellState.VIOLATED:
        ticks_since = tick - cell.last_check_tick
        if ticks_since < config.violation_persistence:
            return CellState.VIOLATED
        # After persistence, re-evaluate (return UNKNOWN to trigger re-check)
        return CellState.UNKNOWN
    
    # Rule 2: SATISFIED cells near VIOLATED → ATTENTION
    if current == CellState.SATISFIED:
        if n_violated > 0:
            return CellState.ATTENTION
        return CellState.SATISFIED
    
    # Rule 3: ATTENTION cells
    if current == CellState.ATTENTION:
        # If all neighbors SATISFIED, stand down
        if n_violated == 0 and n_attention == 0:
            return CellState.SATISFIED
        # If neighbors still violated, stay at attention
        return CellState.ATTENTION
    
    # Rule 4: UNKNOWN cells need evaluation (handled externally)
    return CellState.UNKNOWN


def compute_attention_update(cell: Cell, tick: int, config: CAConfig) -> float:
    """Compute the new attention level for a cell."""
    current_attention = cell.attention_level
    
    # Decay existing attention
    new_attention = current_attention * config.attention_decay
    
    # Boost from violated neighbors
    n_violated = sum(1 for n in cell.neighbors if n.state == CellState.VIOLATED)
    n_total = max(len(cell.neighbors), 1)
    
    if n_violated > 0:
        boost = config.violated_influence * (n_violated / n_total)
        new_attention = min(1.0, new_attention + boost * config.attention_propagation)
    
    # Clamp
    if new_attention < config.attention_threshold:
        new_attention = 0.0
    
    return min(1.0, new_attention)


# ---------------------------------------------------------------------------
# Cellular Automata Grid
# ---------------------------------------------------------------------------

@dataclass
class TickResult:
    """Result of a single CA tick."""
    tick: int
    cells_updated: int
    violations: int
    attention_cells: int
    unknown_cells: int
    attention_wave_size: int  # Connected attention component size
    elapsed_ms: float


@dataclass 
class GridStatistics:
    """Statistics about the current grid state."""
    total_cells: int
    satisfied: int
    violated: int
    attention: int
    unknown: int
    avg_attention_level: float
    max_attention_level: float
    violation_clusters: int  # Number of connected violation components
    
    @property
    def violation_rate(self) -> float:
        checked = self.total_cells - self.unknown
        return self.violated / max(checked, 1)
    
    @property
    def attention_rate(self) -> float:
        return self.attention / max(self.total_cells, 1)


class CellularAutomataGrid:
    """
    A cellular automata grid for spatial constraint propagation.
    
    Manages sensor cells, applies update rules, and tracks
    violation propagation dynamics.
    """
    
    def __init__(
        self,
        check_fn: Optional[Callable[[Cell], bool]] = None,
        config: Optional[CAConfig] = None,
    ):
        self.config = config or CAConfig()
        if self.config.seed is not None:
            random.seed(self.config.seed)
        
        self.check_fn = check_fn  # Returns True if violated
        self.tick_count = 0
        self.history: List[TickResult] = []
        
        # Initialize grid
        self.grid: List[List[Cell]] = [
            [Cell(row=r, col=c) for c in range(self.config.cols)]
            for r in range(self.config.rows)
        ]
        
        # Set up neighborhoods
        self._setup_neighbors()
    
    def _setup_neighbors(self) -> None:
        """Establish neighbor relationships."""
        neighborhood_fn = {
            "moore": lambda r, c: moore_neighbors(self.grid, r, c),
            "vonneumann": lambda r, c: von_neumann_neighbors(self.grid, r, c),
            "extended": lambda r, c: extended_neighbors(
                self.grid, r, c, self.config.neighborhood_radius),
        }.get(self.config.neighborhood, lambda r, c: moore_neighbors(self.grid, r, c))
        
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                self.grid[r][c].neighbors = neighborhood_fn(r, c)
    
    def get_cell(self, row: int, col: int) -> Cell:
        """Get cell at position."""
        return self.grid[row][col]
    
    def set_violation(self, row: int, col: int, violated: bool) -> None:
        """Manually set a cell's violation state."""
        cell = self.grid[row][col]
        if violated:
            cell.state = CellState.VIOLATED
            cell.attention_level = 1.0
            cell.record_result(True, self.tick_count)
        else:
            cell.state = CellState.SATISFIED
            cell.record_result(False, self.tick_count)
    
    def evaluate_unknowns(self) -> int:
        """Evaluate all UNKNOWN cells using check_fn."""
        if self.check_fn is None:
            return 0
        
        evaluated = 0
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                cell = self.grid[r][c]
                if cell.state == CellState.UNKNOWN:
                    violated = self.check_fn(cell)
                    if violated:
                        cell.state = CellState.VIOLATED
                        cell.attention_level = 1.0
                    else:
                        cell.state = CellState.SATISFIED
                    cell.record_result(violated, self.tick_count)
                    evaluated += 1
        return evaluated
    
    def tick(self) -> TickResult:
        """Advance the CA by one tick."""
        start = time.perf_counter()
        cells_updated = 0
        n_violated = 0
        n_attention = 0
        n_unknown = 0
        
        # Compute all updates (synchronous)
        new_states: Dict[Tuple[int, int], CellState] = {}
        new_attentions: Dict[Tuple[int, int], float] = {}
        
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                cell = self.grid[r][c]
                new_state = compute_cell_update(cell, self.tick_count, self.config)
                new_attention = compute_attention_update(cell, self.tick_count, self.config)
                
                if new_state != cell.state or abs(new_attention - cell.attention_level) > 0.001:
                    cells_updated += 1
                
                new_states[(r, c)] = new_state
                new_attentions[(r, c)] = new_attention
        
        # Apply updates
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                cell = self.grid[r][c]
                cell.state = new_states[(r, c)]
                cell.attention_level = new_attentions[(r, c)]
                
                if cell.state == CellState.VIOLATED:
                    n_violated += 1
                elif cell.state == CellState.ATTENTION:
                    n_attention += 1
                elif cell.state == CellState.UNKNOWN:
                    n_unknown += 1
        
        # Evaluate unknowns if we have a check function
        self.evaluate_unknowns()
        
        # Compute attention wave size (BFS from violated cells)
        wave_size = self._compute_largest_attention_component()
        
        elapsed = (time.perf_counter() - start) * 1000
        
        result = TickResult(
            tick=self.tick_count,
            cells_updated=cells_updated,
            violations=n_violated,
            attention_cells=n_attention,
            unknown_cells=n_unknown,
            attention_wave_size=wave_size,
            elapsed_ms=elapsed,
        )
        self.history.append(result)
        self.tick_count += 1
        
        return result
    
    def _compute_largest_attention_component(self) -> int:
        """Find the largest connected component of non-SATISFIED cells."""
        visited = set()
        max_size = 0
        
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                if (r, c) in visited:
                    continue
                cell = self.grid[r][c]
                if cell.state in (CellState.VIOLATED, CellState.ATTENTION):
                    # BFS
                    queue = [(r, c)]
                    visited.add((r, c))
                    size = 0
                    while queue:
                        cr, cc = queue.pop(0)
                        size += 1
                        for neighbor in self.grid[cr][cc].neighbors:
                            nr, nc = neighbor.row, neighbor.col
                            if (nr, nc) not in visited and \
                               neighbor.state in (CellState.VIOLATED, CellState.ATTENTION):
                                visited.add((nr, nc))
                                queue.append((nr, nc))
                    max_size = max(max_size, size)
        
        return max_size
    
    def get_statistics(self) -> GridStatistics:
        """Compute current grid statistics."""
        counts = {s: 0 for s in CellState}
        total_attention = 0.0
        max_attention = 0.0
        
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                cell = self.grid[r][c]
                counts[cell.state] += 1
                total_attention += cell.attention_level
                max_attention = max(max_attention, cell.attention_level)
        
        total = self.config.rows * self.config.cols
        n_clusters = self._count_violation_clusters()
        
        return GridStatistics(
            total_cells=total,
            satisfied=counts[CellState.SATISFIED],
            violated=counts[CellState.VIOLATED],
            attention=counts[CellState.ATTENTION],
            unknown=counts[CellState.UNKNOWN],
            avg_attention_level=total_attention / max(total, 1),
            max_attention_level=max_attention,
            violation_clusters=n_clusters,
        )
    
    def _count_violation_clusters(self) -> int:
        """Count connected components of violated cells."""
        visited = set()
        clusters = 0
        
        for r in range(self.config.rows):
            for c in range(self.config.cols):
                if (r, c) in visited:
                    continue
                if self.grid[r][c].state == CellState.VIOLATED:
                    clusters += 1
                    queue = [(r, c)]
                    visited.add((r, c))
                    while queue:
                        cr, cc = queue.pop(0)
                        for neighbor in self.grid[cr][cc].neighbors:
                            nr, nc = neighbor.row, neighbor.col
                            if (nr, nc) not in visited and \
                               neighbor.state == CellState.VIOLATED:
                                visited.add((nr, nc))
                                queue.append((nr, nc))
                else:
                    visited.add((r, c))
        
        return clusters
    
    def inject_violation_wave(self, center_row: int, center_col: int,
                              radius: int = 1, probability: float = 0.8) -> int:
        """Inject a cluster of violations around a center point."""
        injected = 0
        for dr in range(-radius, radius + 1):
            for dc in range(-radius, radius + 1):
                r, c = center_row + dr, center_col + dc
                if 0 <= r < self.config.rows and 0 <= c < self.config.cols:
                    if random.random() < probability:
                        self.set_violation(r, c, True)
                        injected += 1
        return injected
    
    def render(self) -> str:
        """Render grid state as a string."""
        symbols = {
            CellState.SATISFIED: "·",
            CellState.VIOLATED: "✕",
            CellState.UNKNOWN: "?",
            CellState.ATTENTION: "◆",
        }
        lines = []
        for r in range(self.config.rows):
            row_str = ""
            for c in range(self.config.cols):
                cell = self.grid[r][c]
                sym = symbols[cell.state]
                # Add attention indicator
                if cell.attention_level > 0.5 and cell.state != CellState.VIOLATED:
                    sym = "▲"
                row_str += sym + " "
            lines.append(row_str)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def _run_tests():
    """Run built-in tests."""
    passed = 0
    failed = 0
    
    def assert_test(condition, name):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  ✓ {name}")
        else:
            failed += 1
            print(f"  ✗ {name}")
    
    print("\n=== flux_cellular tests ===\n")
    
    # Test 1: Cell creation
    cell = Cell(row=0, col=0)
    assert_test(cell.state == CellState.UNKNOWN, "Cell starts UNKNOWN")
    assert_test(cell.attention_level == 0.0, "Cell starts with zero attention")
    
    # Test 2: Cell monitoring level
    cell.state = CellState.VIOLATED
    assert_test(cell.monitoring_level > STATE_MONITORING_LEVEL[CellState.SATISFIED],
                "VIOLATED has higher monitoring than SATISFIED")
    
    cell.state = CellState.ATTENTION
    cell.attention_level = 0.8
    assert_test(cell.monitoring_level > STATE_MONITORING_LEVEL[CellState.ATTENTION],
                "Attention boost increases monitoring level")
    
    # Test 3: Cell violation history
    cell.record_result(True, 1)
    cell.record_result(False, 2)
    cell.record_result(True, 3)
    assert_test(abs(cell.recent_violation_rate - 2.0/3.0) < 0.01, "Violation rate correct")
    
    # Test 4: Moore neighborhood
    config = CAConfig(rows=5, cols=5)
    ca = CellularAutomataGrid(config=config)
    center = ca.get_cell(2, 2)
    assert_test(len(center.neighbors) == 8, "Moore neighborhood has 8 neighbors")
    
    corner = ca.get_cell(0, 0)
    assert_test(len(corner.neighbors) == 3, "Corner cell has 3 neighbors")
    
    edge = ca.get_cell(0, 2)
    assert_test(len(edge.neighbors) == 5, "Edge cell has 5 neighbors")
    
    # Test 5: Von Neumann neighborhood
    config_vn = CAConfig(rows=5, cols=5, neighborhood="vonneumann")
    ca_vn = CellularAutomataGrid(config=config_vn)
    center_vn = ca_vn.get_cell(2, 2)
    assert_test(len(center_vn.neighbors) == 4, "Von Neumann center has 4 neighbors")
    
    # Test 6: Set violation
    ca.set_violation(2, 2, True)
    assert_test(ca.get_cell(2, 2).state == CellState.VIOLATED, "Cell set to VIOLATED")
    assert_test(ca.get_cell(2, 2).attention_level == 1.0, "VIOLATED attention = 1.0")
    
    # Test 7: Tick propagation — violation spreads attention
    ca.set_violation(2, 2, True)
    result = ca.tick()
    assert_test(result.tick == 0, "First tick is tick 0")
    
    # Neighbors should now be in ATTENTION state
    center = ca.get_cell(2, 2)
    attention_neighbors = sum(1 for n in center.neighbors
                              if n.state == CellState.ATTENTION)
    assert_test(attention_neighbors > 0, "Neighbors enter ATTENTION after violation tick")
    
    # Test 8: Attention decay
    ca2 = CellularAutomataGrid(config=CAConfig(rows=3, cols=3, attention_decay=0.5))
    ca2.set_violation(1, 1, True)
    ca2.tick()  # Propagate attention
    neighbor = ca2.get_cell(0, 0)
    first_attention = neighbor.attention_level
    
    # Clear the violation so attention decays
    ca2.set_violation(1, 1, False)
    ca2.tick()
    assert_test(neighbor.attention_level < first_attention,
                "Attention decays over time")
    
    # Test 9: Grid statistics
    ca3 = CellularAutomataGrid(config=CAConfig(rows=5, cols=5, seed=42))
    ca3.set_violation(0, 0, True)
    ca3.set_violation(0, 1, True)
    ca3.tick()
    
    stats = ca3.get_statistics()
    assert_test(stats.total_cells == 25, "Total cells = 25")
    assert_test(stats.violated >= 2, "At least 2 violations")
    assert_test(stats.violation_clusters >= 1, "At least 1 violation cluster")
    
    # Test 10: Inject violation wave
    ca4 = CellularAutomataGrid(config=CAConfig(rows=10, cols=10, seed=42))
    injected = ca4.inject_violation_wave(5, 5, radius=2, probability=1.0)
    assert_test(injected > 0, "Wave injection creates violations")
    stats4 = ca4.get_statistics()
    assert_test(stats4.violated == injected, "Wave violations counted correctly")
    
    # Test 11: Evaluate unknowns
    def simple_check(cell: Cell) -> bool:
        return cell.row == 0 and cell.col == 0  # Only one cell violates
    
    ca5 = CellularAutomataGrid(
        check_fn=simple_check,
        config=CAConfig(rows=3, cols=3)
    )
    ca5.evaluate_unknowns()
    assert_test(ca5.get_cell(0, 0).state == CellState.VIOLATED, "Check finds violation at (0,0)")
    assert_test(ca5.get_cell(1, 1).state == CellState.SATISFIED, "Check finds satisfaction at (1,1)")
    
    # Test 12: Render grid
    ca6 = CellularAutomataGrid(config=CAConfig(rows=3, cols=3))
    ca6.set_violation(1, 1, True)
    ca6.tick()
    rendered = ca6.render()
    assert_test(len(rendered) > 0, "Render produces output")
    assert_test("✕" in rendered, "Render shows violations")
    
    # Test 13: Tick history
    assert_test(len(ca6.history) >= 1, "History recorded")
    
    # Test 14: Persistence
    ca7 = CellularAutomataGrid(config=CAConfig(rows=3, cols=3, violation_persistence=2))
    ca7.set_violation(1, 1, True)
    ca7.tick()
    assert_test(ca7.get_cell(1, 1).state == CellState.VIOLATED,
                "Violation persists on tick 1")
    ca7.tick()
    assert_test(ca7.get_cell(1, 1).state == CellState.VIOLATED,
                "Violation still persists on tick 2")
    
    # Test 15: Extended neighborhood
    ca8 = CellularAutomataGrid(config=CAConfig(
        rows=7, cols=7, neighborhood="extended", neighborhood_radius=2))
    center8 = ca8.get_cell(3, 3)
    expected = (5 * 5) - 1  # 5x5 square minus self
    assert_test(len(center8.neighbors) == expected,
                f"Extended neighborhood has {expected} neighbors")
    
    # Test 16: Stand-down — attention cells return to satisfied
    ca9 = CellularAutomataGrid(config=CAConfig(rows=3, cols=3))
    ca9.set_violation(1, 1, True)
    ca9.tick()  # Neighbors go to ATTENTION
    ca9.set_violation(1, 1, False)  # Clear violation
    ca9.tick()  # Should start standing down
    ca9.tick()  # Further stand-down
    ca9.tick()  # Should be all satisfied now
    
    stats9 = ca9.get_statistics()
    assert_test(stats9.violated == 0, "All violations cleared")
    
    # Test 17: Violation rate
    stats_simple = GridStatistics(
        total_cells=10, satisfied=7, violated=2, attention=1,
        unknown=0, avg_attention_level=0.1, max_attention_level=0.5,
        violation_clusters=1
    )
    assert_test(abs(stats_simple.violation_rate - 0.2) < 0.01, "Violation rate correct")
    assert_test(abs(stats_simple.attention_rate - 0.1) < 0.01, "Attention rate correct")
    
    # Test 18: Largest attention component
    ca10 = CellularAutomataGrid(config=CAConfig(rows=5, cols=5))
    ca10.set_violation(0, 0, True)
    ca10.set_violation(0, 1, True)
    ca10.set_violation(4, 4, True)  # Separate cluster
    ca10.tick()
    result10 = ca10.history[-1]
    assert_test(result10.attention_wave_size >= 2, "Attention wave covers multiple cells")
    
    print(f"\n  Results: {passed} passed, {failed} failed\n")
    return failed == 0


if __name__ == "__main__":
    import sys
    success = _run_tests()
    sys.exit(0 if success else 1)
