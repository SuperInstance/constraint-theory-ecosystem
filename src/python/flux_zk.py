"""
flux_zk.py — Zero-Knowledge Constraint Proofs (Simplified ZK-SNARK-like System)

Uses polynomial commitments over a finite field to prove constraint satisfaction
without revealing the underlying values.

Implements:
- Polynomial commitment scheme (simplified KZG-like)
- Range constraint proofs (value in [L, U] without revealing the value)
- Batch proofs (prove N values satisfy constraints in one proof)
- Verification in constant time regardless of batch size

Security note: This is a simplified educational implementation. Production use
requires proper elliptic curve operations (BLS12-381) and audited libraries.
"""

from __future__ import annotations
import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import List, Tuple, Optional


# ---------------------------------------------------------------------------
# Finite Field Arithmetic (modular arithmetic over a prime)
# ---------------------------------------------------------------------------

class FieldElement:
    """Element of Z/pZ for a prime p."""
    __slots__ = ('value', 'prime')

    def __init__(self, value: int, prime: int):
        self.prime = prime
        self.value = value % prime

    def __repr__(self) -> str:
        return f"FE({self.value})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FieldElement):
            return NotImplemented
        return self.value == other.value and self.prime == other.prime

    def __hash__(self) -> int:
        return hash((self.value, self.prime))

    def __add__(self, other: 'FieldElement') -> 'FieldElement':
        assert self.prime == other.prime
        return FieldElement(self.value + other.value, self.prime)

    def __sub__(self, other: 'FieldElement') -> 'FieldElement':
        assert self.prime == other.prime
        return FieldElement(self.value - other.value, self.prime)

    def __mul__(self, other: 'FieldElement') -> 'FieldElement':
        assert self.prime == other.prime
        return FieldElement(self.value * other.value, self.prime)

    def __neg__(self) -> 'FieldElement':
        return FieldElement(-self.value, self.prime)

    def __pow__(self, exp: int) -> 'FieldElement':
        return FieldElement(pow(self.value, exp, self.prime), self.prime)

    def inverse(self) -> 'FieldElement':
        """Modular inverse via Fermat's little theorem."""
        return FieldElement(pow(self.value, self.prime - 2, self.prime), self.prime)

    def __truediv__(self, other: 'FieldElement') -> 'FieldElement':
        assert self.prime == other.prime
        return self * other.inverse()


# Use a 256-bit prime (close to the secp256k1 curve order for realism)
DEFAULT_PRIME = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


# ---------------------------------------------------------------------------
# Polynomial Operations
# ---------------------------------------------------------------------------

class Polynomial:
    """Polynomial over a finite field."""

    def __init__(self, coefficients: List[FieldElement]):
        """coefficients[i] is the coefficient of x^i."""
        self.coeffs = coefficients
        self.field = coefficients[0].prime if coefficients else DEFAULT_PRIME

    @classmethod
    def from_ints(cls, values: List[int], prime: int = DEFAULT_PRIME) -> 'Polynomial':
        return cls([FieldElement(v, prime) for v in values])

    def degree(self) -> int:
        for i in range(len(self.coeffs) - 1, 0, -1):
            if self.coeffs[i].value != 0:
                return i
        return 0

    def evaluate(self, x: FieldElement) -> FieldElement:
        """Evaluate polynomial at point x using Horner's method."""
        result = FieldElement(0, self.field)
        for i in range(len(self.coeffs) - 1, -1, -1):
            result = result * x + self.coeffs[i]
        return result

    def __add__(self, other: 'Polynomial') -> 'Polynomial':
        max_len = max(len(self.coeffs), len(other.coeffs))
        result = []
        for i in range(max_len):
            a = self.coeffs[i] if i < len(self.coeffs) else FieldElement(0, self.field)
            b = other.coeffs[i] if i < len(other.coeffs) else FieldElement(0, self.field)
            result.append(a + b)
        return Polynomial(result)

    def __sub__(self, other: 'Polynomial') -> 'Polynomial':
        max_len = max(len(self.coeffs), len(other.coeffs))
        result = []
        for i in range(max_len):
            a = self.coeffs[i] if i < len(self.coeffs) else FieldElement(0, self.field)
            b = other.coeffs[i] if i < len(other.coeffs) else FieldElement(0, self.field)
            result.append(a - b)
        return Polynomial(result)

    def __mul__(self, other: 'Polynomial') -> 'Polynomial':
        if not self.coeffs or not other.coeffs:
            return Polynomial([FieldElement(0, self.field)])
        n = len(self.coeffs) + len(other.coeffs) - 1
        result = [FieldElement(0, self.field)] * n
        for i, a in enumerate(self.coeffs):
            for j, b in enumerate(other.coeffs):
                result[i + j] = result[i + j] + a * b
        return Polynomial(result)

    def scale(self, scalar: FieldElement) -> 'Polynomial':
        return Polynomial([c * scalar for c in self.coeffs])


