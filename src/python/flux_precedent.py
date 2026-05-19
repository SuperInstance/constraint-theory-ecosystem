"""
FLUX Precedent Library — Stare Decisis for Constraint Tiles

Courts find the nearest precedent and adapt its ratio decidendi. Precedent
hierarchy gives weight. Old precedents decay. This is EXACTLY what constraint
tiles need — find the nearest matching tile, adapt its bounds, apply.

Core theorem: A constraint system with a precedent library has strictly higher
coverage than one without, and coverage grows monotonically with the number of
precedents. Higher court precedents are more reliable but resist adaptation.

This IS the accumulated correctness cycle: each new edge case becomes a
precedent for future cases. Stare decisis as computational law.

Dependencies: numpy only.
Forgemaster ⚒️ — 2026-05-19
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


# =============================================================================
# 1. CourtLevel — hierarchy of binding authority
# =============================================================================

class CourtLevel(IntEnum):
    TRIAL = 1        # District court — least binding, easy to distinguish
    APPELLATE = 2    # Circuit court — moderately binding
    SUPREME = 3      # Supreme court — most binding, resists adaptation


# =============================================================================
# 2. Case — a legal precedent as a constraint tile
# =============================================================================

@dataclass(frozen=True)
class Case:
    """A legal precedent for constraint checking.

    Features encode the 'facts of the case' — what domain, dimensionality,
    severity, etc. Bounds are the 'ruling' — the constraint limits established.
    The ruling_mask is the ratio decidendi — the core principle.
    """
    case_id: str
    features: Dict[str, float]          # constraint properties
    bounds: List[Tuple[float, float]]   # [(lo, hi), ...] per dimension
    ruling_mask: int                     # bitmask of constraints this case handles
    court_level: CourtLevel
    timestamp: float                     # when decided (unix epoch)
    citations: List[str] = field(default_factory=list)

    def age(self, now: Optional[float] = None) -> float:
        """Seconds since this case was decided."""
        now = now or time.time()
        return max(0.0, now - self.timestamp)


# =============================================================================
# 3. PrecedentLibrary — the case law database
# =============================================================================

class PrecedentLibrary:
    """Stores precedent cases and retrieves nearest matches by feature similarity.

    Feature similarity: weighted euclidean distance over normalized features.
    Precedent weight = court_level * decay^age (older = less binding).
    """

    def __init__(self, decay_rate: float = 0.1, feature_weights: Optional[Dict[str, float]] = None):
        """
        Args:
            decay_rate: exponential decay per year of age (0.1 = 10% loss/year)
            feature_weights: optional per-feature importance weights
        """
        self.cases: Dict[str, Case] = {}
        self.decay_rate = decay_rate
        self.feature_weights = feature_weights or {}
        self._feature_keys: List[str] = []
        self._feature_matrix: Optional[np.ndarray] = None  # shape (n_cases, n_features)

    def add_case(self, case: Case) -> None:
        """Add a new precedent to the library."""
        self.cases[case.case_id] = case
        self._rebuild_index()

    def add_cases(self, cases: Sequence[Case]) -> None:
        """Bulk add precedents."""
        for c in cases:
            self.cases[c.case_id] = c
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild the feature matrix for fast nearest-neighbor lookup."""
        if not self.cases:
            self._feature_matrix = None
            return

        # Collect all feature keys across all cases
        all_keys = set()
        for case in self.cases.values():
            all_keys.update(case.features.keys())
        self._feature_keys = sorted(all_keys)

        case_list = list(self.cases.values())
        n = len(case_list)
        d = len(self._feature_keys)

        self._feature_matrix = np.zeros((n, d))
        self._case_order = [c.case_id for c in case_list]

        for i, case in enumerate(case_list):
            for j, key in enumerate(self._feature_keys):
                self._feature_matrix[i, j] = case.features.get(key, 0.0)

    def _normalize_query(self, query_features: Dict[str, float]) -> np.ndarray:
        """Convert query features to the same vector space as the index."""
        vec = np.zeros(len(self._feature_keys))
        for j, key in enumerate(self._feature_keys):
            vec[j] = query_features.get(key, 0.0)
        return vec

    def _weight_vector(self) -> np.ndarray:
        """Feature importance weights as a vector."""
        if not self._feature_keys:
            return np.ones(0)
        w = np.ones(len(self._feature_keys))
        for j, key in enumerate(self._feature_keys):
            if key in self.feature_weights:
                w[j] = self.feature_weights[key]
        return w

    def _precedent_weight(self, case: Case, now: float) -> float:
        """Weight = court_level * decay^(age_in_years)."""
        age_years = case.age(now) / (365.25 * 86400)
        decay = self.decay_rate ** age_years if age_years > 0 else 1.0
        return float(case.court_level) * decay

    def find_precedent(
        self,
        query_features: Dict[str, float],
        k: int = 5,
        now: Optional[float] = None,
    ) -> List[Tuple[Case, float]]:
        """Find k nearest cases by feature similarity.

        Returns list of (case, relevance_score) sorted by descending relevance.
        Relevance = precedent_weight * exp(-distance * sharpness).
        """
        if self._feature_matrix is None or len(self._feature_matrix) == 0:
            return []

        now = now or time.time()
        query_vec = self._normalize_query(query_features)
        weights = self._weight_vector()

        # Weighted euclidean distance
        diff = self._feature_matrix - query_vec[np.newaxis, :]
        dist = np.sqrt(np.sum(weights[np.newaxis, :] * diff ** 2, axis=1))

        # Relevance: high court level + recent + close distance = high relevance
        relevance = np.zeros(len(self._case_order))
        for i, cid in enumerate(self._case_order):
            case = self.cases[cid]
            pw = self._precedent_weight(case, now)
            # Sharpness controls how fast relevance drops with distance
            relevance[i] = pw * np.exp(-dist[i] * 0.5)

        # Top-k by relevance
        top_k_idx = np.argsort(-relevance)[:min(k, len(relevance))]
        results = []
        for idx in top_k_idx:
            cid = self._case_order[idx]
            if relevance[idx] > 0:
                results.append((self.cases[cid], float(relevance[idx])))
        return results


