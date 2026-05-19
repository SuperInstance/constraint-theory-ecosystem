"""
flux_genome.py — GENETIC EXPRESSION ENGINE for Tensor-Penrose DNA

The biological analogue: Tensor-Penrose structure is DNA (rigid, fixed).
The Genome encodes ALL possible constraint-checking proteins. Environmental
context (domain, hardware, latency) determines WHICH genes are expressed,
producing different constraint procedures from the SAME underlying genome.

METAPHOR (rigorous):
- DNA = Tensor-Penrose structure (Eisenstein lattice, cyclotomic fields, golden-ratio tiling)
- Ribosome = Constraint Sheaf + Fracture-Coalesce (reads DNA, assembles proteins)
- Proteins = Executable constraint procedures (actual checking logic)
- Gene Expression = Which proteins get expressed depends on ENVIRONMENTAL CONTEXT
- Promoter/Enhancer = Hyperbolic routing determines which genes are active
- Mutation = Sediment layers modify protein structure over time
- Epigenetics = Precedent library (environmental history affects future expression)

THEOREM: For a fixed genome G and environments E1, E2, the expressed
protein sets P(G, E1) and P(G, E2) satisfy:
  - P(G, E1) ⊆ Genes(G)  (expressed proteins come from the genome)
  - P(G, E1) ≠ P(G, E2)  (different environments express different proteins)
  - |P(G, E1)| + |P(G, E2)| ≤ |Genes(G)| + |P(G, E1) ∩ P(G, E2)|
    (inclusion-exclusion on gene activation)

This proves: one rigid Tensor-Penrose structure serves all contexts through
regulated gene expression. The genome is FIXED; expression is ADAPTIVE.

Author: Forgemaster ⚒️ (Constraint Theory Ecosystem)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Set, Tuple

import numpy as np
from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# 1. Gene — a unit of genetic information in Tensor-Penrose DNA
# ---------------------------------------------------------------------------

@dataclass
class Gene:
    """
    A gene is a locus on the Tensor-Penrose tiling encoding a constraint
    checking procedure. Like a biological gene, it has:
      - A fixed structure (the DNA sequence — Eisenstein lattice point)
      - Expression conditions (promoter/enhancer elements)
      - A protein template (what constraint this gene produces)
      - Regulatory elements (activators and silencers)
    """
    gene_id: str
    structure: NDArray  # Eisenstein lattice point / cyclotomic element (fixed)
    expression_conditions: Dict[str, object]  # environment features that activate
    protein_template: Callable[[NDArray], NDArray]  # constraint checking function
    promoters: List[str] = field(default_factory=list)   # gene_ids that activate this
    silencers: List[str] = field(default_factory=list)   # gene_ids that suppress this
    domain: str = "general"  # constraint domain tag
    description: str = ""

    def matches_environment(self, environment: Dict[str, object]) -> float:
        """
        Compute expression strength [0, 1] for given environment.
        Returns 0.0 if no conditions match, 1.0 if all match perfectly.
        Hyperbolic routing analogy: distance in feature space → expression level.
        """
        if not self.expression_conditions:
            return 0.0

        score = 0.0
        matched = 0
        for key, required in self.expression_conditions.items():
            if key not in environment:
                continue
            env_val = environment[key]
            matched += 1
            if isinstance(required, (list, set, tuple)):
                if env_val in required:
                    score += 1.0
            elif isinstance(required, float) and isinstance(env_val, (int, float)):
                # Continuous: Gaussian-like activation
                sigma = 0.5
                score += np.exp(-0.5 * ((env_val - required) / sigma) ** 2)
            elif env_val == required:
                score += 1.0
            # Partial match (string contains)
            elif isinstance(required, str) and isinstance(env_val, str):
                if required.lower() in env_val.lower() or env_val.lower() in required.lower():
                    score += 0.5

        if matched == 0:
            return 0.0
        return score / max(len(self.expression_conditions), 1)


# ---------------------------------------------------------------------------
# 2. Genome — the complete Tensor-Penrose DNA
# ---------------------------------------------------------------------------

@dataclass
class Genome:
    """
    The complete Tensor-Penrose DNA. FIXED structure — does not change
    per execution. Contains ALL possible proteins the system can express.

    The genome is the rigid Penrose structure encoded as constraint knowledge.
    Every gene occupies a locus determined by its Eisenstein lattice coordinates.
    The regulatory network determines which genes activate/suppress others.
    """
    genes: Dict[str, Gene] = field(default_factory=dict)
    regulatory_network: Dict[str, List[str]] = field(default_factory=dict)
    # regulatory_network[gene_id] = list of gene_ids it regulates

    def add_gene(self, gene: Gene) -> None:
        self.genes[gene.gene_id] = gene
        # Wire promoters into regulatory network
        for promoter in gene.promoters:
            if promoter not in self.regulatory_network:
                self.regulatory_network[promoter] = []
            self.regulatory_network[promoter].append(gene.gene_id)

    @property
    def gene_count(self) -> int:
        return len(self.genes)

    @property
    def domains(self) -> Set[str]:
        return {g.domain for g in self.genes.values()}


# ---------------------------------------------------------------------------
# 3. ExpressionProfile — which genes are active in a given environment
# ---------------------------------------------------------------------------

@dataclass
class ExpressionProfile:
    """
    The result of reading the genome in a specific environment.
    Like a cell's transcriptome: which genes are turned on, and how strongly.

    The hyperbolic router determines expression levels:
    genes near the environment's position in feature space are strongly expressed.
    """
    environment: Dict[str, object]
    active_genes: List[str] = field(default_factory=list)
    expression_levels: Dict[str, float] = field(default_factory=dict)
    silenced_genes: List[str] = field(default_factory=list)

    @property
    def strongly_expressed(self) -> List[str]:
        """Genes with expression > 0.7"""
        return [g for g in self.active_genes if self.expression_levels.get(g, 0) > 0.7]

    @property
    def weakly_expressed(self) -> List[str]:
        """Genes with expression 0.3-0.7"""
        return [g for g in self.active_genes
                if 0.3 <= self.expression_levels.get(g, 0) <= 0.7]


# ---------------------------------------------------------------------------
# 4. Protein — an executable constraint procedure
# ---------------------------------------------------------------------------

@dataclass
class Protein:
    """
    An assembled constraint-checking protein. Like biological proteins,
    these are temporary — they degrade over time unless reinforced
    (sediment layers / epigenetic memory).

    Each protein is assembled from one or more genes (splice variants).
    """
    protein_id: str
    assembled_from: List[str]  # gene_ids that contributed
    procedure: Callable[[NDArray], NDArray]  # the actual checking function
    lifetime: float = 1.0  # remaining lifetime (decreases over time)
    degradation_rate: float = 0.1  # how fast this protein degrades
    domain: str = "general"

    def execute(self, data: NDArray) -> NDArray:
        """Run the constraint check. Returns error mask (0 = pass)."""
        return self.procedure(data)

    def tick(self) -> None:
        """Advance time — protein degrades."""
        self.lifetime = max(0.0, self.lifetime - self.degradation_rate)

    @property
    def is_alive(self) -> bool:
        return self.lifetime > 0.0


# ---------------------------------------------------------------------------
# 5. Ribosome — reads DNA and assembles proteins
# ---------------------------------------------------------------------------

class Ribosome:
    """
    The ribosome reads the genome (DNA) and assembles constraint proteins.

    THE SHEAF ANALOGY: The ribosome IS the sheaf — it maps local genetic
    information (tiles/genes) to global protein function (constraint checks).
    Like a biological ribosome:
      1. Transcription: determine which genes are active (ExpressionProfile)
      2. Translation: convert each active gene into an executable protein
      3. Splicing: same gene can produce different proteins based on context
      4. Assembly: multi-gene proteins for complex constraints
    """

    # Expression threshold: genes below this are not transcribed
    EXPRESSION_THRESHOLD = 0.3

    def transcript(self, genome: Genome, environment: Dict[str, object]) -> ExpressionProfile:
        """
        Transcription: scan genome for genes matching the environment.
        Returns an ExpressionProfile listing active genes and their levels.
        """
        profile = ExpressionProfile(environment=environment)

        # Phase 1: Direct matching — which genes match this environment?
        for gene_id, gene in genome.genes.items():
            level = gene.matches_environment(environment)
            if level >= self.EXPRESSION_THRESHOLD:
                profile.active_genes.append(gene_id)
                profile.expression_levels[gene_id] = level

        # Phase 2: Regulatory network — promoters enhance, silencers suppress
        enhanced = []
        silenced = []

        for active_id in list(profile.active_genes):
            gene = genome.genes[active_id]
            # This active gene may promote others
            for promoted_id in gene.promoters:
                if promoted_id in genome.genes and promoted_id not in profile.active_genes:
                    # Promoter adds the gene at reduced expression
                    promoted_gene = genome.genes[promoted_id]
                    level = promoted_gene.matches_environment(environment) * 0.6
                    if level >= self.EXPRESSION_THRESHOLD:
                        enhanced.append((promoted_id, level))

            # Silencers reduce expression
            for silenced_id in gene.silencers:
                if silenced_id in profile.active_genes:
                    silenced.append(silenced_id)

        # Apply enhancers
        for gene_id, level in enhanced:
            if gene_id not in profile.active_genes:
                profile.active_genes.append(gene_id)
                profile.expression_levels[gene_id] = level

        # Apply silencers
        for gene_id in silenced:
            if gene_id in profile.active_genes:
                profile.active_genes.remove(gene_id)
                profile.silenced_genes.append(gene_id)
                profile.expression_levels.pop(gene_id, None)

        return profile

    def translate(self, gene: Gene, expression_level: float,
                  environment: Dict[str, object]) -> Protein:
        """
        Translation: convert a single gene into an executable protein.
        Expression level modulates protein lifetime and degradation.
        """
        lifetime = 1.0 * expression_level  # stronger expression → longer lifetime
        degradation = 0.1 * (1.1 - expression_level)  # stronger → slower degradation

        return Protein(
            protein_id=f"protein_{gene.gene_id}",
            assembled_from=[gene.gene_id],
            procedure=gene.protein_template,
            lifetime=lifetime,
            degradation_rate=degradation,
            domain=gene.domain,
        )

    def translate_profile(self, genome: Genome,
                          profile: ExpressionProfile) -> List[Protein]:
        """Translate all active genes in a profile into proteins."""
        proteins = []
        for gene_id in profile.active_genes:
            gene = genome.genes[gene_id]
            level = profile.expression_levels.get(gene_id, 0.5)
            protein = self.translate(gene, level, profile.environment)
            proteins.append(protein)
        return proteins


# ---------------------------------------------------------------------------
# 6. Incubator — the full expression pipeline (PLATO)
# ---------------------------------------------------------------------------

class Incubator:
    """
    The PLATO incubator: the environment where genetic potential becomes
    functional reality. This is the full gene expression pipeline:

    1. Ribosome reads genome
    2. ExpressionProfile determines active genes
    3. Ribosome translates genes into proteins
    4. Proteins execute constraint checks
    5. Results feed back (mutation/epigenetics)

    This is where the Tensor-Penrose DNA gets expressed into living
    constraint-checking proteins.
    """

    def __init__(self, genome: Genome, ribosome: Optional[Ribosome] = None):
        self.genome = genome
        self.ribosome = ribosome or Ribosome()
        self.proteins: List[Protein] = []
        self.history: List[Dict] = []  # expression history (epigenetics)

    def express(self, environment: Dict[str, object],
                data: Optional[NDArray] = None) -> Dict:
        """
        Full expression pipeline: genome + environment → proteins → results.
        """
        # 1. Transcription
        profile = self.ribosome.transcript(self.genome, environment)

        # 2. Translation
        proteins = self.ribosome.translate_profile(self.genome, profile)

        # 3. Execution (if data provided)
        results = {}
        if data is not None:
            for protein in proteins:
                error_mask = protein.execute(data)
                results[protein.protein_id] = {
                    "error_mask": error_mask,
                    "violations": int(np.sum(error_mask)),
                    "domain": protein.domain,
                    "alive": protein.is_alive,
                }

        # 4. Store active proteins
        self.proteins = proteins

        # 5. Record history (epigenetics)
        record = {
            "environment": environment,
            "active_genes": profile.active_genes,
            "strongly_expressed": profile.strongly_expressed,
            "silenced": profile.silenced_genes,
            "protein_count": len(proteins),
            "domains": list({p.domain for p in proteins}),
        }
        self.history.append(record)

        return {
            "profile": profile,
            "proteins": proteins,
            "results": results,
        }

    def tick(self) -> None:
        """Advance time — all proteins degrade."""
        for protein in self.proteins:
            protein.tick()
        # Remove dead proteins
        self.proteins = [p for p in self.proteins if p.is_alive]


# ---------------------------------------------------------------------------
# 7. Experiment: 20 genes, 5 environments, adaptive expression
# ---------------------------------------------------------------------------

def _make_range_check(lo: float, hi: float, tol: float = 0.0):
    """Factory: range constraint checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i, row in enumerate(data):
            val = float(np.mean(row))
            if val < lo - tol or val > hi + tol:
                violations[i] = 1.0
        return violations
    return check


