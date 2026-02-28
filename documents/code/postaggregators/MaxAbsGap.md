# `MaxAbsGap` — `postaggregators/MaxGap.py`

Computes and proves the **KS test statistic** — the maximum absolute gap between the empirical CDFs of two histogram-summarised samples:

```
cdf_a = cumsum(a[:, :n_bins]) / sum(a)
cdf_b = cumsum(b[:, :n_bins]) / sum(b)
KS    = max(|cdf_a - cdf_b|)
```

where `a` and `b` are the root values of the two sample SMTs (bin-count histograms produced by `BinCount`).

## Inner class: `AbsGapModel` (torch.nn.Module)

Computes the CDF-based KS statistic from two histogram tensors.

### Constructor

```python
AbsGapModel(nbins=1)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `nbins` | `int` | `1` | Number of histogram bins to use. |

### `forward(aval, bval)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `aval` | `torch.Tensor` | Sample 1 root value; only `[:, :nbins]` is used. |
| `bval` | `torch.Tensor` | Sample 2 root value; only `[:, :nbins]` is used. |

**Returns** `torch.Tensor` — scalar maximum absolute gap (the KS statistic).

**Steps:**

1. Slice first `nbins` elements from each tensor.
2. Compute normalised cumulative sums (CDFs), with `EPS=1e-6` to avoid division by zero.
3. Return `max(|cdf_a - cdf_b|)`.

---

## `MaxAbsGap` class

### Constructor

```python
MaxAbsGap(
    outdir_name="abs_gap_zk_api",
    zkp_scale=10,
    shape=None,
    nbins=None,
    trailer_extras=2
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `outdir_name` | `str` | `"abs_gap_zk_api"` | Output directory for artifacts and proofs. |
| `zkp_scale` | `int` | `10` | Fixed-point scale for EZKL. |
| `shape` | `any` | `None` | Kept for API compatibility; not used internally. |
| `nbins` | `int \| None` | `None` | Number of histogram bins. If `None`, inferred from the first `forward()` call. |
| `trailer_extras` | `int` | `2` | Number of non-bin fields at the end of each root value tensor (the transform salt dimensions). Subtracted when inferring `nbins`. |

**EZKL configuration (`py_run_args`):**

| Setting | Value |
|---------|-------|
| `input_visibility` | `"hashed"` |
| `output_visibility` | `"public"` |
| `param_visibility` | `"private"` |
| `logrows` | `20` |
| `decomp_legs` | `5` |
| `decomp_base` | `16384` |
| `rebase_frac_zero_constants` | `True` |

!!! note
    Unlike `LRTStatistic`, `MaxAbsGap` delays ONNX export and circuit setup until the first `forward()` call, because `nbins` must be inferred from the actual input tensors.

---

### `_export_and_setup(nbins)` *(async)*

Exports `AbsGapModel(nbins)` to ONNX, resets old artifacts, and runs the full EZKL setup.

| Parameter | Type | Description |
|-----------|------|-------------|
| `nbins` | `int` | Number of bins for the circuit. Overwrites `self.nbins`. |

---

### `_setup_once()` *(async)*

Runs `gen_settings → compile_circuit → get_srs → setup` in sequence.

---

### `_dump_data(a_vals, b_vals, run_id=None)`

Writes `input.json` (and optionally `input_run<run_id>.json`) for EZKL witness generation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `a_vals` | `torch.Tensor` | Sample 1 root value. |
| `b_vals` | `torch.Tensor` | Sample 2 root value. |
| `run_id` | `int \| None` | If not `None`, also writes a run-specific input file. |

---

### `_ensure_ready(a_vals, b_vals)` *(async)*

Infers `nbins` from `min(len(a), len(b)) - trailer_extras`. Calls `_export_and_setup` if `nbins` is not yet set or has changed.

| Parameter | Type | Description |
|-----------|------|-------------|
| `a_vals` | `torch.Tensor` | Sample 1 root value. |
| `b_vals` | `torch.Tensor` | Sample 2 root value. |

!!! warning
    If `nbins` changes between calls (e.g., because input shapes changed), all existing circuit artifacts are deleted and rebuilt. This is a slow operation.

---

### `_generate_proof_for(a, b, run_id)` *(async)*

Generates a witness and proof for one `(a, b)` pair.

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Sample 1 root value. |
| `b` | `torch.Tensor` | Sample 2 root value. |
| `run_id` | `int` | Run identifier for file naming. |

**Returns** `dict`:

| Key | Type | Description |
|-----|------|-------------|
| `run_id` | `int` | Run identifier. |
| `witness_path` | `Path` | Path to the witness JSON. |
| `proof_path` | `Path` | Path to the `.pf` proof file. |
| `supremum` | `float` | The computed KS statistic (max absolute gap). |

---

### `forward(a_vals, b_vals, run_id=1)`

Synchronous entry point. Infers `nbins` if necessary, generates a proof, then verifies.

| Parameter | Type | Description |
|-----------|------|-------------|
| `a_vals` | `torch.Tensor` | Sample 1 SMT root value. |
| `b_vals` | `torch.Tensor` | Sample 2 SMT root value. |
| `run_id` | `int` | Run identifier. Default `1`. |

**Returns** `tuple[dict, bool, list]` — `(result, ok, failed)`.

---

### `verify_all_with_single_vk()`

Verifies all `proof_*.pf` files in `outdir_name/` against the single verification key.

**Returns** `tuple[bool, list]` — `(all_ok, failed_list)`.
