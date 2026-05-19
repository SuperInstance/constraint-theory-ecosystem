"""
flux_tile_compression.py — Thermodynamic Tile Compression (H8 Experiment)

Hypothesis: PLATO tiles can be compressed using the thermodynamic distribution
of error masks. High-probability violation patterns get short codes via Huffman
coding on the partition function.

This proves: "The information content of a tile is bounded by the thermodynamic
entropy of the constraint system."

Provides:
- ErrorMaskDistribution — empirical distribution from constraint checks
- TileHuffmanCoder — compress/decompress procedure tiles
- ThermodynamicCompressor — theoretical bounds and verification

Author: Forgemaster ⚒️ (Constraint Theory Ecosystem)
"""

from __future__ import annotations

import heapq
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

import numpy as np
from numpy.typing import NDArray


# =============================================================================
# 1. ErrorMaskDistribution — empirical error mask frequencies
# =============================================================================

@dataclass
class ErrorMaskDistribution:
    """
    Empirical distribution of error masks from N constraint checks.

    An error mask is a binary vector where bit i = 1 if constraint i is violated.
    The distribution encodes which violation patterns are thermodynamically
    probable (low energy) vs improbable (high energy).
    """
    n_constraints: int
    mask_counts: Counter = field(default_factory=Counter)
    total_samples: int = 0

    def add_mask(self, mask: int) -> None:
        """Record one error mask observation."""
        self.mask_counts[mask] += 1
        self.total_samples += 1

    def add_masks(self, masks: Sequence[int]) -> None:
        """Record multiple error mask observations."""
        for m in masks:
            self.mask_counts[m] += 1
            self.total_samples += 1

    def probability(self, mask: int) -> float:
        """Empirical probability of a given error mask."""
        if self.total_samples == 0:
            return 0.0
        return self.mask_counts[mask] / self.total_samples

    def probabilities(self) -> Dict[int, float]:
        """Full probability distribution."""
        if self.total_samples == 0:
            return {}
        return {m: c / self.total_samples for m, c in self.mask_counts.items()}

    def shannon_entropy(self) -> float:
        """
        Shannon entropy H = -Σ p_i log2(p_i) in bits.
        This is the theoretical minimum average code length.
        """
        if self.total_samples == 0:
            return 0.0
        H = 0.0
        for count in self.mask_counts.values():
            if count > 0:
                p = count / self.total_samples
                H -= p * math.log2(p)
        return H

    def thermodynamic_weights(self, temperature: float = 1.0) -> Dict[int, float]:
        """
        Thermodynamic weights from the partition function Z.
        w_i = -temperature * ln(p_i), proportional to Boltzmann factor.
        """
        probs = self.probabilities()
        weights = {}
        for mask, p in probs.items():
            if p > 0:
                weights[mask] = -temperature * math.log(p)
            else:
                weights[mask] = float('inf')
        return weights

    def partition_function(self, temperature: float = 1.0) -> float:
        """Z = Σ exp(-E_i / T) where E_i = -T·ln(p_i)."""
        probs = self.probabilities()
        Z = 0.0
        for p in probs.values():
            if p > 0:
                Z += p  # With our energy definition, exp(-E/T) = p
        return Z

    def mask_to_bits(self, mask: int) -> str:
        """Convert integer mask to binary string of length n_constraints."""
        return format(mask, f'0{self.n_constraints}b')

    @classmethod
    def from_constraint_checks(
        cls,
        n_constraints: int,
        check_fn,
        n_samples: int = 100_000,
        rng: Optional[np.random.Generator] = None,
    ) -> "ErrorMaskDistribution":
        """
        Build distribution by running constraint checks on random inputs.

        Parameters
        ----------
        n_constraints : int
            Number of constraints (bits in error mask).
        check_fn : callable
            Function that takes a vector and returns a boolean list/array
            of length n_constraints (True = violated).
        n_samples : int
            Number of random samples to check.
        rng : optional Generator
            Numpy random generator for reproducibility.

        Returns
        -------
        ErrorMaskDistribution
        """
        if rng is None:
            rng = np.random.default_rng(42)

        dist = cls(n_constraints=n_constraints)
        dim = n_constraints  # one constraint per dimension

        for _ in range(n_samples):
            x = rng.standard_normal(dim)
            violations = check_fn(x)
            # Pack boolean violations into integer mask
            mask = 0
            for i, v in enumerate(violations):
                if v:
                    mask |= (1 << i)
            dist.add_mask(mask)

        return dist


# =============================================================================
# 2. TileHuffmanCoder — Huffman coding for procedure tiles
# =============================================================================

@dataclass(order=True)
class _HuffmanNode:
    """Internal node for Huffman tree construction."""
    sort_key: float
    symbol: Optional[int] = field(default=None, compare=False)
    left: Optional["_HuffmanNode"] = field(default=None, compare=False)
    right: Optional["_HuffmanNode"] = field(default=None, compare=False)


