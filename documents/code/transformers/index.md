# transformers/

Leaf-level transformation functions (`F`) applied to each salted user record before it enters the Sparse Merkle Tree. Every transformer is a `torch.nn.Module` subclass so it can be exported to ONNX and compiled into an EZKL zk-SNARK circuit.

## Classes

| File | Class | Description |
|------|-------|-------------|
| [FlowThrough.md](FlowThrough.md) | `FlowThrough` | Identity transformer — passes input through unchanged. |
| [Affine.md](Affine.md) | `Affine` | Matrix-vector multiplication followed by bias addition. |
| [Exponent.md](Exponent.md) | `Exponent` | Element-wise integer exponentiation (powers 0–4). |
| [Length.md](Length.md) | `Length` | Non-zero indicator — outputs 1 if any element is non-zero. |
| [BinCount.md](BinCount.md) | `BinCount` | Histogram bin-count (one-hot bin assignment). Used for KS test. |
| [LogisticFunction.md](LogisticFunction.md) | `LogisticRegression` | Per-record logistic accuracy contribution. |
| [LogisticLogLikelihood.md](LogisticLogLikelihood.md) | `LogLogLikelihood` | Per-record logistic log-likelihood contribution. Used for LRT. |

---

## Common interface

All transformers share the following constructor attributes and methods. Individual classes extend this with their own parameters.

### Shared constructor attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `length_transform_salt` | `int` | Number of dimensions in the transform salt vector `TS_i`. |
| `size` | `int` or `tuple` | Shape of the output tensor. Set by `MerkleProver` after the default value is computed. |
| `hash_func` | `callable` | Poseidon hash function injected by `SparseMerkleTree`. |
| `default_value` | `torch.Tensor` | Default leaf value (all zeros). |
| `ltr_path` | `str` | Directory for storing per-record witness/input JSON files. |
| `ltr_settings_path` | `str` | Path to the compiled EZKL `settings.json`. |
| `ltr_compiled_model_path` | `str` | Path to the compiled EZKL circuit (`.compiled`). |
| `_async_srs` | `coroutine` | Async function to fetch/verify the SRS; injected by `MerkleProver`. |
| `_async_compile` | `coroutine` | Async function to generate an EZKL witness; injected by `MerkleProver`. |

### Shared methods

#### `_convert_float_array_to_tensor(h_array)`

Converts a flat list of floats back to a `torch.Tensor` of the expected shape.

| Parameter | Type | Description |
|-----------|------|-------------|
| `h_array` | `list[float]` | Flat list read from an EZKL witness JSON. |

**Returns** `torch.Tensor` reshaped to `self.size`.

---

#### `_convert_tensor_to_float_array(h_tensor)`

Flattens one or more tensors into a plain Python list of floats for JSON serialisation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `h_tensor` | `torch.Tensor` or `list[torch.Tensor]` | Input tensor(s). |

**Returns** `list[float]`.

---

#### `setup_proof(model, default_value, model_path, settings_path, compiled_model_path, vk_path, pk_path, py_run_args)`

Runs the full one-time EZKL circuit setup for this transformer:

1. Exports the PyTorch model to ONNX.
2. Calls `ezkl.gen_settings` to produce `settings.json`.
3. Calls `ezkl.compile_circuit` to produce the compiled circuit.
4. Calls `ezkl.setup` to generate the proving key (`pk`) and verification key (`vk`).

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `nn.Module` | The transformer instance itself. |
| `default_value` | `torch.Tensor` | Used to determine input shapes for ONNX export. |
| `model_path` | `str` | Destination path for the `.onnx` file. |
| `settings_path` | `str` | Destination path for `settings.json`. |
| `compiled_model_path` | `str` | Destination path for the `.compiled` circuit. |
| `vk_path` | `str` | Destination path for the verification key. |
| `pk_path` | `str` | Destination path for the proving key. |
| `py_run_args` | `ezkl.PyRunArgs` | EZKL run configuration (visibility, scale, logrows, etc.). |

!!! note
    Transformer-specific extra inputs (e.g. `slope`, `intercept`, `exponent`, `edges`, `beta`) are included in the ONNX export tuple automatically by each subclass.

---

#### `dump_data_for_proof_gen(raw_value, salt, data_path)`

Serialises the inputs required for EZKL witness generation to a JSON file at `data_path`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `raw_value` | `torch.Tensor` | Salted raw value `SD_i`. |
| `salt` | `torch.Tensor` | Transform salt `TS_i`. |
| `data_path` | `str` | Output path for the `input_<hash>.json` file. |

---

#### `_generate_witness(settings_path, data_path, compiled_model_path, witness_path)`

Runs EZKL witness generation asynchronously using the pre-compiled circuit.

| Parameter | Type | Description |
|-----------|------|-------------|
| `settings_path` | `str` | Path to `settings.json`. |
| `data_path` | `str` | Path to the input JSON produced by `dump_data_for_proof_gen`. |
| `compiled_model_path` | `str` | Path to the compiled circuit. |
| `witness_path` | `str` | Output path for the generated witness JSON. |

**Returns** `torch.Tensor` — the rescaled forward-pass output extracted from the witness file.

---

#### `extract_raw_value(proof_path)`

Reads a completed `.pf` proof file and extracts the public output hash.

| Parameter | Type | Description |
|-----------|------|-------------|
| `proof_path` | `str` | Path to a `.pf` proof file. |

**Returns** `tuple` — `(1, 0, 0, zk_output)` where `zk_output` is the rescaled output list from `pretty_public_inputs`.

---

#### `forward_dry(a, salt, use_witness_file=True)`

Computes the leaf transform without generating a full zk-SNARK proof.

- If `use_witness_file=True`: serialises inputs, runs `_generate_witness`, and reads the result back from the witness file (uses the compiled circuit but does not prove).
- If `use_witness_file=False`: calls `forward()` directly in Python.

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Salted raw value `SD_i`. |
| `salt` | `torch.Tensor` | Transform salt `TS_i`. |
| `use_witness_file` | `bool` | Whether to run through the EZKL witness pipeline. Default `True`. |

**Returns** `torch.Tensor` — the transformed salted leaf value `SLT_i`.
