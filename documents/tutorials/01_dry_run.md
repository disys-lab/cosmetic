# Tutorial 01 — Dry Run (No zk-SNARKs)

**Goal**: Get the framework running end-to-end in minutes without any circuit compilation or proof generation. This is the best starting point for understanding the data flow.

**Prerequisites**: Python dependencies installed (`pip install -r requirements.txt`).

---

## Step 1 — Run the default dry run

```bash
ZKP_MODE=0 python driver.py
```

`ZKP_MODE=0` disables all EZKL machinery. Leaf transforms and aggregations are computed using standard PyTorch `forward()` calls instead of generating zk-SNARK proofs.

---

## Step 2 — Read the output

You should see output similar to:

```
Root Value: tensor([[ 9.2000, 2.9600, ...]])
Root Hash: 0x3a1f...

===== INCLUSION TEST: Picking raw data value that exists =====
...
Path walk complete. Leaf found at position 0x...
Proof generation skipped (ZKP_MODE=0).

===== EXCLUSION TEST: Picking raw data value that does not exist =====
...
Leaf at position 0x... is a default leaf. Non-membership confirmed.
Proof generation skipped (ZKP_MODE=0).
```

### What happened

1. `driver.py` loaded 12 user records from the `s&p_loglikelihood_debug` dataset.
2. Each record's salted value was passed through the `FlowThrough` transformer (identity function).
3. The `Adder` aggregated the transformed values into the Merkle tree bottom-up.
4. The root value and hash were printed.
5. An **inclusion test** was run on `user_3` (a member of the dataset).
6. An **exclusion test** was run on an absent record (not in the dataset).

---

## Step 3 — Try a different transformer

```bash
ZKP_MODE=0 LTR_CHOICE=affine python driver.py
```

The `Affine` transformer applies `m * x + c` to each salted record before aggregation. The root value will be different but the membership/non-membership logic is identical.

Try each of:

```bash
ZKP_MODE=0 LTR_CHOICE=flow-through python driver.py
ZKP_MODE=0 LTR_CHOICE=affine      python driver.py
ZKP_MODE=0 LTR_CHOICE=exponent    python driver.py
ZKP_MODE=0 LTR_CHOICE=length      python driver.py
```

---

## Step 4 — Understand the dataset

Open `driver.py` and look at the `s&p_loglikelihood_debug` branch (line ~53). Each entry in `raw_data` has:

- `name` — a label (not used cryptographically).
- `value` — a `(1, 16)` tensor: 6 binary features followed by 10 continuous values as the user salt.
- `transform_salt` — a `(1, 2)` tensor appended after the transformer output.

The `test_absent_data_record` (labelled `user_11` but with slightly different values) is the record used in the exclusion test.

---

## What's next

- To generate actual zero-knowledge proofs, see [Tutorial 02 — Full ZKP Run](02_full_zkp_run.md).
- To understand the mathematical concepts behind inclusion/exclusion, see [concepts.md](../concepts.md).
