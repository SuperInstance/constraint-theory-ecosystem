# Cryptography of Constraints

> Synthesis of six deep-dive explorations at the intersection of constraint theory and cryptography/blockchain.

---

## Overview

Constraint checking is fundamentally about proving that data satisfies predicates. Cryptography provides the tools to make these proofs **private**, **compact**, **tamper-proof**, and **verifiable by third parties** — transforming constraints from internal validation logic into cryptographic primitives.

This document covers six approaches, each addressing a different dimension of the constraint-cryptography intersection.

---

## 1. Constraint Merkle Mountain Range (CMMR)

### Problem
FLUX proof logs grow monotonically. Old entries consume storage but must remain provable.

### Solution: CMMR
A Merkle Mountain Range variant where pruned leaves retain just enough metadata to verify both membership and constraint satisfaction.

**Pruned leaf structure:**
```
P_j = (c_j,           // Leaf commitment: H(L_j)
       V_j,           // Minimal constraint verification projection vector
       pos_j,         // MMR position at append time
       n_j,           // Total leaves when j was added
       R_j,           // MMR root after adding j
       params_j,      // Global constraints at n_j
       π_j^M)         // Merkle proof of c_j against R_j
```

**Complexity:**
| Operation | Time |
|-----------|------|
| Append | O(log n) |
| Prune | O(1) |
| Verify | O(log n + k) |

**Key insight:** Raw log data is deleted. The projection vector `V_j` captures only the fields needed to re-check constraints — validator ID, signature, block height, check result. Historical parameter sets are batched per epoch to avoid per-leaf overhead.

**Cryptographic guarantees:** Collision-resistant hashes protect membership integrity. The projection vector ensures constraint integrity. Historical roots provide non-repudiation.

---

## 2. Homomorphic Constraint Checking

### Problem
Check that encrypted sensor readings satisfy range constraints without decrypting them.

### Two Approaches

**Paillier (Partially Homomorphic):**
- Supports additive homomorphism: E(a) × E(b) = E(a+b)
- Range check: compute E(x-L) and E(U-x), then use ZKP to prove non-negativity
- Overhead: ~25–120 ms per check (dominated by ZKP)
- Best for: small-scale IoT with integer readings

**BFV/CKKS (Fully Homomorphic):**
- Supports arbitrary arithmetic on encrypted data
- Range check: homomorphic subtraction + comparison circuit
- Batch processing: 4096+ readings per ciphertext
- Overhead: ~5–30 ms single, ~0.002–0.01 ms per reading in batch mode
- Best for: high-throughput sensor fleets

**Protocol (BFV):**
```
1. Client encrypts sensor reading x → ct_x
2. Server computes ct_d1 = ct_x - E(L), ct_d2 = E(U) - ct_x
3. Server evaluates: ct_result = (ct_d1 ≥ 0) AND (ct_d2 ≥ 0)
4. Client decrypts ct_result → binary pass/fail
```

**Key insight:** BFV with batching achieves ~100,000 readings/sec throughput — practical for real-time sensor networks.

---

## 3. zk-SNARK Batch Constraint Proofs

### Problem
Prove that 1M sensor readings all passed their constraints, verifiable in O(1) time.

### Circuit Design (Groth16 on BLS12-381)

**Per-sensor constraints (7-bit range check):**
```
s'_i = s_i + |L|          // Shift to non-negative
s'_i = Σ b_{i,k} · 2^k    // Bit decomposition (7 bits)
b_{i,k} · (1 - b_{i,k}) = 0  // Boolean constraint
```

**Batch verification:**
```
Σ f_i = 0  // Sum of failure flags must be zero
```

**Complexity:**
| Component | Complexity |
|-----------|-----------|
| Trusted Setup | O(M · K) — once per circuit |
| Proof Generation | O(M · K) — minutes for 1M sensors |
| Verification | **O(1)** — constant regardless of batch |
| Proof Size | **128 bytes** (BLS12-381) |

**Key insight:** The prover does all the work (linear), but the verifier only needs to check 2-3 pairing operations — constant time regardless of whether there are 1 or 1 billion readings.

**Optimizations:**
- Recursive SNARKs for real-time streaming (aggregate sub-batches)
- Halo2/STARKs for trustless setup (no toxic waste)
- Poseidon hash for SNARK-friendly circuits

---

## 4. Constraint Contracts (Solidity Analog)

### Problem
Encode constraint sets as blockchain primitives that multiple parties agree to, with automatic violation handling.

### Contract Architecture

```solidity
contract ConstraintContract {
    // State
    mapping(address => bool) public parties;        // Agreed participants
    mapping(bytes32 => Constraint) public constraints; // Named constraints
    mapping(bytes32 => Action) public violationActions; // Auto-triggers
    
    // Lifecycle
    function proposeConstraint(bytes32 id, bytes memory checkLogic, ...) 
    function agreeToConstraint(bytes32 id)           // Multi-party sign-off
    function activateConstraint(bytes32 id)           // All parties agreed → active
    
    // Runtime
    function check(bytes32 id, bytes memory input) → (bool, string)
    function reportViolation(bytes32 id, bytes memory evidence)
    
    // Events
    event ConstraintViolated(bytes32 indexed id, address reporter, string reason);
    event RemediationExecuted(bytes32 indexed id, bool success);
}
```

