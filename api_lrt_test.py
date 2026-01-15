from concurrent.futures import ThreadPoolExecutor
import atexit, time, os, json, zipfile, io, torch, ezkl
from flask import Flask, jsonify, request, abort, send_file
import requests 
from modules.LogisticLRT import LogisticLRT
import threading

API_lrt_port = int(os.getenv("API_lrt_port", "5014"))
SAMPLE_INTERVAL = float(os.environ.get("SAMPLE_INTERVAL", "0.5"))
STATS_LOGGER_URL = os.getenv("STATS_LOGGER_URL", "http://localhost:5003")
TARGET_CONTAINER = os.environ.get("TARGET_CONTAINER", "").strip()
DOCKER_SCRAPE_INTERVAL = float(os.environ.get("DOCKER_SCRAPE_INTERVAL", "0.5"))
JOBS = {}
SETUP_JOBS = {} 
LRT_SETUP_LOCK = threading.Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=2)
app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROOFS_DIR = os.path.join(BASE_DIR, "proofs", "logistic_lrt")
COSMETIC_PKL = os.path.join(PROOFS_DIR, "cosmetic.pkl")
os.makedirs(PROOFS_DIR, exist_ok=True)
cosmet = None
if os.path.exists(COSMETIC_PKL):
    cosmet = LogisticLRT.load(COSMETIC_PKL)
    cosmet.use_zkp = int(os.environ.get("ZKP_MODE",1))
    cosmet.gen_full_proof = int(os.environ.get("GEN_FULL_PROOF",1))

def trigger_stats_snapshot(container_name: str, tag: str = None):
    url = f"{STATS_LOGGER_URL}/create-prover-snapshot"
    payload = {"container_name": container_name}
    if tag:
        payload["tag"] = tag
    try:
        r = requests.post(url, json=payload, timeout=5)
        r.raise_for_status()
        data = r.json() if r.headers.get("content-type","").startswith("application/json") else {}
        print(f"[stats_logger] snapshot triggered for {container_name}, tag={tag}")
        return data
    except Exception as e:
        print(f"[stats_logger] snapshot failed: {e}")
        return None

def _new_job():
    return str(int(time.time() * 1000))

def _enqueue(job_type: str, payload: dict) -> str:
    job_id = _new_job()
    JOBS[job_id] = {"job_id": job_id,"type": job_type,"status": "queued","started_at": time.time(),"result": None,"error": None,}
    if job_type == "proof":
        nonce = payload.get("nonce")
        JOBS[job_id].update({"user_hash": payload.get("user_hash"),"smt_list": payload.get("smt_list", []),"nonce": nonce.tolist() if isinstance(nonce, torch.Tensor) else nonce,})
        EXECUTOR.submit(_run_job, job_id, cosmet, payload)
        return job_id

    if job_type == "lrt-setup":
        def _runner():
            global cosmet
            if not LRT_SETUP_LOCK.acquire(blocking=False):
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["error"] = "LRT setup already running"
                return
            try:
                JOBS[job_id]["status"] = "running"
                snap_start = trigger_stats_snapshot(TARGET_CONTAINER or "zkpprover",tag=f"{job_id}-setup-start")
                result = _run_lrt_setup(payload)
                snap_end = trigger_stats_snapshot(TARGET_CONTAINER or "zkpprover",tag=f"{job_id}-setup-end")
                cosmet = LogisticLRT.load("./proofs/logistic_lrt/cosmetic.pkl")
                cosmet.use_zkp = int(os.environ.get("ZKP_MODE", 1))
                cosmet.gen_full_proof = int(os.environ.get("GEN_FULL_PROOF", 1))
                JOBS[job_id]["status"] = "done"
                JOBS[job_id]["result"] = result
                JOBS[job_id]["snapshots"] = {"setup_start": snap_start,"setup_end": snap_end}
            except Exception as e:
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["error"] = str(e)
            finally:
                LRT_SETUP_LOCK.release()
        EXECUTOR.submit(_runner)
        return job_id
    JOBS[job_id]["status"] = "error"
    JOBS[job_id]["error"] = f"Unknown job type: {job_type}"
    return job_id