class TileHuffmanCoder:
    """
    Compresses procedure tiles using Huffman coding derived from
    the thermodynamic error mask distribution.

    Each procedure step maps to an error mask; high-probability masks
    (low-energy violations) get shorter codes.
    """

    def __init__(self, distribution: ErrorMaskDistribution):
        self._dist = distribution
        self._codes: Dict[int, str] = {}
        self._decode_tree: Optional[_HuffmanNode] = None
        self._build_tree()

    def _build_tree(self) -> None:
        """Build Huffman tree from the error mask distribution."""
        probs = self._dist.probabilities()

        if not probs:
            # Degenerate: no data
            self._codes = {}
            return

        if len(probs) == 1:
            # Single symbol: code is "0"
            sym = next(iter(probs))
            self._codes[sym] = "0"
            self._decode_tree = _HuffmanNode(sort_key=0, symbol=sym)
            return

        # Build priority queue of leaf nodes
        heap: List[_HuffmanNode] = []
        for mask, prob in probs.items():
            heapq.heappush(heap, _HuffmanNode(sort_key=prob, symbol=mask))

        # Merge two smallest until one tree remains
        while len(heap) > 1:
            left = heapq.heappop(heap)
            right = heapq.heappop(heap)
            merged = _HuffmanNode(
                sort_key=left.sort_key + right.sort_key,
                left=left,
                right=right,
            )
            heapq.heappush(heap, merged)

        self._decode_tree = heap[0]

        # Extract codes by walking the tree
        self._codes = {}
        self._walk(self._decode_tree, "")

    def _walk(self, node: _HuffmanNode, prefix: str) -> None:
        """Recursively walk tree to extract Huffman codes."""
        if node.symbol is not None:
            self._codes[node.symbol] = prefix if prefix else "0"
            return
        if node.left:
            self._walk(node.left, prefix + "0")
        if node.right:
            self._walk(node.right, prefix + "1")

    @property
    def codes(self) -> Dict[int, str]:
        """Mapping from error mask → Huffman code."""
        return dict(self._codes)

    def encode(self, masks: Sequence[int]) -> str:
        """Encode a sequence of error masks into a bitstream string."""
        bits = []
        for m in masks:
            if m not in self._codes:
                raise ValueError(f"Mask {m} ({self._dist.mask_to_bits(m)}) not in distribution")
            bits.append(self._codes[m])
        return "".join(bits)

    def decode(self, bitstream: str, n_symbols: int) -> List[int]:
        """Decode a bitstream back into a sequence of error masks."""
        if self._decode_tree is None:
            raise ValueError("No decode tree (empty distribution)")

        result = []
        node = self._decode_tree

        # Handle single-symbol tree
        if self._decode_tree.symbol is not None:
            return [self._decode_tree.symbol] * n_symbols

        for bit in bitstream:
            if bit == "0":
                node = node.left
            else:
                node = node.right

            if node is None:
                raise ValueError(f"Invalid bitstream at position {len(result)}")

            if node.symbol is not None:
                result.append(node.symbol)
                node = self._decode_tree
                if len(result) == n_symbols:
                    break

        if len(result) != n_symbols:
            raise ValueError(
                f"Decoded {len(result)} symbols, expected {n_symbols}"
            )

        return result

    def average_code_length(self) -> float:
        """Expected code length in bits per symbol."""
        if self._dist.total_samples == 0:
            return 0.0
        total = 0.0
        for mask, code in self._codes.items():
            p = self._dist.probability(mask)
            total += p * len(code)
        return total

    def max_code_length(self) -> int:
        """Maximum code length in the Huffman table."""
        if not self._codes:
            return 0
        return max(len(c) for c in self._codes.values())


# =============================================================================
# 3. ThermodynamicCompressor — theoretical bounds & verification
# =============================================================================

@dataclass
class CompressionReport:
    """Complete compression analysis report."""
    n_constraints: int
    n_samples: int
    n_unique_masks: int
    shannon_entropy: float       # H in bits — theoretical minimum
    avg_huffman_length: float    # Actual Huffman average
    entropy_gap: float           # avg_huffman_length - shannon_entropy
    fixed_bit_cost: int          # n_constraints bits per mask (uncompressed)
    compression_ratio: float     # fixed_bit_cost / avg_huffman_length
    theoretical_ratio: float     # fixed_bit_cost / shannon_entropy
    efficiency: float            # shannon_entropy / avg_huffman_length (should be ~1.0)
    entropy_within_02: bool      # Is gap < 0.2 bits?


