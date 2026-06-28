# `LogisticRegression` — `transformers/LogisticFunction.py`

**Logistic accuracy contribution transformer.** Computes the per-record accuracy contribution of a logistic classifier — i.e., whether the model's binary prediction matches the true label — normalised by the total sample size `N`.

```
eta = x @ coefs^T
pred = (eta >= 0) ? 1 : 0
result = (pred == y) ? 1/N : 0
SLT_i = Concat(result, TS_i)
```

When summed across all records (via the `Adder` aggregator), the SMT root value equals the overall classification accuracy.

## Constructor

```python
LogisticRegression(size=0, length_transform_salt=0, beta=None, sample_size=None)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `size` | `int` | `0` | Expected output shape. |
| `length_transform_salt` | `int` | `0` | Dimensionality of `TS_i`. |
| `beta` | `torch.Tensor` | `None` | Coefficient vector of the logistic model, shape `(n_coefs, 1)`. |
| `sample_size` | `torch.Tensor` | `None` | Total sample size `N`, shape `(1, 1)`. Sourced from the root value of the `Length` SMT. |

## `forward(a, salt, beta, sample_size)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Salted raw value `SD_i`. First `x_dim` columns are features `x`; column `x_dim` is label `y`. |
| `salt` | `torch.Tensor` | Transform salt `TS_i`. |
| `beta` | `torch.Tensor` | Logistic coefficient vector. |
| `sample_size` | `torch.Tensor` | `N` as a `(1, 1)` tensor. |

**Returns** `torch.Tensor` — `Concat((pred == y) / N, salt)`.

!!! note
    `beta` and `sample_size` are private circuit inputs included in the ONNX export — the prover keeps the model coefficients secret.

---

See [index.md](index.md) for the shared interface inherited by all transformers.