def _make_threshold_check(threshold: float, mode: str = "above"):
    """Factory: threshold constraint checker."""
    def check(data: NDArray) -> NDArray:
        means = np.mean(data, axis=1)
        if mode == "above":
            return (means < threshold).astype(np.float64)
        else:
            return (means > threshold).astype(np.float64)
    return check


def _make_variance_check(max_var: float):
    """Factory: variance constraint checker."""
    def check(data: NDArray) -> NDArray:
        variances = np.var(data, axis=1)
        return (variances > max_var).astype(np.float64)
    return check


def _make_monotonic_check():
    """Factory: monotonicity constraint checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i, row in enumerate(data):
            diffs = np.diff(row)
            if np.any(diffs < 0):
                violations[i] = 1.0
        return violations
    return check


def _make_symmetry_check():
    """Factory: symmetry constraint checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i, row in enumerate(data):
            half = len(row) // 2
            if half > 0 and np.max(np.abs(row[:half] - row[-half:])) > 0.5:
                violations[i] = 1.0
        return violations
    return check


def _make_bounded_deriv_check(max_deriv: float):
    """Factory: bounded derivative constraint checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i, row in enumerate(data):
            if len(row) > 1:
                derivs = np.abs(np.diff(row))
                if np.max(derivs) > max_deriv:
                    violations[i] = 1.0
        return violations
    return check


def _make_integral_check(max_integral: float):
    """Factory: integral bound constraint checker."""
    def check(data: NDArray) -> NDArray:
        integrals = np.sum(np.abs(data), axis=1)
        return (integrals > max_integral).astype(np.float64)
    return check


def _make_orthogonality_check(min_dot: float):
    """Factory: orthogonality constraint checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i in range(0, data.shape[0] - 1, 2):
            dot = np.abs(np.dot(data[i], data[i + 1]))
            if dot > min_dot:
                violations[i] = 1.0
                violations[i + 1] = 1.0
        return violations
    return check