# =============================================================================
# 4. PrecedentAdapter — adapt a precedent to new circumstances
# =============================================================================

class PrecedentAdapter:
    """Adapts a precedent's bounds to new circumstances.

    Computes feature delta and adjusts bounds proportionally.
    Higher court cases resist adaptation more (scaling factor decreases).
    """

    def __init__(self, adapt_rate: float = 0.3):
        """
        Args:
            adapt_rate: base rate of adaptation (0 = no adaptation, 1 = full override)
        """
        self.adapt_rate = adapt_rate

    def adapt(
        self,
        precedent: Case,
        query_features: Dict[str, float],
        n_dims: int,
    ) -> List[Tuple[float, float]]:
        """Adapt precedent bounds to new circumstances.

        Bounds shift proportionally to feature delta. Supreme cases resist
        adaptation: their scaling factor is reduced by court_level.
        """
        # Feature delta: how different is the new case?
        precedent_features = precedent.features
        all_keys = set(list(precedent_features.keys()) + list(query_features.keys()))
        if not all_keys:
            # No features to compare — return precedent bounds unchanged
            return list(precedent.bounds[:n_dims])

        deltas = []
        for key in all_keys:
            pv = precedent_features.get(key, 0.0)
            qv = query_features.get(key, 0.0)
            denom = max(abs(pv), abs(qv), 1.0)
            deltas.append(abs(qv - pv) / denom)
        delta = np.mean(deltas) if deltas else 0.0

        # Court resistance: higher court = less adaptation
        court_resistance = 1.0 / float(precedent.court_level)
        effective_scale = self.adapt_rate * delta * court_resistance

        adapted = []
        for i in range(n_dims):
            if i < len(precedent.bounds):
                lo, hi = precedent.bounds[i]
                span = hi - lo
                shift = effective_scale * span
                # Shift toward wider bounds (conservative: expand, don't contract)
                adapted.append((lo - shift * 0.5, hi + shift * 0.5))
            else:
                # No precedent for this dimension — wide bounds
                adapted.append((-1e6, 1e6))

        return adapted