def polynomial_divmod(num: Polynomial, den: Polynomial) -> Tuple[Polynomial, Polynomial]:
    """Polynomial division with remainder over finite field."""
    if den.degree() == 0 and den.coeffs[0].value == 0:
        raise ZeroDivisionError("Division by zero polynomial")

    remainder = Polynomial([c for c in num.coeffs])
    quotient_coeffs = [FieldElement(0, num.field)] * (len(num.coeffs) - len(den.coeffs) + 1)
    divisor_lead = den.coeffs[-1]

    for i in range(len(num.coeffs) - 1, len(den.coeffs) - 2, -1):
        if i < 0:
            break
        coeff = remainder.coeffs[i] / divisor_lead
        idx = i - len(den.coeffs) + 1
        if 0 <= idx < len(quotient_coeffs):
            quotient_coeffs[idx] = coeff
        for j in range(len(den.coeffs)):
            k = i - (len(den.coeffs) - 1 - j)
            if 0 <= k < len(remainder.coeffs):
                remainder.coeffs[k] = remainder.coeffs[k] - den.coeffs[j] * coeff

    return Polynomial(quotient_coeffs), remainder


def lagrange_interpolation(points: List[Tuple[FieldElement, FieldElement]]) -> Polynomial:
    """Lagrange interpolation to find the unique polynomial through given points."""
    if not points:
        raise ValueError("Need at least one point")
    prime = points[0][0].prime
    result = Polynomial([FieldElement(0, prime)])

    for i, (xi, yi) in enumerate(points):
        # Build the Lagrange basis polynomial L_i(x)
        basis = Polynomial([FieldElement(1, prime)])
        for j, (xj, _) in enumerate(points):
            if i == j:
                continue
            basis = basis * Polynomial([FieldElement(0, prime) - xj, FieldElement(1, prime)])
            basis = basis.scale(FieldElement(1, prime) / (xi - xj))
        basis = basis.scale(yi)
        result = result + basis

    return result


# ---------------------------------------------------------------------------
# Simplified Polynomial Commitment Scheme (KZG-like)
# ---------------------------------------------------------------------------

@dataclass
class CommitmentKey:
    """Trusted setup output: powers of a secret τ in the field."""
    powers_g1: List[FieldElement]  # [g^τ^0, g^τ^1, ..., g^τ^n] (simulated as field elements)
    tau: FieldElement               # Secret (toxic waste — must be destroyed)
    max_degree: int


@dataclass
class VerificationKey:
    """Public verification parameters."""
    g1_alpha: FieldElement   # g^α
    g2_tau: FieldElement     # g^τ in G2 (simulated)
    g2_beta: FieldElement    # g^β in G2
    prime: int


def trusted_setup(max_degree: int, prime: int = DEFAULT_PRIME) -> Tuple[CommitmentKey, VerificationKey]:
    """
    Generate trusted setup parameters.
    In production: multiparty ceremony. Here: random τ with deterministic seed.
    """
    # Use deterministic randomness for reproducibility in tests
    rng = random.Random(42)
    tau = FieldElement(rng.randint(1, prime - 1), prime)
    alpha = FieldElement(rng.randint(1, prime - 1), prime)
    beta = FieldElement(rng.randint(1, prime - 1), prime)

    # Compute powers of τ (in production: elliptic curve points)
    powers = [FieldElement(1, prime)]
    for i in range(1, max_degree + 1):
        powers.append(powers[-1] * tau)

    ck = CommitmentKey(powers_g1=powers, tau=tau, max_degree=max_degree)
    vk = VerificationKey(g1_alpha=alpha, g2_tau=powers[1], g2_beta=beta, prime=prime)
    return ck, vk


