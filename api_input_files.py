"""
Unified API: list and download all LTR input files (input_<hash>.json)
from ACC, LRT, and KS proof-results folders.
Run on port 5015 (same Docker setup, same proofs mount).
"""
import os
import io
import zipfile
from flask import Flask, jsonify, send_file

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROOFS_ROOT = os.path.join(BASE_DIR, "proofs")

# (app_name, branch_name, path_under_proofs)
# Each branch has 1/proof-results-*/ltr/input_*.json
INPUT_FILE_BRANCHES = [
    ("acc", "log_acc", os.path.join("logistic_accuracy", "log_acc")),
    ("acc", "log_acc_length", os.path.join("logistic_accuracy", "log_acc_length")),
    ("lrt", "ll_full", os.path.join("logistic_lrt", "ll_full")),
    ("lrt", "ll_reduced", os.path.join("logistic_lrt", "ll_reduced")),
    ("ks", "s1", os.path.join("ks", "simple_sum_bincount_s1")),
    ("ks", "s2", os.path.join("ks", "simple_sum_bincount_s2")),
]


def _collect_all_input_files():
    """Scan all branches and return list of (app, branch, proof_results_dirname, hash, full_path)."""
    out = []
    for app_name, branch_name, path_under_proofs in INPUT_FILE_BRANCHES:
        base = os.path.join(PROOFS_ROOT, path_under_proofs, "1")
        if not os.path.isdir(base):
            continue
        for item in os.listdir(base):
            proof_dir = os.path.join(base, item)
            if not os.path.isdir(proof_dir) or not item.startswith("proof-results-"):
                continue
            ltr_dir = os.path.join(proof_dir, "ltr")
            if not os.path.isdir(ltr_dir):
                continue
            for fname in os.listdir(ltr_dir):
                if fname.startswith("input_") and fname.endswith(".json"):
                    hash_part = fname[6:-5]  # strip "input_" and ".json"
                    full_path = os.path.join(ltr_dir, fname)
                    if os.path.isfile(full_path):
                        out.append((app_name, branch_name, item, hash_part, full_path))
    return out


@app.get("/input-files/")
@app.get("/input-files/list")
def list_input_files():
    """
    Return JSON list of all input files found in ACC, LRT, and KS proof-results.
    Each entry: app, branch, proof_results, hash, path (relative to proofs root).
    """
    files = _collect_all_input_files()
    proofs_root = os.path.normpath(PROOFS_ROOT)
    result = []
    for app_name, branch_name, proof_results, hash_part, full_path in files:
        try:
            rel = os.path.relpath(full_path, proofs_root)
        except ValueError:
            rel = full_path
        result.append({
            "app": app_name,
            "branch": branch_name,
            "proof_results": proof_results,
            "hash": hash_part,
            "path": rel,
        })
    return jsonify({"count": len(result), "files": result}), 200


@app.get("/input-files/zip")
def zip_all_input_files():
    """
    Build a zip of all input_<hash>.json files from ACC, LRT, and KS.
    Names inside zip: {app}/{branch}/{proof_results}/ltr/input_{hash}.json
    """
    files = _collect_all_input_files()
    if not files:
        return jsonify({"error": True, "detail": "No input files found under proofs"}), 404

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for app_name, branch_name, proof_results, hash_part, full_path in files:
            arcname = os.path.join(app_name, branch_name, proof_results, "ltr", f"input_{hash_part}.json")
            zf.write(full_path, arcname)

    zip_buf.seek(0)
    return send_file(
        zip_buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name="all_input_files.zip",
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "input-files"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("API_input_files_port", "5015"))
    app.run(host="0.0.0.0", port=port, debug=False)
