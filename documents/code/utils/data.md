# `utils/data.py`

Data preparation utilities shared across all three statistical test modules. Handles user record construction (with salting), dataset loading, and the `RegressionData` class for flexible logistic regression data management.

---

## General utilities

### `print_root_value(mrp, title)`

Prints the root value of a `MerkleProver` in a formatted block.

| Parameter | Type | Description |
|-----------|------|-------------|
| `mrp` | `MerkleProver` | The prover whose root value to display. |
| `title` | `str` | Label printed above the root value (e.g. `"Accuracy"`). |

---

### `create_inclusion_case(raw_data, idx)`

Returns the record at position `idx` from `raw_data`. Used to build a known-member test case for inclusion proofs.

| Parameter | Type | Description |
|-----------|------|-------------|
| `raw_data` | `list[dict]` | Full dataset. |
| `idx` | `int` | Index of the record to use. Must be `< len(raw_data)`. |

**Returns** `dict` — the record at `raw_data[idx]`.

**Raises** `AssertionError` if `idx >= len(raw_data)`.

---

### `create_users(x_values, y_values=None, salt_shape=1, transform_salt_shape=2, rand_bit=1, seed=None)`

The core factory for building CoSMeTIC-formatted user record lists from raw feature arrays. Handles optional labels, user salt generation, and transform salt generation.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `x_values` | `array-like` | — | Feature matrix, shape `(n_users, n_features)` or `(n_users,)`. |
| `y_values` | `array-like \| None` | `None` | Optional label vector/matrix, shape `(n_users,)` or `(n_users, y_shape)`. If provided, concatenated with `x_values`. |
| `salt_shape` | `int` | `1` | Number of user salt dimensions appended to `Concat(x, y)`. |
| `transform_salt_shape` | `int` | `2` | Number of transform salt dimensions. |
| `rand_bit` | `int` | `1` | Multiplier for salt randomisation. Set to `0` to produce zero salts (for debugging). |
| `seed` | `int \| None` | `None` | Random seed for reproducibility. Passed to `torch.manual_seed`. |

**Per-user processing:**

1. Concatenate features `x` and labels `y` (if provided) → `features` of shape `(1, record_shape + y_shape)`.
2. Generate user salt: `rand_bit * randint([0, 2^5), shape=(1, salt_shape))`.
3. Concatenate features and user salt → `value` of shape `(1, record_shape + y_shape + salt_shape)`.
4. Generate transform salt: `rand_bit * randint([0, 2^15), shape=(1, transform_salt_shape))`.

**Returns** `list[dict]` — one dict per user:

| Key | Type | Description |
|-----|------|-------------|
| `name` | `str` | `"user_1"`, `"user_2"`, etc. |
| `value` | `torch.Tensor` | Shape `(1, record_shape + y_shape + salt_shape)`. This is `SD_i = Concat(D_i, US_i)`. |
| `transform_salt` | `torch.Tensor` | Shape `(1, transform_salt_shape)`. This is `TS_i`. |

!!! note
    User salts are drawn from `[0, 31]` (5-bit range) while transform salts are drawn from `[0, 32767]` (15-bit range). This asymmetry reflects the different roles: user salts are concatenated with raw data before hashing, while transform salts are concatenated with the transformer output.

---

## Logistic regression utilities

### `prepare_coefs(path, to_tensor=True)`

Loads logistic regression coefficients and intercept from a Pickle file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | — | Path to the Pickle file. Expected keys: `"coefs"`, `"intercept"`. |
| `to_tensor` | `bool` | `True` | If `True`, converts numpy arrays to `torch.float32` tensors. |

**Returns** `tuple[tensor, tensor]` — `(coefs, intercept)`.

---

### `prepare_real_data(path, n_samples=None, to_tensor=True)`

Loads test data from a Pickle file. Expected keys: `"X_test"`, `"y_test"`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | — | Path to the Pickle file. |
| `n_samples` | `int \| None` | `None` | If provided, returns only the first `n_samples` rows. |
| `to_tensor` | `bool` | `True` | If `True`, converts to `torch.float32` tensors. `y` is reshaped to `(-1, 1)`. |

**Returns** `tuple[tensor, tensor]` — `(X, y)`.

---

### `setup_logreg_HIV_example(model_path, data_path, n_samples=None, salt_shape=2, transform_salt_shape=2, rand_bit=1, seed=None)`

