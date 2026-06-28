# `MerkleProver` — `merkletree/MerkleProver.py`

The central orchestrator. Wraps a `SparseMerkleTree` with EZKL circuit setup and proof generation. Manages file paths for all artifacts, coordinates transformer and aggregator, and exposes the public API for building trees, testing inclusion/exclusion, and generating proofs.

## Constructor

```python
MerkleProver(
    prover_name="default_mrp",
    aggregator=None,
    transformer=None,
    zkp_scale=10,
    tree_height=256,
    raw_default_value=None,
    raw_data=None,
    root_path="./proofs/",
    length_transform_salt=10,
    setup_mrp=0,
    setup_ltr=0,
    id=None,
    create_timestamp=False
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prover_name` | `str` | `"default_mrp"` | Logical name; determines the top-level subdirectory under `root_path`. |
| `aggregator` | `nn.Module` | `None` | An `Adder` instance (or compatible aggregator). |
| `transformer` | `nn.Module` | `None` | Any transformer from `transformers/`. |
| `zkp_scale` | `int` | `10` | Fixed-point scale passed to EZKL settings. |
| `tree_height` | `int` | `256` | Height of the SMT. Determines hash truncation length. |
| `raw_default_value` | `torch.Tensor` | `None` | Default raw leaf value (all zeros, same shape as a user record). |
| `raw_data` | `list[dict]` | `None` | List of user records: `[{"name": str, "value": Tensor, "transform_salt": Tensor}, ...]`. |
| `root_path` | `str` | `"./proofs/"` | Root directory for all circuit and proof artifacts. |
| `length_transform_salt` | `int` | `10` | Dimensionality of `TS_i`. |
| `setup_mrp` | `int` (0/1) | `0` | If `1`, compiles and key-gens the MRP circuit. Automatically set to `1` when `id=None`. |
| `setup_ltr` | `int` (0/1) | `0` | If `1`, compiles and key-gens the LTR circuit. Automatically set to `1` when `id=None`. |
| `id` | `str \| None` | `None` | UUID of pre-existing circuits to reuse. If `None`, a new UUID is generated via `uuid.uuid1()`. |
| `create_timestamp` | `bool` | `False` | If `True`, proof result files are placed in a timestamped subfolder. |

**Artifact directories created by `__init__`:**

```
root_path/<prover_name>/<uuid>/
├── mrp_keys/          ← compiled MRP circuit, pk, vk, settings.json
├── ltr_keys/          ← compiled LTR circuit, pk, vk, settings.json
└── proof-results-<timestamp>/
    ├── mrp/           ← per-step witness/input/proof files
    └── ltr/           ← per-record witness/input/proof files
```

---

## Initialisation methods

### `create_timestamped_folder(create_timestamp=True)`

Returns a timestamped folder name `proof-results-YYYYMMDDHHMMSS`. Used to organise proof output files per run.

| Parameter | Type | Description |
|-----------|------|-------------|
| `create_timestamp` | `bool` | If `False`, always returns the same static folder name. |

**Returns** `str`.

---

### `_prepare_proofs()`

Initialises all file paths for the MRP and LTR circuits and configures `ezkl.PyRunArgs` for both:

- **MRP** (`py_run_args_mrp`): inputs and outputs are hashed; params are private.
- **LTR** (`py_run_args_ltr`): same visibility, plus `rebase_frac_zero_constants=True`.

Both use `logrows=20`, `decomp_legs=4`, `decomp_base=16384`.

Called automatically in `__init__`.

---

### `setup_proofs(setup_mrp=False, setup_ltr=False)`

Triggers circuit compilation and key generation for the MRP and/or LTR circuits.

| Parameter | Type | Description |
|-----------|------|-------------|
| `setup_mrp` | `bool` | If `True`, calls `aggregator.setup_proof(...)` with MRP paths and args. |
| `setup_ltr` | `bool` | If `True`, calls `transformer.setup_proof(...)` with LTR paths and args. |

---

## EZKL async helpers

### `_async_srs(settings_path)`

Async coroutine that fetches/validates the Structured Reference String (SRS) required by EZKL.

| Parameter | Type | Description |
|-----------|------|-------------|
| `settings_path` | `str` | Path to `settings.json`. |

---

### `_async_compile(data_path, compiled_model_path, witness_path)`

Async coroutine that generates an EZKL witness from an input JSON file.

