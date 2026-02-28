# `SparseMerkleTree` — `merkletree/SparseMerkleTree.py`

Implements a Sparse Merkle Tree where leaves are indexed by the integer representation of the Poseidon hash of the leaf value. Only occupied positions are stored in memory; all others are assumed to hold a precomputed default value.

## Constructor

```python
SparseMerkleTree(
    tree_height=256,
    aggregator_numeric_check=None,
    transformer_numeric_check=None,
    default_value=None,
    length_transform_salt=10,
    zkp_scale=8,
    ZERO_SEL=None,
    rf=1000
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tree_height` | `int` | `256` | Number of levels (determines the hash length used: `2 * tree_height / 8` hex characters). |
| `aggregator_numeric_check` | `nn.Module` | `None` | Aggregator instance (`Adder`). Stored as `self.aggregator`. |
| `transformer_numeric_check` | `nn.Module` | `None` | Transformer instance. Stored as `self.transformer`. |
| `default_value` | `torch.Tensor` | `None` | Raw default value (all zeros). Transformed during `__init__` to produce the default leaf value. |
| `length_transform_salt` | `int` | `10` | Dimensionality of the transform salt `TS_i`. |
| `zkp_scale` | `int` | `8` | Fixed-point scale used in the legacy `poseidon_hash_old`. |
| `ZERO_SEL` | `torch.Tensor` | `None` | Selector tensor `tensor([0.0])` injected by `MerkleProver`. |
| `rf` | `int` | `1000` | Rounding factor (legacy, unused in current hashing). |

**Key computed attributes set during `__init__`:**

| Attribute | Description |
|-----------|-------------|
| `default_value` | Transformed default leaf value: `transformer.forward_dry(raw_default, zero_salt)`. |
| `default_string` | Poseidon hash of `default_value`. Used as the sentinel for empty leaves. |
| `default_nonce_value` | Zero tensor the same shape as `default_value`. |
| `level_defaults` | List of `{"hash", "value"}` dicts, one per tree level, precomputed by `default_hashes()`. |
| `tree` | `dict` mapping `(level, pos) → {"hash", "value"}`. Only populated entries (non-default). |
| `tree_only_hashes` | `dict` mapping `(level, pos) → {"hash"}`. Lighter-weight view of the tree. |

---

## Utility methods

### `hex_to_binary_str(hex_str)`

Converts a hex string to a binary string (zero-padded to full bit width).

| Parameter | Type | Description |
|-----------|------|-------------|
| `hex_str` | `str` | Hexadecimal hash string. |

**Returns** `str` — binary string.

---

### `hex_to_binary_list(hex_str)`

Converts a hex string to a list of integer bits `[0, 1, ...]`.

**Returns** `list[int]`.

---

### `binary_list_to_hex(bit_list)`

Converts a list of bits back to a zero-padded hex string.

**Returns** `str`.

---

### `bit_list_to_uint(bit_list)`

Converts a list of bits to an unsigned integer.

**Returns** `int`.

---

### `reverse_binary_list(binary_list)`

Reverses a list of bits (used to convert between little-endian and big-endian selector representations).

**Returns** `list[int]`.

---

### `obtain_leaf_index(leaf)`

Converts a leaf hash string to its integer position in the ordered leaf set.

| Parameter | Type | Description |
|-----------|------|-------------|
| `leaf` | `str` | Hex hash string of a leaf value. |

**Returns** `int` — the integer position (which also encodes the binary path from root to leaf).

---

## Hashing methods

### `poseidon_hash(x_tensor, print_log=False)`

The primary hash function. Scales the tensor values by 1024, converts to integer field elements, and calls EZKL's Poseidon hash.

| Parameter | Type | Description |
|-----------|------|-------------|
| `x_tensor` | `torch.Tensor` | Input tensor. |
| `print_log` | `bool` | If `True`, prints intermediate values. Default `False`. |

**Returns** `str` — truncated hex Poseidon digest of length `2 * tree_height / 8`.