Convenience wrapper that loads coefficients and data from Pickle files and calls `create_users`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_path` | `str` | Path to the model coefficients Pickle. |
| `data_path` | `str` | Path to the data Pickle. |
| `n_samples` | `int \| None` | Number of records to use. |
| `salt_shape` | `int` | User salt dimensions. |
| `transform_salt_shape` | `int` | Transform salt dimensions. |
| `rand_bit` | `int` | Salt randomisation multiplier. |
| `seed` | `int \| None` | Random seed. |

**Returns** `tuple[list[dict], tensor, tensor]` — `(raw_data, coefs, intercept)`.

---

### `setup_logreg_synthetic_example(x_values, y_values, coefs, intercept, salt_shape=2, transform_salt_shape=2, rand_bit=1, seed=None)`

Same as `setup_logreg_HIV_example` but accepts synthetic in-memory arrays instead of file paths.

| Parameter | Type | Description |
|-----------|------|-------------|
| `x_values` | `array-like` | Feature matrix. |
| `y_values` | `array-like` | Label vector. |
| `coefs` | `array-like` | Coefficient array, converted to shape `(1, n_coefs)`. |
| `intercept` | `array-like` | Intercept, converted to shape `(1, 1)`. |

**Returns** `tuple[list[dict], tensor, tensor]` — `(raw_data, coefs_tensor, intercept_tensor)`.

---

## KS test utility

### `setup_ks_HD_example(data_path, n_samples=None, salt_shape=2, transform_salt_shape=2, rand_bit=1, seed=None)`

Loads healthy and HD (Huntington's Disease) samples from a Pickle file and prepares two user record lists with shared bin edges.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data_path` | `str` | — | Path to `data_for_ks_test.pkl`. Expected keys: `"healthy"`, `"HD"`. |
| `n_samples` | `int \| None` | `None` | If provided, truncates each sample to the first `n_samples` records. |
| `salt_shape` | `int` | `2` | User salt dimensions. |
| `transform_salt_shape` | `int` | `2` | Transform salt dimensions. |
| `rand_bit` | `int` | `1` | Salt randomisation multiplier. |
| `seed` | `int \| None` | `None` | Random seed. |

**Bin edges:** `torch.arange(start=10, end=90, step=5)` → 16 edges, 15 bins.

**Returns** `tuple[list[dict], list[dict], torch.Tensor]` — `(raw_data_s1, raw_data_s2, edges)`.

---

## `RegressionData` class

A flexible data manager for logistic regression datasets stored as Pickle files. Supports optional feature sub-sampling, observation sub-sampling, and intercept addition.

### Constructor

```python
RegressionData(
    file_path,
    add_intercept=True,
    n_features=None,
    to_tensor=True,
    max_tries=1000,
    random_state=None
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `file_path` | `str` | — | Path to Pickle file. Expected keys: `"X_train"`, `"X_test"`, `"y_train"`, `"y_test"`, `"feature_names"`. |
| `add_intercept` | `bool` | `True` | If `True`, prepends a column of ones to `X` (intercept term). |
| `n_features` | `int \| None` | `None` | If set, sub-samples this many features using a round-robin group strategy. |
| `to_tensor` | `bool` | `True` | If `True`, converts outputs to `torch.float32` tensors. |
| `max_tries` | `int` | `1000` | Maximum random sampling attempts when selecting observations. |
| `random_state` | `int \| None` | `None` | NumPy random seed for reproducibility. |

**Calls `load_full_data()` on construction.**

---

### `load_full_data()`

Loads the full dataset from `self.file_path` into memory as instance attributes:

| Attribute | Description |
|-----------|-------------|
| `full_X_train` | Full training feature matrix. |
| `full_X_test` | Full test feature matrix. |
| `full_y_train` | Training labels, shape `(N, 1)`. |
| `full_y_test` | Test labels, shape `(N, 1)`. |
| `full_feature_names` | List of feature name strings. |
| `N_train`, `N_test` | Number of training/test observations. |
| `F` | Total number of features. |

---

### `prepare_train_data(n_samples)`

Prepares training data with optional feature and observation sub-sampling, then optionally adds an intercept column.

| Parameter | Type | Description |
|-----------|------|-------------|
| `n_samples` | `int \| None` | Number of training observations to select. If `None`, uses all. |

**Processing pipeline:**

1. `__feature_sampling`: selects `n_features` columns using a round-robin group strategy based on `feature_names` prefixes. Stores `selected_feature_indices` for reuse in `prepare_test_data`.
2. `__observation_sampling`: randomly selects `n_samples` rows, retrying up to `max_tries` times until a sample with no constant features or labels is found.
3. Optionally prepends an intercept column.
4. Converts to tensors if `to_tensor=True`.

**Returns** `tuple[X, y]`.

**Raises:**
- `ValueError` if `n_samples > N_train`.
- `ValueError` if no valid subset is found within `max_tries`.

---

### `prepare_test_data(n_samples, strategy='first_n')`

Prepares test data using the same feature selection as `prepare_train_data`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `n_samples` | `int \| None` | — | Number of test observations to select. If `None`, uses all. |
| `strategy` | `str` | `"first_n"` | `"first_n"`: takes the first `n_samples` rows. `"random"`: draws `n_samples` rows without replacement (seed = `random_state + 1`). |

!!! warning
    `prepare_train_data` must be called before `prepare_test_data` if `n_features` is set, because feature selection indices computed during training are reused for the test set.

**Returns** `tuple[X, y]`.

**Raises:**
- `ValueError` if `n_samples > N_test`.
- `ValueError` if called with `n_features` set but `prepare_train_data` has not been called yet.
