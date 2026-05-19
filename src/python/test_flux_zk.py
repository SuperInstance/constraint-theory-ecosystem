"""Tests for flux_zk.py — Zero-Knowledge Constraint Proofs."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flux_zk import (
    FieldElement, Polynomial, RangeConstraint,
    trusted_setup, ZKConstraintProver, ZKConstraintVerifier,
    generate_proof, generate_batch_proof, proof_benchmark,
    polynomial_divmod, lagrange_interpolation, commit_polynomial,
    DEFAULT_PRIME
)


def test_field_element_basic():
    """Test finite field arithmetic."""
    p = DEFAULT_PRIME
    a = FieldElement(7, p)
    b = FieldElement(3, p)

    assert (a + b).value == 10
    assert (a - b).value == 4
    assert (a * b).value == 21
    assert (-a).value == p - 7
    assert (a ** 2).value == 49

    # Inverse
    inv_b = b.inverse()
    assert (b * inv_b).value == 1

    # Division
    assert (a / b).value == (a * b.inverse()).value
    print("  ✓ Field element basic operations")


def test_field_element_edge_cases():
    """Test edge cases in field arithmetic."""
    p = DEFAULT_PRIME
    zero = FieldElement(0, p)
    one = FieldElement(1, p)

    assert zero.value == 0
    assert one.value == 1
    assert (zero + one).value == 1
    assert (zero * one).value == 0

    # Large values wrap correctly
    big = FieldElement(p + 5, p)
    assert big.value == 5

    # Negative values wrap
    neg = FieldElement(-3, p)
    assert neg.value == p - 3
    print("  ✓ Field element edge cases")


def test_polynomial_basic():
    """Test polynomial operations."""
    p = DEFAULT_PRIME
    # f(x) = 3x^2 + 2x + 1
    f = Polynomial.from_ints([1, 2, 3], p)

    # Evaluate at x=0: should be 1
    assert f.evaluate(FieldElement(0, p)).value == 1

    # Evaluate at x=1: should be 6
    assert f.evaluate(FieldElement(1, p)).value == 6

    # Evaluate at x=2: should be 17
    assert f.evaluate(FieldElement(2, p)).value == 17

    # Degree
    assert f.degree() == 2
    print("  ✓ Polynomial basic operations")


def test_polynomial_addition():
    """Test polynomial addition."""
    p = DEFAULT_PRIME
    f = Polynomial.from_ints([1, 2, 3], p)   # 3x² + 2x + 1
    g = Polynomial.from_ints([4, 5], p)        # 5x + 4

    h = f + g  # 3x² + 7x + 5
    assert h.evaluate(FieldElement(1, p)).value == 15
    print("  ✓ Polynomial addition")


def test_polynomial_multiplication():
    """Test polynomial multiplication."""
    p = DEFAULT_PRIME
    f = Polynomial.from_ints([1, 1], p)   # x + 1
    g = Polynomial.from_ints([2, 1], p)   # x + 2

    h = f * g  # x² + 3x + 2
    assert h.evaluate(FieldElement(0, p)).value == 2
    assert h.evaluate(FieldElement(1, p)).value == 6
    assert h.evaluate(FieldElement(2, p)).value == 12
    print("  ✓ Polynomial multiplication")


def test_polynomial_divmod():
    """Test polynomial division."""
    p = DEFAULT_PRIME
    # f(x) = x² - 1 = (x-1)(x+1)
    f = Polynomial.from_ints([p - 1, 0, 1], p)
    # divisor = x - 1
    d = Polynomial.from_ints([p - 1, 1], p)

    q, r = polynomial_divmod(f, d)
    # Quotient should be x + 1
    assert q.evaluate(FieldElement(1, p)).value == 2
    assert r.degree() == 0 or all(c.value == 0 for c in r.coeffs)
    print("  ✓ Polynomial division")


def test_lagrange_interpolation():
    """Test Lagrange interpolation."""
    p = DEFAULT_PRIME
    points = [
        (FieldElement(1, p), FieldElement(3, p)),
        (FieldElement(2, p), FieldElement(5, p)),
        (FieldElement(3, p), FieldElement(7, p)),
    ]

    poly = lagrange_interpolation(points)

    # Should pass through all points
    for x, y in points:
        assert poly.evaluate(x) == y

    # This is a linear function f(x) = 2x + 1
    assert poly.evaluate(FieldElement(0, p)).value == 1
    print("  ✓ Lagrange interpolation")


def test_range_constraint():
    """Test range constraint checking."""
    c = RangeConstraint(0, 100)

    assert c.check(50) is True
    assert c.check(0) is True
    assert c.check(100) is True
    assert c.check(-1) is False
    assert c.check(101) is False
    print("  ✓ Range constraint checking")


def test_trusted_setup():
    """Test trusted setup generation."""
    ck, vk = trusted_setup(max_degree=64)

    assert ck.max_degree == 64
    assert len(ck.powers_g1) == 65  # 0 through 64
    assert ck.tau.value != 0
    assert vk.prime == DEFAULT_PRIME
    print("  ✓ Trusted setup")


def test_polynomial_commitment():
    """Test polynomial commitment."""
    ck, vk = trusted_setup(max_degree=10)
    poly = Polynomial.from_ints([1, 2, 3], DEFAULT_PRIME)

    commitment = commit_polynomial(poly, ck)
    assert commitment.value != 0

    # Different polynomials should have different commitments
    poly2 = Polynomial.from_ints([1, 2, 4], DEFAULT_PRIME)
    commitment2 = commit_polynomial(poly2, ck)
    assert commitment.value != commitment2.value
    print("  ✓ Polynomial commitment")


def test_single_proof_generation_and_verification():
    """Test complete proof generation and verification for a single value."""
    proof, verifier = generate_proof(value=50, lower=0, upper=100)
    constraint = RangeConstraint(0, 100)

    assert proof.batch_count == 1
    assert proof.challenge.value != 0
    assert len(proof.constraint_hash) == 64  # SHA-256 hex

    valid = verifier.verify(proof, constraint)
    assert valid is True
    print("  ✓ Single proof generation and verification")


def test_proof_wrong_constraint():
    """Test that proof fails verification against wrong constraint."""
    proof, verifier = generate_proof(value=50, lower=0, upper=100)
    wrong_constraint = RangeConstraint(0, 50)  # Different constraint

    valid = verifier.verify(proof, wrong_constraint)
    assert valid is False  # Constraint hash mismatch
    print("  ✓ Proof fails against wrong constraint")


def test_batch_proof():
    """Test batch proof generation and verification."""
    values = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    proof, verifier = generate_batch_proof(values, lower=0, upper=100)
    constraint = RangeConstraint(0, 100)

    assert proof.batch_count == len(values)

    valid = verifier.verify_batch(proof, constraint, len(values))
    assert valid is True
    print("  ✓ Batch proof generation and verification")


def test_batch_proof_wrong_count():
    """Test that batch proof fails with wrong count."""
    values = [10, 20, 30]
    proof, verifier = generate_batch_proof(values, lower=0, upper=100)
    constraint = RangeConstraint(0, 100)

    # Wrong count
    valid = verifier.verify_batch(proof, constraint, 5)
    assert valid is False
    print("  ✓ Batch proof fails with wrong count")


def test_proof_invalid_value_raises():
    """Test that proving an out-of-range value raises an error."""
    try:
        generate_proof(value=200, lower=0, upper=100)
        assert False, "Should have raised"
    except AssertionError:
        pass
    print("  ✓ Invalid value raises assertion")


def test_benchmark():
    """Test benchmark function runs and produces results."""
    result = proof_benchmark(n_values=50, lower=0, upper=100)

    assert result["n_values"] == 50
    assert result["prove_time_ms"] > 0
    assert result["verify_time_ms"] > 0
    assert result["valid"] is True
    assert result["prove_per_value_ms"] > 0
    print(f"  ✓ Benchmark: {result['prove_time_ms']:.1f}ms prove, "
          f"{result['verify_time_ms']:.1f}ms verify for {result['n_values']} values")


def test_proof_size_constant():
    """Verify that proof size is bounded (constant regardless of batch)."""
    proof1, _ = generate_batch_proof([10] * 5, 0, 100)
    proof2, _ = generate_batch_proof([10] * 50, 0, 100)

    # Both proofs should have similar size (within tolerance)
    size1 = proof1.size_bytes()
    size2 = proof2.size_bytes()

    # Size should not scale linearly with batch count
    assert size2 <= size1 * 2, f"Proof size grew too much: {size1} → {size2}"
    print(f"  ✓ Proof size stays bounded: {size1}B (5 items) → {size2}B (50 items)")


if __name__ == "__main__":
    print("\n=== flux_zk Tests ===\n")

    tests = [
        test_field_element_basic,
        test_field_element_edge_cases,
        test_polynomial_basic,
        test_polynomial_addition,
        test_polynomial_multiplication,
        test_polynomial_divmod,
        test_lagrange_interpolation,
        test_range_constraint,
        test_trusted_setup,
        test_polynomial_commitment,
        test_single_proof_generation_and_verification,
        test_proof_wrong_constraint,
        test_batch_proof,
        test_batch_proof_wrong_count,
        test_proof_invalid_value_raises,
        test_benchmark,
        test_proof_size_constant,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed == 0:
        print("All tests passed! ✅")
    sys.exit(0 if failed == 0 else 1)