def _run_lrt_setup(payload: dict):
    """
    Equivalent to:
      ID=1,1 ZKP_MODE=1 GEN_FULL_PROOF=1 SETUP_MRP=1 SETUP_LTR=1 python driver_logistic_lrt_modules.py
    """
    id_val         = str(payload.get("ID", os.getenv("ID", "1,1")))
    zkp_mode       = int(payload.get("ZKP_MODE", os.getenv("ZKP_MODE", "1")))
    gen_full_proof = int(payload.get("GEN_FULL_PROOF", os.getenv("GEN_FULL_PROOF", "1")))
    setup_mrp      = int(payload.get("SETUP_MRP", os.getenv("SETUP_MRP", "1")))
    setup_ltr      = int(payload.get("SETUP_LTR", os.getenv("SETUP_LTR", "1")))
    zkp_scaler     = int(payload.get("ZKP_SCALER", os.getenv("ZKP_SCALER", "10")))
    tree_height    = int(payload.get("TREE_HEIGHT", os.getenv("TREE_HEIGHT", "256")))

    test_inclusion = bool(payload.get("TEST_INCLUSION", False))
    test_exclusion = bool(payload.get("TEST_EXCLUSION", False))

    # apply env vars (so class reads exactly like CLI)
    os.environ["ID"] = id_val
    os.environ["ZKP_MODE"] = str(zkp_mode)
    os.environ["GEN_FULL_PROOF"] = str(gen_full_proof)
    os.environ["SETUP_MRP"] = str(setup_mrp)
    os.environ["SETUP_LTR"] = str(setup_ltr)
    os.environ["ZKP_SCALER"] = str(zkp_scaler)
    os.environ["TREE_HEIGHT"] = str(tree_height)

    t0 = time.time()
    lrt = LogisticLRT()
    lrt.run(TEST_INCLUSION=test_inclusion, TEST_EXCLUSION=test_exclusion)
    lrt.save()

    # reload check
    lrt2 = LogisticLRT.load(COSMETIC_PKL) if os.path.exists(COSMETIC_PKL) else None

    return {
        "ok": True,
        "elapsed_sec": round(time.time() - t0, 3),
        "env": {
            "ID": id_val,
            "ZKP_MODE": zkp_mode,
            "GEN_FULL_PROOF": gen_full_proof,
            "SETUP_MRP": setup_mrp,
            "SETUP_LTR": setup_ltr,
            "ZKP_SCALER": zkp_scaler,
            "TREE_HEIGHT": tree_height
        },
        "outputs": {
            "cosmetic_pkl": os.path.abspath("./proofs/logistic_lrt/cosmetic.pkl"),
            "abs_gap_dir": os.path.abspath("./proofs/logistic_lrt/abs_gap_zk_api"),
            "proof_root": os.path.abspath("./proofs/logistic_lrt"),
        },
        "reload_check": bool(lrt2 is not None),
    }

def filter_by_raw_hash(directory: str, raw_value_hash: str):
    ltr_file = f"test_{raw_value_hash}.pf"
    ltr_path = os.path.join(directory, ltr_file)
    ltr = [ltr_path] if os.path.isfile(ltr_path) else []
    prefix = f"test_{raw_value_hash}_"
    mrp = [os.path.join(directory, fname)for fname in os.listdir(directory)if fname.startswith(prefix)]
    return {"ltr": ltr, "mrp": mrp}

