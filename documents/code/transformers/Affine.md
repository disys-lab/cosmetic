# `Affine` — `transformers/Affine.py`

**Affine (linear) transformer.** Applies a matrix-vector multiplication followed by a bias addition, then appends the transform salt.

```
TSD_i = slope @ SD_i + intercept
SLT_i = Concat(TSD_i, TS_i)
```

## Constructor

```python
Affine(size=0, length_transform_salt=0, slope=None, intercept=None)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `size` | `int` | `0` | Expected output shape. |
| `length_transform_salt` | `int` | `0` | Dimensionality of `TS_i`. |
| `slope` | `torch.Tensor` | `None` | Weight matrix for the linear transform. Shape must be compatible with `SD_i`. |
| `intercept` | `torch.Tensor` | `None` | Bias vector added after the matrix multiply. |

## `forward(a, salt, slope, intercept)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Salted raw value `SD_i`. |
| `salt` | `torch.Tensor` | Transform salt `TS_i`. |
| `slope` | `torch.Tensor` | Weight matrix `m`. |
| `intercept` | `torch.Tensor` | Bias vector `c`. |

**Returns** `torch.Tensor` — `Concat(slope @ a + intercept, salt)`.

!!! note
    `slope` and `intercept` are treated as private circuit inputs and included in the ONNX export. This means the prover can keep them secret while still generating a valid proof.

---

See [index.md](index.md) for the shared interface inherited by all transformers.