# =============================================================================
# 5. StareDecisis — the full legal reasoning pipeline
# =============================================================================

class StareDecisis:
    """Full stare decisis pipeline for constraint checking.

    1. Find nearest precedents
    2. Select most binding (highest court_level * relevance)
    3. Adapt bounds to new circumstances
    4. Check constraints using adapted bounds
    5. If violation found that no precedent covers → NEW precedent

    This IS the accumulated correctness cycle: each edge case becomes law.
    """

    def __init__(
        self,
        library: PrecedentLibrary,
        adapter: Optional[PrecedentAdapter] = None,
        novelty_threshold: float = 0.1,
        auto_precedent: bool = False,
    ):
        """
        Args:
            library: the case law database
            adapter: how to adapt precedents (default: PrecedentAdapter())
            novelty_threshold: relevance below this = "case of first impression" (novel)
            auto_precedent: if True, novel cases are automatically added to library
        """
        self.library = library
        self.adapter = adapter or PrecedentAdapter()
        self.novelty_threshold = novelty_threshold
        self.auto_precedent = auto_precedent
        self.novel_count = 0
        self.precedent_count = 0

    def check(
        self,
        values: np.ndarray,
        query_features: Dict[str, float],
        ground_truth_bounds: Optional[List[Tuple[float, float]]] = None,
        now: Optional[float] = None,
    ) -> dict:
        """Check constraints using stare decisis reasoning.

        Args:
            values: point to check, shape (n_dims,)
            query_features: features describing the constraint context
            ground_truth_bounds: if provided, used to evaluate accuracy
            now: current time (for precedent decay)

        Returns:
            dict with: bound_applied, violation_mask, precedent_used,
                       is_novel, coverage, accuracy
        """
        now = now or time.time()
        n_dims = len(values)

        # Step 1: Find nearest precedents
        precedents = self.library.find_precedent(query_features, k=5, now=now)

        if not precedents or precedents[0][1] < self.novelty_threshold:
            # Case of first impression — no good precedent
            self.novel_count += 1
            # Use very wide bounds (conservative)
            bounds = [(-1e6, 1e6)] * n_dims
            is_novel = True
            precedent_used = None

            # Novel cases get their precedent created below in the auto_precedent block
            # to avoid duplication
        else:
            # Step 2: Select most binding precedent
            best_case, best_relevance = precedents[0]
            precedent_used = best_case
            self.precedent_count += 1
            is_novel = False

            # Step 3: Adapt bounds
            bounds = self.adapter.adapt(best_case, query_features, n_dims)

        # Step 4: Check constraints using adapted bounds
        violation_mask = 0
        for i, (lo, hi) in enumerate(bounds):
            if i < len(values) and (values[i] < lo or values[i] > hi):
                violation_mask |= (1 << i)

        # Step 5: Evaluate if requested
        result = {
            "bounds_applied": bounds,
            "violation_mask": violation_mask,
            "precedent_used": precedent_used.case_id if precedent_used else None,
            "is_novel": is_novel,
            "n_precedents_found": len(precedents),
        }

        if ground_truth_bounds is not None:
            gt_violation = 0
            for i, (lo, hi) in enumerate(ground_truth_bounds):
                if i < len(values) and (values[i] < lo or values[i] > hi):
                    gt_violation |= (1 << i)
            result["ground_truth_violation"] = gt_violation
            result["accuracy"] = 1.0 if violation_mask == gt_violation else 0.0
            # Coverage: did we find a usable precedent?
            result["coverage"] = 0.0 if is_novel else 1.0

            # If novel and auto_precedent, create new precedent with ground truth ruling
            if is_novel and self.auto_precedent:
                self._create_precedent(
                    f"auto_{self.novel_count}", query_features,
                    ground_truth_bounds, gt_violation, CourtLevel.TRIAL, now, []
                )

        return result

    def _create_precedent(
        self,
        case_id: str,
        features: Dict[str, float],
        bounds: List[Tuple[float, float]],
        ruling_mask: int,
        court_level: CourtLevel,
        timestamp: float,
        citations: List[str],
    ) -> Case:
        case = Case(
            case_id=case_id,
            features=features,
            bounds=bounds,
            ruling_mask=ruling_mask,
            court_level=court_level,
            timestamp=timestamp,
            citations=citations,
        )
        self.library.add_case(case)
        return case