def update_zip_buf(zip_buf, proofs_path_list, subdir):
    with zipfile.ZipFile(zip_buf, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        for proof_path in proofs_path_list:
            proof_abs_path = os.path.abspath(proof_path)
            if not os.path.isfile(proof_abs_path):
                raise FileNotFoundError(f"Missing proof file: {proof_abs_path}")
            arcname = os.path.join(subdir, os.path.basename(proof_abs_path))
            zf.write(proof_abs_path, arcname=arcname)

def proofs_for_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:raise ValueError("Unknown job id")
    if job.get("status") != "done":raise ValueError(f"Job is not done yet (status={job.get('status')})")
    raw_user_hash = job.get("user_hash")
    if raw_user_hash is None:raise ValueError("raw user hash is None")
    active_smts = job.get("active_smts") or []
    if not active_smts:active_smts = ["full", "reduced"]
    proofs_by_smt = {}
    if "full" in active_smts:
        ltr = filter_by_raw_hash(cosmet.mrp_full.ltr_proving_results_folder, raw_user_hash)["ltr"]
        mrp = filter_by_raw_hash(cosmet.mrp_full.mrp_proving_results_folder, raw_user_hash)["mrp"]
        proofs_by_smt["full"] = {"ltr": ltr, "mrp": mrp}
    if "reduced" in active_smts:
        ltr = filter_by_raw_hash(cosmet.mrp_reduced.ltr_proving_results_folder, raw_user_hash)["ltr"]
        mrp = filter_by_raw_hash(cosmet.mrp_reduced.mrp_proving_results_folder, raw_user_hash)["mrp"]
        proofs_by_smt["reduced"] = {"ltr": ltr, "mrp": mrp}
    return raw_user_hash, active_smts, proofs_by_smt

def _zip_proofs_for_job(job_id: str) -> tuple[bytes, str]:
    raw_user_hash, smt_list, proofs_by_smt = proofs_for_job(job_id)
    zip_buf = io.BytesIO()
    zname = f"proofs_{job_id}.zip"
    if "full" in smt_list:
        proofs_full = proofs_by_smt.get("full", {})
        update_zip_buf(zip_buf, proofs_full.get("ltr", []), "full/ltr")
        update_zip_buf(zip_buf, proofs_full.get("mrp", []), "full/mrp")
    if "reduced" in smt_list:
        proofs_reduced = proofs_by_smt.get("reduced", {})
        update_zip_buf(zip_buf, proofs_reduced.get("ltr", []), "reduced/ltr")
        update_zip_buf(zip_buf, proofs_reduced.get("mrp", []), "reduced/mrp")
    zip_buf.seek(0)
    return zip_buf.read(), zname

def generate_proof(cosmet, payload):
    smt_list = payload.get("smt_list") or []
    if isinstance(smt_list, str):smt_list = [smt_list]
    smt_list = [s.strip().lower() for s in smt_list]
    if not smt_list:smt_list = ["full", "reduced"]
    valid = {"full", "reduced"}
    unknown = [s for s in smt_list if s not in valid]
    if unknown:return {"error": True, "proving_error": f"Unknown SMT(s): {unknown}. Valid: {sorted(valid)}"}
    raw_user_hash = payload.get("user_hash")
    if raw_user_hash is None:return {"error": True, "proving_error": "user_hash is None"}
    nonce = payload.get("nonce", None)
    if isinstance(nonce, list):nonce = torch.tensor(nonce, dtype=torch.float32)
    active_smts = []
    mode_by_smt = {}
    try:
        if "full" in smt_list:
            if raw_user_hash in cosmet.mrp_full.map_rawhash_transformedhash:
                cosmet.test_inclusion(cosmet.mrp_full,raw_hash_present=raw_user_hash,total_shape=cosmet.full_total_shape + cosmet.transform_salt_shape,nonce=nonce,)
                mode_by_smt["full"] = "inc"
            else:
                cosmet.mrp_full.path_walk(raw_value_hash=raw_user_hash,nonce=nonce,use_zkp=cosmet.use_zkp,gen_full_proof=cosmet.gen_full_proof,)
                mode_by_smt["full"] = "exc"
            active_smts.append("full")
        if "reduced" in smt_list:
            if raw_user_hash in cosmet.mrp_reduced.map_rawhash_transformedhash:
                cosmet.test_inclusion(cosmet.mrp_reduced,raw_hash_present=raw_user_hash,total_shape=cosmet.reduced_total_shape + cosmet.transform_salt_shape,nonce=nonce,)
                mode_by_smt["reduced"] = "inc"
            else:
                cosmet.mrp_reduced.path_walk(raw_value_hash=raw_user_hash,nonce=nonce,use_zkp=cosmet.use_zkp,gen_full_proof=cosmet.gen_full_proof,)
                mode_by_smt["reduced"] = "exc"
            active_smts.append("reduced")
        return {"error": False, "active_smts": active_smts}
    except Exception as e:
        return {"error": True, "proving_error": f"Exception {e}"}

def _run_job(job_id, cosmet, payload):
    try:
        JOBS[job_id]["status"] = "running"
        snap_start = trigger_stats_snapshot(TARGET_CONTAINER or "zkpprover", tag=f"{job_id}-proof-start")
        result = generate_proof(cosmet, payload)
        JOBS[job_id].update({"status": "done","result": result,"active_smts": result.get("active_smts", []),})
        snap_end = trigger_stats_snapshot(TARGET_CONTAINER or "zkpprover", tag=f"{job_id}-proof-end")
        JOBS[job_id]["snapshots"] = {"proof_start": snap_start, "proof_end": snap_end}
    except Exception as e:
        JOBS[job_id].update({"status": "error", "error": str(e)})

def _delete_proofs_for_job(job_id: str):
    _, _, proofs_by_smt = proofs_for_job(job_id)
    for proofs in proofs_by_smt.values():
        for kind in ("ltr", "mrp"):
            for proof_path in proofs.get(kind, []):
                if proof_path and os.path.isfile(proof_path):
                    os.remove(proof_path)

def _resolve_artifacts(data: dict, kind: str):
    smt_list = data.get("smt_list") or data.get("smt") or []
    which_list = data.get("which") or []
    if isinstance(smt_list, str): smt_list = [smt_list]
    if isinstance(which_list, str): which_list = [which_list]
    if not smt_list or not which_list:return [], [{"reason": "Missing smt or which"}]
    artifacts, missing = [], []
    for smt in smt_list:
        mp = cosmet.mrp_full if smt == "full" else cosmet.mrp_reduced if smt == "reduced" else None
        if not mp:
            missing.append({"smt": smt, "reason": "invalid smt"})
            continue
        for w in which_list:
            if w not in ("ltr","mrp"):
                missing.append({"smt": smt, "which": w, "reason": "invalid which"})
                continue
            if kind == "vk":attr = "ltr_vk_path" if w == "ltr" else "mrp_vk_path"
            elif kind == "settings":attr = "ltr_settings_path" if w == "ltr" else "mrp_settings_path"
            elif kind == "cc":attr = "ltr_compiled_model_path" if w == "ltr" else "mrp_compiled_model_path"
            else:
                missing.append({"smt": smt, "which": w, "reason": "invalid kind"})
                continue
            path = getattr(mp, attr, None)
            if path and os.path.isfile(path):artifacts.append({"smt": smt, "which": w, "path": path})
            else:missing.append({"smt": smt, "which": w, "reason": f"{attr} missing"})
    return artifacts, missing

def _handle_artifact_zip_request(kind: str, label: str, zip_name: str):
    data = request.get_json() or {}
    artifacts, missing = _resolve_artifacts(data, kind)
    if not artifacts:
        return jsonify({"error": True,"detail": f"No {label} available","missing": missing}), 404
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for a in artifacts:
            arc = os.path.join(a["smt"], a["which"], os.path.basename(a["path"]))
            zf.write(a["path"], arc)
    zip_buf.seek(0)
    return send_file(io.BytesIO(zip_buf.read()),mimetype="application/zip",as_attachment=True,download_name=zip_name,)

def _verify_proofs(job_id: str):
    raw_user_hash, smt_list, proofs_by_smt = proofs_for_job(job_id)
    results = []
    for smt, proofs in proofs_by_smt.items():
        for kind in ("ltr", "mrp"):
            for proof_path in proofs.get(kind, []):
                entry = {"smt": smt,"kind": kind,"proof": os.path.basename(proof_path),}
                try:
                    vk_list, _ = _resolve_artifacts({"smt": [smt], "which": [kind]}, "vk")
                    st_list, _ = _resolve_artifacts({"smt": [smt], "which": [kind]}, "settings")
                    vk_path = vk_list[0]["path"]
                    settings_path = st_list[0]["path"]
                    ok = ezkl.verify(proof_path=proof_path,vk_path=vk_path,srs_path=None,settings_path=settings_path,)
                except Exception as e:
                    entry["ok"] = False
                    entry["error"] = str(e)
                results.append(entry)
    overall_ok = all(r.get("ok") for r in results)
    return {"ok": overall_ok,"user_hash": raw_user_hash,"results": results,}

@app.get("/jobs/<job_id>")
def get_status(job_id):
    job = JOBS.get(job_id)
    if not job:abort(404, description="Unknown job id")
    return jsonify(job), 200

@app.post("/lrt/setup")
def lrt_setup():
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {} 
    job_id = _enqueue("lrt-setup", payload)
    return jsonify({"job_id": job_id, "status_url": f"/jobs/{job_id}"}), 202

@app.post("/prove-hash/")
def prove_hash_endpoint():
    payload_data = request.get_json()
    smt_list = payload_data.get("smt_list",[])
    nonce = payload_data.get("nonce",None)
    user_hash = payload_data.get("user_hash",None)
    if nonce is not None:nonce = torch.tensor(nonce, dtype=torch.float32)
    payload = {"smt_list":smt_list,"nonce":nonce,"user_hash":user_hash}
    job_id = _enqueue("proof", payload)
    return jsonify({"job_id": job_id, "status_url": f"/jobs/{job_id}"}), 202

@app.post("/verify-job/<job_id>")
def verify_job(job_id):
    job = JOBS.get(job_id)
    if not job:abort(404, description="Unknown job id")
    if job.get("status") != "done":return jsonify({"ok": False, "error": "job not finished yet"}), 409
    try:
        snap_start = trigger_stats_snapshot(TARGET_CONTAINER or "zkpprover",tag=f"{job_id}-verify-start")
        summary = _verify_proofs(job_id)
        snap_end = trigger_stats_snapshot(TARGET_CONTAINER or "zkpprover",tag=f"{job_id}-verify-end")
        job["verification"] = summary
        job.setdefault("snapshots", {})
        job["snapshots"].update({"verify_start": snap_start,"verify_end": snap_end})
        return jsonify(summary), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.get("/jobs/<job_id>/download")
def download_job_proofs(job_id):
    try:
        data, zname = _zip_proofs_for_job(job_id)
        return send_file(io.BytesIO(data), mimetype="application/zip",as_attachment=True, download_name=zname)
    except Exception as e:return jsonify({"ok": False, "error": str(e)}), 400

@app.get("/abs-gap-proof")
def download_abs_gap_proof():
    proof_path = "proofs/logistic_lrt/abs_gap_zk_api/proof_1.pf"
    if not os.path.isfile(proof_path):abort(404, description="abs gap proof file not found")
    return send_file(proof_path,mimetype="application/octet-stream",as_attachment=True,download_name="proof_1.pf",)

@app.post("/fetch-vk")
def fetch_vk():
    return _handle_artifact_zip_request("vk", "VK", "vk_artifacts.zip")

@app.post("/fetch-settings")
def fetch_settings():
    return _handle_artifact_zip_request("settings", "settings", "settings_artifacts.zip")

@app.post("/fetch-cc")
def fetch_cc():
    return _handle_artifact_zip_request("cc", "CC", "cc_artifacts.zip")

@app.delete("/jobs/<job_id>")
def delete_job(job_id):
    job = JOBS.get(job_id)
    if not job:abort(404, description="Unknown job id")
    if job.get("status") == "done":_delete_proofs_for_job(job_id)
    job["status"] = "error"
    job["error"] = "cancelled"
    return jsonify({"ok": True, "job_id": job_id}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=API_lrt_port, debug=False)