!!! note
    The truncation length is determined by `tree_height`. For `tree_height=8`, hashes are 2 hex characters; for `tree_height=256`, they are 64 hex characters.

---

### `sha256(x)` / `sha8(x)`

Legacy SHA-256-based hash functions. Not used in the current pipeline but retained for reference.

| Parameter | Type | Description |
|-----------|------|-------------|
| `x` | `bytes` | Raw bytes to hash. |

---

## Tree construction methods

### `default_hashes()`

Precomputes the default hash and value at every tree level bottom-up. Each level's default is the parent of two children that are both the level below's default. Populates `self.level_defaults`.

Called automatically in `__init__`.

---

### `hash_node(left_value, right_value, left_hash="ff", right_hash="ff", sel=None, nonce=None)`

Computes the aggregated parent value and its hash for a pair of sibling nodes.

| Parameter | Type | Description |
|-----------|------|-------------|
| `left_value` | `torch.Tensor` | Left child value. |
| `right_value` | `torch.Tensor` | Right child value. |
| `left_hash` | `str` | Pre-computed hash of left child. `"ff"` triggers recomputation. |
| `right_hash` | `str` | Pre-computed hash of right child. `"ff"` triggers recomputation. |
| `sel` | `torch.Tensor` | Selector bit. Defaults to `self.ZERO_SEL`. |
| `nonce` | `torch.Tensor` | Nonce vector. Defaults to `self.default_nonce_value`. |

**Returns** `tuple[str, torch.Tensor]` — `(parent_hash, parent_value)`.

---

### `build_tree(leaves)`

Inserts all non-default leaves into `self.tree` and recomputes all affected parent nodes up to the root.

| Parameter | Type | Description |
|-----------|------|-------------|
| `leaves` | `list[dict]` | List of `{"hash": str, "value": torch.Tensor}` dicts, one per user record. |

**Side effects:** Populates `self.tree` and `self.tree_only_hashes`.

---

## Proof methods

### `get_inclusion_proof(leaf)`

Retrieves the Merkle path (sibling hashes, sibling values, and selector bits) for a given leaf hash.

| Parameter | Type | Description |
|-----------|------|-------------|
| `leaf` | `str` | Hex hash of the transformed leaf value `SLT_i`. |

**Returns** `tuple[list, dict, dict]`:

- `hash_path`: list of sibling hashes and the root hash (bottom to top).
- `full_proof_values`: dict containing `leaf_value`, `siblings_value`, `root_value`, `selectors`, `path_tensor`.
- `full_proof_hashes`: dict containing `leaf_hash`, `siblings_hash`, `root_hash`, `selectors`.

!!! note
    If the leaf is not present in `self.tree` (i.e., it is a non-member), the path still exists — it leads to the default leaf at that position. This is the mechanism used for exclusion proofs.

---

### `verify_proof(leaf_value, siblings_values, selectors, root_value)`

Reconstructs the Merkle root from a proof path and checks it against the stored root.

| Parameter | Type | Description |
|-----------|------|-------------|
| `leaf_value` | `torch.Tensor` | The leaf value being proved. |
| `siblings_values` | `list[torch.Tensor]` | List of sibling values, bottom to top. |
| `selectors` | `list[int]` | Selector bits: `1` means the current node is the right child. |
| `root_value` | `torch.Tensor` | The expected root value. |

**Returns** `tuple[bool, bool, list]` — `(proof_valid, key_present, hash_path)`.

- `proof_valid`: `True` if the reconstructed root hash matches.
- `key_present`: `True` if the leaf is not the default string (i.e., the record was included).

---

### `test_inclusion(key)`

Convenience method: retrieves the inclusion proof for `key` and immediately verifies it.

| Parameter | Type | Description |
|-----------|------|-------------|
| `key` | `str` | Hex hash of the leaf being queried. |

**Returns** `tuple[bool, bool, list, list, list]` — `(proof_valid, key_present, hash_path, full_proof_hashes, selectors)`.
