# `BinCount` — `transformers/BinCount.py`

**Histogram bin-count transformer.** Assigns each scalar data record to a histogram bin defined by a set of edges, producing a one-hot bin-membership vector, then appends the transform salt. Used for the KS test.

```
bin_mask = one_hot_bin_assignment(SD_i[0], edges)
SLT_i = Concat(bin_mask.flatten(), TS_i)
```

The scalar feature `a[:, 0]` is linearly rescaled from the source range `[0, 31]` to the edge range before binning.

## Constructor

```python
BinCount(size=0, length_transform_salt=0, edges=None)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `size` | `int` | `0` | Expected output shape. |
| `length_transform_salt` | `int` | `0` | Dimensionality of `TS_i`. |
| `edges` | `torch.Tensor` | `None` | 1-D tensor of bin boundary values. `n_bins = len(edges) - 1`. |

## `forward(a, salt, edges)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Salted raw value `SD_i`, shape `(1, record_dim)`. Only `a[:, 0]` is used as the scalar feature. |
| `salt` | `torch.Tensor` | Transform salt `TS_i`. |
| `edges` | `torch.Tensor` | Bin boundaries. |

**Returns** `torch.Tensor` of shape `(1, n_bins + salt_dim)`.

**Internal steps:**

1. Extract scalar feature: `x = a[:, 0]`.
2. Rescale from `[0, 31]` to `[edges[0], edges[-1]]`.
3. Compute `bin_mask`: a float indicator per bin — 1.0 if the scaled value falls in `[lower, upper)`.
4. Zero out bins for rows where the entire input is zero (default records).
5. Flatten and concatenate with salt.

!!! warning
    Only the first column of `a` is used. All other columns (user salt) are ignored by this transform.

---

See [index.md](index.md) for the shared interface inherited by all transformers.
