# `LogisticLRT` — `modules/LogisticLRT.py`

Proves the **Likelihood Ratio Test (LRT)** statistic comparing a full logistic regression model against a reduced (intercept-only) model.

```
LRT = -2 * (ll_reduced - ll_full) = 2 * (ll_full - ll_reduced)
```

Two SMTs are built using `LogLogLikelihood` as the transformer, one for each model. The `LRTStatistic` post-aggregator then takes both root values and generates a zk-SNARK for the LRT statistic itself.

| SMT | Prover name | Model | Features |
|-----|-------------|-------|---------|
| `mrp_full` | `ll_full` | Full model | First `n_params` features (with intercept). |
| `mrp_reduced` | `ll_reduced` | Reduced (intercept-only) | First column only. |

## Constructor

```python
LogisticLRT(proof_root_path="./proofs/")
```

**Environment variables read on construction:**

| Variable | Default | Description |
|----------|---------|-------------|
| `ZKP_MODE` | `1` | Enable zk-SNARKs. |
| `GEN_FULL_PROOF` | `1` | Full proof at every level. |
| `SETUP_MRP` | `1` | MRP circuit setup. |
| `SETUP_LTR` | `1` | LTR circuit setup. |
| `ZKP_SCALER` | `12` | Fixed-point scale. |
| `TREE_HEIGHT` | `256` | SMT height. |
| `ID` | `None` | `"id_full,id_reduced"`. |

**Fixed data shapes:**

| Shape | Value | Description |
|-------|-------|-------------|
| `full_record_shape` | `6` | Features in the full model (before intercept). |
| `reduced_record_shape` | `2` | Features in the reduced model. |
| `salt_shape` | `2` | User salt dimensions. |
| `transform_salt_shape` | `2` | Transform salt dimensions. |

---

## Methods

### `process_data(data_file_name, coefficients_file_name)`

Loads training data and model coefficients. When `SCALING_DOWN=True` (hardcoded), uses the first 12 samples and first 5 parameters.

**Returns** `tuple` — `(beta_full, beta_reduced, mask_full, mask_reduced, raw_data_full, raw_data_reduced, raw_default_value_full, raw_default_value_reduced)`.

The `mask_full` tensor has all 1s (all features active); `mask_reduced` has 1 only in position 0 (intercept column only).

---

### `create_smt_full(beta_full, mask_full, raw_data_full, raw_default_value_full)`

Builds the full-model log-likelihood SMT. Prover name `"ll_full"`.

**Returns** `MerkleProver` (`self.mrp_full`).

---

### `create_smt_reduced(beta_reduced, mask_reduced, raw_data_reduced, raw_default_value_reduced)`

Builds the reduced-model log-likelihood SMT. Prover name `"ll_reduced"`.

**Returns** `MerkleProver` (`self.mrp_reduced`).

---

### `buildAllSMT()`

Full setup pipeline: `process_data → create_smt_full → create_smt_reduced → LRTStatistic.forward(ll_full, ll_reduced)`.

Prints the LRT statistic and verification status.

---

### `run(TEST_INCLUSION=False, TEST_EXCLUSION=False)`

Triggers inclusion/exclusion tests on both `mrp_full` and `mrp_reduced`.

---

### `save()` / `load(cosmet_save_path)` *(static method)*

Same pattern as `LogisticAccuracy`. Strips `PyRunArgs` before pickling; re-attaches on load.