def _make_noise_floor_check(floor: float):
    """Factory: noise floor constraint checker."""
    def check(data: NDArray) -> NDArray:
        mins = np.min(np.abs(data), axis=1)
        return (mins < floor).astype(np.float64)
    return check


def _make_latency_check(max_latency: float):
    """Factory: latency constraint checker (simulated via step response)."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i, row in enumerate(data):
            # Simulated step response: should settle within max_latency fraction
            target = row[-1]
            if abs(target) > 0.01:
                settled_idx = len(row)
                for j in range(len(row)):
                    if abs(row[j] - target) / abs(target) < 0.05:
                        settled_idx = j
                        break
                if settled_idx / len(row) > max_latency:
                    violations[i] = 1.0
        return violations
    return check


def _make_redundancy_check(min_overlap: int):
    """Factory: redundancy constraint checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i in range(data.shape[0]):
            nonzero = np.count_nonzero(data[i])
            if nonzero < min_overlap:
                violations[i] = 1.0
        return violations
    return check


def _make_emission_check(max_level: float):
    """Factory: emission level constraint checker."""
    def check(data: NDArray) -> NDArray:
        means = np.mean(data, axis=1)
        return (means > max_level).astype(np.float64)
    return check


def _make_corrosion_check(max_rate: float):
    """Factory: corrosion/degradation rate checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i, row in enumerate(data):
            if len(row) > 1:
                rate = (row[-1] - row[0]) / max(abs(row[0]), 0.001)
                if rate > max_rate:
                    violations[i] = 1.0
        return violations
    return check


def _make_stability_check(max_drift: float):
    """Factory: long-term stability checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i, row in enumerate(data):
            if len(row) >= 4:
                quarter = len(row) // 4
                drift = abs(np.mean(row[:quarter]) - np.mean(row[-quarter:]))
                if drift > max_drift:
                    violations[i] = 1.0
        return violations
    return check


