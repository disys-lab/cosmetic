# `FlowThrough` — `transformers/FlowThrough.py`

**Identity transformer.** Passes the salted raw value through unchanged and appends the transform salt.

```
SLT_i = Concat(SD_i, TS_i)
```

## Constructor

```python
FlowThrough(size=0, length_transform_salt=0, atol=1e-3, rtol=1e-12)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `size` | `int` | `0` | Expected output shape (set by `MerkleProver`). |
| `length_transform_salt` | `int` | `0` | Dimensionality of `TS_i`. |
| `atol` | `float` | `1e-3` | Absolute tolerance (reserved for numeric checks). |
| `rtol` | `float` | `1e-12` | Relative tolerance (reserved for numeric checks). |

## `forward(a, salt)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Salted raw value, shape `(1, record_dim)`. |
| `salt` | `torch.Tensor` | Transform salt, shape `(1, salt_dim)`. |

**Returns** `torch.Tensor` of shape `(1, record_dim + salt_dim)` — `Concat(a, salt)`.

!!! note
    This is the default transformer used in `driver.py` (`LTR_CHOICE=flow-through`). It is also the simplest transformer to debug with because the output is the direct concatenation of the inputs.

---

See [index.md](index.md) for the shared interface inherited by all transformers.