**Violation handling pipeline:**
```
check() fails → reportViolation() → emit ConstraintViolated → 
  executeViolationAction() → remediation actions (try/catch) → 
  emit RemediationExecuted
```

**Gas considerations:**
- Constraint checks: VIEW functions (no gas for read-only)
- Violation reporting: ~50K–150K gas per report
- Remediation: variable, depends on action complexity
- Limit constraints/actions per contract to avoid block gas limits

**Key insight:** Constraint contracts bridge declarative constraint definitions and blockchain enforcement — parties agree to rules, violations trigger automatic on-chain responses.

---

## 5. Proof Aggregation via Bilinear Pairings

### Problem
N constraint check proofs require N verification operations. Can we compress to one?

### Aggregation Protocol (Groth16-based)

**Setup:**
- Pairing groups (G₁, G₂, G_T) with bilinear map e: G₁ × G₂ → G_T
- Constraint circuit C with proving key PK and verification key VK

**Per-instance proving:**
```
For each (x_i, w_i) where C(x_i, w_i) = 1:
  π_i = Prove(PK, x_i, w_i) = (A_i, B_i, C_i)
```

**Aggregation (Fiat-Shamir):**
```
t = H(VK || x_1 || B_1 || x_2 || B_2 || ... || x_N || B_N)
π_agg = Prove(PK_agg, (x_1,...,x_N), (w_1,...,w_N))
```

**Verification:**
```
V_agg(VK_agg, (x_1,...,x_N), π_agg) = 1
```
Single pairing check confirms ALL N constraints passed.

**Concrete sizes (BLS12-381):**
| Component | Size |
|-----------|------|
| Single proof | 192 bytes |
| Aggregate proof | **192 bytes** (constant!) |
| Verification time | 6 pairing checks (constant!) |

**Special case — BLS aggregation:**
When the constraint is "σ_i = H(m_i)^sk", aggregation simplifies to:
```
π_agg = Σ σ_i
e(π_agg, g₂) = Π e(H(m_i), pk)
```

**Key insight:** Pairing-based SNARKs compress N proofs into one 192-byte proof. The verifier does 6 fixed pairing checks regardless of N.

---

## 6. TEE-Based Constraint Checking (Intel SGX)

### Problem
Run constraint checking in a hardware enclave where even the host OS can't tamper with results.

### Architecture

**ECALLs (host → enclave):**
| Function | Purpose |
|----------|---------|
| `attest_me(nonce)` | Generate DCAP Quote for remote attestation |
| `run_constraint_check(input)` | Execute constraints, return signed result |
| `seal_result(raw_result)` | Encrypt result to platform-bound key |
| `unseal_result(sealed_blob)` | Decrypt sealed result |

**Attestation flow:**
```
1. Verifier → Host: nonce N1
2. Host → Enclave: attest_me(N1)
3. Enclave: generate report (MRENCLAVE, MRSIGNER, N1, PK_ENCLAVE)
4. Quoting Enclave: wrap in DCAP Quote, sign with PCK
5. Host → Verifier: signed Quote
6. Verifier: validate chain against Intel Root CA, check MRENCLAVE/MRSIGNER
```

**Sealing:**
- Results encrypted with platform-bound key (MRENCLAVE + CPU secret)
- Only the same enclave on the same CPU can unseal
- Safe to store on compromised host disk

**Threat model:**
| Threat | Mitigation |
|--------|-----------|
| Malicious host OS | Enclave memory encrypted, inaccessible |
| Side-channel (Spectre) | Constant-time code, disable hyperthreading |
| Cold boot attacks | CPU Total Memory Encryption |
| Replay attacks | Nonce in attestation |
| Debug mode | Verify DEBUG_MODE=0 in Quote |

**Key insight:** TEEs provide hardware-rooted trust — the attestation proves not just that correct code ran, but that it ran on genuine hardware with memory isolation.

---

## Cross-Cutting Synthesis

These six approaches form a layered security architecture:

```
Layer 5: TEE Enforcement     — Hardware-guaranteed execution integrity
Layer 4: Smart Contracts     — Multi-party agreement + automatic enforcement
Layer 3: zk-SNARKs           — Zero-knowledge batch proofs (O(1) verify)
Layer 2: Proof Aggregation   — Compress N proofs → 1 constant-size proof
Layer 1: Homomorphic Checks  — Compute on encrypted data
Layer 0: CMMR                — Prunable audit trail with cryptographic guarantees
```

**Composability:** These layers compose. For example:
- Homomorphic range checks (Layer 1) can be proven via zk-SNARKs (Layer 3)
- SNARK proofs can be aggregated (Layer 2) and stored in CMMR (Layer 0)
- TEE attestation (Layer 5) can anchor the whole chain of trust

**The unifying principle:** Constraints are predicates. Cryptography transforms predicates into proofs — compact, private, tamper-proof, and efficiently verifiable.

---

## Implementation Status

| Component | File | Status |
|-----------|------|--------|
| Zero-Knowledge Constraint Proofs | `src/python/flux_zk.py` | Implemented (simplified polynomial commitment) |
| Proof Aggregation | `src/python/flux_aggregate.py` | Implemented (BLS-like combining) |
| Tests | `src/python/test_flux_zk.py` | Implemented |
| Tests | `src/python/test_flux_aggregate.py` | Implemented |

---

*Generated: 2026-05-19 | Research: Seed-2.0-mini via DeepInfra | Synthesis: Forgemaster ⚒️*