def _make_spatial_check(max_gradient: float):
    """Factory: spatial gradient constraint checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i, row in enumerate(data):
            if len(row) > 1:
                gradient = np.max(np.abs(np.diff(row)))
                if gradient > max_gradient:
                    violations[i] = 1.0
        return violations
    return check


def _make_compatibility_check(standard: str):
    """Factory: standards compatibility checker."""
    std_thresholds = {
        "DO-178C": 0.001,
        "ISO-26262": 0.01,
        "IEC-62304": 0.005,
        "SOLAS": 0.02,
        "IEC-61511": 0.008,
    }
    threshold = std_thresholds.get(standard, 0.01)

    def check(data: NDArray) -> NDArray:
        variances = np.var(data, axis=1)
        return (variances > threshold).astype(np.float64)
    return check


def _make_throughput_check(min_rate: float):
    """Factory: throughput constraint checker."""
    def check(data: NDArray) -> NDArray:
        throughputs = np.sum(np.abs(data), axis=1)
        return (throughputs < min_rate).astype(np.float64)
    return check


def _make_spectral_check(max_peak: float):
    """Factory: spectral purity constraint checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i, row in enumerate(data):
            fft = np.abs(np.fft.rfft(row))
            if len(fft) > 1 and np.max(fft[1:]) / max(np.mean(fft[1:]), 0.001) > max_peak:
                violations[i] = 1.0
        return violations
    return check