class ThermodynamicCompressor:
    """
    Theoretical compression bounds based on thermodynamic entropy.

    Core theorem:
        Minimum tile size = Shannon entropy of the error mask distribution.
        Huffman coding achieves average code length < H + 1.
        As sample size → ∞, avg code length → H.

    This proves the information content of a tile is bounded by the
    thermodynamic entropy of the constraint system.
    """

    def __init__(self, distribution: ErrorMaskDistribution):
        self._dist = distribution
        self._coder = TileHuffmanCoder(distribution)

    @property
    def distribution(self) -> ErrorMaskDistribution:
        return self._dist

    @property
    def coder(self) -> TileHuffmanCoder:
        return self._coder

    def report(self) -> CompressionReport:
        """Generate a full compression analysis report."""
        H = self._dist.shannon_entropy()
        avg_len = self._coder.average_code_length()
        fixed = self._dist.n_constraints

        return CompressionReport(
            n_constraints=self._dist.n_constraints,
            n_samples=self._dist.total_samples,
            n_unique_masks=len(self._dist.mask_counts),
            shannon_entropy=H,
            avg_huffman_length=avg_len,
            entropy_gap=avg_len - H,
            fixed_bit_cost=fixed,
            compression_ratio=fixed / avg_len if avg_len > 0 else float('inf'),
            theoretical_ratio=fixed / H if H > 0 else float('inf'),
            efficiency=H / avg_len if avg_len > 0 else 0.0,
            entropy_within_02=(avg_len - H) < 0.2,
        )

    def verify_roundtrip(self, test_masks: Sequence[int]) -> bool:
        """Verify encode → decode roundtrip integrity."""
        encoded = self._coder.encode(test_masks)
        decoded = self._coder.decode(encoded, len(test_masks))
        return list(test_masks) == decoded

    def convergence_analysis(
        self,
        check_fn,
        sample_sizes: Sequence[int] = (1000, 5000, 10000, 50000, 100000),
        rng: Optional[np.random.Generator] = None,
    ) -> List[Tuple[int, float, float]]:
        """
        Show that Huffman average length converges to Shannon entropy
        as sample size increases.

        Returns list of (n_samples, shannon_entropy, avg_huffman_length).
        """
        if rng is None:
            rng = np.random.default_rng(42)

        results = []
        # Pre-generate all samples
        max_n = max(sample_sizes)
        dim = self._dist.n_constraints
        all_masks = []
        for _ in range(max_n):
            x = rng.standard_normal(dim)
            violations = check_fn(x)
            mask = 0
            for i, v in enumerate(violations):
                if v:
                    mask |= (1 << i)
            all_masks.append(mask)

        for n in sample_sizes:
            sub_dist = ErrorMaskDistribution(n_constraints=self._dist.n_constraints)
            sub_dist.add_masks(all_masks[:n])
            compressor = ThermodynamicCompressor(sub_dist)
            r = compressor.report()
            results.append((n, r.shannon_entropy, r.avg_huffman_length))

        return results


# =============================================================================
# 4. Built-in constraint checkers for experiments
# =============================================================================

def make_bound_checker(bounds: Sequence[Tuple[float, float]]):
    """
    Create a constraint checker from a list of (lo, hi) bounds.
    Violation = value outside [lo, hi].
    """
    def check(x):
        violations = []
        for i, (lo, hi) in enumerate(bounds):
            violations.append(x[i] < lo or x[i] > hi)
        return violations
    return check


def make_sigma_checker(n_dims: int, n_sigma: float = 2.0):
    """
    Constraint checker: each dimension must be within n_sigma standard devs.
    With standard normal input, this is a tight bound that produces
    non-trivial error mask distributions.
    """
    lo, hi = -n_sigma, n_sigma
    def check(x):
        return [xi < lo or xi > hi for xi in x]
    return check


# =============================================================================
# 5. Experiment runner
# =============================================================================

def run_experiment(
    n_constraints: int = 8,
    n_samples: int = 100_000,
    n_sigma: float = 2.0,
    seed: int = 42,
) -> CompressionReport:
    """
    Run the full H8 thermodynamic tile compression experiment.

    1. Generate N constraint checks on random Gaussian vectors
    2. Compute error mask distribution
    3. Huffman encode
    4. Verify average code length within 0.2 bits of Shannon entropy
    5. Report compression ratio vs fixed 8-bit encoding
    """
    rng = np.random.default_rng(seed)
    check_fn = make_sigma_checker(n_constraints, n_sigma)

    dist = ErrorMaskDistribution.from_constraint_checks(
        n_constraints=n_constraints,
        check_fn=check_fn,
        n_samples=n_samples,
        rng=rng,
    )

    compressor = ThermodynamicCompressor(dist)
    report = compressor.report()

    # Verify roundtrip
    test_masks = list(dist.mask_counts.keys())[:20]
    if test_masks:
        assert compressor.verify_roundtrip(test_masks), "Roundtrip verification failed!"

    return report
