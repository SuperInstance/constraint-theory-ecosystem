"""
Test flux_tile_compression.py — H8 Thermodynamic Tile Compression

Verifies:
- Error mask distribution computed correctly
- Shannon entropy matches theory
- Huffman coding roundtrips perfectly
- Average code length within 0.2 bits of Shannon entropy
- Compression ratio 2-6x over fixed 8-bit encoding
- Convergence to entropy as sample size increases
"""

import math
import sys
import numpy as np

sys.path.insert(0, ".")

from flux_tile_compression import (
    ErrorMaskDistribution,
    TileHuffmanCoder,
    ThermodynamicCompressor,
    make_sigma_checker,
    make_bound_checker,
    run_experiment,
)


def test_error_mask_distribution_basic():
    """Basic distribution: counts, probabilities, entropy."""
    dist = ErrorMaskDistribution(n_constraints=3)
    dist.add_masks([0, 0, 0, 1, 1, 2, 3, 4, 5, 6, 7])
    assert dist.total_samples == 11

    # Mask 0 appears 3 times
    assert abs(dist.probability(0) - 3 / 11) < 1e-10
    # Mask 1 appears 2 times
    assert abs(dist.probability(1) - 2 / 11) < 1e-10

    # Shannon entropy should be > 0 (non-degenerate)
    H = dist.shannon_entropy()
    assert H > 0, f"Entropy should be positive, got {H}"
    # Max entropy for 3 bits = 3 bits (uniform over 8 symbols)
    # Here we have 8 symbols but non-uniform, so H < 3
    assert H < 3.0, f"Entropy should be < 3 bits, got {H}"

    print(f"  ✓ Basic distribution: 11 samples, {len(dist.mask_counts)} unique masks, H={H:.4f} bits")


def test_error_mask_degenerate():
    """All same mask → entropy = 0."""
    dist = ErrorMaskDistribution(n_constraints=4)
    dist.add_masks([5, 5, 5, 5])
    assert dist.shannon_entropy() == 0.0
    print("  ✓ Degenerate distribution: H=0")


def test_error_mask_uniform():
    """Uniform over all 2^n masks → entropy = n."""
    n = 3
    dist = ErrorMaskDistribution(n_constraints=n)
    for mask in range(2**n):
        dist.add_mask(mask)
    H = dist.shannon_entropy()
    assert abs(H - n) < 1e-10, f"Uniform entropy should be {n}, got {H}"
    print(f"  ✓ Uniform distribution over {2**n} masks: H={H:.4f} = {n} bits")


def test_huffman_basic():
    """Huffman coder produces valid codes and roundtrips."""
    dist = ErrorMaskDistribution(n_constraints=3)
    # Non-uniform: mask 0 very common, others rare
    for _ in range(100):
        dist.add_mask(0)
    for _ in range(10):
        dist.add_mask(1)
    for _ in range(5):
        dist.add_mask(2)
    for _ in range(1):
        dist.add_mask(3)

    coder = TileHuffmanCoder(dist)
    codes = coder.codes

    # All codes should be prefix-free (no code is prefix of another)
    code_list = list(codes.values())
    for i, c1 in enumerate(code_list):
        for j, c2 in enumerate(code_list):
            if i != j:
                assert not c2.startswith(c1), f"Prefix violation: {c1} is prefix of {c2}"

    # Most frequent symbol (0) should have shortest code
    assert len(codes[0]) <= len(codes[3]), "Most frequent should have shortest code"

    # Roundtrip
    test = [0, 1, 2, 3, 0, 0, 1]
    encoded = coder.encode(test)
    decoded = coder.decode(encoded, len(test))
    assert decoded == test, f"Roundtrip failed: {test} → {decoded}"

    print(f"  ✓ Huffman basic: codes={[codes[m] for m in [0,1,2,3]]}, roundtrip OK")


def test_huffman_single_symbol():
    """Single symbol → code '0', roundtrip works."""
    dist = ErrorMaskDistribution(n_constraints=2)
    for _ in range(100):
        dist.add_mask(1)

    coder = TileHuffmanCoder(dist)
    assert coder.codes[1] == "0"

    encoded = coder.encode([1, 1, 1])
    decoded = coder.decode(encoded, 3)
    assert decoded == [1, 1, 1]
    print("  ✓ Single symbol: code='0', roundtrip OK")


def test_thermodynamic_weights():
    """Thermodynamic weights inversely related to probability."""
    dist = ErrorMaskDistribution(n_constraints=2)
    dist.add_masks([0, 0, 0, 1])  # p(0)=0.75, p(1)=0.25

    weights = dist.thermodynamic_weights(temperature=1.0)
    # Higher probability → lower energy
    assert weights[0] < weights[1], f"w(0)={weights[0]} should be < w(1)={weights[1]}"

    # Partition function
    Z = dist.partition_function()
    assert abs(Z - 1.0) < 1e-10, f"Z should be 1.0, got {Z}"
    print(f"  ✓ Thermodynamic weights: w(0)={weights[0]:.4f} < w(1)={weights[1]:.4f}, Z={Z:.6f}")


def test_compression_report():
    """Compression report has correct fields."""
    dist = ErrorMaskDistribution(n_constraints=4)
    for m in range(16):
        for _ in range(max(1, (m + 1) * 3)):
            dist.add_mask(m)

    compressor = ThermodynamicCompressor(dist)
    report = compressor.report()

    assert report.n_constraints == 4
    assert report.n_unique_masks == 16
    assert report.shannon_entropy > 0
    assert report.avg_huffman_length > 0
    assert report.entropy_gap >= 0  # Huffman >= entropy
    assert report.compression_ratio > 0
    assert 0 < report.efficiency <= 1.0
    print(f"  ✓ Compression report: H={report.shannon_entropy:.4f}, avg={report.avg_huffman_length:.4f}, "
          f"ratio={report.compression_ratio:.2f}x, efficiency={report.efficiency:.4f}")


