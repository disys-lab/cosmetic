# `Length` — `transformers/Length.py`

**Non-zero indicator transformer.** Converts each element to a binary indicator (1 if non-zero, 0 if zero), takes the row-wise max, and appends the transform salt.

```
mask_i = (SD_i != 0) ? 1 : 0
eta = max(mask_i, dim=1)
SLT_i = Concat(eta, TS_i)
```

This effectively outputs `1.0` if **any** element of the record is non-zero and `0.0` if the record is all zeros (i.e., a default record).

## Constructor

```python
Length(size=0, length_transform_salt=0)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `size` | `int` | `0` | Expected output shape. |
| `length_transform_salt` | `int` | `0` | Dimensionality of `TS_i`. |

## `forward(a, salt)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Salted raw value `SD_i`, shape `(1, record_dim)`. |
| `salt` | `torch.Tensor` | Transform salt `TS_i`, shape `(1, salt_dim)`. |

**Returns** `torch.Tensor` of shape `(1, 1 + salt_dim)` — `Concat(eta, salt)`.

!!! note
    Used as one of the two transformers in the Logistic Accuracy module (`LogisticAccuracy`) to count the number of non-default records (i.e. the sample size `N`). The root value of the resulting SMT equals `N` in its first element.

---

See [index.md](index.md) for the shared interface inherited by all transformers.
