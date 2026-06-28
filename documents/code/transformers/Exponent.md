# `Exponent` — `transformers/Exponent.py`

**Elementwise exponentiation transformer.** Raises each element of `SD_i` to a fixed integer power, then appends the transform salt.

```
TSD_i = SD_i ^ exponent   (elementwise)
SLT_i = Concat(TSD_i, TS_i)
```

Supported exponents: `0`, `1`, `2`, `3`, `4`. Any other value returns zeros (fallback branch).

## Constructor

```python
Exponent(exponent=1, size=0, length_transform_salt=0)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `exponent` | `int` | `1` | Integer power to raise each element to (0–4). |
| `size` | `int` | `0` | Expected output shape. |
| `length_transform_salt` | `int` | `0` | Dimensionality of `TS_i`. |

## `forward(a, salt, exponent)`

Uses nested `torch.where` calls to branch on the integer exponent value without Python control flow, keeping the computation graph differentiable and ONNX-exportable.

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Salted raw value `SD_i`. |
| `salt` | `torch.Tensor` | Transform salt `TS_i`. |
| `exponent` | `torch.Tensor` | Scalar integer tensor `(1,)`. |

**Returns** `torch.Tensor` — `Concat(a^exponent, salt)`.

!!! warning
    Exponents outside 0–4 silently produce a zero tensor. Validate the exponent value before circuit setup.

---

See [index.md](index.md) for the shared interface inherited by all transformers.