def test_roundtrip_integrity():
    """Full roundtrip: encode all observed masks and decode."""
    dist = ErrorMaskDistribution(n_constraints=8)
    check_fn = make_sigma_checker(8, n_sigma=1.5)
    rng = np.random.default_rng(123)

    for _ in range(5000):
        x = rng.standard_normal(8)
        violations = check_fn(x)
        mask = 0
        for i, v in enumerate(violations):
            if v:
                mask |= (1 << i)
        dist.add_mask(mask)

    compressor = ThermodynamicCompressor(dist)
    all_masks = list(dist.mask_counts.keys())

    encoded = compressor.coder.encode(all_masks)
    decoded = compressor.coder.decode(encoded, len(all_masks))
    assert decoded == all_masks, "Full roundtrip failed"
    print(f"  ✓ Roundtrip integrity: {len(all_masks)} unique masks, {len(encoded)} bits encoded")


def test_main_experiment():
    """THE KEY EXPERIMENT: 100K checks, 8 dims, Huffman within 0.2 bits of entropy."""
    report = run_experiment(n_constraints=8, n_samples=100_000, n_sigma=2.0, seed=42)

    print(f"\n{'='*60}")
    print(f"  H8 EXPERIMENT RESULTS")
    print(f"{'='*60}")
    print(f"  Constraints:     {report.n_constraints}")
    print(f"  Samples:         {report.n_samples:,}")
    print(f"  Unique masks:    {report.n_unique_masks}")
    print(f"  Shannon entropy: {report.shannon_entropy:.6f} bits")
    print(f"  Avg Huffman len: {report.avg_huffman_length:.6f} bits")
    print(f"  Entropy gap:     {report.entropy_gap:.6f} bits")
    print(f"  Fixed-bit cost:  {report.fixed_bit_cost} bits/mask")
    print(f"  Compression:     {report.compression_ratio:.2f}x (vs fixed {report.fixed_bit_cost}-bit)")
    print(f"  Theoretical max: {report.theoretical_ratio:.2f}x (at Shannon limit)")
    print(f"  Efficiency:      {report.efficiency:.6f}")
    print(f"  Within 0.2 bits: {report.entropy_within_02}")
    print(f"{'='*60}\n")

    # The critical assertions
    assert report.entropy_gap < 0.2, (
        f"FAIL: Huffman avg ({report.avg_huffman_length:.4f}) not within 0.2 bits of "
        f"Shannon entropy ({report.shannon_entropy:.4f}). Gap = {report.entropy_gap:.4f}"
    )
    assert report.compression_ratio >= 2.0, (
        f"FAIL: Compression ratio {report.compression_ratio:.2f}x < 2.0x"
    )
    assert report.compression_ratio <= 10.0, (
        f"Suspicious: ratio {report.compression_ratio:.2f}x seems too high, check experiment"
    )

    print(f"  ✅ H8 PASSED: avg code length within {report.entropy_gap:.4f} bits of entropy")
    print(f"  ✅ Compression ratio: {report.compression_ratio:.2f}x")


def test_convergence():
    """Show convergence of Huffman avg → Shannon entropy as samples increase."""
    n_constraints = 8
    rng = np.random.default_rng(42)
    check_fn = make_sigma_checker(n_constraints, n_sigma=2.0)

    # Build a big distribution to get compressor
    dist = ErrorMaskDistribution.from_constraint_checks(
        n_constraints=n_constraints, check_fn=check_fn, n_samples=1000, rng=rng,
    )
    compressor = ThermodynamicCompressor(dist)

    rng2 = np.random.default_rng(99)
    results = compressor.convergence_analysis(
        check_fn,
        sample_sizes=[500, 2000, 10000, 50000],
        rng=rng2,
    )

    print("  Convergence analysis:")
    gaps = []
    for n, H, avg in results:
        gap = avg - H
        gaps.append(gap)
        print(f"    N={n:>6}: H={H:.4f}, avg={avg:.4f}, gap={gap:.4f}")

    # Gap should generally decrease (not strictly monotonic but trend down)
    assert gaps[-1] < 0.5, f"Final gap {gaps[-1]:.4f} should be small"
    print(f"  ✓ Convergence: final gap = {gaps[-1]:.4f} bits")


def test_bound_checker():
    """Test make_bound_checker with asymmetric bounds."""
    bounds = [(-1, 1), (-2, 2), (-0.5, 0.5)]
    check_fn = make_bound_checker(bounds)

    # x = [0, 0, 0] → no violations
    assert check_fn([0, 0, 0]) == [False, False, False]

    # x = [1.5, 0, 0] → violates first
    assert check_fn([1.5, 0, 0]) == [True, False, False]

    # x = [0, 3, 0.6] → violates second and third
    assert check_fn([0, 3, 0.6]) == [False, True, True]
    print("  ✓ Bound checker works correctly")


if __name__ == "__main__":
    tests = [
        test_error_mask_distribution_basic,
        test_error_mask_degenerate,
        test_error_mask_uniform,
        test_huffman_basic,
        test_huffman_single_symbol,
        test_thermodynamic_weights,
        test_compression_report,
        test_roundtrip_integrity,
        test_bound_checker,
        test_convergence,
        test_main_experiment,
    ]

    passed = 0
    failed = 0
    for t in tests:
        name = t.__name__
        try:
            print(f"\n▶ {name}")
            t()
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  RESULTS: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    if failed:
        sys.exit(1)