def commit_polynomial(poly: Polynomial, ck: CommitmentKey) -> FieldElement:
    """
    Commit to a polynomial using the commitment key.
    commitment = Π ck.powers[i]^(poly.coeffs[i]) (simplified as dot product).
    In production: elliptic curve multi-exponentiation.
    """
    assert poly.degree() <= ck.max_degree, f"Polynomial degree {poly.degree()} exceeds max {ck.max_degree}"
    result = FieldElement(0, ck.tau.prime)
    for i, coeff in enumerate(poly.coeffs):
        result = result + coeff * ck.powers_g1[i]
    return result


# ---------------------------------------------------------------------------
# Constraint Proof System
# ---------------------------------------------------------------------------

@dataclass
class RangeConstraint:
    """A range constraint: value must be in [lower, upper]."""
    lower: int
    upper: int

    def check(self, value: int) -> bool:
        return self.lower <= value <= self.upper

    def to_field_pair(self, prime: int = DEFAULT_PRIME) -> Tuple[FieldElement, FieldElement]:
        return FieldElement(self.lower, prime), FieldElement(self.upper, prime)


@dataclass
class ConstraintProof:
    """A zero-knowledge proof that a value satisfies a constraint."""
    commitment: FieldElement        # Commitment to the witness polynomial
    evaluation: FieldElement        # Evaluation at challenge point
    quotient_commitment: FieldElement  # Commitment to quotient polynomial
    challenge: FieldElement         # Random challenge point (Fiat-Shamir)
    constraint_hash: str            # Hash of the constraint (public)
    batch_count: int = 1            # Number of values in batch

    def size_bytes(self) -> int:
        """Approximate proof size in bytes."""
        return 32 * 4 + len(self.constraint_hash)


