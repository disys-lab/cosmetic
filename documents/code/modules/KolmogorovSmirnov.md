# `KolmogorovSmirnov` — `modules/KolmogorovSmirnov.py`

Proves the **Kolmogorov–Smirnov (KS) test statistic** — the maximum absolute difference between the empirical CDFs of two samples.

Two SMTs are built (one per sample) using the `BinCount` transformer. Both use the same bin edges. The `MaxAbsGap` post-aggregator then takes both root values (which are bin-count histograms) and generates a zk-SNARK for the supremum of `|CDF_1 - CDF_2|`.

| SMT | Prover name | Sample |
|-----|-------------|--------|
| `mrp1` | `simple_sum_bincount_s1` | Sample 1 (healthy). |
| `mrp2` | `simple_sum_bincount_s2` | Sample 2 (HD). |

## Constructor

```python
KolmogorovSmirnov(proof_root_path="./proofs/")
```

**Environment variables read on construction:**

| Variable | Default | Description |
|----------|---------|-------------|
| `ZKP_MODE` | `1` | Enable zk-SNARKs. |
| `GEN_FULL_PROOF` | `1` | Full proof at every level. |
| `SETUP_MRP` | `1` | MRP circuit setup. |
| `SETUP_LTR` | `1` | LTR circuit setup. |
| `ZKP_SCALER` | `10` | Fixed-point scale. |
| `TREE_HEIGHT` | `256` | SMT height. |
| `ID` | `None` | `"id_s1,id_s2"`. |

**Fixed data shapes:**

| Shape | Value | Description |
|-------|-------|-------------|
| `record_shape` | `1` | Single scalar observation per user. |
| `salt_shape` | `2` | User salt dimensions. |
| `transform_salt_shape` | `2` | Transform salt dimensions. |

---

## Methods

### `process_data(data_path, n_samples=12, rand_seed=110)`

Loads healthy and HD samples from a Pickle file. Generates bin edges `[10, 15, 20, ..., 85]` (step 5, via `torch.arange(10, 90, 5)`).

| Parameter | Type | Description |
|-----------|------|-------------|
| `data_path` | `str` | Path to `data_for_ks_test.pkl`. |
| `n_samples` | `int` | Records per sample (default 12). |
| `rand_seed` | `int` | Seed for salt generation. |

**Returns** `tuple` — `(raw_data_s1, raw_data_s2, edges, n_bins, raw_default_value_s1, raw_default_value_s2)`.

---

### `create_smt_sample(raw_data, raw_default_value, name_suffix, id_val, transformer)`

Builds one sample's SMT.

| Parameter | Type | Description |
|-----------|------|-------------|
| `raw_data` | `list[dict]` | User records for this sample. |
| `raw_default_value` | `torch.Tensor` | Default value. |
| `name_suffix` | `str` | `"s1"` or `"s2"` — appended to the prover name. |
| `id_val` | `str \| None` | Circuit UUID for this sample. |
| `transformer` | `BinCount` | Shared transformer instance (same edges for both samples). |

**Returns** `MerkleProver`.

---

### `buildAllSMT()`

Full setup pipeline: `process_data → create_smt_sample(s1) → create_smt_sample(s2) → MaxAbsGap.forward(root_s1, root_s2)`.

Prints the KS statistic (maximum gap) and verification status.

---

### `run(TEST_INCLUSION=False, TEST_EXCLUSION=False)`

Triggers inclusion/exclusion tests on both `mrp1` and `mrp2`.

---

### `save()` / `load(cosmet_save_path)` *(static method)*

Same pattern as other modules. Strips `PyRunArgs` before pickling; re-attaches on load.
