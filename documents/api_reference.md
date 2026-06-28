# API Reference — CoSMeTIC Prover APIs

CoSMeTIC exposes three independent Flask APIs, each targeting a different statistical test. All three share the same job-based workflow and endpoint structure.

---

## Services and ports

| API | File | Default port | Test |
|-----|------|-------------|------|
| `api_acc_test.py` | Logistic Accuracy | `5012` | Proves accuracy of a logistic classifier |
| `api_ks_test.py` | Kolmogorov-Smirnov | `5013` | Proves the KS test statistic |
| `api_lrt_test.py` | Likelihood Ratio Test | `5014` | Proves the LRT statistic (full vs. reduced model) |

Replace `<HOST>` and `<PORT>` in all examples below with the actual server address and port.

---

## Workflow overview

```
POST /<test>/setup          (async) → job_id
GET  /jobs/<job_id>         → poll until "done"

POST /prove-hash/           (async) → job_id
GET  /jobs/<job_id>         → poll until "done"

POST /verify-job/<job_id>   → verification result
GET  /jobs/<job_id>/download → ZIP of .pf files

DELETE /jobs/<job_id>       → cleanup
```

---

## Key concepts

### `user_hash`

The raw hash string identifying the user record (leaf) you want to prove membership or non-membership for.

- If the hash exists in the SMT → inclusion proof.
- If the hash does not exist → exclusion proof using the default-leaf path.

### `nonce`

A random vector used to ensure zero-knowledge soundness across repeated proofs.

- Shape varies by test (see table below).
- If omitted, the server generates a random nonce automatically.
- If provided, must match the exact shape expected by the circuit.

| API | Nonce shape | Example |
|-----|-------------|---------|
| ACC | `(1, 3)` | `[[0.0, 0.0, 0.0]]` |
| LRT | `(1, 11)` | `[[0.0, 0.0, ..., 0.0]]` (11 values) |
| KS | `(1, 17)` | `[[0.0, 0.0, ..., 0.0]]` (17 values) |

### `smt_list`

The list of SMTs to generate proofs for within a single request.

| API | Valid values | Meaning |
|-----|-------------|---------|
| ACC | `["length", "acc"]` | Two sub-trees for accuracy |
| LRT | `["full", "reduced"]` | Full model vs. reduced model |
| KS | *(not required)* | `s1` and `s2` are implicit |

---

## 1. Setup

Setup builds the SMTs and compiles EZKL circuits (proving keys, verification keys, settings). It must complete before any proof jobs can run.

### Invocation modes

**Mode 1 — explicit JSON (recommended)**

```bash
curl -X POST "http://<HOST>:<PORT>/<TEST>/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "ID": "1,1",
    "ZKP_MODE": 1,
    "GEN_FULL_PROOF": 1,
    "SETUP_MRP": 1,
    "SETUP_LTR": 1,
    "ZKP_SCALER": 10,
    "TREE_HEIGHT": 8,
    "TEST_INCLUSION": false,
    "TEST_EXCLUSION": false
  }'
```

Replace `<TEST>` with `acc`, `ks`, or `lrt`.

**Mode 2 — defaults from environment variables**

```bash
curl -X POST "http://<HOST>:<PORT>/<TEST>/setup"
```

**Mode 3 — partial override**

```bash
curl -X POST "http://<HOST>:<PORT>/<TEST>/setup" \
  -H "Content-Type: application/json" \
  -d '{"TREE_HEIGHT": 16}'
```

### Setup payload fields

| Field | Type | Description |
|-------|------|-------------|
| `ID` | string | Comma-separated run IDs (`"1,1"`) |
| `ZKP_MODE` | int (0/1) | Enable actual zk-SNARK generation |
| `GEN_FULL_PROOF` | int (0/1) | Generate proofs at every SMT level |
| `SETUP_MRP` | int (0/1) | Compile/key-gen for the MRP circuit |
| `SETUP_LTR` | int (0/1) | Compile/key-gen for the LTR circuit |
| `ZKP_SCALER` | int | Fixed-point scaling factor for circuits |
| `TREE_HEIGHT` | int | SMT height (e.g., `8`, `16`, `256`) |
| `TEST_INCLUSION` | bool | Run an inclusion test after setup |
| `TEST_EXCLUSION` | bool | Run an exclusion test after setup |

