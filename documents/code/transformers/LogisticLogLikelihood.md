# `LogLogLikelihood` — `transformers/LogisticLogLikelihood.py`

**Logistic log-likelihood transformer.** Computes the per-record log-likelihood contribution of a logistic regression model using a polynomial approximation of the softplus function, compatible with EZKL's fixed-point arithmetic.

```
eta = (mask * x) @ beta
ll_i = y * eta - softplus(eta)
SLT_i = Concat(ll_i, TS_i)
```

When summed (via `Adder`), the SMT root gives the total log-likelihood of the dataset under the model — used for both the full and reduced models in the LRT.

## Constructor

```python
LogLogLikelihood(size=0, length_transform_salt=0, beta=None, mask=None)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `size` | `int` | `0` | Expected output shape. |
| `length_transform_salt` | `int` | `0` | Dimensionality of `TS_i`. |
| `beta` | `torch.Tensor` | `None` | Coefficient vector, shape `(n_coefs, 1)`. |
| `mask` | `torch.Tensor` | `None` | Binary feature-selection mask applied to `x` before the dot product. Enables the reduced model to use a subset of features. |

## `softplus_piecewise(eta)`

A degree-6 polynomial approximation of `log(1 + exp(eta))` (softplus), valid on `[-K, K]` where `K=10`. Outside this range:

- `eta <= -K` → returns `0` (left tail).
- `eta >= K` → returns `eta` (right tail, i.e., the linear asymptote).

| Parameter | Type | Description |
|-----------|------|-------------|
| `eta` | `torch.Tensor` | Linear predictor value. |

**Returns** `torch.Tensor` — piecewise approximation of `softplus(eta)`.

!!! note
    The polynomial approximation is necessary because `torch.log` and `torch.exp` in their standard forms produce arithmetic circuits that are too large for practical EZKL proof generation. The piecewise polynomial keeps circuit size tractable.

## `logistic_ll_piecewise(eta, y)`

Computes the log-likelihood contribution for a single record.

```
ll = y * eta - softplus(eta)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `eta` | `torch.Tensor` | Linear predictor `(mask * x) @ beta`. |
| `y` | `torch.Tensor` | Binary label `{0, 1}`. |

**Returns** `torch.Tensor` — per-record log-likelihood scalar.

## `forward(a, salt, beta, mask)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `a` | `torch.Tensor` | Salted raw value. First `x_dim` columns are features; column `x_dim` is label `y`. |
| `salt` | `torch.Tensor` | Transform salt `TS_i`. |
| `beta` | `torch.Tensor` | Coefficient vector. |
| `mask` | `torch.Tensor` | Feature-selection mask. For the full model all entries are 1; for the reduced model only the intercept column is 1. |

**Returns** `torch.Tensor` — `Concat(ll_i, salt)`. Default (all-zero) records return 0 contribution.

---

See [index.md](index.md) for the shared interface inherited by all transformers.