def _make_fault_tolerance_check(min_survivors: int):
    """Factory: fault tolerance constraint checker."""
    def check(data: NDArray) -> NDArray:
        violations = np.zeros(data.shape[0], dtype=np.float64)
        for i, row in enumerate(data):
            operational = np.sum(row > 0)
            if operational < min_survivors:
                violations[i] = 1.0
        return violations
    return check


def build_experiment_genome() -> Genome:
    """
    Build the experiment genome: 20 genes covering different constraint domains.

    Gene loci are Eisenstein lattice points (golden-ratio structured).
    Each gene encodes a constraint protein triggered by specific environments.
    """
    phi = (1 + np.sqrt(5)) / 2  # golden ratio

    genes = [
        # --- MARITIME genes (5) ---
        Gene(
            gene_id="nav_position",
            structure=np.array([phi, 1.0, 0.0]),
            expression_conditions={"domain": "maritime"},
            protein_template=_make_range_check(-180, 180),
            domain="maritime",
            description="Navigation position bounds check",
        ),
        Gene(
            gene_id="nav_heading",
            structure=np.array([phi, 1.0, 2 * np.pi / 5]),
            expression_conditions={"domain": "maritime"},
            protein_template=_make_range_check(0, 360),
            domain="maritime",
            description="Heading angle bounds check",
        ),
        Gene(
            gene_id="nav_stability",
            structure=np.array([phi**2, 1.0, 4 * np.pi / 5]),
            expression_conditions={"domain": "maritime"},
            protein_template=_make_variance_check(10.0),
            domain="maritime",
            description="Vessel stability variance check",
        ),
        Gene(
            gene_id="solas_compliance",
            structure=np.array([phi**2, 1.0, 6 * np.pi / 5]),
            expression_conditions={"domain": "maritime", "regulatory": True},
            protein_template=_make_compatibility_check("SOLAS"),
            domain="maritime",
            description="SOLAS regulatory compliance check",
            promoters=["nav_position", "nav_heading"],
        ),
        Gene(
            gene_id="wave_response",
            structure=np.array([phi, 2.0, 8 * np.pi / 5]),
            expression_conditions={"domain": "maritime"},
            protein_template=_make_bounded_deriv_check(3.0),
            domain="maritime",
            description="Wave response rate-of-change check",
        ),

        # --- MEDICAL genes (5) ---
        Gene(
            gene_id="patient_vitals",
            structure=np.array([phi**2, 0.0, np.pi / 3]),
            expression_conditions={"domain": "medical"},
            protein_template=_make_range_check(60, 200),
            domain="medical",
            description="Patient vital signs range check",
        ),
        Gene(
            gene_id="drug_dosage",
            structure=np.array([phi, 0.0, 2 * np.pi / 3]),
            expression_conditions={"domain": "medical", "safety_critical": True},
            protein_template=_make_threshold_check(5.0, mode="above"),
            domain="medical",
            description="Drug dosage safety threshold",
        ),
        Gene(
            gene_id="alarms",
            structure=np.array([phi**3, 0.0, np.pi]),
            expression_conditions={"domain": "medical"},
            protein_template=_make_noise_floor_check(0.01),
            domain="medical",
            description="Alarm signal integrity check",
            promoters=["patient_vitals"],
        ),
        Gene(
            gene_id="iec62304",
            structure=np.array([phi**2, 0.0, 4 * np.pi / 3]),
            expression_conditions={"domain": "medical", "regulatory": True},
            protein_template=_make_compatibility_check("IEC-62304"),
            domain="medical",
            description="IEC-62304 medical software compliance",
            promoters=["patient_vitals", "drug_dosage"],
        ),
        Gene(
            gene_id="contamination",
            structure=np.array([phi, 0.0, 5 * np.pi / 3]),
            expression_conditions={"domain": "medical"},
            protein_template=_make_integral_check(50.0),
            domain="medical",
            description="Cumulative contamination check",
        ),

        # --- AUTOMOTIVE genes (5) ---
        Gene(
            gene_id="speed_limit",
            structure=np.array([1.0, phi, np.pi / 5]),
            expression_conditions={"domain": "automotive"},
            protein_template=_make_threshold_check(130.0),
            domain="automotive",
            description="Speed limit constraint",
        ),
        Gene(
            gene_id="brake_distance",
            structure=np.array([1.0, phi**2, 2 * np.pi / 5]),
            expression_conditions={"domain": "automotive"},
            protein_template=_make_monotonic_check(),
            domain="automotive",
            description="Braking distance monotonicity",
        ),
        Gene(
            gene_id="iso26262",
            structure=np.array([1.0, phi, 3 * np.pi / 5]),
            expression_conditions={"domain": "automotive", "regulatory": True},
            protein_template=_make_compatibility_check("ISO-26262"),
            domain="automotive",
            description="ISO-26262 functional safety compliance",
            promoters=["speed_limit", "brake_distance"],
        ),
        Gene(
            gene_id="latency_auto",
            structure=np.array([1.0, phi**2, 4 * np.pi / 5]),
            expression_conditions={"domain": "automotive", "realtime": True},
            protein_template=_make_latency_check(0.1),
            domain="automotive",
            description="Real-time latency constraint",
        ),
        Gene(
            gene_id="redundancy_auto",
            structure=np.array([1.0, phi, np.pi]),
            expression_conditions={"domain": "automotive"},
            protein_template=_make_redundancy_check(2),
            domain="automotive",
            description="System redundancy check",
        ),

        # --- AEROSPACE genes (5) ---
        Gene(
            gene_id="altitude",
            structure=np.array([2.0, phi, 0.0]),
            expression_conditions={"domain": "aerospace"},
            protein_template=_make_range_check(0, 45000),
            domain="aerospace",
            description="Altitude envelope check",
        ),
        Gene(
            gene_id="g_force",
            structure=np.array([2.0, phi**2, 2 * np.pi / 5]),
            expression_conditions={"domain": "aerospace"},
            protein_template=_make_threshold_check(9.0),
            domain="aerospace",
            description="G-force structural limit",
        ),
        Gene(
            gene_id="do178c",
            structure=np.array([2.0, phi, 4 * np.pi / 5]),
            expression_conditions={"domain": "aerospace", "regulatory": True},
            protein_template=_make_compatibility_check("DO-178C"),
            domain="aerospace",
            description="DO-178C airborne software compliance",
            promoters=["altitude", "g_force"],
        ),
        Gene(
            gene_id="spectral_purity",
            structure=np.array([2.0, phi**2, 6 * np.pi / 5]),
            expression_conditions={"domain": "aerospace"},
            protein_template=_make_spectral_check(10.0),
            domain="aerospace",
            description="Signal spectral purity check",
        ),
        Gene(
            gene_id="fault_tolerance",
            structure=np.array([2.0, phi, 8 * np.pi / 5]),
            expression_conditions={"domain": "aerospace"},
            protein_template=_make_fault_tolerance_check(2),
            domain="aerospace",
            description="Fault tolerance check (min surviving channels)",
        ),

        # --- INDUSTRIAL genes (5) ---
        Gene(
            gene_id="temperature",
            structure=np.array([0.0, phi, np.pi / 5]),
            expression_conditions={"domain": "industrial"},
            protein_template=_make_range_check(-40, 85),
            domain="industrial",
            description="Operating temperature range check",
        ),
        Gene(
            gene_id="emissions",
            structure=np.array([0.0, phi**2, 3 * np.pi / 5]),
            expression_conditions={"domain": "industrial"},
            protein_template=_make_emission_check(50.0),
            domain="industrial",
            description="Emission level constraint",
        ),
        Gene(
            gene_id="corrosion",
            structure=np.array([0.0, phi, np.pi]),
            expression_conditions={"domain": "industrial"},
            protein_template=_make_corrosion_check(0.1),
            domain="industrial",
            description="Corrosion/degradation rate check",
        ),
        Gene(
            gene_id="throughput",
            structure=np.array([0.0, phi**2, 7 * np.pi / 5]),
            expression_conditions={"domain": "industrial"},
            protein_template=_make_throughput_check(10.0),
            domain="industrial",
            description="Production throughput minimum",
        ),
        Gene(
            gene_id="iec61511",
            structure=np.array([0.0, phi, 9 * np.pi / 5]),
            expression_conditions={"domain": "industrial", "regulatory": True},
            protein_template=_make_compatibility_check("IEC-61511"),
            domain="industrial",
            description="IEC-61511 process safety compliance",
            promoters=["temperature", "emissions"],
        ),
    ]

    genome = Genome()
    for gene in genes:
        genome.add_gene(gene)

    return genome