### Setup response

```json
{
  "job_id": "<uuid>",
  "status_url": "/jobs/<uuid>"
}
```

---

## 2. Check job status

All async operations (setup and prove) return a `job_id`. Poll until `status == "done"`.

```bash
curl -s "http://<HOST>:<PORT>/jobs/<job-id>"
```

### Status values

| Status | Meaning |
|--------|---------|
| `queued` | Waiting to be picked up by the executor |
| `running` | Actively generating proofs or running setup |
| `done` | Complete — proofs/artifacts are ready |
| `error` | Failed — check the `error` field in the response |

---

## 3. Submit a proof generation job

### ACC

```bash
curl -X POST "http://<HOST>:<PORT>/prove-hash/" \
  -H "Content-Type: application/json" \
  -d '{
    "smt_list": ["length", "acc"],
    "user_hash": "<RAW_HASH>",
    "nonce": [[0.0, 0.0, 0.0]]
  }'
```

### LRT

```bash
curl -X POST "http://<HOST>:<PORT>/prove-hash/" \
  -H "Content-Type: application/json" \
  -d '{
    "smt_list": ["full", "reduced"],
    "user_hash": "<RAW_HASH>",
    "nonce": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
  }'
```

### KS

```bash
curl -X POST "http://<HOST>:<PORT>/prove-hash/" \
  -H "Content-Type: application/json" \
  -d '{
    "user_hash": "<RAW_HASH>",
    "nonce": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
  }'
```

---

## 4. Verify proofs

```bash
curl -s -X POST "http://<HOST>:<PORT>/verify-job/<job-id>"
```

### Response structure

```json
{
  "ok": true,
  "user_hash": "<RAW_HASH>",
  "results": [
    {"proof_file": "s1/ltr/test_<hash>.pf", "verified": true},
    ...
  ]
}
```

---

## 5. Download proofs (ZIP)

```bash
curl -OJ "http://<HOST>:<PORT>/jobs/<job-id>/download"
```

The downloaded archive contains `.pf` proof files organized by SMT and proof type:

```
<smt_name>/
  ltr/
    test_<raw_hash>.pf
  mrp/
    test_<raw_hash>_<level>.pf
```

---

## 6. Download precomputed abs-gap proof (KS and LRT only)

```bash
curl -OJ "http://<HOST>:<PORT>/abs-gap-proof"
```

Returns a single `proof_1.pf` file representing the abs-gap statistic generated during setup.

---

## 7. Download compiled artifacts

These static artifacts are produced during setup and can be reused for many proof jobs.

### Compiled circuits

```bash
curl -X POST "http://<HOST>:<PORT>/fetch-cc" \
  -H "Content-Type: application/json" \
  -d '{"smt_list": ["s1", "s2"], "which": ["ltr", "mrp"]}' -OJ
```

### Verification keys

```bash
curl -X POST "http://<HOST>:<PORT>/fetch-vk" \
  -H "Content-Type: application/json" \
  -d '{"smt_list": ["s1", "s2"], "which": ["ltr", "mrp"]}' -OJ
```

### Settings

```bash
curl -X POST "http://<HOST>:<PORT>/fetch-settings" \
  -H "Content-Type: application/json" \
  -d '{"smt_list": ["s1", "s2"], "which": ["ltr", "mrp"]}' -OJ
```

For ACC and LRT, replace `["s1", "s2"]` with the relevant `smt_list` (e.g., `["full", "reduced"]` for LRT).

---

## 8. Delete a job

```bash
curl -X DELETE "http://<HOST>:<PORT>/jobs/<job-id>"
```

Marks the job as cancelled and removes its proof files from disk if the job was in `done` state.
