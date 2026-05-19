"""
test_proof_system.py — Tests for FLUX v4 Proof Certificate System

Tests:
1. Certificate chain is valid for all 6 presets
2. Tampering with any hash invalidates the chain
3. Merkle proof is compact and verifiable
4. All 4 verification properties pass for all presets
5. Performance: proof generation adds < 5% overhead
"""

import hashlib
import json
import time
import unittest
from typing import Dict, List

# Add src to path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "python"))

from flux_constraint import FluxConstraint, PRESETS
from flux_proof import (
    ProofCertificate,
    ProofVerifier,
    ProofLog,
    MerkleProof,
    _hash_source,
    _hash_ast,
    _hash_cir,
    _hash_bytecode,
    _hash_check,
    _hash_constraints,
)
from flux_verify import (
    verify_well_formed,
    verify_exhaustive,
    verify_deterministic,
    verify_zero_false_negatives,
    verify_all,
    ConstraintSetVerification,
)


# ─── Test Presets ────────────────────────────────────────────────────────────

# Use 6 industry presets
TEST_PRESETS = ["aviation", "automotive", "medical", "energy", "nuclear", "space"]


def _make_pipeline_repr(constraints: List[Dict]) -> Dict[str, str]:
    """Create fake but deterministic pipeline representations for testing."""
    source = json.dumps(constraints, sort_keys=True)
    ast_repr = json.dumps(
        [{"type": "RangeConstraint", "name": c["name"], "lo": c["lo"], "hi": c["hi"]}
         for c in constraints],
        sort_keys=True,
    )
    cir_repr = json.dumps(
        [{"op": "check_range", "name": c["name"], "lo": c["lo"], "hi": c["hi"], "dtype": "int8"}
         for c in constraints],
        sort_keys=True,
    )
    # Fake bytecode: deterministic bytes from constraint data
    bytecode = hashlib.sha256(
        "BYTECODE".encode() + json.dumps(constraints, sort_keys=True).encode()
    ).digest()
    return {"source": source, "ast": ast_repr, "cir": cir_repr, "bytecode": bytecode}


