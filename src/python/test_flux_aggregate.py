"""Tests for flux_aggregate.py — Proof Aggregation."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from flux_aggregate import (
    AggregateKeyPair, ConstraintDef, ConstraintCheckProof,
    ProofAggregator, AggregateProof, AggregationPipeline,
    multi_party_aggregate, multi_party_aggregate, aggregate_benchmark,
    AGGREGATE_PROOF_SIZE
)


def test_key_generation():
    """Test aggregate key pair generation."""
    key1 = AggregateKeyPair.generate(seed=b"test1")
    key2 = AggregateKeyPair.generate(seed=b"test2")

    assert key1.private_key != key2.private_key
    assert key1.public_key != key2.public_key
    assert len(key1.private_key) == 32
    assert len(key1.public_key) == 32
    print("  ✓ Key generation")


def test_key_deterministic():
    """Test that same seed produces same key."""
    key1 = AggregateKeyPair.generate(seed=b"deterministic")
    key2 = AggregateKeyPair.generate(seed=b"deterministic")

    assert key1.private_key == key2.private_key
    assert key1.public_key == key2.public_key
    print("  ✓ Key determinism")


def test_constraint_def():
    """Test constraint definition."""
    c = ConstraintDef("temperature", lower=-40, upper=85, unit="celsius")

    assert c.check(20) is True
    assert c.check(-40) is True
    assert c.check(85) is True
    assert c.check(-41) is False
    assert c.check(86) is False

    # Hash is deterministic
    assert c.hash() == c.hash()
    print("  ✓ Constraint definition")


def test_sign_single_check():
    """Test signing a single constraint check."""
    key = AggregateKeyPair.generate(seed=b"sign_test")
    agg = ProofAggregator(key)
    constraint = ConstraintDef("pressure", 0, 100, "psi")

    proof = agg.sign_check("check_001", 50.0, constraint)

    assert proof.check_id == "check_001"
    assert len(proof.signature) == 32
    assert len(proof.value_hash) == 32
    assert proof.constraint_hash == constraint.hash()
    print("  ✓ Single check signing")


def test_sign_fails_for_invalid():
    """Test that signing a failing check raises an error."""
    agg = ProofAggregator()
    constraint = ConstraintDef("temperature", 0, 100, "celsius")

    try:
        agg.sign_check("check_bad", 200.0, constraint)
        assert False, "Should have raised"
    except AssertionError as e:
        assert "Cannot sign failing check" in str(e)
    print("  ✓ Signing fails for invalid checks")


def test_aggregate_basic():
    """Test basic proof aggregation."""
    agg = ProofAggregator(AggregateKeyPair.generate(seed=b"agg_test"))
    constraint = ConstraintDef("temp", 0, 100, "celsius")

    # Sign 5 checks
    for i in range(5):
        proof = agg.sign_check(f"check_{i:03d}", float(i * 20), constraint)
        agg.add_proof(proof)

    result = agg.aggregate()

    assert result.proof_count == 5
    assert len(result.aggregate_signature) == 32
    assert len(result.merkle_root) == 32
    assert len(result.challenge) == 32
    print("  ✓ Basic aggregation")


def test_aggregate_verify_with_proofs():
    """Test aggregate verification with individual proofs."""
    agg = ProofAggregator(AggregateKeyPair.generate(seed=b"verify_test"))
    constraint = ConstraintDef("humidity", 0, 100, "percent")

    for i in range(10):
        proof = agg.sign_check(f"h_check_{i:03d}", float(50 + i), constraint)
        agg.add_proof(proof)

    result = agg.aggregate()

    # Full verification with individual proofs
    assert result.verify() is True

    # With constraint definitions
    constraints = {f"h_check_{i:03d}": constraint for i in range(10)}
    assert result.verify(constraint_defs=constraints) is True
    print("  ✓ Aggregate verification with proofs")


def test_aggregate_verify_without_proofs():
    """Test aggregate verification without individual proofs (structural only)."""
    agg = ProofAggregator(AggregateKeyPair.generate(seed=b"struct_test"))
    constraint = ConstraintDef("temp", 0, 100, "celsius")

    for i in range(3):
        proof = agg.sign_check(f"check_{i}", float(30 + i), constraint)
        agg.add_proof(proof)

    result = agg.aggregate()
    assert result.verify_without_proofs() is True
    print("  ✓ Structural verification without proofs")


def test_aggregate_tamper_detection():
    """Test that tampering with the aggregate is detected."""
    agg = ProofAggregator(AggregateKeyPair.generate(seed=b"tamper_test"))
    constraint = ConstraintDef("temp", 0, 100, "celsius")

    for i in range(5):
        proof = agg.sign_check(f"t_{i}", float(i * 20), constraint)
        agg.add_proof(proof)

    result = agg.aggregate()

    # Tamper with merkle root
    tampered = AggregateProof(
        aggregate_signature=result.aggregate_signature,
        merkle_root=b'\x00' * 32,  # Tampered!
        value_commitment=result.value_commitment,
        challenge=result.challenge,
        public_key=result.public_key,
        proof_count=result.proof_count,
        timestamp=result.timestamp,
        _individual_proofs=result._individual_proofs,
    )
    assert tampered.verify() is False
    print("  ✓ Tamper detection")


def test_aggregate_wrong_constraint_defs():
    """Test that wrong constraint definitions fail verification."""
    agg = ProofAggregator(AggregateKeyPair.generate(seed=b"wrong_c"))
    constraint = ConstraintDef("temp", 0, 100, "celsius")

    for i in range(3):
        proof = agg.sign_check(f"w_{i}", float(i * 30), constraint)
        agg.add_proof(proof)

    result = agg.aggregate()

    # Use different constraint for verification
    wrong_constraint = ConstraintDef("temp", 0, 50, "celsius")
    wrong_defs = {f"w_{i}": wrong_constraint for i in range(3)}
    assert result.verify(constraint_defs=wrong_defs) is False
    print("  ✓ Wrong constraint detection")


def test_constant_proof_size():
    """Test that aggregate proof size is constant regardless of batch size."""
    key = AggregateKeyPair.generate(seed=b"size_test")

    # Small batch
    agg1 = ProofAggregator(AggregateKeyPair.generate(seed=b"size_small"))
    constraint = ConstraintDef("temp", 0, 100, "celsius")
    for i in range(10):
        agg1.sign_and_aggregate([(f"s_{i}", float(i * 10), constraint)])

    # Clear pending from sign_and_aggregate (it returns aggregate with 1 proof)
    # Let's do it properly
    agg_small = ProofAggregator(key)
    for i in range(10):
        proof = agg_small.sign_check(f"s_{i}", float(i * 10), constraint)
        agg_small.add_proof(proof)
    result_small = agg_small.aggregate()

    # Large batch
    agg_large = ProofAggregator(key)
    for i in range(100):
        proof = agg_large.sign_check(f"l_{i}", float(i % 100), constraint)
        agg_large.add_proof(proof)
    result_large = agg_large.aggregate()

    # Both should report the same constant size
    assert result_small.size_bytes() == AGGREGATE_PROOF_SIZE
    assert result_large.size_bytes() == AGGREGATE_PROOF_SIZE
    assert result_small.size_bytes() == result_large.size_bytes()
    print(f"  ✓ Constant proof size: {AGGREGATE_PROOF_SIZE}B for both 10 and 100 checks")


def test_sign_and_aggregate():
    """Test one-shot sign-and-aggregate."""
    agg = ProofAggregator()
    constraint = ConstraintDef("voltage", 0, 240, "volts")

    checks = [
        ("v_001", 120.0, constraint),
        ("v_002", 115.0, constraint),
        ("v_003", 118.5, constraint),
    ]

    result = agg.sign_and_aggregate(checks)

    assert result.proof_count == 3
    assert result.verify() is True
    print("  ✓ One-shot sign and aggregate")


def test_aggregation_pipeline():
    """Test streaming aggregation pipeline."""
    key = AggregateKeyPair.generate(seed=b"pipeline_test")
    pipeline = AggregationPipeline(key=key, batch_size=5)
    constraint = ConstraintDef("pressure", 0, 100, "psi")

    # Submit 12 checks (should produce 2 batches + 2 remaining)
    aggregates = []
    for i in range(12):
        result = pipeline.submit(f"p_{i:03d}", float(40 + i), constraint)
        if result is not None:
            aggregates.append(result)

    # Flush remaining
    final = pipeline.flush()
    if final is not None:
        aggregates.append(final)

    assert pipeline.total_proofs() == 12
    assert len(aggregates) == 3  # 5 + 5 + 2
    assert all(a.verify() for a in aggregates)

    total_checks = sum(a.proof_count for a in aggregates)
    assert total_checks == 12
    print("  ✓ Aggregation pipeline (3 batches from 12 checks)")


def test_empty_aggregation_raises():
    """Test that aggregating with no proofs raises an error."""
    agg = ProofAggregator()
    try:
        agg.aggregate()
        assert False, "Should have raised"
    except ValueError as e:
        assert "No proofs" in str(e)
    print("  ✓ Empty aggregation raises ValueError")


def test_multi_party_aggregation():
    """Test multi-party aggregation from multiple provers."""
    # 3 provers, each with their own key
    prover1_key = AggregateKeyPair.generate(seed=b"prover1")
    prover2_key = AggregateKeyPair.generate(seed=b"prover2")
    prover3_key = AggregateKeyPair.generate(seed=b"prover3")

    constraint = ConstraintDef("sensor", 0, 100, "units")

    agg1 = ProofAggregator(prover1_key)
    for i in range(5):
        agg1.add_proof(agg1.sign_check(f"p1_{i}", float(i * 20), constraint))
    result1 = agg1.aggregate()

    agg2 = ProofAggregator(prover2_key)
    for i in range(5):
        agg2.add_proof(agg2.sign_check(f"p2_{i}", float(i * 15), constraint))
    result2 = agg2.aggregate()

    agg3 = ProofAggregator(prover3_key)
    for i in range(5):
        agg3.add_proof(agg3.sign_check(f"p3_{i}", float(i * 10), constraint))
    result3 = agg3.aggregate()

    # Multi-party aggregate
    multi = multi_party_aggregate([
        (result1, prover1_key.public_key),
        (result2, prover2_key.public_key),
        (result3, prover3_key.public_key),
    ])

    assert multi.signer_count == 3
    assert multi.total_checks == 15
    assert multi.size_bytes() == AGGREGATE_PROOF_SIZE

    # Verify with sub-commitments (how multi_party_aggregate builds the merkle root)
    sub_commitments = [
        (result1.merkle_root, result1.value_commitment),
        (result2.merkle_root, result2.value_commitment),
        (result3.merkle_root, result3.value_commitment),
    ]
    assert multi.verify(keys, sub_commitments=sub_commitments) is True

    # Wrong number of keys
    assert multi.verify(keys[:2], sub_commitments=sub_commitments[:2]) is False
    print("  ✓ Multi-party aggregation (3 provers, 15 checks)")


def test_merkle_root():
    """Test Merkle root computation."""
    hashes = [b'\x01' * 32, b'\x02' * 32, b'\x03' * 32]
    root1 = ProofAggregator._compute_merkle_root(hashes)
    root2 = ProofAggregator._compute_merkle_root(hashes)

    # Deterministic
    assert root1 == root2

    # Different inputs → different roots
    different_hashes = [b'\x04' * 32, b'\x05' * 32, b'\x06' * 32]
    root3 = ProofAggregator._compute_merkle_root(different_hashes)
    assert root1 != root3
    print("  ✓ Merkle root computation")


def test_benchmark():
    """Test aggregation benchmark."""
    result = aggregate_benchmark(n_checks=100, n_constraints=3)

    assert result["n_checks"] == 100
    assert result["aggregate_time_ms"] > 0
    assert result["verify_time_ms"] > 0
    assert result["valid"] is True
    assert result["constant_size"] is True
    assert result["proof_size_bytes"] == AGGREGATE_PROOF_SIZE

    print(f"  ✓ Benchmark: {result['aggregate_time_ms']:.1f}ms aggregate, "
          f"{result['verify_time_ms']:.2f}ms verify for {result['n_checks']} checks, "
          f"{result['per_check_ms']:.2f}ms/check")


if __name__ == "__main__":
    print("\n=== flux_aggregate Tests ===\n")

    tests = [
        test_key_generation,
        test_key_deterministic,
        test_constraint_def,
        test_sign_single_check,
        test_sign_fails_for_invalid,
        test_aggregate_basic,
        test_aggregate_verify_with_proofs,
        test_aggregate_verify_without_proofs,
        test_aggregate_tamper_detection,
        test_aggregate_wrong_constraint_defs,
        test_constant_proof_size,
        test_sign_and_aggregate,
        test_aggregation_pipeline,
        test_empty_aggregation_raises,
        test_multi_party_aggregation,
        test_merkle_root,
        test_benchmark,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed == 0:
        print("All tests passed! ✅")
    sys.exit(0 if failed == 0 else 1)
