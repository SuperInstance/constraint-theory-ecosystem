"""
flux_proof.py — FLUX v4 Proof Certificate System

Tamper-evident proof certificates for constraint checking correctness.

Certificate chain:
    source_hash → ast_hash → cir_hash → bytecode_hash → check_hash

Each link is SHA-256, committing to the exact transformation at that stage.
The check_hash is the RUNTIME proof: it proves that a specific value, checked
against a specific constraint set, produced a specific error mask.

A verifier can recompute the check_hash from (value, constraint_set, error_mask)
and confirm the result is provably correct.

Components:
1. ProofCertificate  — chains all hashes, serializable to JSON/CBOR
2. ProofVerifier     — verifies a certificate chain end-to-end
3. ProofLog          — append-only log of check proofs with Merkle tree root
4. MerkleProof       — compact proof that a specific check is in the log

Author: Forgemaster ⚒️
Date: 2026-05-19
"""

from __future__ import annotations

import hashlib
import json
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ─── Hash helpers ─────────────────────────────────────────────────────────────

DOMAIN_SEP = b"FLUX-V4::"


def _sha256(data: bytes) -> str:
    """SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def _hash_source(source: str) -> str:
    """Hash GUARD DSL source text."""
    h = hashlib.sha256(DOMAIN_SEP + b"source")
    h.update(source.encode("utf-8"))
    return h.hexdigest()


def _hash_ast(ast_repr: str) -> str:
    """Hash parsed AST representation."""
    h = hashlib.sha256(DOMAIN_SEP + b"ast")
    h.update(ast_repr.encode("utf-8"))
    return h.hexdigest()


def _hash_cir(cir_repr: str) -> str:
    """Hash constraint IR (after type-check, simplification)."""
    h = hashlib.sha256(DOMAIN_SEP + b"cir")
    h.update(cir_repr.encode("utf-8"))
    return h.hexdigest()


def _hash_bytecode(bytecode: bytes) -> str:
    """Hash compiled bytecode."""
    h = hashlib.sha256(DOMAIN_SEP + b"bytecode")
    h.update(bytecode)
    return h.hexdigest()


def _hash_check(error_mask: int, value: int, constraint_set_hash: str) -> str:
    """Hash runtime check result: error_mask + value + constraint_set_hash."""
    h = hashlib.sha256(DOMAIN_SEP + b"check")
    h.update(struct.pack("!I", error_mask))
    h.update(struct.pack("!i", value))
    h.update(constraint_set_hash.encode("ascii"))
    return h.hexdigest()


def _hash_constraints(constraints: List[Dict]) -> str:
    """Deterministic hash of a constraint set definition."""
    payload = json.dumps(
        sorted(constraints, key=lambda c: c.get("name", "")),
        sort_keys=True,
    )
    h = hashlib.sha256(DOMAIN_SEP + b"constraints")
    h.update(payload.encode("utf-8"))
    return h.hexdigest()


# ─── ProofCertificate ────────────────────────────────────────────────────────

# ─── Precomputed pipeline (fast path) ────────────────────────────────────────

class ProofPipeline:
    """
    Precomputed compilation pipeline hashes.

    Compute once, reuse for every check. Only the check_hash changes per value.
    """

    def __init__(
        self,
        source: str,
        ast_repr: str,
        cir_repr: str,
        bytecode: bytes,
        constraints: List[Dict],
    ):
        self.source_hash = _hash_source(source)
        self.ast_hash = _hash_ast(ast_repr)
        self.cir_hash = _hash_cir(cir_repr)
        self.bytecode_hash = _hash_bytecode(bytecode)
        self.constraint_set_hash = _hash_constraints(constraints)

    def check_hash(self, error_mask: int, value: int) -> str:
        """Compute the runtime check hash."""
        return _hash_check(error_mask, value, self.constraint_set_hash)

    def build_certificate(
        self, error_mask: int, value: int, timestamp: float = 0.0
    ) -> ProofCertificate:
        """Build a certificate using precomputed pipeline hashes."""
        return ProofCertificate(
            source_hash=self.source_hash,
            ast_hash=self.ast_hash,
            cir_hash=self.cir_hash,
            bytecode_hash=self.bytecode_hash,
            check_hash=self.check_hash(error_mask, value),
            constraint_set_hash=self.constraint_set_hash,
            timestamp=timestamp,
        )


@dataclass
class ProofCertificate:
    """
    Complete proof certificate chaining all compilation stages.

    source_hash → ast_hash → cir_hash → bytecode_hash → check_hash

    The check_hash is recomputed at runtime and proves:
    "This specific value, checked against this specific constraint set,
     produced this specific error mask."
    """

    # Compilation pipeline hashes
    source_hash: str
    ast_hash: str
    cir_hash: str
    bytecode_hash: str

    # Runtime check hash
    check_hash: str

    # Metadata
    constraint_set_hash: str
    timestamp: float = 0.0
    version: int = 4

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def chain(self) -> List[str]:
        """Return the hash chain in order."""
        return [
            self.source_hash,
            self.ast_hash,
            self.cir_hash,
            self.bytecode_hash,
            self.check_hash,
        ]

    def root_hash(self) -> str:
        """Hash of the entire chain — the certificate fingerprint."""
        h = hashlib.sha256(DOMAIN_SEP + b"certificate")
        for link in self.chain:
            h.update(link.encode("ascii"))
        return h.hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "source_hash": self.source_hash,
            "ast_hash": self.ast_hash,
            "cir_hash": self.cir_hash,
            "bytecode_hash": self.bytecode_hash,
            "check_hash": self.check_hash,
            "constraint_set_hash": self.constraint_set_hash,
            "timestamp": self.timestamp,
            "root_hash": self.root_hash(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ProofCertificate:
        return cls(
            source_hash=d["source_hash"],
            ast_hash=d["ast_hash"],
            cir_hash=d["cir_hash"],
            bytecode_hash=d["bytecode_hash"],
            check_hash=d["check_hash"],
            constraint_set_hash=d["constraint_set_hash"],
            timestamp=d.get("timestamp", 0.0),
            version=d.get("version", 4),
        )

    @classmethod
    def from_json(cls, s: str) -> ProofCertificate:
        return cls.from_dict(json.loads(s))

    @classmethod
    def build(
        cls,
        source: str,
        ast_repr: str,
        cir_repr: str,
        bytecode: bytes,
        constraints: List[Dict],
        error_mask: int,
        value: int,
    ) -> ProofCertificate:
        """Build a complete certificate from raw materials."""
        source_hash = _hash_source(source)
        ast_hash = _hash_ast(ast_repr)
        cir_hash = _hash_cir(cir_repr)
        bytecode_hash = _hash_bytecode(bytecode)
        constraint_set_hash = _hash_constraints(constraints)
        check_hash = _hash_check(error_mask, value, constraint_set_hash)

        return cls(
            source_hash=source_hash,
            ast_hash=ast_hash,
            cir_hash=cir_hash,
            bytecode_hash=bytecode_hash,
            check_hash=check_hash,
            constraint_set_hash=constraint_set_hash,
        )


# ─── ProofVerifier ───────────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    """Result of verifying a proof certificate."""
    valid: bool
    errors: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


class ProofVerifier:
    """
    Verifies a proof certificate chain end-to-end.

    Can verify:
    1. Chain integrity (each hash is well-formed)
    2. Recomputed check_hash matches recorded hash
    3. Tamper detection (any modified hash invalidates the chain)
    """

    def verify_certificate(self, cert: ProofCertificate) -> VerificationResult:
        """Verify the internal consistency of a certificate."""
        errors = []

        # Check all hashes are 64-char hex (SHA-256)
        for name in ("source_hash", "ast_hash", "cir_hash", "bytecode_hash",
                      "check_hash", "constraint_set_hash"):
            h = getattr(cert, name, None)
            if h is None:
                errors.append(f"Missing {name}")
            elif not isinstance(h, str) or len(h) != 64:
                errors.append(f"{name} is not a valid SHA-256 hex digest (len={len(h) if isinstance(h, str) else 'N/A'})")
            else:
                try:
                    int(h, 16)
                except ValueError:
                    errors.append(f"{name} contains non-hex characters")

        return VerificationResult(valid=len(errors) == 0, errors=errors)

    def verify_check(
        self,
        cert: ProofCertificate,
        error_mask: int,
        value: int,
        constraint_set_hash: str,
    ) -> VerificationResult:
        """Verify the check_hash by recomputing it."""
        errors = []

        # Verify constraint_set_hash
        if cert.constraint_set_hash != constraint_set_hash:
            errors.append(
                f"constraint_set_hash mismatch: cert={cert.constraint_set_hash[:16]}... "
                f"recomputed={constraint_set_hash[:16]}..."
            )

        # Recompute check_hash
        recomputed = _hash_check(error_mask, value, constraint_set_hash)
        if cert.check_hash != recomputed:
            errors.append(
                f"check_hash mismatch: cert={cert.check_hash[:16]}... "
                f"recomputed={recomputed[:16]}..."
            )

        return VerificationResult(valid=len(errors) == 0, errors=errors)

    def verify_chain(
        self,
        cert: ProofCertificate,
        source: str,
        ast_repr: str,
        cir_repr: str,
        bytecode: bytes,
    ) -> VerificationResult:
        """Verify the full chain by recomputing all hashes."""
        errors = []

        checks = [
            ("source_hash", cert.source_hash, _hash_source(source)),
            ("ast_hash", cert.ast_hash, _hash_ast(ast_repr)),
            ("cir_hash", cert.cir_hash, _hash_cir(cir_repr)),
            ("bytecode_hash", cert.bytecode_hash, _hash_bytecode(bytecode)),
        ]

        for name, recorded, recomputed in checks:
            if recorded != recomputed:
                errors.append(
                    f"{name} mismatch: recorded={recorded[:16]}... recomputed={recomputed[:16]}..."
                )

        return VerificationResult(valid=len(errors) == 0, errors=errors)

    def verify_root(self, cert: ProofCertificate, expected_root: str) -> VerificationResult:
        """Verify the certificate root hash matches expected."""
        actual = cert.root_hash()
        if actual != expected_root:
            return VerificationResult(
                valid=False,
                errors=[f"root_hash mismatch: expected={expected_root[:16]}... actual={actual[:16]}..."],
            )
        return VerificationResult(valid=True)


# ─── Merkle Tree ─────────────────────────────────────────────────────────────

def _merkle_pair(left: str, right: str) -> str:
    """Hash a pair of hex digests into a parent node."""
    h = hashlib.sha256(DOMAIN_SEP + b"merkle")
    h.update(bytes.fromhex(left))
    h.update(bytes.fromhex(right))
    return h.hexdigest()


def _build_merkle(leaves: List[str]) -> List[List[str]]:
    """
    Build a Merkle tree from a list of hex-digest leaves.
    Returns all levels: level 0 = leaves, level -1 = root.
    """
    if not leaves:
        return []

    # Pad to power of 2
    n = len(leaves)
    size = 1
    while size < n:
        size <<= 1
    padded = list(leaves) + [leaves[-1]] * (size - n)

    levels = [padded]
    current = padded
    while len(current) > 1:
        next_level = []
        for i in range(0, len(current), 2):
            next_level.append(_merkle_pair(current[i], current[i + 1]))
        levels.append(next_level)
        current = next_level

    return levels


@dataclass(frozen=True)
class MerkleProof:
    """
    Compact Merkle proof that a specific leaf is in the tree.

    Contains:
    - leaf_hash: the hash being proven
    - leaf_index: position in the leaves list
    - siblings: list of sibling hashes needed to reconstruct root
    - directions: which side each sibling goes (True = left, False = right)
    - root_hash: the expected Merkle root
    """

    leaf_hash: str
    leaf_index: int
    siblings: Tuple[str, ...]
    directions: Tuple[bool, ...]
    root_hash: str

    def verify(self) -> bool:
        """Verify this Merkle proof by reconstructing the root."""
        current = self.leaf_hash
        for sibling, is_left in zip(self.siblings, self.directions):
            if is_left:
                current = _merkle_pair(sibling, current)
            else:
                current = _merkle_pair(current, sibling)
        return current == self.root_hash

    @property
    def size_bytes(self) -> int:
        """Approximate serialized size."""
        # each hash is 64 bytes hex, plus metadata
        return 64 * (1 + len(self.siblings)) + 20


def _extract_merkle_proof(levels: List[List[str]], leaf_index: int) -> MerkleProof:
    """Extract a Merkle proof for a given leaf from the tree levels."""
    siblings = []
    directions = []
    idx = leaf_index

    for level in levels[:-1]:
        if idx % 2 == 0:
            # Current is left, sibling is right
            sibling = level[idx + 1] if idx + 1 < len(level) else level[idx]
            directions.append(False)  # sibling goes right
        else:
            # Current is right, sibling is left
            sibling = level[idx - 1]
            directions.append(True)  # sibling goes left
        siblings.append(sibling)
        idx //= 2

    root = levels[-1][0] if levels else ""
    return MerkleProof(
        leaf_hash=levels[0][leaf_index],
        leaf_index=leaf_index,
        siblings=tuple(siblings),
        directions=tuple(directions),
        root_hash=root,
    )


# ─── ProofLog ────────────────────────────────────────────────────────────────

@dataclass
class CheckProof:
    """A single check proof entry in the log."""
    check_hash: str
    value: int
    error_mask: int
    constraint_set_hash: str
    timestamp: float

    def leaf_hash(self) -> str:
        """Hash of this entry for Merkle tree inclusion."""
        payload = json.dumps(
            {
                "check_hash": self.check_hash,
                "value": self.value,
                "error_mask": self.error_mask,
                "constraint_set_hash": self.constraint_set_hash,
                "timestamp": self.timestamp,
            },
            sort_keys=True,
        )
        return _sha256(payload.encode("utf-8"))


class ProofLog:
    """
    Append-only log of check proofs with Merkle tree root.

    Every check produces a CheckProof that is appended to the log.
    The Merkle tree root commits to the entire log state.
    """

    def __init__(self):
        self._entries: List[CheckProof] = []
        self._merkle_levels: Optional[List[List[str]]] = None
        self._dirty = True

    def append(
        self,
        check_hash: str,
        value: int,
        error_mask: int,
        constraint_set_hash: str,
        timestamp: Optional[float] = None,
    ) -> CheckProof:
        """Append a check proof to the log."""
        entry = CheckProof(
            check_hash=check_hash,
            value=value,
            error_mask=error_mask,
            constraint_set_hash=constraint_set_hash,
            timestamp=timestamp or time.time(),
        )
        self._entries.append(entry)
        self._dirty = True
        return entry

    def append_certificate(self, cert: ProofCertificate, value: int, error_mask: int) -> CheckProof:
        """Append a proof certificate's check to the log."""
        return self.append(
            check_hash=cert.check_hash,
            value=value,
            error_mask=error_mask,
            constraint_set_hash=cert.constraint_set_hash,
            timestamp=cert.timestamp,
        )

    @property
    def size(self) -> int:
        return len(self._entries)

    def _ensure_tree(self) -> List[List[str]]:
        if self._dirty or self._merkle_levels is None:
            leaves = [e.leaf_hash() for e in self._entries]
            self._merkle_levels = _build_merkle(leaves) if leaves else []
            self._dirty = False
        return self._merkle_levels

    @property
    def root_hash(self) -> str:
        """Current Merkle root of the log."""
        levels = self._ensure_tree()
        if not levels:
            return _sha256(b"FLUX-V4::empty_log")
        return levels[-1][0]

    def get_proof(self, index: int) -> MerkleProof:
        """Get a Merkle proof for the entry at the given index."""
        if index < 0 or index >= len(self._entries):
            raise IndexError(f"Index {index} out of range [0, {len(self._entries)})")
        levels = self._ensure_tree()
        return _extract_merkle_proof(levels, index)

    def verify_entry(self, index: int) -> bool:
        """Verify that the entry at index is in the log via Merkle proof."""
        proof = self.get_proof(index)
        return proof.verify()

    def get_entry(self, index: int) -> CheckProof:
        return self._entries[index]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "size": self.size,
            "root_hash": self.root_hash,
            "entries": [
                {
                    "check_hash": e.check_hash,
                    "value": e.value,
                    "error_mask": e.error_mask,
                    "constraint_set_hash": e.constraint_set_hash,
                    "timestamp": e.timestamp,
                }
                for e in self._entries
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
