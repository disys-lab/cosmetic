# CoSMeTIC Documentation

**CoSMeTIC** — *Cryptographically-Secured Sparse Merkle Tree Inclusion/Exclusion Commitment* — is a framework for producing zero-knowledge proofs of membership and non-membership in aggregated computations over private user data. It is the software implementation accompanying the paper:

> **"CoSMeTIC: Zero-Knowledge Computational Sparse Merkle Trees with Inclusion-Exclusion Proofs for Clinical Research"**
> Mohammad Shahid, Paritosh Ramanan, Mohammad Fili, Guiping Hu, Hillel Haim
> arXiv:2601.12136

---

## Guides

| File | Description |
|------|-------------|
| [concepts.md](concepts.md) | Core cryptographic and mathematical concepts behind CoSMeTIC |
| [architecture.md](architecture.md) | Codebase structure, module responsibilities, and data flow |
| [quickstart.md](quickstart.md) | Getting started locally with `driver.py` (no Docker) |
| [api_reference.md](api_reference.md) | Full reference for the three Flask proof APIs (ACC / LRT / KS) |
| [docker_deployment.md](docker_deployment.md) | Running the full stack with Docker Compose |

## Tutorials

| File | Description |
|------|-------------|
| [tutorials/01_dry_run.md](tutorials/01_dry_run.md) | Running a dry run without zk-SNARKs |
| [tutorials/02_full_zkp_run.md](tutorials/02_full_zkp_run.md) | Full proof generation with zk-SNARKs |
| [tutorials/03_api_workflow.md](tutorials/03_api_workflow.md) | End-to-end proof via the REST APIs |

## Code Reference

Documentation is organised by package, mirroring the source tree.

### `merkletree/` — Core data structures

| File | Class | Description |
|------|-------|-------------|
| [code/merkletree/SparseMerkleTree.md](code/merkletree/SparseMerkleTree.md) | `SparseMerkleTree` | Sparse Merkle Tree data structure and proof path utilities |
| [code/merkletree/MerkleProver.md](code/merkletree/MerkleProver.md) | `MerkleProver` | Central orchestrator: tree build, EZKL setup, proof generation |

### `transformers/` — Leaf-level transforms

| File | Class | Description |
|------|-------|-------------|
| [code/transformers/index.md](code/transformers/index.md) | *(shared interface)* | Common constructor attributes and methods for all transformers |
| [code/transformers/FlowThrough.md](code/transformers/FlowThrough.md) | `FlowThrough` | Identity transform — concatenates input and salt |
| [code/transformers/Affine.md](code/transformers/Affine.md) | `Affine` | Affine (linear) transform with private slope/intercept |
| [code/transformers/Exponent.md](code/transformers/Exponent.md) | `Exponent` | Element-wise integer exponentiation (powers 0–4) |
| [code/transformers/Length.md](code/transformers/Length.md) | `Length` | Non-zero indicator; used to count sample size `N` |
| [code/transformers/BinCount.md](code/transformers/BinCount.md) | `BinCount` | Histogram bin assignment; used for the KS test |
| [code/transformers/LogisticFunction.md](code/transformers/LogisticFunction.md) | `LogisticRegression` | Per-record logistic accuracy contribution |
| [code/transformers/LogisticLogLikelihood.md](code/transformers/LogisticLogLikelihood.md) | `LogLogLikelihood` | Per-record log-likelihood (polynomial softplus); used for LRT |

### `aggregators/` — Node aggregation

| File | Class | Description |
|------|-------|-------------|
| [code/aggregators/Adder.md](code/aggregators/Adder.md) | `Adder` | Element-wise summation of sibling node values |

### `modules/` — High-level test pipelines

| File | Class | Description |
|------|-------|-------------|
| [code/modules/LogisticAccuracy.md](code/modules/LogisticAccuracy.md) | `LogisticAccuracy` | Proves logistic regression accuracy over a committed dataset |
| [code/modules/LogisticLRT.md](code/modules/LogisticLRT.md) | `LogisticLRT` | Proves the Likelihood Ratio Test statistic |
| [code/modules/KolmogorovSmirnov.md](code/modules/KolmogorovSmirnov.md) | `KolmogorovSmirnov` | Proves the KS test statistic between two samples |

### `postaggregators/` — Post-tree statistics

| File | Class | Description |
|------|-------|-------------|
| [code/postaggregators/LRTStatistic.md](code/postaggregators/LRTStatistic.md) | `LRTStatistic` | Computes and proves `LRT = 2*(ll_full - ll_reduced)` |
| [code/postaggregators/MaxAbsGap.md](code/postaggregators/MaxAbsGap.md) | `MaxAbsGap` | Computes and proves the KS supremum `max|CDF_1 - CDF_2|` |

### `stats_logger/` — Docker sidecar

| File | Description |
|------|-------------|
| [code/stats_logger/stats_logger.md](code/stats_logger/stats_logger.md) | Flask sidecar that scrapes and snapshots Docker container metrics |

### `utils/` — Shared data utilities

| File | Description |
|------|-------------|
| [code/utils/data.md](code/utils/data.md) | User record creation, data loading, `RegressionData` class |

---

## Quick orientation

The framework proves two things:

- **Inclusion**: a specific user's (private) data *was* used in computing a public aggregate.
- **Exclusion**: a specific user's (private) data *was not* used in computing a public aggregate.

Both proofs use **Sparse Merkle Trees (SMTs)** backed by **zk-SNARKs** (via [EZKL](https://github.com/zkonduit/ezkl)) so that neither the raw data nor the transformation function needs to be disclosed publicly.