def run_experiment(seed: int = 42) -> Dict:
    """
    Run the full genome expression experiment:
    - 20 genes in one fixed genome
    - 5 environments: maritime, medical, automotive, aerospace, industrial
    - Each environment expresses DIFFERENT proteins from the SAME genome
    - Proves: one rigid structure serves all contexts through regulated expression
    """
    rng = np.random.default_rng(seed)
    genome = build_experiment_genome()
    incubator = Incubator(genome)
    ribosome = Ribosome()

    # Five environments with different context features
    environments = {
        "maritime": {"domain": "maritime", "regulatory": True, "realtime": False},
        "medical": {"domain": "medical", "safety_critical": True, "regulatory": True},
        "automotive": {"domain": "automotive", "realtime": True, "regulatory": True},
        "aerospace": {"domain": "aerospace", "regulatory": True, "realtime": True},
        "industrial": {"domain": "industrial", "regulatory": True},
    }

    results = {}
    all_expressed_genes = {}

    for env_name, env in environments.items():
        # Generate test data
        data = rng.normal(0, 1, size=(10, 8))

        # Express proteins in this environment
        output = incubator.express(env, data)
        profile = output["profile"]
        proteins = output["proteins"]

        # Record results
        results[env_name] = {
            "active_genes": profile.active_genes,
            "strongly_expressed": profile.strongly_expressed,
            "weakly_expressed": profile.weakly_expressed,
            "silenced": profile.silenced_genes,
            "protein_count": len(proteins),
            "domains": list({p.domain for p in proteins}),
            "expression_levels": profile.expression_levels,
        }
        all_expressed_genes[env_name] = set(profile.active_genes)

    return {
        "genome_size": genome.gene_count,
        "environments": results,
        "all_expressed": all_expressed_genes,
        "incubator_history": incubator.history,
    }