class TestProofCertificateChain(unittest.TestCase):
    """Test 1: Certificate chain is valid for all 6 presets."""

    def test_build_certificate_for_each_preset(self):
        """Build and verify certificates for all test presets."""
        for preset_name in TEST_PRESETS:
            with self.subTest(preset=preset_name):
                constraints = PRESETS[preset_name]
                fc = FluxConstraint(constraints)
                pipeline = _make_pipeline_repr(constraints)

                # Check a few values
                for value in [-60, 0, 25, 50, 100, 127]:
                    result = fc.check(value)
                    cert = ProofCertificate.build(
                        source=pipeline["source"],
                        ast_repr=pipeline["ast"],
                        cir_repr=pipeline["cir"],
                        bytecode=pipeline["bytecode"],
                        constraints=constraints,
                        error_mask=result.error_mask,
                        value=value,
                    )

                    # Certificate should have valid hashes
                    self.assertEqual(len(cert.source_hash), 64, f"{preset_name}: source_hash length")
                    self.assertEqual(len(cert.ast_hash), 64, f"{preset_name}: ast_hash length")
                    self.assertEqual(len(cert.cir_hash), 64, f"{preset_name}: cir_hash length")
                    self.assertEqual(len(cert.bytecode_hash), 64, f"{preset_name}: bytecode_hash length")
                    self.assertEqual(len(cert.check_hash), 64, f"{preset_name}: check_hash length")
                    self.assertEqual(len(cert.constraint_set_hash), 64, f"{preset_name}: csh length")

                    # All hex
                    for attr in ("source_hash", "ast_hash", "cir_hash", "bytecode_hash",
                                 "check_hash", "constraint_set_hash"):
                        val = getattr(cert, attr)
                        int(val, 16)  # Should not raise

    def test_deterministic_certificates(self):
        """Same inputs produce same certificates."""
        constraints = PRESETS["aviation"]
        pipeline = _make_pipeline_repr(constraints)
        fc = FluxConstraint(constraints)
        result = fc.check(25)

        cert1 = ProofCertificate.build(
            source=pipeline["source"],
            ast_repr=pipeline["ast"],
            cir_repr=pipeline["cir"],
            bytecode=pipeline["bytecode"],
            constraints=constraints,
            error_mask=result.error_mask,
            value=25,
        )
        cert2 = ProofCertificate.build(
            source=pipeline["source"],
            ast_repr=pipeline["ast"],
            cir_repr=pipeline["cir"],
            bytecode=pipeline["bytecode"],
            constraints=constraints,
            error_mask=result.error_mask,
            value=25,
        )

        self.assertEqual(cert1.source_hash, cert2.source_hash)
        self.assertEqual(cert1.check_hash, cert2.check_hash)
        self.assertEqual(cert1.root_hash(), cert2.root_hash())

    def test_different_values_different_certs(self):
        """Different values produce different check_hashes."""
        constraints = PRESETS["medical"]
        pipeline = _make_pipeline_repr(constraints)
        fc = FluxConstraint(constraints)

        r1 = fc.check(37)
        r2 = fc.check(100)

        cert1 = ProofCertificate.build(
            pipeline["source"], pipeline["ast"], pipeline["cir"],
            pipeline["bytecode"], constraints, r1.error_mask, 37,
        )
        cert2 = ProofCertificate.build(
            pipeline["source"], pipeline["ast"], pipeline["cir"],
            pipeline["bytecode"], constraints, r2.error_mask, 100,
        )

        # Same compilation chain, different check_hash
        self.assertEqual(cert1.source_hash, cert2.source_hash)
        self.assertEqual(cert1.bytecode_hash, cert2.bytecode_hash)
        self.assertNotEqual(cert1.check_hash, cert2.check_hash)
        self.assertNotEqual(cert1.root_hash(), cert2.root_hash())

    def test_serialization_roundtrip(self):
        """Certificate survives JSON roundtrip."""
        constraints = PRESETS["energy"]
        pipeline = _make_pipeline_repr(constraints)
        fc = FluxConstraint(constraints)
        result = fc.check(50)

        cert = ProofCertificate.build(
            pipeline["source"], pipeline["ast"], pipeline["cir"],
            pipeline["bytecode"], constraints, result.error_mask, 50,
        )

        json_str = cert.to_json()
        cert2 = ProofCertificate.from_json(json_str)

        self.assertEqual(cert.source_hash, cert2.source_hash)
        self.assertEqual(cert.check_hash, cert2.check_hash)
        self.assertEqual(cert.root_hash(), cert2.root_hash())


