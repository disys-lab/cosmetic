# Quickstart — Local Python Usage

This guide gets you running CoSMeTIC locally using `driver.py` without Docker. For the Docker-based API stack, see [docker_deployment.md](docker_deployment.md).

---

## Prerequisites

Python 3.9+ is recommended. Install all Python dependencies:

```bash
pip install -r requirements.txt
```

The most important dependency is [EZKL](https://github.com/zkonduit/ezkl), which handles zk-SNARK circuit compilation and proof generation. Refer to the EZKL documentation if you run into platform-specific installation issues.

---

## Understanding `driver.py`

`driver.py` is the entry-point for local experimentation. It:

1. Defines a dataset (`raw_data`) — a list of user records with values and transform salts.
2. Picks a transformer `F` (via `LTR_CHOICE`).
3. Instantiates an `Adder` aggregator.
4. Creates a `MerkleProver` and builds the SMT.
5. Optionally runs inclusion and exclusion tests with or without zk-SNARKs.

---

## Option A — Dry run (fastest, no zk-SNARKs)

This is the best starting point. No circuits are compiled; forward passes are computed directly.

```bash
ZKP_MODE=0 python driver.py
```

Expected output (abbreviated):

```
Root Value: tensor([[ 9.2000, ...]])
Root Hash: <hex string>
===== INCLUSION TEST: Picking raw data value that exists =====
...
===== EXCLUSION TEST: Picking raw data value that does not exist =====
...
```

### Choosing a transformer

```bash
ZKP_MODE=0 LTR_CHOICE=affine python driver.py
```

Available `LTR_CHOICE` values:

| Value | Transformer |
|-------|-------------|
| `flow-through` | Identity (default) |
| `affine` | Linear: `m * x + c` |
| `exponent` | Elementwise exponent |
| `length` | L2 norm |

---

## Option B — Full zk-SNARK run (first time)

The first time you run with ZKP mode enabled you must also run setup, which compiles circuits and generates proving/verification keys. This can take several minutes.

```bash
ZKP_MODE=1 SETUP_MRP=1 SETUP_LTR=1 GEN_FULL_PROOF=1 python driver.py
```

On completion a UUID is printed to stdout and artifacts are written to:

```
proofs/simple_sum_<ltr_choice>/<uuid>/
```

> **Note**: `GEN_FULL_PROOF=1` generates a proof at every hop in the Merkle path. Setting it to `0` skips levels where siblings are default nodes, which is faster but produces fewer proof files.

---

## Option C — Reusing existing circuits

Once setup has been run once, you can reuse the compiled circuits by passing the generated `ID`:

```bash
ID=<your-uuid> ZKP_MODE=1 GEN_FULL_PROOF=0 python driver.py
```

This skips the circuit compilation step and goes straight to proof generation.

---

## Debugging dimension mismatch errors

If EZKL reports a shape error, inspect the compiled ONNX network:

```bash
python -c '
import onnx
m = onnx.load("proofs/<prover_name>/<uuid>/ltr_keys/network.onnx")
print(onnx.helper.printable_graph(m.graph))
'
```

Common causes:

- Mismatch between the `transform_salt_shape` set in the driver and the actual salt dimensions.
- Changing the transformer after circuits were compiled (requires a new setup).

---

## What the tests do

### Inclusion test

Picks `raw_data[2]` (Carol / user_3 in the dataset) as the "present" record, computes its path through the SMT, and generates (or verifies) proofs showing it contributed to the root.

### Exclusion test

Uses a record (`test_absent_data_record`) that was not in the original `raw_data` list. The path walk lands on a default leaf, and the proof demonstrates non-membership.