| Parameter | Type | Description |
|-----------|------|-------------|
| `data_path` | `str` | Path to input JSON. |
| `compiled_model_path` | `str` | Path to compiled circuit. |
| `witness_path` | `str` | Output path for the witness JSON. |

---

## Data acquisition

### `_secure_data_acquisition()`

Transforms all raw user records through the transformer and builds the internal hash maps. Called internally by `_build_smt`.

**Returns** `list[dict]` — `[{"hash": str, "value": Tensor}, ...]`, one entry per user record (hashed transformed leaf values ready for tree insertion).

**Side effects — populates:**

| Map | Keys | Values |
|-----|------|--------|
| `map_rawhash_rawvalue` | `hash(raw_value)` | `raw_value` tensor |
| `map_rawhash_transformedhash` | `hash(raw_value)` | `hash(transformed_value)` |
| `map_rawhash_transformsalt` | `hash(raw_value)` | `transform_salt` tensor |
| `map_rawhash_transformedvalue` | `hash(raw_value)` | `transformed_value` tensor |

---

### `transform_individual_data_record(raw_test_record=None, record_index=-1)`

Transforms a single data record and returns both its raw and transformed hashes. Used to prepare a record for inclusion/exclusion testing without rebuilding the whole tree.

| Parameter | Type | Description |
|-----------|------|-------------|
| `raw_test_record` | `dict \| None` | Dict `{"value": Tensor, "transform_salt": Tensor}`. |
| `record_index` | `int` | If `!= -1`, picks `raw_data[record_index]` instead. |

**Returns** `tuple[str, str]` — `(transformed_hash, raw_hash)`.

---

## Tree construction

### `_build_smt()`

Full tree construction pipeline:

1. Calls `_secure_data_acquisition()` to transform all records.
2. Calls `smt.build_tree(hashed_leaves)` to populate the tree.
3. Extracts `root_value` and `root_hash`.
4. Saves a snapshot to `mrp_snapshot.json` (JSON) and `mrp_snapshot.pkl` (Pickle) in the proving results folder.

**Side effects:** Sets `self.root`, `self.root_value`, `self.root_hash`, `self.tree_only_hashes`.

---

## Membership testing

### `test_inclusion(transformed_hash)`

Queries the SMT for `transformed_hash` and prints membership status and path information.

| Parameter | Type | Description |
|-----------|------|-------------|
| `transformed_hash` | `str` | Hex hash of the transformed leaf value `SLT_i`. |

Prints whether the leaf was found (inclusion) or maps to a default position (exclusion).

---

## Proof generation

### `_generate_proof(data_path, settings_path, compiled_model_path, witness_path, proof_path, pk_path, generate_witness=True)`

Generates a single EZKL proof:

1. Optionally runs witness generation.
2. Runs `ezkl.mock` to validate the circuit.
3. Runs `ezkl.prove` to produce a `.pf` proof file.

| Parameter | Type | Description |
|-----------|------|-------------|
| `data_path` | `str` | Input JSON path. |
| `settings_path` | `str` | `settings.json` path. |
| `compiled_model_path` | `str` | Compiled circuit path. |
| `witness_path` | `str` | Witness JSON path. |
| `proof_path` | `str` | Output `.pf` proof file path. |
| `pk_path` | `str` | Proving key path. |
| `generate_witness` | `bool` | If `False`, skips witness generation (uses existing file). Default `True`. |

**Returns** EZKL proof result dict.

---

### `_prove_ltr(raw_value_hash, raw_value, transform_salt)`

Generates or loads a cached LTR (leaf transform) proof for a single user record.

- If a `.pf` file already exists for this hash, reads hashes from the cached witness file.
- Otherwise, serialises inputs, generates the witness, and calls `_generate_proof`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `raw_value_hash` | `str` | Hex hash of the raw value (used to name files). |
| `raw_value` | `torch.Tensor` | The raw salted value `SD_i`. |
| `transform_salt` | `torch.Tensor` | The transform salt `TS_i`. |

**Returns** `tuple[str, torch.Tensor, str, str]` — `(transformed_value_hash, transformed_value, ltr_proof_path, raw_value_hash_short)`.

---

### `_prove_mrp(index, left_val, right_val, sel, nonce, proof_tag="")`

Generates or loads a cached MRP (Merkle root path) proof for one aggregation step.

