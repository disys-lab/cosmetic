#!/usr/bin/env python3
"""
Show how the three datasets REALLY look: tables with column names, rows = people.
Explains what a "key" is and writes easy-to-read views to data/views/.
"""
import pickle
import os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "views")
os.makedirs(OUT_DIR, exist_ok=True)

def main():
    base = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base, "data")

    # -------------------------------------------------------------------------
    # WHAT IS A "KEY"?
    # -------------------------------------------------------------------------
    # The .pkl file is like a BOX that contains several DRAWERS.
    # Each drawer has a LABEL (that's the "key") and inside the drawer is the data.
    # So: key = the name/label of one piece of data inside the file.
    # Example: key "X_train" means "the drawer labeled X_train" → inside is the training table.
    # -------------------------------------------------------------------------

    # ========== 1. LOGISTIC REGRESSION DATA ==========
    path = os.path.join(data_dir, "data_for_logreg_small.pkl")
    with open(path, "rb") as f:
        data = pickle.load(f)

    X_train = data["X_train"]
    y_train = data["y_train"]
    X_test = data["X_test"]
    y_test = data["y_test"]
    feature_names = list(data["feature_names"])

    # How many people (rows), how many features (columns)
    n_train, n_feat = X_train.shape
    n_test = X_test.shape[0]

    lines = []
    lines.append("# Dataset 1: data_for_logreg_small.pkl")
    lines.append("")
    lines.append("## What's inside the file (the 'keys' are just labels)")
    lines.append("")
    lines.append("Think of the file as a box with 5 labeled drawers:")
    lines.append("  - X_train   = table of training people (rows) × features (columns)")
    lines.append("  - y_train   = one outcome (0 or 1) per training person")
    lines.append("  - X_test    = table of test people × same features")
    lines.append("  - y_test    = one outcome per test person")
    lines.append("  - feature_names = the COLUMN NAMES for the tables")
    lines.append("")
    lines.append("## Yes: each ROW = one person (one individual in the study)")
    lines.append("## Yes: COLUMN NAMES exist — they are in 'feature_names'")
    lines.append("")
    lines.append(f"Training set: {n_train} people (rows), {n_feat} features (columns).")
    lines.append(f"Test set:     {n_test} people (rows), same {n_feat} features.")
    lines.append("")
    lines.append("## Column names (feature_names):")
    lines.append(", ".join(feature_names))
    lines.append("")
    lines.append("## What the TRAINING data looks like (first 10 people)")
    lines.append("(Row = one person. Columns = the features. Last column = outcome 0 or 1.)")
    lines.append("")

    # Header row: feature names + "outcome"
    header = feature_names + ["outcome"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + " --- |" * len(header))

    for i in range(min(10, n_train)):
        row_vals = [str(round(float(x), 2)) for x in X_train[i]]
        row_vals.append(str(int(y_train[i])))
        lines.append("| " + " | ".join(row_vals) + " |")

    lines.append("")
    lines.append("## What the TEST data looks like (first 10 people)")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + " --- |" * len(header))
    for i in range(min(10, n_test)):
        row_vals = [str(round(float(x), 2)) for x in X_test[i]]
        row_vals.append(str(int(y_test[i])))
        lines.append("| " + " | ".join(row_vals) + " |")

    with open(os.path.join(OUT_DIR, "1_logreg_data_how_it_looks.md"), "w") as f:
        f.write("\n".join(lines))

    # Also write a tiny CSV so they can open in Excel/Sheets
    with open(os.path.join(OUT_DIR, "1a_X_train_first10.csv"), "w") as f:
        f.write(",".join(feature_names) + ",outcome\n")
        for i in range(min(10, n_train)):
            row = [str(round(float(x), 4)) for x in X_train[i]] + [str(int(y_train[i]))]
            f.write(",".join(row) + "\n")

    # ========== 2. COEFFICIENTS (logreg_glm_fits) ==========
    path2 = os.path.join(data_dir, "logreg_glm_fits.pkl")
    with open(path2, "rb") as f:
        coefs = pickle.load(f)

    beta_full = coefs["beta_full"]
    beta_reduced = coefs["beta_reduced"]

    lines2 = []
    lines2.append("# Dataset 2: logreg_glm_fits.pkl")
    lines2.append("")
    lines2.append("## What's inside (again, 'keys' = labels for each part)")
    lines2.append("  - beta_full    = one number per feature (the full model's coefficients)")
    lines2.append("  - beta_reduced = one number per feature (the reduced model's coefficients)")
    lines2.append("")
    lines2.append("There are NO rows of people here — only two lists of numbers (one per model).")
    lines2.append("")
    lines2.append("## Full model coefficients (beta_full)")
    lines2.append("Position 0 is usually the intercept; then one number per feature.")
    lines2.append("")
    lines2.append("| index | coefficient |")
    lines2.append("| --- | --- |")
    for i, b in enumerate(beta_full):
        lines2.append(f"| {i} | {round(float(b), 4)} |")
    lines2.append("")
    lines2.append("## Reduced model coefficients (beta_reduced)")
    lines2.append("| index | coefficient |")
    lines2.append("| --- | --- |")
    for i, b in enumerate(beta_reduced):
        lines2.append(f"| {i} | {round(float(b), 4)} |")

    with open(os.path.join(OUT_DIR, "2_logreg_coefficients_how_it_looks.md"), "w") as f:
        f.write("\n".join(lines2))

    # ========== 3. KS DATA ==========
    path3 = os.path.join(data_dir, "data_for_ks_test.pkl")
    with open(path3, "rb") as f:
        ks = pickle.load(f)

    healthy = ks["healthy"]
    hd = ks["HD"]
    n = len(healthy)

    lines3 = []
    lines3.append("# Dataset 3: data_for_ks_test.pkl")
    lines3.append("")
    lines3.append("## What's inside (keys = labels)")
    lines3.append("  - healthy = one number per person in the 'healthy' group (200 people)")
    lines3.append("  - HD      = one number per person in the 'HD' group (200 people)")
    lines3.append("")
    lines3.append("No column names for the numbers — just one measurement per person.")
    lines3.append("Each ROW below = one person. Two columns = the two groups.")
    lines3.append("")
    lines3.append("## First 15 people in each group (side by side)")
    lines3.append("")
    lines3.append("| person_index | healthy | HD |")
    lines3.append("| --- | --- | --- |")
    for i in range(min(15, n)):
        lines3.append(f"| {i} | {round(float(healthy[i]), 4)} | {round(float(hd[i]), 4)} |")
    lines3.append("")
    lines3.append("So: each row is one person in the healthy group and one in the HD group (same row index = different people in each group).")

    with open(os.path.join(OUT_DIR, "3_ks_data_how_it_looks.md"), "w") as f:
        f.write("\n".join(lines3))

    # CSV for KS: two columns, 200 rows each
    with open(os.path.join(OUT_DIR, "3a_ks_healthy_and_HD_first20.csv"), "w") as f:
        f.write("person_index,healthy,HD\n")
        for i in range(min(20, n)):
            f.write(f"{i},{healthy[i]},{hd[i]}\n")

    print("Done. Views written to data/views/")
    print("  - 1_logreg_data_how_it_looks.md   (tables with column names, rows = people)")
    print("  - 1a_X_train_first10.csv          (open in Excel/Sheets)")
    print("  - 2_logreg_coefficients_how_it_looks.md")
    print("  - 3_ks_data_how_it_looks.md")
    print("  - 3a_ks_healthy_and_HD_first20.csv")

if __name__ == "__main__":
    main()