# =============================================================================
# 6. Experiment — Stare Decisis Accumulation
# =============================================================================

def run_experiment(seed: int = 42) -> dict:
    """Run the precedent library experiment.

    - Build library of 50 precedent cases across domains
    - 1000 new queries, varying similarity to precedents
    - Measure coverage, accuracy, accumulation
    """
    rng = np.random.RandomState(seed)
    now = time.time()

    # Domain definitions with characteristic features
    domains = {
        "automotive": {"domain": 0.0, "severity": 0.9, "safety_critical": 1.0},
        "medical":    {"domain": 0.2, "severity": 1.0, "safety_critical": 1.0},
        "aerospace":  {"domain": 0.4, "severity": 0.95, "safety_critical": 1.0},
        "space":      {"domain": 0.6, "severity": 0.85, "safety_critical": 0.9},
        "industrial": {"domain": 0.8, "severity": 0.7, "safety_critical": 0.6},
        "consumer":   {"domain": 1.0, "severity": 0.3, "safety_critical": 0.2},
    }

    # --- Build 50 precedent cases ---
    library = PrecedentLibrary(decay_rate=0.1)
    cases = []
    domain_names = list(domains.keys())

    for i in range(50):
        domain_name = domain_names[i % len(domains)]
        base = domains[domain_name]

        # Add some variation
        features = {
            "domain": base["domain"] + rng.normal(0, 0.03),
            "severity": np.clip(base["severity"] + rng.normal(0, 0.05), 0, 1),
            "safety_critical": np.clip(base["safety_critical"] + rng.normal(0, 0.05), 0, 1),
            "n_dims": float(rng.randint(2, 8)),
            "noise_level": np.clip(rng.exponential(0.1), 0, 0.5),
            "temperature": np.clip(rng.normal(0.5, 0.2), 0, 1),
        }

        n_dims = int(features["n_dims"])
        severity = features["severity"]
        bounds = []
        for _ in range(n_dims):
            span = (1.0 - severity) * rng.uniform(0.5, 2.0) + 0.5
            center = rng.normal(0, 1)
            bounds.append((center - span / 2, center + span / 2))

        # Court level: mostly trial, some appellate, few supreme
        r = rng.random()
        if r < 0.15:
            court = CourtLevel.SUPREME
        elif r < 0.45:
            court = CourtLevel.APPELLATE
        else:
            court = CourtLevel.TRIAL

        # Spread timestamps over the last 5 years
        age_seconds = rng.uniform(0, 5 * 365.25 * 86400)
        ts = now - age_seconds

        case = Case(
            case_id=f"case_{i:03d}",
            features=features,
            bounds=bounds,
            ruling_mask=rng.randint(1, 2**n_dims),
            court_level=court,
            timestamp=ts,
            citations=[],
        )
        cases.append(case)

    library.add_cases(cases)

    # --- Run 1000 queries ---
    adapter = PrecedentAdapter(adapt_rate=0.3)
    sd = StareDecisis(library, adapter, novelty_threshold=0.05)

    total = 1000
    results = {
        "coverage": [],
        "accuracy": [],
        "novel_count": 0,
        "precedent_count": 0,
        "court_level_accuracy": {1: [], 2: [], 3: []},
        "distance_accuracy": [],  # (feature_distance, accuracy) pairs
    }

    for q in range(total):
        # Generate query — 70% near existing precedents, 30% novel
        if rng.random() < 0.7:
            # Pick a base case and perturb
            base_case = cases[rng.randint(len(cases))]
            query_features = {}
            for k, v in base_case.features.items():
                query_features[k] = v + rng.normal(0, 0.05)
        else:
            # Novel case
            domain_name = domain_names[rng.randint(len(domain_names))]
            base = domains[domain_name]
            query_features = {
                "domain": base["domain"] + rng.normal(0, 0.1),
                "severity": np.clip(base["severity"] + rng.normal(0, 0.15), 0, 1),
                "safety_critical": np.clip(base["safety_critical"] + rng.normal(0, 0.1), 0, 1),
                "n_dims": float(rng.randint(2, 8)),
                "noise_level": np.clip(rng.exponential(0.2), 0, 0.5),
                "temperature": np.clip(rng.normal(0.5, 0.3), 0, 1),
            }

        n_dims = int(query_features["n_dims"])
        values = rng.normal(0, 1, size=n_dims)

        # Ground truth bounds based on features
        severity = query_features["severity"]
        gt_bounds = []
        for _ in range(n_dims):
            span = (1.0 - severity) * rng.uniform(0.5, 2.0) + 0.5
            center = rng.normal(0, 1)
            gt_bounds.append((center - span / 2, center + span / 2))

        check_result = sd.check(values, query_features, ground_truth_bounds=gt_bounds, now=now)

        results["coverage"].append(check_result.get("coverage", 0.0))
        results["accuracy"].append(check_result.get("accuracy", 0.0))
        if check_result["is_novel"]:
            results["novel_count"] += 1
        else:
            results["precedent_count"] += 1
            if check_result["precedent_used"]:
                pc = library.cases[check_result["precedent_used"]]
                results["court_level_accuracy"][int(pc.court_level)].append(
                    check_result.get("accuracy", 0.0)
                )

    # --- Compute summary ---
    coverage_rate = np.mean(results["coverage"])
    accuracy_rate = np.mean(results["accuracy"])

    summary = {
        "n_precedents": len(library.cases),
        "n_queries": total,
        "coverage_rate": float(coverage_rate),
        "accuracy_rate": float(accuracy_rate),
        "novel_count": results["novel_count"],
        "precedent_count": results["precedent_count"],
        "court_accuracy": {
            level: float(np.mean(accs)) if accs else 0.0
            for level, accs in results["court_level_accuracy"].items()
        },
    }

    # --- Accumulation experiment: show more precedents → better coverage ---
    accumulation = []
    for n_lib in [5, 10, 20, 35, 50]:
        if n_lib > len(cases):
            continue
        lib_subset = PrecedentLibrary(decay_rate=0.1)
        lib_subset.add_cases(cases[:n_lib])
        sd_sub = StareDecisis(lib_subset, PrecedentAdapter(0.3), novelty_threshold=0.05)

        covered = 0
        correct = 0
        for q in range(200):
            if rng.random() < 0.7:
                base_case = cases[rng.randint(len(cases))]
                qf = {k: v + rng.normal(0, 0.05) for k, v in base_case.features.items()}
            else:
                dn = domain_names[rng.randint(len(domain_names))]
                b = domains[dn]
                qf = {
                    "domain": b["domain"] + rng.normal(0, 0.1),
                    "severity": np.clip(b["severity"] + rng.normal(0, 0.15), 0, 1),
                    "safety_critical": np.clip(b["safety_critical"] + rng.normal(0, 0.1), 0, 1),
                    "n_dims": float(rng.randint(2, 8)),
                    "noise_level": np.clip(rng.exponential(0.2), 0, 0.5),
                    "temperature": np.clip(rng.normal(0.5, 0.3), 0, 1),
                }
            nd = int(qf["n_dims"])
            vals = rng.normal(0, 1, size=nd)
            sev = qf["severity"]
            gt = [
                (rng.normal(0, 1) - (1 - sev) * rng.uniform(0.25, 1.0),
                 rng.normal(0, 1) + (1 - sev) * rng.uniform(0.25, 1.0))
                for _ in range(nd)
            ]
            r = sd_sub.check(vals, qf, ground_truth_bounds=gt, now=now)
            covered += r.get("coverage", 0.0)
            correct += r.get("accuracy", 0.0)

        accumulation.append({
            "n_precedents": n_lib,
            "coverage": float(covered / 200),
            "accuracy": float(correct / 200),
        })

    summary["accumulation"] = accumulation
    return summary
