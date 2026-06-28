# Tutorial 03 — End-to-End Proof via the REST APIs

**Goal**: Run a complete proof lifecycle (setup → prove → verify → download) against the CoSMeTIC Flask APIs using `curl`.

**Prerequisites**:
- The Docker stack is running (`docker compose up -d`) — see [docker_deployment.md](../docker_deployment.md).
- `curl` and `jq` available on your machine.

This tutorial targets the **KS API** on port `5013`. The same steps apply to the ACC (`5012`) and LRT (`5014`) APIs — just change the port and any API-specific fields (see [api_reference.md](../api_reference.md)).

---

## Variables used in this tutorial

```bash
HOST="localhost"
PORT="5013"
BASE="http://${HOST}:${PORT}"
```

---

## Step 1 — Check the server is up

```bash
curl -s "${BASE}/"
```

You should get a JSON response or a short status message confirming the API is running.

---

## Step 2 — Run setup

Setup builds the Sparse Merkle Trees and compiles EZKL circuits. It only needs to run once per configuration.

```bash
SETUP_JOB=$(curl -s -X POST "${BASE}/ks/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "ZKP_MODE": 1,
    "GEN_FULL_PROOF": 0,
    "SETUP_MRP": 1,
    "SETUP_LTR": 1,
    "ZKP_SCALER": 10,
    "TREE_HEIGHT": 8
  }')

echo "${SETUP_JOB}" | jq .

SETUP_JOB_ID=$(echo "${SETUP_JOB}" | jq -r '.job_id')
echo "Setup job ID: ${SETUP_JOB_ID}"
```

---

## Step 3 — Poll until setup is done

```bash
while true; do
  STATUS=$(curl -s "${BASE}/jobs/${SETUP_JOB_ID}" | jq -r '.status')
  echo "$(date '+%H:%M:%S') setup status: ${STATUS}"
  if [[ "${STATUS}" == "done" || "${STATUS}" == "error" ]]; then break; fi
  sleep 10
done
```

When `status` is `done`, setup is complete. If it is `error`, check the `error` field in the response.

---

## Step 4 — Obtain a `user_hash`

The `user_hash` is the raw hash of a user's salted leaf value. In a real deployment this comes from your data pipeline. For testing, check the setup job result for example hashes, or use one logged by `driver.py` during a dry run.

```bash
# Example — substitute with an actual hash from your data
USER_HASH="0xabc123..."
```

---

## Step 5 — Submit a proof generation job

```bash
PROVE_RESP=$(curl -s -X POST "${BASE}/prove-hash/" \
  -H "Content-Type: application/json" \
  -d "{
    \"user_hash\": \"${USER_HASH}\"
  }")

echo "${PROVE_RESP}" | jq .
PROOF_JOB_ID=$(echo "${PROVE_RESP}" | jq -r '.job_id')
echo "Proof job ID: ${PROOF_JOB_ID}"
```

> The KS API does not require `smt_list` — both `s1` and `s2` SMTs are probed automatically.
> To pass a specific nonce (for reproducibility): add `"nonce": [[0.0, 0.0, ..., 0.0]]` (17 values for KS).

---

## Step 6 — Poll until proof generation is done

```bash
while true; do
  STATUS=$(curl -s "${BASE}/jobs/${PROOF_JOB_ID}" | jq -r '.status')
  echo "$(date '+%H:%M:%S') proof status: ${STATUS}"
  if [[ "${STATUS}" == "done" || "${STATUS}" == "error" ]]; then break; fi
  sleep 10
done
```

---

## Step 7 — Verify the proofs

```bash
curl -s -X POST "${BASE}/verify-job/${PROOF_JOB_ID}" | jq .
```

Expected response:

```json
{
  "ok": true,
  "user_hash": "0xabc123...",
  "results": [
    {"proof_file": "s1/ltr/test_0xabc123....pf", "verified": true},
    {"proof_file": "s1/mrp/test_0xabc123..._0.pf", "verified": true},
    ...
  ]
}
```

---

## Step 8 — Download the proof archive

```bash
curl -OJ "${BASE}/jobs/${PROOF_JOB_ID}/download"
```

This downloads a `.zip` file containing all `.pf` proof files for the job, organized by SMT and proof type:

```
s1/ltr/test_<hash>.pf
s1/mrp/test_<hash>_<level>.pf
s2/ltr/test_<hash>.pf
s2/mrp/test_<hash>_<level>.pf
```

---

## Step 9 (optional) — Download the abs-gap proof

The KS test also produces a precomputed abs-gap proof during setup:

```bash
curl -OJ "${BASE}/abs-gap-proof"
```

---

## Step 10 (optional) — Download verification artifacts

If you need to verify proofs offline, download the verification keys and settings:

```bash
curl -X POST "${BASE}/fetch-vk" \
  -H "Content-Type: application/json" \
  -d '{"smt_list": ["s1", "s2"], "which": ["ltr", "mrp"]}' -OJ

curl -X POST "${BASE}/fetch-settings" \
  -H "Content-Type: application/json" \
  -d '{"smt_list": ["s1", "s2"], "which": ["ltr", "mrp"]}' -OJ
```

---

## Step 11 — Clean up the job

```bash
curl -X DELETE "${BASE}/jobs/${PROOF_JOB_ID}"
```

---

## Adapting this tutorial for ACC or LRT

| Change | ACC (`5012`) | LRT (`5014`) |
|--------|-------------|-------------|
| Port | `5012` | `5014` |
| Setup endpoint | `/acc/setup` | `/lrt/setup` |
| `smt_list` in prove | `["length", "acc"]` | `["full", "reduced"]` |
| Nonce shape | `(1, 3)` | `(1, 11)` |

Everything else (polling, verify, download) is identical.