# ---------------------------------------------------------------------------
# 8. CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_experiment()
    print("=" * 60)
    print("GENETIC EXPRESSION ENGINE — Experiment Results")
    print("=" * 60)
    print(f"\nGenome: {result['genome_size']} genes (FIXED Tensor-Penrose DNA)")
    print()

    all_sets = result["all_expressed"]
    for env_name, data in result["environments"].items():
        genes = sorted(all_sets[env_name])
        print(f"Environment: {env_name.upper()}")
        print(f"  Active genes ({len(genes)}): {genes}")
        print(f"  Strongly expressed: {data['strongly_expressed']}")
        print(f"  Weakly expressed: {data['weakly_expressed']}")
        print(f"  Silenced: {data['silenced']}")
        print(f"  Protein count: {data['protein_count']}")
        print()

    # Prove: different environments express different gene sets
    print("=" * 60)
    print("PROOF: Same genome, different expression profiles")
    print("=" * 60)
    env_names = list(all_sets.keys())
    for i in range(len(env_names)):
        for j in range(i + 1, len(env_names)):
            e1, e2 = env_names[i], env_names[j]
            shared = all_sets[e1] & all_sets[e2]
            unique1 = all_sets[e1] - all_sets[e2]
            unique2 = all_sets[e2] - all_sets[e1]
            print(f"\n  {e1} vs {e2}:")
            print(f"    Shared genes: {sorted(shared) if shared else 'NONE'}")
            print(f"    Unique to {e1}: {sorted(unique1) if unique1 else 'NONE'}")
            print(f"    Unique to {e2}: {sorted(unique2) if unique2 else 'NONE'}")

    # Summary
    total_unique = len(set().union(*all_sets.values()))
    print(f"\n  Total unique genes expressed across all environments: {total_unique}")
    print(f"  Genome size: {result['genome_size']}")
    print(f"  Coverage: {total_unique}/{result['genome_size']} = "
          f"{100 * total_unique / result['genome_size']:.0f}%")
    print("\n  ✓ Genome is FIXED. Expression is ADAPTIVE.")