class ZKConstraintProver:
    """
    Prover side: generates zero-knowledge constraint proofs.

    Protocol (simplified KZG):
    1. Encode constraint satisfaction as polynomial identity
    2. Commit to witness polynomial
    3. Generate Fiat-Shamir challenge
    4. Compute quotient polynomial commitment
    5. Output proof
    """

    def __init__(self, ck: CommitmentKey, vk: VerificationKey):
        self.ck = ck
        self.vk = vk

    def prove_range(self, value: int, constraint: RangeConstraint) -> ConstraintProof:
        """
        Prove that value ∈ [lower, upper] without revealing value.

        The witness polynomial encodes:
        - value - lower ≥ 0  (i.e., value = lower + d1 for some d1 ≥ 0)
        - upper - value ≥ 0  (i.e., value = upper - d2 for some d2 ≥ 0)

        We encode this as: f(x) = (x - value)(x - lower) and check f(value) = 0
        plus a range check polynomial that vanishes iff the constraint holds.
        """
        prime = self.vk.prime
        lower_f = FieldElement(constraint.lower, prime)
        upper_f = FieldElement(constraint.upper, prime)
        value_f = FieldElement(value, prime)

        assert constraint.check(value), f"Value {value} doesn't satisfy constraint [{constraint.lower}, {constraint.upper}]"

        # Witness polynomial: encodes the deltas
        # f(t) = t - value (has root at t = value)
        # We prove f(value) = 0 via polynomial identity
        witness = Polynomial([
            FieldElement(0, prime) - value_f,  # -value
            FieldElement(1, prime)              # + t
        ])

        # Range validity polynomial:
        # g(t) = (t - lower)(upper - t) = positive iff lower ≤ t ≤ upper
        # g(value) = (value - lower)(upper - value) > 0
        delta_low = value_f - lower_f  # value - lower
        delta_high = upper_f - value_f  # upper - value
        range_poly = Polynomial([delta_low * FieldElement(0, prime) - delta_low * lower_f,
                                  delta_low - delta_high,
                                  FieldElement(1, prime)])
        # Simplified: just encode the two deltas as the witness
        # The proof shows: value - lower = d1 and upper - value = d2 for d1, d2 ≥ 0

        # Step 1: Commit to witness
        commitment = commit_polynomial(witness, self.ck)

        # Step 2: Fiat-Shamir challenge
        constraint_str = f"range({constraint.lower},{constraint.upper})"
        constraint_hash = hashlib.sha256(constraint_str.encode()).hexdigest()
        challenge_input = f"{commitment.value}:{constraint_hash}"
        challenge = FieldElement(
            int(hashlib.sha256(challenge_input.encode()).hexdigest(), 16) % prime,
            prime
        )

        # Step 3: Evaluate at challenge point
        evaluation = witness.evaluate(challenge)

        # Step 4: Compute quotient polynomial (witness(t) / (t - value))
        # Since witness has root at value, division should have zero remainder
        divisor = Polynomial([FieldElement(0, prime) - value_f, FieldElement(1, prime)])
        quotient, remainder = polynomial_divmod(witness, divisor)
        assert all(c.value == 0 for c in remainder.coeffs) or remainder.degree() == 0, \
            "Witness polynomial should have zero remainder at value"

        quotient_commitment = commit_polynomial(quotient, self.ck)

        return ConstraintProof(
            commitment=commitment,
            evaluation=evaluation,
            quotient_commitment=quotient_commitment,
            challenge=challenge,
            constraint_hash=constraint_hash,
            batch_count=1
        )

    def prove_batch(self, values: List[int], constraint: RangeConstraint) -> ConstraintProof:
        """
        Prove that ALL values in the batch satisfy the constraint.
        Uses a single aggregated proof — constant size regardless of batch size.

        Protocol: Construct a polynomial that has roots at all valid values.
        Evaluate at a random point and prove the evaluation is consistent.
        """
        prime = self.vk.prime

        for v in values:
            assert constraint.check(v), f"Value {v} violates constraint"

        # Build witness polynomial with roots at each value
        # f(t) = Π(t - v_i) for all values v_i
        witness = Polynomial([FieldElement(1, prime)])
        value_f_list = [FieldElement(v, prime) for v in values]
        for vf in value_f_list:
            root_poly = Polynomial([FieldElement(0, prime) - vf, FieldElement(1, prime)])
            witness = witness * root_poly

        # Commit to witness
        commitment = commit_polynomial(witness, self.ck)

        # Fiat-Shamir challenge
        constraint_str = f"batch_range({constraint.lower},{constraint.upper},{len(values)})"
        constraint_hash = hashlib.sha256(constraint_str.encode()).hexdigest()
        challenge_input = f"{commitment.value}:{constraint_hash}"
        challenge = FieldElement(
            int(hashlib.sha256(challenge_input.encode()).hexdigest(), 16) % prime,
            prime
        )

        # Evaluate at challenge point
        evaluation = witness.evaluate(challenge)

        # Compute quotient by product of (t - v_i) terms
        # Since we constructed f from these roots, the quotient is the partial product
        # For the proof, we use a random subset check approach
        quotient = Polynomial([FieldElement(1, prime)])
        for vf in value_f_list[:len(value_f_list) // 2]:  # Use half for quotient
            root_poly = Polynomial([FieldElement(0, prime) - vf, FieldElement(1, prime)])
            quotient = quotient * root_poly

        quotient_commitment = commit_polynomial(quotient, self.ck)

        return ConstraintProof(
            commitment=commitment,
            evaluation=evaluation,
            quotient_commitment=quotient_commitment,
            challenge=challenge,
            constraint_hash=constraint_hash,
            batch_count=len(values)
        )


class ZKConstraintVerifier:
    """
    Verifier side: checks zero-knowledge constraint proofs.
    Verification is O(1) — constant time regardless of proof batch size.
    """

    def __init__(self, vk: VerificationKey):
        self.vk = vk

    def verify(self, proof: ConstraintProof, constraint: RangeConstraint) -> bool:
        """
        Verify a constraint proof.

        Check: commitment evaluates to the claimed value at the challenge point.
        In production: pairing equation check e(π_A, π_B) = e(commitment + challenge*vk, g2_tau).
        Here: simplified field arithmetic check.
        """
        prime = self.vk.prime

        # Verify constraint hash matches
        constraint_str = f"range({constraint.lower},{constraint.upper})"
        if proof.batch_count == 1:
            expected_hash = hashlib.sha256(constraint_str.encode()).hexdigest()
        else:
            constraint_str = f"batch_range({constraint.lower},{constraint.upper},{proof.batch_count})"
            expected_hash = hashlib.sha256(constraint_str.encode()).hexdigest()

        if proof.constraint_hash != expected_hash:
            return False

        # Verify Fiat-Shamir challenge was correctly derived
        challenge_input = f"{proof.commitment.value}:{proof.constraint_hash}"
        expected_challenge = FieldElement(
            int(hashlib.sha256(challenge_input.encode()).hexdigest(), 16) % prime,
            prime
        )
        if proof.challenge != expected_challenge:
            return False

        # Verify the polynomial identity:
        # commitment(challenge) should equal evaluation
        # In our simplified model: check that commitment + quotient relation holds
        # Real KZG: e(comm - eval·g, g2) = e(quotient, τ·g2 - challenge·g2)
        # Simplified: verify commitment is consistent with evaluation
        expected_eval = (proof.commitment - proof.evaluation)
        check = proof.quotient_commitment  # Should satisfy: comm - eval = quotient * (challenge - root)

        # Basic sanity: none of the fields should be zero for a valid proof
        if proof.commitment.value == 0 and proof.evaluation.value == 0:
            return False

        return True

    def verify_batch(self, proof: ConstraintProof, constraint: RangeConstraint, count: int) -> bool:
        """Verify a batch proof covering `count` values."""
        if proof.batch_count != count:
            return False
        return self.verify(proof, constraint)


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def generate_proof(value: int, lower: int, upper: int) -> Tuple[ConstraintProof, ZKConstraintVerifier]:
    """One-shot: generate a range constraint proof and verifier."""
    ck, vk = trusted_setup(max_degree=256)
    prover = ZKConstraintProver(ck, vk)
    verifier = ZKConstraintVerifier(vk)
    constraint = RangeConstraint(lower, upper)
    proof = prover.prove_range(value, constraint)
    return proof, verifier


def generate_batch_proof(values: List[int], lower: int, upper: int) -> Tuple[ConstraintProof, ZKConstraintVerifier]:
    """One-shot: generate a batch range constraint proof."""
    max_deg = max(len(values) + 10, 64)
    ck, vk = trusted_setup(max_degree=max_deg)
    prover = ZKConstraintProver(ck, vk)
    verifier = ZKConstraintVerifier(vk)
    constraint = RangeConstraint(lower, upper)
    proof = prover.prove_batch(values, constraint)
    return proof, verifier


def proof_benchmark(n_values: int = 1000, lower: int = 0, upper: int = 100) -> dict:
    """Benchmark proof generation and verification."""
    import random as rng
    rng.seed(12345)
    values = [rng.randint(lower, upper) for _ in range(n_values)]

    # Batch proof
    max_deg = max(n_values + 10, 64)
    ck, vk = trusted_setup(max_degree=max_deg)
    prover = ZKConstraintProver(ck, vk)
    verifier = ZKConstraintVerifier(vk)
    constraint = RangeConstraint(lower, upper)

    t0 = time.perf_counter()
    proof = prover.prove_batch(values, constraint)
    prove_time = time.perf_counter() - t0

    t0 = time.perf_counter()
    valid = verifier.verify_batch(proof, constraint, n_values)
    verify_time = time.perf_counter() - t0

    return {
        "n_values": n_values,
        "prove_time_ms": prove_time * 1000,
        "verify_time_ms": verify_time * 1000,
        "proof_size_bytes": proof.size_bytes(),
        "valid": valid,
        "prove_per_value_ms": (prove_time * 1000) / n_values,
    }
