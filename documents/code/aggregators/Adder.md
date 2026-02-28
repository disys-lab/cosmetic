# `Adder` — `aggregators/Adder.py`

Global aggregation function (`G`) that combines two sibling node values at each level of the Sparse Merkle Tree. `Adder` is a `torch.nn.Module` subclass so it can be compiled into an EZKL zk-SNARK circuit.

The only built-in aggregator. Computes **element-wise addition** of two sibling values, with an optional nonce term controlled by a selector bit.

```
parent = a + b + (sel * flipper_mask) * nonce
```

In practice, `flipper_mask` is always `0.0`, making the nonce term inactive. The selector bit `sel` and nonce are retained in the circuit interface to enable future zero-knowledge proofs of the path walk (the selector bit encodes the left/right relationship between a leaf and its sibling at each tree level).

!!! note
    Addition is commutative and associative, which is required for the recursive Merkle aggregation strategy used by `SparseMerkleTree.build_tree`. Any future aggregator must satisfy the same property.

## Constructor

```python
Adder(size=0, length_with_nonce=1)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `size` | `int` | `0` | Expected output shape. Set by `MerkleProver` after the default leaf value is computed. |
| `length_with_nonce` | `int` | `1` | Dimensionality of the nonce vector. Updated by `SparseMerkleTree` to match the leaf value width. |

**Internal attributes:**

| Attribute | Value | Description |
|-----------|-------|-------------|
| `flipper_mask` | `tensor([0.0])` | Multiplier for the nonce term — currently always zero, making `nonce` inactive. |
| `mrp_path` | `None` (set externally) | Directory for storing per-step witness/input files. |
| `mrp_settings_path` | `None` (set externally) | Path to `settings.json`. |
| `mrp_compiled_model_path` | `None` (set externally) | Path to the compiled circuit. |

---

## Methods

### `_convert_float_array_to_tensor(h_array)`

Converts a flat list of floats (from an EZKL witness JSON) to a `torch.Tensor` of shape `self.size`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `h_array` | `list[float]` | Flat list of rescaled outputs from EZKL. |

**Returns** `torch.Tensor`.

---

### `_convert_tensor_to_float_array(h_tensor)`

Flattens tensor(s) into a Python list for JSON serialisation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `h_tensor` | `torch.Tensor` or `list[torch.Tensor]` | Input tensor(s). |

**Returns** `list[float]`.

---

### `setup_proof(model, default_value, model_path, settings_path, compiled_model_path, vk_path, pk_path, py_run_args)`

One-time EZKL circuit setup for the aggregator:

1. Exports to ONNX using dummy zero tensors for `(current_value, sibling_value, sel, nonce)`.
2. Generates settings, compiles circuit, generates proving/verification keys.

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `Adder` | The aggregator instance. |
| `default_value` | `torch.Tensor` | Used to infer tensor shapes for ONNX export. |
| `model_path` | `str` | Destination for the `.onnx` file. |
| `settings_path` | `str` | Destination for `settings.json`. |
| `compiled_model_path` | `str` | Destination for the `.compiled` circuit. |
| `vk_path` | `str` | Destination for the verification key. |
| `pk_path` | `str` | Destination for the proving key. |
| `py_run_args` | `ezkl.PyRunArgs` | EZKL circuit configuration. |

---

### `dump_data_for_proof_gen(left_val, right_val, sel, nonce, data_path)`

Serialises the inputs for one aggregation step to a JSON file.

| Parameter | Type | Description |
|-----------|------|-------------|
| `left_val` | `torch.Tensor` | Left child value. |
| `right_val` | `torch.Tensor` | Right child value (sibling). |
| `sel` | `torch.Tensor` | Selector bit: `0.0` if the current node is the left child, `1.0` if it is the right child. |
| `nonce` | `torch.Tensor` | Random nonce vector (currently has no effect due to `flipper_mask=0`). |
| `data_path` | `str` | Output path for the `input_<index>.json` file. |

---

### `_generate_witness(settings_path, data_path, compiled_model_path, witness_path)`

Runs EZKL witness generation for one aggregation step.

| Parameter | Type | Description |
|-----------|------|-------------|
| `settings_path` | `str` | Path to `settings.json`. |
| `data_path` | `str` | Path to the input JSON. |
| `compiled_model_path` | `str` | Path to the compiled circuit. |
| `witness_path` | `str` | Output path for the witness JSON. |

**Returns** `torch.Tensor` — the parent node value extracted from the witness.

---

### `extract_raw_value(witness_path)`

Reads a completed witness file and extracts the rescaled parent node value.

| Parameter | Type | Description |
|-----------|------|-------------|
| `witness_path` | `str` | Path to a witness JSON (not a proof file — reads from `pretty_elements`). |

**Returns** `tuple` — `(1, 0, 0, parent_value_tensor)`.

!!! note
    Unlike the transformer's `extract_raw_value` which reads from a `.pf` proof file, the aggregator reads from a witness file. This is because the aggregator witness is generated during the path walk and the value is needed immediately.

---

### `forward_dry(a, b, sel, nonce, index="ff-ff")`

Computes one aggregation step without generating a full zk-SNARK proof. Serialises inputs, runs `_generate_witness`, and returns the parent node value.

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Left child value. |
| `b` | `torch.Tensor` | Right child value (sibling). |
| `sel` | `torch.Tensor` | Selector bit. |
| `nonce` | `torch.Tensor` | Nonce vector. |
| `index` | `str` | Unique label for this step, typically `"<left_hash>-<right_hash>"`. Used to name the witness/input files. Default `"ff-ff"`. |

**Returns** `torch.Tensor` — the computed parent node value.

---

### `forward(a, b, sel, nonce)`

Pure PyTorch forward pass for the aggregation function.

```
nonce_multiplier = sel * flipper_mask   # always 0
parent = a + b + nonce_multiplier * nonce
```

Because `flipper_mask = tensor([0.0])`, this always reduces to `a + b`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Left child value. |
| `b` | `torch.Tensor` | Right child value. |
| `sel` | `torch.Tensor` | Selector bit (retained for circuit interface). |
| `nonce` | `torch.Tensor` | Nonce vector (currently inactive). |

**Returns** `torch.Tensor` — element-wise sum `a + b`.