- If a `.pf` file already exists for this `proof_tag`, reads hashes from the cached witness.
- Otherwise serialises inputs, generates the witness, and calls `_generate_proof`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `index` | `str` | Step identifier, typically `"<left_hash>-<right_hash>"`. |
| `left_val` | `torch.Tensor` | Left sibling value. |
| `right_val` | `torch.Tensor` | Right sibling value. |
| `sel` | `torch.Tensor` | Selector bit. |
| `nonce` | `torch.Tensor` | Nonce vector. |
| `proof_tag` | `str` | Optional tag appended to the proof filename to prevent collisions across users. |

**Returns** `tuple[str, str, str, str, torch.Tensor]` — `(parent_hash, mrp_proof_path, sibling_hash, sel_comp_hash, parent_value)`.

---

### `path_walk(data_record=None, raw_value_hash=None, nonce=None, use_zkp=True, gen_full_proof=False)`

The main proof generation entry point. Walks the Merkle path from a leaf to the root, generating LTR and MRP proofs at each step.

| Parameter | Type | Description |
|-----------|------|-------------|
| `data_record` | `dict \| None` | Full record dict `{"value": Tensor, "transform_salt": Tensor}`. Used for exclusion tests where the hash is unknown. |
| `raw_value_hash` | `str \| None` | Pre-computed raw hash. Used for inclusion tests where the record is already in the map. |
| `nonce` | `torch.Tensor` | Random nonce for the MRP proofs. |
| `use_zkp` | `bool` | If `True`, generates actual EZKL proofs. If `False`, computes values directly. |
| `gen_full_proof` | `bool` | If `True`, generates a proof at every SMT level. If `False`, skips levels where both the current node and its sibling are at the same default hash (optimisation). |

!!! note
    At least one of `data_record` or `raw_value_hash` must be non-`None`.

!!! note
    Proofs are named using `<raw_value_hash>_<nonce_hash>_<level_index>` to avoid collision between runs for the same user record with different nonces.

---

## Snapshot methods

### `_build_paths_index(as_tensors=False)`

Builds a dictionary of all Merkle paths for every non-default leaf in the tree.

| Parameter | Type | Description |
|-----------|------|-------------|
| `as_tensors` | `bool` | If `True`, keeps `torch.Tensor` objects (suitable for Pickle). If `False`, converts to Python lists (suitable for JSON). |

**Returns** `dict` mapping `leaf_hash → {"siblings_hash", "siblings_value", "selectors", "leaf_value"}`.

---

### `to_snapshot(tensors=False)`

Materialises the full prover state as a Python dict.

| Parameter | Type | Description |
|-----------|------|-------------|
| `tensors` | `bool` | If `True`, values remain as `torch.Tensor`. If `False`, converted to lists. |

**Returns** `dict` with keys: `version`, `prover_id`, `tree`, `shapes`, `config`, `maps`.

---

### `save_snapshot(path, tensors_for_pickle=True)`

Saves the prover snapshot to disk.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | `str` | Output file path. `.pkl`/`.pickle` → Pickle format; anything else → JSON. |
| `tensors_for_pickle` | `bool` | Whether to keep tensors in Pickle output. |

---

### `prove_membership_from_snapshot(snapshot_path, raw_value_tensor, transform_salt_tensor, nonce_tensor, use_zkp=True)`

Proves membership for a single user purely from a pre-saved snapshot, without requiring access to the full dataset.

| Parameter | Type | Description |
|-----------|------|-------------|
| `snapshot_path` | `str` | Path to a `mrp_snapshot.json` file. |
| `raw_value_tensor` | `torch.Tensor` | The user's raw value, shape `(1, total_shape)`. |
| `transform_salt_tensor` | `torch.Tensor` | The user's transform salt, shape `(1, transform_salt_shape)`. |
| `nonce_tensor` | `torch.Tensor` | Nonce for MRP proofs. |
| `use_zkp` | `bool` | Whether to generate actual EZKL proofs. Default `True`. |

**Returns** `dict`:

| Key | Type | Description |
|-----|------|-------------|
| `ltr_proof` | `str` | Path to the LTR `.pf` file. |
| `mrp_proofs` | `list[str]` | Paths to MRP `.pf` files, one per tree level. |
| `leaf_hash` | `str` | Hex hash of the transformed leaf. |
| `root_hash` | `str` | Root hash from the snapshot. |

!!! warning
    Raises `ValueError` if the transformed hash of the provided record is not found in the snapshot. This means the record was not part of the original tree.
