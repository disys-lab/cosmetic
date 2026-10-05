# How the datasets really look (visual guide)

Generated views are in **`data/views/`**. This file explains format, keys, and rows.

---

## What is a "key"?

A **key** is just the **label** for one part of the data inside the file.

- Think of the `.pkl` file as a **box with drawers**.
- Each drawer has a **name** on it — that name is the **key**.
- Example: the key **"feature_names"** is the label for the list that holds the **column names** (375_I, 375_M, …). So **feature_names** is a key; the column names are the *content* of that key.

---

## Do the datasets have column names?

**Yes, for the logistic regression data.**

- The column names are stored under the key **feature_names**.
- They are: **375_I, 375_M, 375_N, 375_S, 375_T, 375_Y, 426_I, 426_K, 426_L, 426_M, 426_R, 426_T, 434_K, 434_M, 434_R, 434_T, 434_V, 475_M, 475_V** (19 columns).
- In the views, the first row of each table is the header: these names plus **outcome** (0 or 1).

The KS dataset has no column names — just two lists of numbers (healthy group and HD group).

---

## Are rows = different people?

**Yes.**

- **Dataset 1 (data_for_logreg_small.pkl):** Each **row** = one person. Row 1 = person 1, row 2 = person 2, etc. There are 479 training people and 85 test people. Columns are the 19 features plus outcome.
- **Dataset 3 (data_for_ks_test.pkl):** The **healthy** list has 200 numbers (200 people). The **HD** list has 200 numbers (200 different people). In the table we put them side by side; same row index = one person from healthy and one from HD (they are not the same person).

---

## Quick visual summary

### 1. data_for_logreg_small.pkl

```
Keys (drawer labels):  X_train, y_train, X_test, y_test, feature_names

X_train looks like this (first row = column names, each other row = one person):

| 375_I | 375_M | 375_N | ... | 475_V | outcome |
| ----- | ----- | ----- | --- | ----- | ------- |
| 0.0   | 0.0   | 0.0   | ... | 0.0   | 1       |   ← person 1
| 0.0   | 0.0   | 0.0   | ... | 1.0   | 1       |   ← person 2
...
```

- **479 rows** of training people, **85 rows** of test people.
- **19 feature columns** (names from feature_names) + **1 outcome column** (0 or 1).

### 2. logreg_glm_fits.pkl

```
Keys:  beta_full, beta_reduced

No rows of people — just two lists of numbers (coefficients).
beta_full has 20 numbers; beta_reduced has 8 numbers.
```

### 3. data_for_ks_test.pkl

```
Keys:  healthy, HD

healthy:  200 numbers (one per person in healthy group)
HD:      200 numbers (one per person in HD group)

| person_index | healthy  | HD      |
| ------------ | -------- | ------- |
| 0            | 16.76    | 47.64   |
| 1            | 20.82    | 42.38   |
...
```

---

## Files in data/views/

| File | What it shows |
|------|----------------|
| **1_logreg_data_how_it_looks.md** | Full tables with column names; rows = people. |
| **1a_X_train_first10.csv** | First 10 training people — open in Excel/Sheets. |
| **2_logreg_coefficients_how_it_looks.md** | Coefficient lists (no people rows). |
| **3_ks_data_how_it_looks.md** | Healthy vs HD numbers, first 15. |
| **3a_ks_healthy_and_HD_first20.csv** | Same, first 20 — open in Excel/Sheets. |

To regenerate:  
`docker run --rm -v "$(pwd):/workspace" -w /workspace anon2026dpeval/cosmeticprover:latest python3 visualize_datasets.py`