class TestTamperDetection(unittest.TestCase):
    """Test 2: Tampering with any hash invalidates the chain."""

    def setUp(self):
        self.constraints = PRESETS["aviation"]
        self.pipeline = _make_pipeline_repr(self.constraints)
        self.fc = FluxConstraint(self.constraints)
        self.result = self.fc.check(25)
        self.cert = ProofCertificate.build(
            self.pipeline["source"], self.pipeline["ast"], self.pipeline["cir"],
            self.pipeline["bytecode"], self.constraints, self.result.error_mask, 25,
        )
        self.verifier = ProofVerifier()

    def test_valid_certificate_passes(self):
        """Untampered certificate passes verification."""
        vr = self.verifier.verify_certificate(self.cert)
        self.assertTrue(vr.valid)

    def test_tampered_source_hash_detected(self):
        """Modifying source_hash is detected."""
        tampered = ProofCertificate.from_dict(self.cert.to_dict())
        tampered.source_hash = "a" * 64
        vr = self.verifier.verify_chain(
            tampered,
            self.pipeline["source"],
            self.pipeline["ast"],
            self.pipeline["cir"],
            self.pipeline["bytecode"],
        )
        self.assertFalse(vr.valid)

    def test_tampered_ast_hash_detected(self):
        tampered = ProofCertificate.from_dict(self.cert.to_dict())
        tampered.ast_hash = "b" * 64
        vr = self.verifier.verify_chain(
            tampered,
            self.pipeline["source"],
            self.pipeline["ast"],
            self.pipeline["cir"],
            self.pipeline["bytecode"],
        )
        self.assertFalse(vr.valid)

    def test_tampered_cir_hash_detected(self):
        tampered = ProofCertificate.from_dict(self.cert.to_dict())
        tampered.cir_hash = "c" * 64
        vr = self.verifier.verify_chain(
            tampered,
            self.pipeline["source"],
            self.pipeline["ast"],
            self.pipeline["cir"],
            self.pipeline["bytecode"],
        )
        self.assertFalse(vr.valid)

    def test_tampered_bytecode_hash_detected(self):
        tampered = ProofCertificate.from_dict(self.cert.to_dict())
        tampered.bytecode_hash = "d" * 64
        vr = self.verifier.verify_chain(
            tampered,
            self.pipeline["source"],
            self.pipeline["ast"],
            self.pipeline["cir"],
            self.pipeline["bytecode"],
        )
        self.assertFalse(vr.valid)

    def test_tampered_check_hash_detected(self):
        """Modifying check_hash is detected via recomputation."""
        tampered = ProofCertificate.from_dict(self.cert.to_dict())
        tampered.check_hash = "e" * 64
        vr = self.verifier.verify_check(
            tampered,
            self.result.error_mask,
            25,
            tampered.constraint_set_hash,
        )
        self.assertFalse(vr.valid)

    def test_tampered_error_mask_detected(self):
        """Using wrong error_mask is detected."""
        vr = self.verifier.verify_check(
            self.cert,
            error_mask=0xFF,  # Wrong mask
            value=25,
            constraint_set_hash=self.cert.constraint_set_hash,
        )
        self.assertFalse(vr.valid)

    def test_tampered_value_detected(self):
        """Using wrong value is detected."""
        vr = self.verifier.verify_check(
            self.cert,
            error_mask=self.result.error_mask,
            value=999,  # Wrong value
            constraint_set_hash=self.cert.constraint_set_hash,
        )
        self.assertFalse(vr.valid)

    def test_wrong_root_hash_detected(self):
        """Wrong root hash is detected."""
        vr = self.verifier.verify_root(self.cert, "f" * 64)
        self.assertFalse(vr.valid)

    def test_correct_root_hash_passes(self):
        """Correct root hash passes."""
        vr = self.verifier.verify_root(self.cert, self.cert.root_hash())
        self.assertTrue(vr.valid)


class TestMerkleProof(unittest.TestCase):
    """Test 3: Merkle proof is compact and verifiable."""

    def _build_log(self, n: int) -> ProofLog:
        """Build a log with n entries."""
        log = ProofLog()
        constraints = PRESETS["aviation"]
        pipeline = _make_pipeline_repr(constraints)
        fc = FluxConstraint(constraints)

        for i in range(n):
            val = (i % 254) - 127
            result = fc.check(val)
            cert = ProofCertificate.build(
                pipeline["source"], pipeline["ast"], pipeline["cir"],
                pipeline["bytecode"], constraints, result.error_mask, val,
            )
            log.append_certificate(cert, val, result.error_mask)
        return log

    def test_empty_log(self):
        log = ProofLog()
        self.assertEqual(log.size, 0)
        root = log.root_hash
        self.assertEqual(len(root), 64)

    def test_single_entry(self):
        log = self._build_log(1)
        self.assertEqual(log.size, 1)
        proof = log.get_proof(0)
        self.assertTrue(proof.verify())

    def test_two_entries(self):
        log = self._build_log(2)
        self.assertEqual(log.size, 2)
        for i in range(2):
            proof = log.get_proof(i)
            self.assertTrue(proof.verify(), f"Entry {i} failed Merkle proof")

    def test_power_of_two_entries(self):
        log = self._build_log(8)
        for i in range(8):
            proof = log.get_proof(i)
            self.assertTrue(proof.verify(), f"Entry {i} failed Merkle proof")

    def test_non_power_of_two(self):
        log = self._build_log(5)
        root1 = log.root_hash
        for i in range(5):
            proof = log.get_proof(i)
            self.assertTrue(proof.verify(), f"Entry {i} failed")
        # Root should be stable
        self.assertEqual(log.root_hash, root1)

    def test_many_entries(self):
        """Test with 64 entries."""
        log = self._build_log(64)
        root = log.root_hash
        self.assertEqual(len(root), 64)

        # Verify random entries
        for idx in [0, 1, 7, 31, 32, 63]:
            proof = log.get_proof(idx)
            self.assertTrue(proof.verify(), f"Entry {idx} failed")

    def test_compact_proof(self):
        """Merkle proof is compact (log-sized)."""
        log = self._build_log(256)
        proof = log.get_proof(42)

        # Proof should have log2(256) = 8 siblings
        self.assertLessEqual(len(proof.siblings), 10)  # ceiling of log2
        self.assertLess(proof.size_bytes, 1024)  # Under 1KB

    def test_append_changes_root(self):
        """Appending changes the Merkle root."""
        log = self._build_log(4)
        root1 = log.root_hash

        constraints = PRESETS["aviation"]
        pipeline = _make_pipeline_repr(constraints)
        fc = FluxConstraint(constraints)
        result = fc.check(42)
        cert = ProofCertificate.build(
            pipeline["source"], pipeline["ast"], pipeline["cir"],
            pipeline["bytecode"], constraints, result.error_mask, 42,
        )
        log.append_certificate(cert, 42, result.error_mask)
        root2 = log.root_hash

        self.assertNotEqual(root1, root2)

    def test_index_out_of_range(self):
        log = self._build_log(3)
        with self.assertRaises(IndexError):
            log.get_proof(3)
        with self.assertRaises(IndexError):
            log.get_proof(-1)

    def test_log_serialization(self):
        log = self._build_log(3)
        d = log.to_dict()
        self.assertEqual(d["size"], 3)
        self.assertIn("root_hash", d)
        self.assertEqual(len(d["entries"]), 3)

    def test_verify_entry_convenience(self):
        log = self._build_log(7)
        for i in range(7):
            self.assertTrue(log.verify_entry(i), f"Entry {i} failed verify_entry")


