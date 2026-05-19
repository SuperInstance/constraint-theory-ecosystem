"""
FLUX Hyperbolic — Poincaré Ball Geometry for Model Capability Routing

Hyperbolic geometry router that maps model capabilities onto a Poincaré ball,
where distance naturally captures specialization hierarchies:
  - General models near the center (low norm)
  - Specialized models near the boundary (high norm)
  - Boundary distances grow exponentially, reflecting capability gaps

Architecture:
  CapabilitySpace (8D Poincaré ball) → TaskRouter (nearest model) → FrechetMean (fleet consensus)

Mathematical formulation:
  Poincaré distance: d(u,v) = arcosh(1 + 2||u-v||² / ((1-||u||²)(1-||v||²)))
  Möbius addition: u ⊕ v = ((1+2<u,v>+||v||²)u + (1-||u||²)v) / (1+2<u,v>+||u||²||v||²)
  Exponential map: exp₀(v) = tanh(λ₀||v||/2) * v/||v||
  Logarithmic map: log₀(u) = (2/(λ₀*||u||)) * artanh(||u||) * u
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np


# ---------------------------------------------------------------------------
# Poincaré Ball Operations
# ---------------------------------------------------------------------------

class PoincareBall:
    """Hyperbolic geometry operations on the Poincaré ball model.

    The Poincaré ball is the open unit ball {x ∈ R^n : ||x|| < 1} with
    the Riemannian metric tensor:
        g_x = (2/(1 - ||x||²))² · I

    Curvature c = -1 (standard hyperbolic space).
    """

    EPS = 1e-5  # boundary clamp
    MAX_NORM = 1.0 - 1e-5

    @staticmethod
    def distance(u: np.ndarray, v: np.ndarray) -> float:
        """Poincaré distance between two points on the ball.

        d(u,v) = arcosh(1 + 2||u-v||² / ((1-||u||²)(1-||v||²)))
        """
        u = np.asarray(u, dtype=np.float64)
        v = np.asarray(v, dtype=np.float64)
        diff_sq = np.sum((u - v) ** 2)
        u_sq = np.sum(u ** 2)
        v_sq = np.sum(v ** 2)
        denom = (1.0 - u_sq) * (1.0 - v_sq)
        if denom < 1e-12:
            denom = 1e-12
        arg = 1.0 + 2.0 * diff_sq / denom
        # Clamp for numerical stability
        arg = max(arg, 1.0 + 1e-15)
        return float(np.arccosh(arg))

    @staticmethod
    def norm(v: np.ndarray) -> float:
        """Euclidean norm of a point on the ball."""
        return float(np.linalg.norm(v))

    @staticmethod
    def project(v: np.ndarray, eps: float = 1e-5) -> np.ndarray:
        """Project point onto ball: clamp ||v|| < 1-eps."""
        v = np.asarray(v, dtype=np.float64)
        n = np.linalg.norm(v)
        max_norm = 1.0 - eps
        if n >= max_norm:
            return v * (max_norm / n)
        return v

    @staticmethod
    def mobius_add(u: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Möbius addition on the Poincaré ball.

        u ⊕ v = ((1 + 2<u,v> + ||v||²)·u + (1 - ||u||²)·v) /
                (1 + 2<u,v> + ||u||²·||v||²)
        """
        u = np.asarray(u, dtype=np.float64)
        v = np.asarray(v, dtype=np.float64)
        uv = np.dot(u, v)
        u_sq = np.sum(u ** 2)
        v_sq = np.sum(v ** 2)
        denom = 1.0 + 2.0 * uv + u_sq * v_sq
        if abs(denom) < 1e-12:
            denom = 1e-12
        num_u = (1.0 + 2.0 * uv + v_sq) * u
        num_v = (1.0 - u_sq) * v
        return PoincareBall.project(num_u + num_v) / denom

    @staticmethod
    def conformal_factor(v: np.ndarray) -> float:
        """Conformal factor λ_v = 2 / (1 - ||v||²)."""
        v = np.asarray(v, dtype=np.float64)
        v_sq = np.sum(v ** 2)
        return 2.0 / (1.0 - v_sq)

    @staticmethod
    def expmap(origin: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Exponential map from tangent space at origin to manifold.

        exp_o(v) = o ⊕ (tanh(λ_o · ||v|| / 2) · v / ||v||)
        When origin = 0: exp_0(v) = tanh(||v||) · v / ||v||
        """
        origin = np.asarray(origin, dtype=np.float64)
        v = np.asarray(v, dtype=np.float64)
        v_norm = np.linalg.norm(v)
        if v_norm < 1e-10:
            return origin.copy()

        lam = PoincareBall.conformal_factor(origin)
        coeff = np.tanh(lam * v_norm / 2.0)
        direction = v / v_norm
        result = PoincareBall.mobius_add(origin, coeff * direction)
        return PoincareBall.project(result)

    @staticmethod
    def logmap(origin: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Logarithmic map from manifold to tangent space at origin.

        log_o(v) = (2 / (λ_o · ||−o ⊕ v||)) · artanh(||−o ⊕ v||) · (−o ⊕ v)
        When origin = 0: log_0(v) = artanh(||v||) · v / ||v||
        """
        origin = np.asarray(origin, dtype=np.float64)
        v = np.asarray(v, dtype=np.float64)
        if np.allclose(origin, v, atol=1e-10):
            return np.zeros_like(v)

        minus_o = -origin
        diff = PoincareBall.mobius_add(minus_o, v)
        diff_norm = np.linalg.norm(diff)
        if diff_norm < 1e-10:
            return np.zeros_like(v)

        lam = PoincareBall.conformal_factor(origin)
        coeff = 2.0 * np.arctanh(min(diff_norm, 1.0 - 1e-10)) / (lam * diff_norm)
        return coeff * diff


# ---------------------------------------------------------------------------
# Capability Space — 8D Poincaré Ball for Model Routing
# ---------------------------------------------------------------------------

@dataclass
class ModelPoint:
    """A model embedded as a point in the capability space.

    Norm encodes specialization level:
      ||v|| < 0.2 → generalist (near center)
      0.2 ≤ ||v|| < 0.7 → moderate specialist
      ||v|| ≥ 0.7 → high specialist (near boundary)

    Direction encodes WHAT the model specializes in.
    """
    name: str
    coords: np.ndarray
    specialization_label: str = ""

    @property
    def norm(self) -> float:
        return PoincareBall.norm(self.coords)

    @property
    def specialization_level(self) -> str:
        n = self.norm
        if n < 0.2:
            return "general"
        elif n < 0.7:
            return "moderate"
        else:
            return "specialist"

    @property
    def conformal_factor(self) -> float:
        return PoincareBall.conformal_factor(self.coords)


class CapabilitySpace:
    """8-dimensional Poincaré ball for model capability routing.

    Dimensions (constraint-space axes):
      0: reasoning_depth  — logical inference capability
      1: code_generation  — code synthesis quality
      2: math_precision   — numerical/mathematical accuracy
      3: context_window   — effective context handling
      4: speed            — inference speed
      5: creativity       — novel synthesis / divergence
      6: safety           — alignment / refusal quality
      7: multilingual     — cross-language capability
    """

    DIM = 8

    def __init__(self) -> None:
        self.models: Dict[str, ModelPoint] = {}

    def add_model(self, name: str, coords: np.ndarray,
                  specialization_label: str = "") -> ModelPoint:
        """Add a model to the capability space."""
        coords = np.asarray(coords, dtype=np.float64)
        assert coords.shape == (self.DIM,), f"Expected {self.DIM}D, got {coords.shape}"
        coords = PoincareBall.project(coords)
        mp = ModelPoint(name=name, coords=coords,
                        specialization_label=specialization_label)
        self.models[name] = mp
        return mp

    def add_general_model(self, name: str, direction: np.ndarray,
                          norm: float = 0.1) -> ModelPoint:
        """Add a general model near the center."""
        d = np.asarray(direction, dtype=np.float64)
        d = d / (np.linalg.norm(d) + 1e-10)
        coords = d * norm
        return self.add_model(name, coords, "general")

    def add_specialist_model(self, name: str, direction: np.ndarray,
                             norm: float = 0.85) -> ModelPoint:
        """Add a specialist model near the boundary."""
        d = np.asarray(direction, dtype=np.float64)
        d = d / (np.linalg.norm(d) + 1e-10)
        coords = d * norm
        return self.add_model(name, coords, "specialist")

    def distance(self, name_a: str, name_b: str) -> float:
        """Poincaré distance between two models."""
        return PoincareBall.distance(self.models[name_a].coords,
                                     self.models[name_b].coords)

    def nearest_model(self, point: np.ndarray, n: int = 1) -> List[Tuple[str, float]]:
        """Find n nearest models to a point in capability space."""
        point = PoincareBall.project(np.asarray(point, dtype=np.float64))
        dists = [(name, PoincareBall.distance(point, mp.coords))
                 for name, mp in self.models.items()]
        dists.sort(key=lambda x: x[1])
        return dists[:n]


# ---------------------------------------------------------------------------
# Task Router — Route Tasks to Best Model
# ---------------------------------------------------------------------------

@dataclass
class RoutingResult:
    """Result of routing a single task."""
    task_id: int
    task_embedding: np.ndarray
    hyperbolic_model: str
    hyperbolic_distance: float
    euclidean_model: str
    euclidean_distance: float
    agree: bool  # do both methods pick the same model?


class TaskRouter:
    """Route tasks to the best model using hyperbolic geometry.

    Embeds tasks as points on the Poincaré ball based on constraint
    dimensions, then finds the nearest model.
    """

    def __init__(self, space: CapabilitySpace) -> None:
        self.space = space

    def embed_task(self, constraint_vector: np.ndarray,
                   specialization: float = 0.5) -> np.ndarray:
        """Embed a task as a hyperbolic point.

        constraint_vector: raw constraint requirements (8D)
        specialization: how specialized the task is (0=general, 1=niche)
        """
        cv = np.asarray(constraint_vector, dtype=np.float64)
        cv = cv / (np.linalg.norm(cv) + 1e-10)
        norm = specialization * 0.9  # scale to stay on ball
        return PoincareBall.project(cv * norm)

    def route_hyperbolic(self, task_embedding: np.ndarray) -> Tuple[str, float]:
        """Route task to nearest model via Poincaré distance."""
        nearest = self.space.nearest_model(task_embedding, n=1)
        return nearest[0]

    def route_euclidean(self, task_embedding: np.ndarray) -> Tuple[str, float]:
        """Route task to nearest model via Euclidean distance."""
        task = np.asarray(task_embedding, dtype=np.float64)
        dists = []
        for name, mp in self.space.models.items():
            d = float(np.linalg.norm(task - mp.coords))
            dists.append((name, d))
        dists.sort(key=lambda x: x[1])
        return dists[0]

    def route_task(self, task_id: int, constraint_vector: np.ndarray,
                   specialization: float = 0.5) -> RoutingResult:
        """Route a single task, comparing hyperbolic vs euclidean."""
        emb = self.embed_task(constraint_vector, specialization)
        h_name, h_dist = self.route_hyperbolic(emb)
        e_name, e_dist = self.route_euclidean(emb)
        return RoutingResult(
            task_id=task_id,
            task_embedding=emb,
            hyperbolic_model=h_name,
            hyperbolic_distance=h_dist,
            euclidean_model=e_name,
            euclidean_distance=e_dist,
            agree=(h_name == e_name),
        )

    def route_batch(self, tasks: List[Tuple[int, np.ndarray, float]]
                    ) -> List[RoutingResult]:
        """Route a batch of tasks."""
        return [self.route_task(tid, cv, spec) for tid, cv, spec in tasks]


# ---------------------------------------------------------------------------
# Fréchet Mean — Hyperbolic Centroid for Fleet Consensus
# ---------------------------------------------------------------------------

class FrechetMean:
    """Compute the Fréchet mean (centroid) in hyperbolic space.

    Uses iterative tangent-space averaging:
      1. Pick initial estimate (e.g., first point)
      2. Logmap all points → tangent space at estimate
      3. Euclidean mean in tangent space
      4. Expmap back → new estimate
      5. Repeat until convergence
    """

    MAX_ITER = 50
    TOL = 1e-7

    @staticmethod
    def compute(points: List[np.ndarray],
                weights: Optional[np.ndarray] = None) -> np.ndarray:
        """Compute the weighted Fréchet mean of points on the ball."""
        if not points:
            raise ValueError("Need at least one point")
        points = [np.asarray(p, dtype=np.float64) for p in points]
        points = [PoincareBall.project(p) for p in points]

        if weights is None:
            weights = np.ones(len(points)) / len(points)
        else:
            weights = np.asarray(weights, dtype=np.float64)
            weights = weights / weights.sum()

        # Initial estimate: weighted Euclidean mean (projected)
        estimate = sum(w * p for w, p in zip(weights, points))
        estimate = PoincareBall.project(estimate)

        for _ in range(FrechetMean.MAX_ITER):
            # Logmap all points to tangent space at estimate
            tangent = [PoincareBall.logmap(estimate, p) for p in points]

            # Weighted Euclidean mean in tangent space
            tangent_mean = sum(w * t for w, t in zip(weights, tangent))

            # Check convergence
            if np.linalg.norm(tangent_mean) < FrechetMean.TOL:
                break

            # Expmap back
            new_estimate = PoincareBall.expmap(estimate, tangent_mean)
            new_estimate = PoincareBall.project(new_estimate)

            # Convergence check
            # Convergence: shift between estimates
            # (tangent_mean norm already checked above)
            estimate = new_estimate

        return estimate


# ---------------------------------------------------------------------------
# Experiment — Routing Comparison
# ---------------------------------------------------------------------------

def run_experiment(seed: int = 42) -> dict:
    """Run hyperbolic vs euclidean routing experiment.

    10 models, 1000 random tasks, compare routing quality.
    """
    rng = np.random.RandomState(seed)

    space = CapabilitySpace()

    # --- 10 models at various specialization levels ---
    # General models (norm < 0.2)
    space.add_general_model("generalist-1", rng.randn(8), norm=0.10)
    space.add_general_model("generalist-2", rng.randn(8), norm=0.15)

    # Moderate specialists (0.2 ≤ norm < 0.7)
    space.add_model("moderate-1", PoincareBall.project(rng.randn(8) * 0.3), "moderate")
    space.add_model("moderate-2", PoincareBall.project(rng.randn(8) * 0.4), "moderate")
    space.add_model("moderate-3", PoincareBall.project(rng.randn(8) * 0.5), "moderate")
    space.add_model("moderate-4", PoincareBall.project(rng.randn(8) * 0.6), "moderate")

    # High specialists (norm ≥ 0.7)
    dirs = [rng.randn(8) for _ in range(4)]
    space.add_specialist_model("specialist-code", dirs[0], norm=0.80)
    space.add_specialist_model("specialist-math", dirs[1], norm=0.85)
    space.add_specialist_model("specialist-reason", dirs[2], norm=0.90)
    space.add_specialist_model("specialist-novel", dirs[3], norm=0.92)

    router = TaskRouter(space)

    # --- Generate 1000 tasks ---
    n_tasks = 1000
    tasks = []
    for i in range(n_tasks):
        cv = rng.randn(8)
        # Specialization drawn from Beta distribution: mix of general and niche
        spec = rng.beta(2, 5)  # mostly general tasks, some niche
        tasks.append((i, cv, spec))

    results = router.route_batch(tasks)

    # --- Analysis ---
    agree_count = sum(1 for r in results if r.agree)
    agree_rate = agree_count / n_tasks

    # Routing precision: do specialized tasks go to specialized models?
    specialist_names = {name for name, mp in space.models.items()
                        if mp.specialization_level == "specialist"}
    general_names = {name for name, mp in space.models.items()
                     if mp.specialization_level == "general"}

    # Tasks with high specialization (>0.5) should route to specialists
    high_spec_tasks = [r for r in results if tasks[r.task_id][2] > 0.5]
    hyp_to_specialist = sum(1 for r in high_spec_tasks
                            if r.hyperbolic_model in specialist_names)
    euc_to_specialist = sum(1 for r in high_spec_tasks
                            if r.euclidean_model in specialist_names)

    hyp_precision = hyp_to_specialist / max(len(high_spec_tasks), 1)
    euc_precision = euc_to_specialist / max(len(high_spec_tasks), 1)

    # Boundary effect: average distance for specialist models
    spec_coords = [mp.coords for name, mp in space.models.items()
                   if mp.specialization_level == "specialist"]
    gen_coords = [mp.coords for name, mp in space.models.items()
                  if mp.specialization_level == "general"]

    if len(spec_coords) > 1:
        spec_dists = []
        for i in range(len(spec_coords)):
            for j in range(i + 1, len(spec_coords)):
                spec_dists.append(PoincaréBall.distance(spec_coords[i], spec_coords[j]))
        avg_spec_dist = float(np.mean(spec_dists))
    else:
        avg_spec_dist = 0.0

    if len(gen_coords) > 1:
        gen_dists = []
        for i in range(len(gen_coords)):
            for j in range(i + 1, len(gen_coords)):
                gen_dists.append(PoincaréBall.distance(gen_coords[i], gen_coords[j]))
        avg_gen_dist = float(np.mean(gen_dists))
    else:
        avg_gen_dist = 0.0

    # Fréchet mean (fleet consensus)
    all_coords = [mp.coords for mp in space.models.values()]
    fleet_centroid = FrechetMean.compute(all_coords)

    return {
        "n_models": len(space.models),
        "n_tasks": n_tasks,
        "agree_rate": agree_rate,
        "agree_count": agree_count,
        "n_high_spec_tasks": len(high_spec_tasks),
        "hyp_specialist_precision": hyp_precision,
        "euc_specialist_precision": euc_precision,
        "avg_specialist_inter_dist": avg_spec_dist,
        "avg_general_inter_dist": avg_gen_dist,
        "boundary_ratio": avg_spec_dist / max(avg_gen_dist, 1e-10),
        "fleet_centroid_norm": float(np.linalg.norm(fleet_centroid)),
        "models": {name: {"norm": mp.norm, "level": mp.specialization_level,
                          "label": mp.specialization_label}
                   for name, mp in space.models.items()},
        "results": results,
    }


# Fix the typo: ensure PoincaréBall references work with ASCII name
# (The class is PoincareBall, references inside FrechetMean use it correctly)
# The run_experiment function had a typo — fix inline:

# Rebinding for run_experiment (handles Unicode issues)
_PoincareBall = PoincareBall

# Monkey-patch the distance function to avoid the Unicode reference issue
_original_run = run_experiment

def run_experiment(seed: int = 42) -> dict:  # type: ignore[no-redef]
    """Run hyperbolic vs euclidean routing experiment (fixed)."""
    rng = np.random.RandomState(seed)

    space = CapabilitySpace()
    PB = PoincareBall

    # --- 10 models at various specialization levels ---
    space.add_general_model("generalist-1", rng.randn(8), norm=0.10)
    space.add_general_model("generalist-2", rng.randn(8), norm=0.15)
    space.add_model("moderate-1", PB.project(rng.randn(8) * 0.3), "moderate")
    space.add_model("moderate-2", PB.project(rng.randn(8) * 0.4), "moderate")
    space.add_model("moderate-3", PB.project(rng.randn(8) * 0.5), "moderate")
    space.add_model("moderate-4", PB.project(rng.randn(8) * 0.6), "moderate")

    dirs = [rng.randn(8) for _ in range(4)]
    space.add_specialist_model("specialist-code", dirs[0], norm=0.80)
    space.add_specialist_model("specialist-math", dirs[1], norm=0.85)
    space.add_specialist_model("specialist-reason", dirs[2], norm=0.90)
    space.add_specialist_model("specialist-novel", dirs[3], norm=0.92)

    router = TaskRouter(space)

    # --- Generate 1000 tasks ---
    n_tasks = 1000
    tasks = []
    for i in range(n_tasks):
        cv = rng.randn(8)
        spec = rng.beta(2, 5)
        tasks.append((i, cv, spec))

    results = router.route_batch(tasks)

    # --- Analysis ---
    agree_count = sum(1 for r in results if r.agree)
    agree_rate = agree_count / n_tasks

    specialist_names = {name for name, mp in space.models.items()
                        if mp.specialization_level == "specialist"}

    high_spec_tasks = [r for r in results if tasks[r.task_id][2] > 0.5]
    hyp_to_specialist = sum(1 for r in high_spec_tasks
                            if r.hyperbolic_model in specialist_names)
    euc_to_specialist = sum(1 for r in high_spec_tasks
                            if r.euclidean_model in specialist_names)

    hyp_precision = hyp_to_specialist / max(len(high_spec_tasks), 1)
    euc_precision = euc_to_specialist / max(len(high_spec_tasks), 1)

    spec_coords = [mp.coords for name, mp in space.models.items()
                   if mp.specialization_level == "specialist"]
    gen_coords = [mp.coords for name, mp in space.models.items()
                  if mp.specialization_level == "general"]

    def avg_pairwise_distance(coords_list):
        if len(coords_list) < 2:
            return 0.0
        dists = []
        for i in range(len(coords_list)):
            for j in range(i + 1, len(coords_list)):
                dists.append(PB.distance(coords_list[i], coords_list[j]))
        return float(np.mean(dists))

    avg_spec_dist = avg_pairwise_distance(spec_coords)
    avg_gen_dist = avg_pairwise_distance(gen_coords)

    all_coords = [mp.coords for mp in space.models.values()]
    fleet_centroid = FrechetMean.compute(all_coords)

    return {
        "n_models": len(space.models),
        "n_tasks": n_tasks,
        "agree_rate": agree_rate,
        "agree_count": agree_count,
        "n_high_spec_tasks": len(high_spec_tasks),
        "hyp_specialist_precision": hyp_precision,
        "euc_specialist_precision": euc_precision,
        "avg_specialist_inter_dist": avg_spec_dist,
        "avg_general_inter_dist": avg_gen_dist,
        "boundary_ratio": avg_spec_dist / max(avg_gen_dist, 1e-10),
        "fleet_centroid_norm": float(np.linalg.norm(fleet_centroid)),
        "models": {name: {"norm": round(mp.norm, 4),
                          "level": mp.specialization_level,
                          "label": mp.specialization_label}
                   for name, mp in space.models.items()},
        "results": results,
    }
