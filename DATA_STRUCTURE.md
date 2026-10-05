# Dataset structure (what’s inside the three .pkl files)

This describes what we found inside the three datasets used by the ACC, LRT, and KS applications. You can re-run the inspection anytime with:

```bash
docker run --rm -v "$(pwd):/workspace" -w /workspace anon2026dpeval/cosmeticprover:latest python3 inspect_datasets.py
```

---

## 1. `data/data_for_logreg_small.pkl` (used by ACC and LRT)

**What it is:** One dictionary with 5 keys. It holds **training and test data** for a logistic regression model (features + binary outcome).

| Key             | Type    | Shape    | Meaning |
|-----------------|---------|----------|---------|
| **X_train**     | ndarray | (479, 19)| Training features: 479 people, 19 numbers each (e.g. biomarkers or 0/1 flags). |
| **y_train**     | ndarray | (479,)   | Training labels: one number per person (0 or 1). |
| **X_test**      | ndarray | (85, 19) | Test features: 85 people, same 19 features. |
| **y_test**      | ndarray | (85,)    | Test labels: one number per person (0 or 1). |
| **feature_names** | list  | 19 names | Names of the 19 columns, e.g. `'375_I'`, `'375_M'`, … `'475_M'`, `'475_V'`. |

**In plain language:**

- **X_train / X_test:** Tables of numbers (rows = people, columns = 19 features). Values in the sample are 0/1 (and possibly continuous); first few values are 0 or 1.
- **y_train / y_test:** One outcome per person (0 or 1). Example: 1, 1, 1, 0, 0 for the first five test people.
- **feature_names:** Just the list of names for the 19 columns (e.g. for interpretation or logging).

**Who uses it:**

- **ACC** uses **X_test** and **y_test** (and optionally the first 12 rows) to build the “length” and “accuracy” trees.
- **LRT** uses **X_train** and **y_train** (and optionally 12 rows and 5 features) to build the “full” and “reduced” log-likelihood trees.

So: same file, different parts (train vs test) and different number of rows/features depending on the app.

---

## 2. `data/logreg_glm_fits.pkl` (used by ACC and LRT)

**What it is:** One dictionary with 2 keys. It holds the **fitted logistic regression coefficients** (one vector per model).

| Key              | Type    | Shape  | Meaning |
|------------------|---------|--------|---------|
| **beta_full**    | ndarray | (20,)  | 20 coefficients for the “full” model (e.g. intercept + 19 features). |
| **beta_reduced** | ndarray | (8,)   | 8 coefficients for the “reduced” (simpler) model. |

**In plain language:**

- **beta_full:** One number per feature (plus intercept). The code uses these with **X** to compute predictions or log-likelihood for the full model. Example values: 4.14, -20.29, -20.13, … (mix of positive and negative).
- **beta_reduced:** Same idea for a smaller model (fewer parameters). Example: 23.57, -22.18, … (8 numbers).

**Who uses it:**

- **ACC** uses only **beta_full** with the test data to compute “accuracy” (correct vs wrong predictions).
- **LRT** uses **beta_full** and **beta_reduced** with the training data to compute two log-likelihoods and then the LRT statistic.

So: same file, ACC uses one model, LRT uses both.

---

## 3. `data/data_for_ks_test.pkl` (used by KS only)

**What it is:** One dictionary with 2 keys. It holds **two groups of one number per person** (no 0/1 labels, no feature table).

| Key        | Type    | Shape  | Meaning |
|------------|---------|--------|---------|
| **healthy** | ndarray | (200,) | 200 numbers for the “healthy” group (e.g. one measurement per person). |
| **HD**      | ndarray | (200,) | 200 numbers for the “HD” group (e.g. same type of measurement). |

**In plain language:**

- **healthy:** 200 floats. Example: 16.76, 20.82, 19.49, 18.33, … (values in a band around ~17–25 in the sample).
- **HD:** 200 floats. Example: 47.64, 42.38, 38.26, 49.64, … (values in a higher band ~38–61 in the sample).

So: two lists of numbers (one per group). The KS application bins them, builds two histograms, and compares the two distributions (e.g. “healthy” vs “HD”). No regression, no betas.

---

## Summary

| File                        | Top-level | Contents in one line |
|-----------------------------|-----------|----------------------|
| **data_for_logreg_small.pkl** | dict, 5 keys | Train/test feature matrices (X_train, X_test), labels (y_train, y_test), and feature names. |
| **logreg_glm_fits.pkl**       | dict, 2 keys | Two coefficient vectors: full model (20) and reduced model (8). |
| **data_for_ks_test.pkl**      | dict, 2 keys | Two arrays of 200 numbers each: “healthy” and “HD”. |

If you want to see the exact numbers again, run `inspect_datasets.py` as in the first line of this file.
