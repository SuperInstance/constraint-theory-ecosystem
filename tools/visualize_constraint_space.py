#!/usr/bin/env python3
"""
visualize_constraint_space.py — Visualization of topological constraint structures

Generates ASCII and matplotlib visualizations of:
- 2D constraint spaces (valid region in 2D)
- Violation surfaces (boundary of valid region)
- Bifurcation diagrams (how valid region changes as bounds move)
- Severity landscapes (severity as a function of position)
"""

import sys
import math
import itertools
from typing import List, Tuple, Optional

# Add parent to path for imports
sys.path.insert(0, '.')
from src.python.flux_topology import (
    ConstraintDef, ConstraintSpace, ViolationSurface,
    DeformationDetector, BifurcationPoint
)


# ---------------------------------------------------------------------------
# ASCII Visualization
# ---------------------------------------------------------------------------

def ascii_2d_constraint_space(
    space: ConstraintSpace,
    resolution: int = 40,
    width: int = 60
) -> str:
    """
    ASCII visualization of a 2D constraint space.

    Legend:
      · = inside valid region
      # = on boundary (violation surface)
      × = outside (violation zone)
      Numbers = severity level
    """
    if space.dimension != 2:
        return "ERROR: ASCII visualization requires 2D space"

    c0, c1 = space.constraints[0], space.constraints[1]

    # Add margin
    margin_x = c0.width() * 0.3
    margin_y = c1.width() * 0.3

    lines = []
    lines.append(f"  2D Constraint Space: [{c0.lo},{c0.hi}] × [{c1.lo},{c1.hi}]")
    lines.append(f"  Constraints: {c0.name}∈[{c0.lo},{c0.hi}], {c1.name}∈[{c1.lo},{c1.hi}]")
    lines.append("")

    for row in range(resolution):
        y = c1.hi + margin_y - (row / (resolution - 1)) * (c1.width() + 2 * margin_y)
        line = ""
        for col in range(width):
            x = c0.lo - margin_x + (col / (width - 1)) * (c0.width() + 2 * margin_x)
            mask = space.violation_mask([x, y])
            severity = bin(mask).count('1')

            if mask == 0:
                line += "·"
            elif severity <= 1:
                line += "#"
            elif severity == 2:
                line += "×"
            else:
                line += str(min(severity, 9))
        lines.append(f"  {line}")

    lines.append("")
    lines.append("  Legend: · = valid, # = boundary, × = violation")
    return "\n".join(lines)


def ascii_severity_landscape(
    space: ConstraintSpace,
    resolution: int = 30,
    width: int = 50
) -> str:
    """
    ASCII severity landscape showing severity as a function of position.

    Uses signed distance: closer to boundary = higher severity visualization.
    """
    if space.dimension != 2:
        return "ERROR: Requires 2D space"

    vs = ViolationSurface(space)
    c0, c1 = space.constraints[0], space.constraints[1]
    margin = max(c0.width(), c1.width()) * 0.3

    lines = []
    lines.append("  Severity Landscape (signed distance to boundary)")
    lines.append("")

    chars = " ·:;=+*#@"  # Increasing severity appearance

    for row in range(resolution):
        y = c1.hi + margin - (row / (resolution - 1)) * (c1.width() + 2 * margin)
        line = ""
        for col in range(width):
            x = c0.lo - margin + (col / (width - 1)) * (c0.width() + 2 * margin)
            sd = vs.signed_distance([x, y])
            if sd < 0:
                # Outside: encode by distance from boundary
                idx = min(int(abs(sd) / max(c0.width(), c1.width()) * 8) + 1, 8)
                line += chars[idx]
            elif sd < 0.01 * min(c0.width(), c1.width()):
                line += "#"  # On boundary
            else:
                line += "·"  # Inside
        lines.append(f"  {line}")

    lines.append("")
    lines.append("  Legend: · = deep inside, # = boundary, :;=+*#@ = outside (increasing distance)")
    return "\n".join(lines)


