# Core Concepts

This document explains the cryptographic and mathematical building blocks that CoSMeTIC is built on. Reading it will make the rest of the codebase much easier to follow.

---

## 1. The Problem Being Solved

In clinical research (and federated machine-learning settings more broadly), a central party may collect private records from many users, compute a global statistic, and then publish that statistic. Later, a user might want to verify:

- "Was my record actually included in that statistic?" (membership / inclusion)
- "Was my record *not* used?" (non-membership / exclusion)

Answering these questions without disclosing the raw record, the full dataset, or even the transformation applied to it requires cryptographic machinery. CoSMeTIC provides exactly that.

---

## 2. Terminology

### Per-user primitives

| Symbol | Variable name in code | Description |
|--------|----------------------|-------------|
| `D_i` | `raw_value` | Raw private data for user *i*. Never disclosed publicly. |
| `US_i` | `user_salt` | Random vector concatenated with `D_i` to make it unique. |
| `SD_i` | `salted_raw_value` | `Concat(D_i, US_i)` |
| `F` | `transformer` | Leaf-level transformation `F(SD_i) → TSD_i`. Kept secret by the prover. Expressed as a `torch.nn.Module`. |
| `TS_i` | `transform_user_salt` | Second random vector appended after the leaf transform. |
| `SLT_i` | `transformed_value` | `Concat(TSD_i, TS_i)` — the value that actually lands in the SMT leaf. |
| `G` | `aggregator` | Global aggregation function `G([SLT_1, ..., SLT_p]) = AggTS`. |
| `AggTS` | — | The published global aggregate (the Merkle root value). |

### Transformer examples

The transformer `F` can be any differentiable PyTorch model:

| Transformer | Description |
|-------------|-------------|
| `FlowThrough` | Identity — passes input unchanged (useful for debugging). |
| `Affine` | `TSD = m * SD + c` |
| `Exponent` | Elementwise exponentiation. |
| `Length` | L2 norm of the salted value. |
| `LogisticFunction` | Logistic sigmoid of a linear combination. |
| `LogisticLogLikelihood` | Log-likelihood of a logistic regression model. |
| `BinCount` | Histogram / bin counting. |

All transformers live in `transformers/`.

---

## 3. Sparse Merkle Trees (SMTs)

An SMT is a Merkle tree with one leaf slot for every possible hash value. For a Poseidon or SHA-256 hash the tree has 2^256 potential leaves — virtually all of them empty ("default value" leaves).

### How a leaf position is determined

1. Compute `HL_i = Hash(SLT_i)`.
2. Interpret `HL_i` as a 256-bit integer.
3. That integer is the 1-indexed position in the ordered leaf set.
4. The bit representation of `HL_i` is also the binary path from the root to that leaf.

Because Hash functions are collision-resistant, each user occupies a unique, deterministic, and unpredictable position.

### Membership proof

To prove that `D_i` contributed to `AggTS`, the prover walks the path from leaf `HL_i` up to the root, supplying the sibling hashes and selector bits at each level. A verifier can reconstruct the root and check it matches the published `AggTS`.

### Non-membership proof

If `D_h` was not used, the leaf at position `HL_h` must contain the default value (`DeafVal`). The prover proves that the path at position `HL_h` leads to a default leaf. The verifier confirms the path bits match `HL_h`, ensuring the prover cannot cheat by picking an arbitrary empty location.

---

## 4. zk-SNARKs via EZKL

Both the leaf transform `F` and each aggregation step `G` can be compiled into a zero-knowledge proof circuit using [EZKL](https://github.com/zkonduit/ezkl), which takes PyTorch/ONNX models and produces ZK circuits.

This means:

- A prover can show `SLT_i = Concat(F(Concat(D_i, US_i)), TS_i)` without revealing `D_i`, `US_i`, `F`, or `TS_i`.
- A verifier only needs the verification key (`vk`) and the public inputs/outputs.

### Circuit artifacts produced during setup

| Artifact | Extension | Purpose |
|----------|-----------|---------|
| Compiled circuit | `.compiled` | The arithmetic circuit for the model |
| Proving key | `.pk` | Used by the prover to generate proofs |
| Verification key | `.vk` | Used by the verifier to check proofs |
| Settings | `settings.json` | Fixed-point scaling and other circuit parameters |

---

## 5. Proof Types

CoSMeTIC generates two families of proofs per user:

| Abbreviation | Meaning |
|--------------|---------|
| `ltr` | **Leaf Transform Proof** — proves the leaf value `SLT_i` was correctly derived from the raw data via `F`. |
| `mrp` | **Merkle Root Proof** — proves the path walk from the leaf up to the root, one level at a time. |

---

## 6. Statistical Tests Implemented

The `modules/` layer wraps the CoSMeTIC machinery for three specific statistical tests used in clinical research:

| Module | Test | Purpose |
|--------|------|---------|
| `LogisticAccuracy` | Accuracy test | Prove that accuracy of a logistic classifier was computed over the committed dataset. |
| `LogisticLRT` | Likelihood Ratio Test (LRT) | Prove the LRT statistic comparing a full vs. reduced logistic model. |
| `KolmogorovSmirnov` | KS test | Prove the KS statistic between two sample distributions. |

Each module builds one or more SMTs internally and exposes them through the Flask API layer.

---

## 7. Proving Set Completeness

Beyond individual membership/exclusion proofs, CoSMeTIC can prove **completeness**: that *exactly* a specified set of users (and no others) contributed to the root. This is done by:

1. Revealing the mappings `Hash(SD_i) → Hash(SLT_i)` for every claimed member.
2. Providing the leaf transform zk-SNARKs for all members.
3. Recursively examining non-default siblings in each member's Merkle path, tracing every non-default node back to a known member's leaf hash.

This is computationally intensive but far more efficient than generating the entire SMT inside a circuit.
