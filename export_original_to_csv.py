#!/usr/bin/env python3
"""
Export the three datasets to CSV exactly as stored in the .pkl files.
NO changes: no rounding, no row limits, no transformations.
Original column names and values only.
"""
import pickle
import os
import csv

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "csv_original")
os.makedirs(OUT_DIR, exist_ok=True)


def write_matrix_csv(path, headers, X, y=None):
    """Write a 2D array to CSV with headers. If y is given, append as last column."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        if y is not None:
            w.writerow(list(headers) + ["outcome"])
            for i in range(len(X)):
                row = [X[i, j] for j in range(X.shape[1])] + [int(y[i])]
                w.writerow(row)
        else:
            w.writerow(headers)
            for i in range(len(X)):
                w.writerow([X[i, j] for j in range(X.shape[1])])
    print(f"  {path} ({len(X)} rows)")


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base, "data")

    # ---------- 1. data_for_logreg_small.pkl (full, unchanged) ----------
    path1 = os.path.join(data_dir, "data_for_logreg_small.pkl")
    with open(path1, "rb") as f:
        data = pickle.load(f)

    X_train = data["X_train"]
    y_train = data["y_train"]
    X_test = data["X_test"]
    y_test = data["y_test"]
    feature_names = list(data["feature_names"])

    write_matrix_csv(
        os.path.join(OUT_DIR, "data_for_logreg_small_X_train.csv"),
        feature_names, X_train, y_train,
    )
    write_matrix_csv(
        os.path.join(OUT_DIR, "data_for_logreg_small_X_test.csv"),
        feature_names, X_test, y_test,
    )

    # ---------- 2. logreg_glm_fits.pkl (full, unchanged) ----------
    path2 = os.path.join(data_dir, "logreg_glm_fits.pkl")
    with open(path2, "rb") as f:
        coefs = pickle.load(f)

    with open(os.path.join(OUT_DIR, "logreg_glm_fits_beta_full.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "coefficient"])
        for i, b in enumerate(coefs["beta_full"]):
            w.writerow([i, b])
    print(f"  {OUT_DIR}/logreg_glm_fits_beta_full.csv ({len(coefs['beta_full'])} rows)")

    with open(os.path.join(OUT_DIR, "logreg_glm_fits_beta_reduced.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "coefficient"])
        for i, b in enumerate(coefs["beta_reduced"]):
            w.writerow([i, b])
    print(f"  {OUT_DIR}/logreg_glm_fits_beta_reduced.csv ({len(coefs['beta_reduced'])} rows)")

    # ---------- 3. data_for_ks_test.pkl (full, unchanged) ----------
    path3 = os.path.join(data_dir, "data_for_ks_test.pkl")
    with open(path3, "rb") as f:
        ks = pickle.load(f)

    healthy = ks["healthy"]
    hd = ks["HD"]
    with open(os.path.join(OUT_DIR, "data_for_ks_test_healthy_and_HD.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["person_index", "healthy", "HD"])
        for i in range(len(healthy)):
            w.writerow([i, healthy[i], hd[i]])
    print(f"  {OUT_DIR}/data_for_ks_test_healthy_and_HD.csv ({len(healthy)} rows)")

    print("\nDone. All files in data/csv_original/ — original data, no changes.")


if __name__ == "__main__":
    main()