def ascii_bifurcation_diagram(
    space: ConstraintSpace,
    dim: int,
    bound: str,
    start: float,
    end: float,
    steps: int = 30,
    width: int = 50
) -> str:
    """
    ASCII bifurcation diagram showing how valid region changes
    as a single bound sweeps from start to end.

    Shows cross-section: other dimensions at midpoint.
    """
    c = space.constraints[dim]
    other_dims = [i for i in range(space.dimension) if i != dim]

    lines = []
    lines.append(f"  Bifurcation Diagram: dim {dim} {bound} sweep [{start:.1f} → {end:.1f}]")
    lines.append("")

    for step in range(steps):
        t = start + (end - start) * step / (steps - 1)

        # Construct deformed constraint
        constraints = list(space.constraints)
        lo, hi = constraints[dim].lo, constraints[dim].hi
        if bound == 'lo':
            lo = t
        else:
            hi = t

        # Width of interval at this parameter
        interval_width = hi - lo

        # Visualize as bar
        bar_filled = int(max(0, interval_width) / max(abs(end - start), 0.001) * width)
        bar_filled = min(bar_filled, width)

        if interval_width < 0:
            marker = "COLLAPSED"
        elif interval_width == 0:
            marker = "POINT"
        else:
            marker = ""

        bar = "█" * bar_filled + "░" * (width - bar_filled)
        lines.append(f"  t={t:7.2f} │{bar}│ {marker}")

    lines.append("")
    lines.append("  █ = valid interval width, ░ = beyond bounds")
    lines.append("  COLLAPSED = interval inverts (empty set), POINT = zero width")
    return "\n".join(lines)


