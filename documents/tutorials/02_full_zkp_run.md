# Tutorial 02 — Full zk-SNARK Run

**Goal**: Generate real zero-knowledge proofs for inclusion and exclusion. This requires a one-time circuit setup (compilation + key generation) and then proof generation.

**Prerequisites**:
- Python dependencies installed (`pip install -r requirements.txt`)
- EZKL installed and functional (verify with `python -c "import ezkl; print(ezkl.__version__)"`)
- Tutorial 01 completed (understanding of the dry-run output)

---

## Overview of what happens

```
Setup phase (once per circuit configuration)
  └── Compile PyTorch model → ONNX → arithmetic circuit
  └── Generate proving key (pk) and verification key (vk)
  └── Write artifacts to proofs/<name>/<uuid>/

Proof phase (per user record)
  └── Run EZKL prove on the compiled circuit
  └── Write .pf proof file
  └── Verify .pf file against vk
```

---

## Step 1 — Run setup and proof generation together

The following command runs everything from scratch:

```bash
ZKP_MODE=1 SETUP_MRP=1 SETUP_LTR=1 GEN_FULL_PROOF=1 python driver.py
```

| Variable | Value | Effect |
|----------|-------|--------|
| `ZKP_MODE` | `1` | Enables actual proof generation |
| `SETUP_MRP` | `1` | Compiles the Merkle path aggregator circuit |
| `SETUP_LTR` | `1` | Compiles the leaf transform circuit |
| `GEN_FULL_PROOF` | `1` | Generates a proof at every level of the SMT path |

> **Time warning**: Setup involves EZKL circuit compilation and can take several minutes per circuit on a laptop, depending on model complexity and `TREE_HEIGHT`.

---

## Step 2 — Note the generated UUID

When setup completes, a UUID is printed (or logged) and artifacts are written to:

```
proofs/simple_sum_flow-through/<uuid>/
├── ltr_keys/
│   ├── network.onnx
│   ├── model.compiled
│   ├── pk.key
│   ├── vk.key
│   └── settings.json
└── mrp_keys/
    ├── network.onnx
    ├── model.compiled
    ├── pk.key
    ├── vk.key
    └── settings.json
```

Copy and save the UUID — you will need it to skip setup on future runs.

---

## Step 3 — Reuse circuits on subsequent runs

Pass the saved UUID as `ID` to skip the expensive setup phase:

```bash
ID=<your-uuid> ZKP_MODE=1 GEN_FULL_PROOF=1 python driver.py
```

Proof generation still runs, but circuit compilation is skipped. This is much faster.

---

## Step 4 — Examine the proof files

After a successful run, `.pf` files are written alongside the keys. You can verify any proof file manually:

```bash
python - <<'EOF'
import ezkl, asyncio

async def check():
    ok = await ezkl.verify(
        proof_path="proofs/simple_sum_flow-through/<uuid>/ltr_keys/test_<hash>.pf",
        settings_path="proofs/simple_sum_flow-through/<uuid>/ltr_keys/settings.json",
        vk_path="proofs/simple_sum_flow-through/<uuid>/ltr_keys/vk.key",
    )
    print("Proof valid:", ok)

asyncio.run(check())
EOF
```

---

## Step 5 — Faster variant (skip default-value levels)

Setting `GEN_FULL_PROOF=0` generates proofs only at SMT levels where a sibling is non-default (i.e., another real user shares a path prefix). This is much faster and still proves membership:

```bash
ID=<your-uuid> ZKP_MODE=1 GEN_FULL_PROOF=0 python driver.py
```

---

## Troubleshooting

### "Dimension mismatch" or ONNX shape error

Inspect the compiled ONNX graph:

```bash
python -c '
import onnx
m = onnx.load("proofs/simple_sum_flow-through/<uuid>/ltr_keys/network.onnx")
print(onnx.helper.printable_graph(m.graph))
'
```

Common fix: ensure `transform_salt_shape` in `driver.py` matches the actual salt tensor dimensions.

### "ID not found" error

The UUID you passed does not have a matching subdirectory under `proofs/`. Either:
- Leave `ID` unset to generate a new one.
- Check the path `proofs/<prover_name>/<uuid>/` exists.

### Out of memory during setup

Reduce `TREE_HEIGHT` or use `GEN_FULL_PROOF=0`. Smaller trees require smaller circuits.

---

## What's next

- Use the REST APIs to generate proofs programmatically: [Tutorial 03 — API Workflow](03_api_workflow.md).
- Deploy the full stack with Docker: [docker_deployment.md](../docker_deployment.md).