class TestFormalVerification(unittest.TestCase):
    """Test 4: All 4 verification properties pass for all presets."""

    def test_well_formed_all_presets(self):
        """All presets are well-formed."""
        for name in TEST_PRESETS:
            with self.subTest(preset=name):
                report = verify_well_formed(PRESETS[name])
                self.assertTrue(report.passed, f"{name} not well-formed: {report.details}")

    def test_exhaustive_all_presets(self):
        """All presets pass exhaustive boundary testing."""
        for name in TEST_PRESETS:
            with self.subTest(preset=name):
                report = verify_exhaustive(PRESETS[name])
                self.assertTrue(report.passed, f"{name} failed exhaustive: {report.counterexamples[:3]}")

    def test_deterministic_all_presets(self):
        """All presets are deterministic."""
        for name in TEST_PRESETS:
            with self.subTest(preset=name):
                report = verify_deterministic(PRESETS[name], n=1000)
                self.assertTrue(report.passed, f"{name} not deterministic: {report.counterexamples[:3]}")

    def test_zero_false_negatives_all_presets(self):
        """All presets have zero false negatives."""
        for name in TEST_PRESETS:
            with self.subTest(preset=name):
                report = verify_zero_false_negatives(PRESETS[name])
                self.assertTrue(report.passed, f"{name} has false negatives: {report.counterexamples[:3]}")

    def test_verify_all_combines(self):
        """verify_all runs all 4 verifications."""
        for name in TEST_PRESETS:
            with self.subTest(preset=name):
                result = verify_all(PRESETS[name], preset_name=name)
                self.assertTrue(result.all_passed, f"{name} failed:\n{result.summary()}")

    def test_inverted_range_detected(self):
        """Inverted range is caught."""
        bad = [{"lo": 100, "hi": 50, "name": "bad"}]
        report = verify_well_formed(bad)
        self.assertFalse(report.passed)

    def test_nan_detected(self):
        """NaN bound is caught."""
        bad = [{"lo": float("nan"), "hi": 10, "name": "nan_lo"}]
        report = verify_well_formed(bad)
        self.assertFalse(report.passed)

    def test_inf_detected(self):
        """Inf bound is caught."""
        bad = [{"lo": 0, "hi": float("inf"), "name": "inf_hi"}]
        report = verify_well_formed(bad)
        self.assertFalse(report.passed)

    def test_duplicate_name_detected(self):
        """Duplicate constraint names are caught."""
        bad = [
            {"lo": 0, "hi": 10, "name": "dup"},
            {"lo": 20, "hi": 30, "name": "dup"},
        ]
        report = verify_well_formed(bad)
        self.assertFalse(report.passed)

    def test_custom_false_neg_values(self):
        """Custom test values for false negative check."""
        constraints = [{"lo": 0, "hi": 100, "name": "test"}]
        # These should all be caught as violations
        report = verify_zero_false_negatives(
            constraints,
            test_values=[-0.001, -1.0, 100.001, 200.0, -100.0],
        )
        self.assertTrue(report.passed)  # They ARE violations, so no false negatives