def ascii_boundary_decomposition(space: ConstraintSpace) -> str:
    """Show the boundary strata decomposition."""
    if space.dimension > 3:
        return "Boundary decomposition only visualized for d ≤ 3"

    vs = ViolationSurface(space)
    lines = []
    lines.append("  Boundary Strata Decomposition")
    lines.append(f"  Dimension: {space.dimension}")
    lines.append("")

    for s in vs.strata():
        kind = "facet" if s.is_facet else ("vertex" if s.codimension == space.dimension else "edge")
        dims_str = ",".join(str(d) for d in s.active_constraints)
        lines.append(f"    Stratum (active=[{dims_str}]): dim={s.dimension}, "
                     f"codim={s.codimension}, type={kind}")

    lines.append("")
    lines.append(f"  Euler characteristic of boundary: {vs.euler_characteristic()}")
    lines.append(f"  Face counts by codimension: {vs.face_count()}")

    if space.dimension <= 3:
        corners = vs.vertex_coordinates()
        lines.append("")
        lines.append("  Corner points:")
        for i, pt in enumerate(corners):
            pt_str = ", ".join(f"{v:.2f}" for v in pt)
            lines.append(f"    {i}: ({pt_str})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Matplotlib Visualization (optional — graceful degradation)
# ---------------------------------------------------------------------------

def matplotlib_2d_constraint_space(
    space: ConstraintSpace,
    filename: Optional[str] = None,
    resolution: int = 200
):
    """
    Matplotlib visualization of 2D constraint space with:
    - Color-coded severity regions
    - Boundary highlighted
    - Corner points marked
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not available — skipping plot generation")
        return

    if space.dimension != 2:
        print("Plotting requires 2D space")
        return

    c0, c1 = space.constraints[0], space.constraints[1]
    margin = max(c0.width(), c1.width()) * 0.3

    x = np.linspace(c0.lo - margin, c0.hi + margin, resolution)
    y = np.linspace(c1.lo - margin, c1.hi + margin, resolution)
    X, Y = np.meshgrid(x, y)

    Z = np.zeros_like(X)
    for i in range(resolution):
        for j in range(resolution):
            Z[i, j] = space.severity([X[i, j], Y[i, j]])

    fig, ax = plt.subplots(1, 1, figsize=(8, 8))
    im = ax.contourf(X, Y, Z, levels=[-0.5, 0.5, 1.5, 2.5], colors=['#2ecc71', '#e74c3c', '#8e44ad'])
    ax.contour(X, Y, Z, levels=[0.5, 1.5, 2.5], colors='black', linewidths=2)

    # Mark corners
    vs = ViolationSurface(space)
    corners = vs.vertex_coordinates()
    for pt in corners:
        ax.plot(pt[0], pt[1], 'ko', markersize=8)

    ax.set_xlabel(c0.name)
    ax.set_ylabel(c1.name)
    ax.set_title(f'Constraint Space: [{c0.name}∈[{c0.lo},{c0.hi}]] × [{c1.name}∈[{c1.lo},{c1.hi}]]')
    ax.set_aspect('equal')

    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2ecc71', label='Valid (severity 0)'),
        Patch(facecolor='#e74c3c', label='1 constraint violated'),
        Patch(facecolor='#8e44ad', label='2 constraints violated'),
    ]
    ax.legend(handles=legend_elements, loc='upper right')

    plt.tight_layout()

    if filename:
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"Saved: {filename}")
    else:
        plt.savefig('/tmp/constraint_space_2d.png', dpi=150, bbox_inches='tight')
        print("Saved: /tmp/constraint_space_2d.png")
    plt.close()


def matplotlib_bifurcation(
    space: ConstraintSpace,
    dim: int,
    bound: str,
    start: float,
    end: float,
    filename: Optional[str] = None,
    steps: int = 200
):
    """
    Matplotlib bifurcation diagram: volume of valid region as bound deforms.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("matplotlib not available")
        return

    params = np.linspace(start, end, steps)
    volumes = []
    for t in params:
        constraints = list(space.constraints)
        lo, hi = constraints[dim].lo, constraints[dim].hi
        if bound == 'lo':
            lo = t
        else:
            hi = t
        vol = max(0, hi - lo)
        for i, c in enumerate(space.constraints):
            if i != dim:
                vol *= c.width()
        volumes.append(vol)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(params, volumes, 'b-', linewidth=2)
    ax.fill_between(params, volumes, alpha=0.3)

    # Mark bifurcation points
    detector = DeformationDetector(space)
    for bp in detector.deformation_series(dim, bound, start, end, steps):
        ax.axvline(x=bp.parameter_value, color='r', linestyle='--', alpha=0.7)
        ax.annotate(bp.bifurcation_type, xy=(bp.parameter_value, 0),
                    rotation=90, va='bottom', fontsize=8)

    ax.set_xlabel(f'Bound parameter ({bound} of dim {dim})')
    ax.set_ylabel('Volume of valid region')
    ax.set_title('Bifurcation Diagram: Volume vs Bound Deformation')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    if filename:
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"Saved: {filename}")
    else:
        plt.savefig('/tmp/bifurcation.png', dpi=150, bbox_inches='tight')
        print("Saved: /tmp/bifurcation.png")
    plt.close()


# ---------------------------------------------------------------------------
# Demo / Main
# ---------------------------------------------------------------------------

def demo():
    """Run all visualizations with a sample constraint space."""
    space = ConstraintSpace([
        ConstraintDef(-2.0, 3.0, "temperature"),
        ConstraintDef(0.0, 5.0, "pressure"),
    ])

    print("=" * 70)
    print("  TOPOLOGICAL CONSTRAINT SPACE VISUALIZATION DEMO")
    print("=" * 70)
    print()

    print(ascii_2d_constraint_space(space, resolution=25, width=55))
    print()
    print(ascii_severity_landscape(space, resolution=20, width=45))
    print()
    print(ascii_boundary_decomposition(space))
    print()
    print(ascii_bifurcation_diagram(
        space, dim=0, bound='hi',
        start=3.0, end=-2.0,
        steps=20, width=40
    ))
    print()

    # Matplotlib plots
    matplotlib_2d_constraint_space(space)
    matplotlib_bifurcation(space, dim=0, bound='hi', start=3.0, end=-2.0)

    print()
    print("Done. All visualizations generated.")


if __name__ == "__main__":
    demo()
