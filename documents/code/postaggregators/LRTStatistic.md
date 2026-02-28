# `LRTStatistic` — `postaggregators/LRTStatistic.py`

Computes and proves the **Likelihood Ratio Test (LRT) statistic**:

```
LRT = -2 * (ll_reduced - ll_full) = 2 * (ll_full - ll_reduced)
```

where `ll_full` and `ll_reduced` are the root values (total log-likelihoods) of the full-model and reduced-model SMTs respectively.

## Inner class: `LRT_Test` (torch.nn.Module)

A minimal PyTorch model that computes the LRT statistic from two root value tensors. Used solely to export a clean ONNX graph for EZKL.

### `forward(ll_full, ll_reduced)`

```python
lrt_statistic = -2 * (ll_reduced[0][0] - ll_full[0][0])
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `ll_full` | `torch.Tensor` | Root value of the full model SMT, shape `(1, dim)`. Only `[0][0]` is used. |
| `ll_reduced` | `torch.Tensor` | Root value of the reduced model SMT, shape `(1, dim)`. Only `[0][0]` is used. |

**Returns** `torch.Tensor` — scalar LRT statistic.

---

## `LRTStatistic` class

### Constructor

```python
LRTStatistic(outdir_name, reduced_dim, full_dim, zkp_scale, setup=True, prove=True)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `outdir_name` | `str` | Directory for all EZKL artifacts and proof files. Created if it does not exist. |
| `reduced_dim` | `int` | Dimensionality of the reduced model root value tensor. |
| `full_dim` | `int` | Dimensionality of the full model root value tensor. |
| `zkp_scale` | `int` | Fixed-point scale for EZKL settings. |
| `setup` | `bool` | If `True`, runs circuit compilation and key generation on construction. |
| `prove` | `bool` | If `True`, generates proofs when `forward()` is called. |

**EZKL configuration (`py_run_args`):**

| Setting | Value |
|---------|-------|
| `input_visibility` | `"hashed"` |
| `output_visibility` | `"public"` |
| `param_visibility` | `"private"` |
| `logrows` | `20` |
| `decomp_legs` | `4` |
| `decomp_base` | `16384` |

**Artifact files in `outdir_name/`:**

| File | Description |
|------|-------------|
| `abs_gap.onnx` | ONNX export of `LRT_Test`. |
| `abs_gap.compiled` | Compiled EZKL circuit. |
| `settings.json` | EZKL settings. |
| `calibration.json` | Calibration data (same as `input.json`). |
| `proving.key` | Proving key. |
| `verifying.key` | Verification key. |

`export_and_setup()` is called automatically in `__init__`.

---

### `dump_data(ll_full, ll_reduced, run_id)`

Writes input JSON for EZKL witness generation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `ll_full` | `torch.Tensor` | Full model root value. |
| `ll_reduced` | `torch.Tensor` | Reduced model root value. |
| `run_id` | `int \| None` | If not `None`, also writes `input_run<run_id>.json`. |

Writes `input.json` and `calibration.json` to `outdir_name/`.

---

### `setup_once()` *(async)*

Runs the full EZKL setup sequence:

1. `ezkl.gen_settings` → `settings.json`
2. `ezkl.compile_circuit` → `.compiled`
3. `ezkl.get_srs` → SRS download/validation
4. `ezkl.setup` → `proving.key` + `verifying.key`

!!! note
    Called via `asyncio.run(self.setup_once())` inside `export_and_setup`. Skipped if both `.compiled` and `.pk` already exist on disk.

---

### `export_and_setup()`

Exports the `LRT_Test` model to ONNX using zero tensors of the correct shape, then conditionally runs `setup_once`. Called automatically in `__init__`.

---

### `generate_proof_for(ll_full, ll_reduced, run_id)` *(async)*

Generates a witness and proof for a single `(ll_full, ll_reduced)` pair.

| Parameter | Type | Description |
|-----------|------|-------------|
| `ll_full` | `torch.Tensor` | Full model root value. |
| `ll_reduced` | `torch.Tensor` | Reduced model root value. |
| `run_id` | `int` | Used to name `witness_<run_id>.json` and `proof_<run_id>.pf`. |

**Returns** `dict`:

| Key | Type | Description |
|-----|------|-------------|
| `run_id` | `int` | The run identifier. |
| `witness_path` | `Path` | Path to the generated witness file. |
| `proof_path` | `Path` | Path to the generated `.pf` proof file. |
| `lrt` | `float` | The computed LRT statistic value. |

---

### `forward(ll_full, ll_reduced, run_id=1)`

Synchronous entry point. Calls `generate_proof_for` via `asyncio.run`, then immediately verifies all proofs in `outdir_name/` with `verify_all_with_single_vk`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `ll_full` | `torch.Tensor` | Full model root value. |
| `ll_reduced` | `torch.Tensor` | Reduced model root value. |
| `run_id` | `int` | Run identifier for file naming. Default `1`. |

**Returns** `tuple[dict, bool, list]` — `(result, ok, failed)`.

---

### `verify_all_with_single_vk()`

Verifies all `proof_*.pf` files in `outdir_name/` against the single verification key.

**Returns** `tuple[bool, list]` — `(all_ok, failed_list)`.

- `all_ok`: `True` if every proof verified.
- `failed_list`: list of `(proof_path, reason)` tuples for any failures.
