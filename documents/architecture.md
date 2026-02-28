# Codebase Architecture

This document describes how the source code is organized and how the components interact at runtime.

---

## Directory layout

```
cosmetic/
├── driver.py                   # Standalone script for local testing
├── api_acc_test.py             # Flask API — Logistic Accuracy
├── api_ks_test.py              # Flask API — Kolmogorov-Smirnov
├── api_lrt_test.py             # Flask API — Likelihood Ratio Test
├── start_apis.sh               # Shell script to start all three APIs
│
├── merkletree/
│   ├── MerkleProver.py         # Core orchestrator: builds SMT, generates proofs
│   └── SparseMerkleTree.py     # SMT data structure and operations
│
├── aggregators/
│   └── Adder.py                # Element-wise sum aggregator (torch.nn.Module)
│
├── transformers/
│   ├── FlowThrough.py          # Identity transform
│   ├── Affine.py               # Affine (linear) transform
│   ├── Exponent.py             # Exponentiation transform
│   ├── Length.py               # L2-norm transform
│   ├── BinCount.py             # Histogram / bin-count transform
│   ├── LogisticFunction.py     # Logistic sigmoid transform
│   └── LogisticLogLikelihood.py# Log-likelihood of logistic model
│
├── modules/
│   ├── LogisticAccuracy.py     # High-level ACC test pipeline
│   ├── LogisticLRT.py          # High-level LRT test pipeline
│   └── KolmogorovSmirnov.py    # High-level KS test pipeline
│
├── postaggregators/
│   ├── LRTStatistic.py         # Computes LRT statistic from two SMT roots
│   └── MaxGap.py               # Computes max-gap (KS) statistic from two roots
│
├── utils/
│   └── data.py                 # Data loading / preprocessing helpers
│
├── stats_logger/
│   └── stats_logger.py         # Flask service collecting CPU/memory stats
│
├── Dockerfile.pyslim.prover    # Image for the prover APIs
├── Dockerfile.pyslim.statslogger # Image for the stats logger
├── docker-compose.yml          # Two-container stack definition
├── Makefile                    # Build helpers
└── requirements.txt            # Python dependencies
```

---

## Layer diagram

```
┌───────────────────────────────────────────────────────┐
│                   Client / Script                     │
│             (driver.py  or  curl / HTTP)              │
└───────────────┬───────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────┐
│            Flask API Layer (optional)                 │
│      api_acc_test.py / api_lrt_test.py / api_ks_test.py │
└───────────────┬───────────────────────────────────────┘
                │ calls
┌───────────────▼───────────────────────────────────────┐
│              Module Layer                             │
│   LogisticAccuracy / LogisticLRT / KolmogorovSmirnov  │
└───────────────┬───────────────────────────────────────┘
                │ instantiates
┌───────────────▼───────────────────────────────────────┐
│             MerkleProver                              │
│     (merkletree/MerkleProver.py)                      │
│                                                       │
│  ┌──────────────┐   ┌───────────────────────────────┐ │
│  │ SparseMerkle │   │  EZKL proof machinery         │ │
│  │    Tree      │   │  (setup / prove / verify)     │ │
│  └──────────────┘   └───────────────────────────────┘ │
└──────┬──────────────────────────┬─────────────────────┘
       │                          │
┌──────▼──────┐           ┌───────▼──────┐
│ Aggregator  │           │  Transformer │
│  (Adder)    │           │  (any F)     │
└─────────────┘           └─────────────┘
```

---

## Key classes and their responsibilities

### `MerkleProver` (`merkletree/MerkleProver.py`)

The central orchestrator. Responsibilities:

- Accepts a list of raw data records, a `transformer`, and an `aggregator`.
- Builds the SMT by applying `F` and then `G` at each level.
- Manages EZKL circuit setup, proof generation, and verification for both leaf transforms (`ltr`) and Merkle path proofs (`mrp`).
- Exposes `_build_smt()`, `test_inclusion()`, `path_walk()`, `transform_individual_data_record()`, and `setup_proofs()`.

Key constructor parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `prover_name` | `str` | Logical name — determines the subdirectory under `proofs/` |
| `id` | `str \| None` | UUID of a pre-existing circuit. `None` triggers new setup. |
| `aggregator` | `torch.nn.Module` | The global aggregation function `G` |
| `transformer` | `torch.nn.Module` | The leaf transform `F` |
| `raw_data` | `list[dict]` | List of `{"name": str, "value": Tensor, "transform_salt": Tensor}` |
| `raw_default_value` | `Tensor` | Default leaf value (all zeros) |
| `length_transform_salt` | `int` | Dimensionality of `TS_i` |
| `setup_mrp` | `bool` | Whether to compile/setup the MRP circuit |
| `setup_ltr` | `bool` | Whether to compile/setup the LTR circuit |

### `SparseMerkleTree` (`merkletree/SparseMerkleTree.py`)

The pure data-structure layer. Stores the tree nodes in memory, computes hashes at each level, and returns sibling lists (Merkle paths) for any leaf position.

### Transformers (`transformers/`)

Each transformer is a `torch.nn.Module` subclass that implements a `forward()` method. This allows EZKL to compile it into an arithmetic circuit. The constructor accepts `length_transform_salt` so it knows how many trailing dimensions are salting values.

### Aggregators (`aggregators/`)

Similarly, aggregators are `torch.nn.Module` subclasses representing `G`. The only built-in aggregator is `Adder` (element-wise summation), which is commutative and associative — required for recursive Merkle aggregation.

### Post-aggregators (`postaggregators/`)

Applied *after* the SMT is built. They combine the roots of two separate SMTs to produce a scalar test statistic:

- `LRTStatistic` — computes `2 * (log-likelihood_full − log-likelihood_reduced)`.
- `MaxGap` — computes the maximum absolute difference between two empirical CDFs (KS statistic).

### Modules (`modules/`)

High-level pipelines that wire together two `MerkleProver` instances (one per sample or model) and one post-aggregator. Used directly by the API layer.

---

## Proof artifact layout on disk

```
proofs/
└── <prover_name>/
    └── <uuid>/
        ├── ltr_keys/
        │   ├── network.onnx
        │   ├── model.compiled
        │   ├── pk.key
        │   ├── vk.key
        │   └── settings.json
        └── mrp_keys/
            ├── network.onnx
            ├── model.compiled
            ├── pk.key
            ├── vk.key
            └── settings.json
```

Generated proof files (`.pf`) are written alongside the keys or into a job-specific subfolder when using the API.

---

## Environment variables (runtime)

| Variable | Default | Effect |
|----------|---------|--------|
| `ZKP_MODE` | `1` | `1` = generate real zk-SNARKs; `0` = dry run (forward pass only) |
| `GEN_FULL_PROOF` | `0` | `1` = generate a proof at every SMT level; `0` = skip levels with no non-default siblings |
| `SETUP_MRP` | `0` | `1` = compile and key-gen for the MRP circuit |
| `SETUP_LTR` | `0` | `1` = compile and key-gen for the LTR circuit |
| `ID` | `None` | UUID of existing circuits to reuse. Leave blank to generate a new one. |
| `LTR_CHOICE` | `"flow-through"` | Transformer to use in `driver.py` (`affine`, `exponent`, `length`, `flow-through`) |