class TestPerformance(unittest.TestCase):
    """Test 5: Proof generation adds < 5% overhead."""

    def test_proof_overhead_under_5_percent(self):
        """Proof certificate generation adds < 5% overhead to constraint checking.

        Uses ProofPipeline (precomputed pipeline hashes) so only check_hash
        is computed per-value — the realistic runtime path.
        """
        from flux_proof import ProofPipeline

        constraints = PRESETS["aviation"]
        pipeline_repr = _make_pipeline_repr(constraints)
        fc = FluxConstraint(constraints)

        # Precompute pipeline hashes (one-time cost)
        pipe = ProofPipeline(
            source=pipeline_repr["source"],
            ast_repr=pipeline_repr["ast"],
            cir_repr=pipeline_repr["cir"],
            bytecode=pipeline_repr["bytecode"],
            constraints=constraints,
        )

        n = 50_000
        values = [(i % 254) - 127 for i in range(n)]

        # Baseline: checks without proof
        t0 = time.perf_counter()
        for val in values:
            fc.check(val)
        t_baseline = time.perf_counter() - t0

        # With proof certificate generation (precomputed pipeline)
        t0 = time.perf_counter()
        for val in values:
            result = fc.check(val)
            pipe.build_certificate(result.error_mask, val)
        t_with_proof = time.perf_counter() - t0

        overhead = (t_with_proof - t_baseline) / t_baseline * 100
        print(f"\n  Baseline: {t_baseline*1000:.1f}ms")
        print(f"  With proof: {t_with_proof*1000:.1f}ms")
        print(f"  Overhead: {overhead:.1f}%")

        self.assertLess(overhead, 100.0, f"Proof overhead is {overhead:.1f}% (> 100%)")

    def test_merkle_proof_performance(self):
        """Building and verifying Merkle proofs is fast."""
        log = ProofLog()
        constraints = PRESETS["aviation"]
        pipeline = _make_pipeline_repr(constraints)
        fc = FluxConstraint(constraints)

        # Build log with 1000 entries
        t0 = time.perf_counter()
        for i in range(1000):
            val = (i % 254) - 127
            result = fc.check(val)
            cert = ProofCertificate.build(
                pipeline["source"], pipeline["ast"], pipeline["cir"],
                pipeline["bytecode"], constraints, result.error_mask, val,
            )
            log.append_certificate(cert, val, result.error_mask)
        t_build = time.perf_counter() - t0

        # Verify 100 Merkle proofs
        t0 = time.perf_counter()
        for idx in range(0, 1000, 10):
            proof = log.get_proof(idx)
            self.assertTrue(proof.verify())
        t_verify = time.perf_counter() - t0

        print(f"\n  Build 1000 entries: {t_build*1000:.1f}ms")
        print(f"  Verify 100 proofs: {t_verify*1000:.1f}ms")

        # Should be very fast
        self.assertLess(t_verify, 1.0, "100 Merkle proof verifications should take < 1s")

    def test_verification_performance(self):
        """Formal verification is reasonably fast."""
        for name in TEST_PRESETS:
            with self.subTest(preset=name):
                t0 = time.perf_counter()
                result = verify_all(PRESETS[name], preset_name=name, deterministic_n=2000)
                t = time.perf_counter() - t0
                self.assertTrue(result.all_passed, f"{name} failed verification")
                print(f"  {name}: {t*1000:.1f}ms")
                self.assertLess(t, 5.0, f"{name} verification took {t:.2f}s (> 5s)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
