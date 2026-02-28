# `LogisticAccuracy` — `modules/LogisticAccuracy.py`

Proves that the **logistic regression accuracy** of a given model was computed over a specific committed dataset.

Two SMTs are built:

| SMT | Prover name | Transformer | Root value meaning |
|-----|-------------|-------------|-------------------|
| `mrp1` (Length) | `log_acc_length` | `Length` | Sample size `N` — count of non-default records. |
| `mrp2` (Accuracy) | `log_acc` | `LogisticRegression` | Sum of per-record accuracy contributions = overall accuracy. |

The `LogisticRegression` transformer is initialised with `sample_size = mrp1.root_value` so that each per-record accuracy contribution is normalised by the correct `N`.

## Constructor

```python
LogisticAccuracy(proof_root_path="./proofs/")
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `proof_root_path` | `str` | `"./proofs/"` | Root directory for proof artifacts. Actual path becomes `proof_root_path/logistic_accuracy/`. |

**Environment variables read on construction:**

| Variable | Default | Description |
|----------|---------|-------------|
| `ZKP_MODE` | `1` | Enable actual zk-SNARK generation. |
| `GEN_FULL_PROOF` | `1` | Generate proofs at every SMT level. |
| `SETUP_MRP` | `1` | Compile/key-gen the MRP circuit. |
| `SETUP_LTR` | `1` | Compile/key-gen the LTR circuit. |
| `ZKP_SCALER` | `10` | Fixed-point scale. |
| `TREE_HEIGHT` | `256` | SMT height. |
| `ID` | `None` | Comma-separated circuit UUIDs `"id_length,id_acc"`. |

**Fixed data shapes:**

| Shape | Value | Description |
|-------|-------|-------------|
| `record_shape` | `21` | Number of feature + label dimensions. |
| `salt_shape` | `2` | User salt dimensions. |
| `transform_salt_shape` | `2` | Transform salt dimensions. |

---

## Methods

### `process_data(data_file_name, coefficients_file_name, scaling_down=True, n_samples=12)`

Loads logistic regression data and model coefficients from Pickle files.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data_file_name` | `str` | `"./data/data_for_logreg_small.pkl"` | Path to the dataset Pickle. |
| `coefficients_file_name` | `str` | `"./data/logreg_glm_fits.pkl"` | Path to model coefficients Pickle. |
| `scaling_down` | `bool` | `True` | If `True`, truncate to first `n_samples` records. |
| `n_samples` | `int` | `12` | Number of records to use when `scaling_down=True`. |

**Returns** `tuple` — `(beta_full, raw_data, raw_default_value_acc, raw_default_value_length)`.

---

### `create_smt_length(raw_data, raw_default_value)`

Builds the Length SMT (`mrp1`): counts non-default records to determine sample size `N`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `raw_data` | `list[dict]` | User records. |
| `raw_default_value` | `torch.Tensor` | Default value (all zeros). |

**Returns** `MerkleProver` (`self.mrp1`). Root value `[0, 0]` is `N` in its first element.

---

### `create_smt_acc(beta_full, mrp1, raw_data, raw_default_value)`

Builds the Accuracy SMT (`mrp2`): sums per-record accuracy contributions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `beta_full` | `torch.Tensor` | Logistic model coefficients. |
| `mrp1` | `MerkleProver` | The Length SMT, whose `root_value` gives `N`. |
| `raw_data` | `list[dict]` | User records. |
| `raw_default_value` | `torch.Tensor` | Default value. |

**Returns** `MerkleProver` (`self.mrp2`). Root value first element = overall accuracy.

---

### `buildAllSMT()`

Orchestration method called by `__init__`. Runs `process_data → create_smt_length → create_smt_acc` in sequence. Stores all results as instance attributes.

---

### `create_inc_exc_test_case(mrp, raw_data, mode="inc")`

Creates a test record for inclusion or exclusion testing.

| Parameter | Type | Description |
|-----------|------|-------------|
| `mrp` | `MerkleProver` | The SMT to test against. |
| `raw_data` | `list[dict]` | The dataset. |
| `mode` | `str` | `"inc"` uses `raw_data[2]` as-is; `"exc"` replaces the feature values with random noise while keeping the user salt. |

**Returns** `str` — `raw_hash` of the test record.

---

### `test_inclusion(mrp, raw_hash_present, total_transform_salt_shape, nonce1=None)`

Runs the full inclusion proof pipeline for a single record against one SMT.

| Parameter | Type | Description |
|-----------|------|-------------|
| `mrp` | `MerkleProver` | The SMT to prove against. |
| `raw_hash_present` | `str` | Raw hash of the test record. |
| `total_transform_salt_shape` | `int` | Total nonce dimensionality. |
| `nonce1` | `torch.Tensor \| None` | Nonce for the path walk. If `None`, a random nonce is generated. |

---

### `constructInExTestcases(mode="inc")`

Constructs test cases for both SMTs (`mrp1` and `mrp2`) simultaneously.

**Returns** `tuple[str, str]` — `(raw_hash_length, raw_hash_acc)`.

---

### `runTestInExForAllSMTs(mode="inc")`

Runs inclusion or exclusion tests on both SMTs.

| Parameter | Type | Description |
|-----------|------|-------------|
| `mode` | `str` | `"inc"` for inclusion, `"exc"` for exclusion. |

---

### `run(TEST_INCLUSION=False, TEST_EXCLUSION=False)`

Public entry point. Triggers inclusion and/or exclusion tests on both SMTs.

| Parameter | Type | Description |
|-----------|------|-------------|
| `TEST_INCLUSION` | `bool` | Run inclusion test. |
| `TEST_EXCLUSION` | `bool` | Run exclusion test. |

---

### `save()` / `saveClass()`

Serialises the `LogisticAccuracy` instance to `./proofs/logistic_accuracy/cosmetic.pkl` using Pickle.

!!! note
    `ezkl.PyRunArgs` objects are stripped before serialisation (they are not picklable) via `_strip_pyrunargs`. On load, `_prepare_proofs()` is called on both MRPs to re-attach them.

---

### `load(cosmet_save_path)` *(static method)*

Loads a saved `LogisticAccuracy` instance from a Pickle file.

| Parameter | Type | Description |
|-----------|------|-------------|
| `cosmet_save_path` | `str` | Path to the `.pkl` file. |

**Returns** `LogisticAccuracy` instance.
**Raises** `FileNotFoundError` if the path does not exist.

---

### `_strip_pyrunargs(obj)`

Recursively removes `ezkl.PyRunArgs` objects from an object tree to make it picklable.

| Parameter | Type | Description |
|-----------|------|-------------|
| `obj` | `any` | Any Python object. |

**Returns** The same object with all `PyRunArgs` instances replaced by `None`.
