# COSMeTIC Framework
This is a cryptograhically secure method to prove that certain user's information was used in computing a global aggregate. 
This can be used for any commutative operations like sum, multiply, minimum and maximum. As a result, it can prove to be a 
very robust mechanism to show whether certain user information was used in computing the global aggregate. On the flip
side it is also capable of proving non-inclusion. Under the hood, this framework uses Sparse Merkle Trees(SMT) to prove
membership and non-membership. The proving mechanism is supported using zk_SNARKs powered by the EZKL framework.

## Foundational Terms
This framework basically relies on the following for user i:
* Raw user data `raw_value` (D_i)
D_i is the raw data used in computing the global aggregate. This data is private and cannot be revealed publicly.

* User_salt `user_salt` (US_i) 
S_i is a random torch vector that is concatenated with D_i to make it distinct and unique.

* Salted raw value `salted_raw_value` (SD_i)
Concatenation of `SD_i = Concatenate(D_i,US_i)`

* Local user/leaf level transformation function `transformer` (F)
A function `F(SD_i)->TSD_i` that denotes transformation of salted raw values. This function is secret and is held by the prover. 
We can have any function as a transformer like
  - `TSD_i = m.SD_i + c`: affine transforms
  - `TSD_i = SVM(SD_i)`: application of a trained Support Vector Machine
  - `TSD_i = NeuralNet(SD_i)`: inference from a trained DNN
  - `TSD_i = Polynomial(SD_i,n)`: polynomial transform with respect to degree n.
  - many other transformations that could be linear or non-linear
Each transformation must be capable of being expressed as a PyTorch model using `torch.nn.module`

* Transformation salt `transform_user_salt` (TS_i).
TS_i is also a random torch vector that is concatenated to any TSD_i obtained from the leaf transform.

* Salted leaf transform `transformed_value` (SLT_i)
Concatenation of `SLT_i = Concatenate(TSD_i,TS_i)`

* Global aggregation function `aggregator` (G)
A function `G([SLT_1,SLT_2....SLT_p]) = AggTS` that aggregates salted leaf transforms to derive the global aggregate AggTS.

## Sparse Merkle Trees
Here is an example of a summation Sparse Merkle Tree.

                                                     Merkle Root
                                                          ▲
                                                        AggTS
            
                                   ┼────  ....          ──┼──         ....     ─────┼
                                                  Recursive Aggregation
             ....       ────┼────         ....          ──┼──         ....            ──────┼──      .....
                            │                             │                                 │                             
                      Hash(G(Li,LD))      ....     Hash(G(Lj, LD))    ....           Hash(G(Lk, LD))   
                            ▲                             ▲                                  ▲
                     ┌──────┴──────┐               ┌──────┴──────┐                    ┌──────┴──────┐
                     │             │               │             │                    │             │
                 Leaf_i         Leaf_D          Leaf_j         Leaf_D               Leaf_k         Leaf_D         
                 SLT_i          DeafVal         SLT_j          DeafVal              SLT_k          DeafVal             
                   ▲                              ▲                                   ▲
            ConCat(TSD_i,TS_i)              Concat(TSD_j,TS_j)                  Concat(TSD_k,TS_k)
                   ▲                              ▲                                   ▲
                F(SD_i)                         F(SD_j)                              F(SD_k)
                   ▲                              ▲                                   ▲
                ConCat(D_i,US_i)                Concat(D_j,US_j)                    Concat(D_k,US_k)
                   ▲                              ▲                                   ▲
                  D_i                            D_j                                 D_k


AggTS = G([SLT_i, SLT_j, SLT_k]) = Aggregator([ [21.3, 0.88], [10.1, 0.70], [15.0, 0.64] ]) = e.g., Element-wise sum → [46.4, 2.22]

### Important points about an SMT
* An SMT comprises of typically the same number of leaves as bits in a hash string. For example for Poseidon hash for any input, 
the output is always 256 bits long. Therefore, the SMT will have potential 2^256 leaves.

* Any input `D_h` will correspond to a particular leaf `Leaf_h = SLT_h` such that `HL_h = Hash(Leaf_h)` occupies a position `pos_Leaf_h = 2^{BitRepresentation(HL_h)}`.

* This position is distinct and can be thought of as the integer obtained by converting `Hash(Leaf_h)` to a decimal representation. 

* As a result, leaf position will be in the range `1<=pos_Leaf_h<=2^256` and will occupy a unique position in the ordered leaf set.

* Additionally, each leaf position can be thought of as a unique path from the root that can be expressed as a list of 1s and 0s of length 256

* This means that **`pos_Leaf_h` in binary representation can also represent a path from the root to the leaf location that `Leaf_h` 
would have occupied had it been considered in the computation of AggTS**

* Therefore, to check non-inclusion of some `D_h` that leads to a unique hash `HL_h = Hash(Leaf_h)` and `Leaf_h = SLT_h`, 
it is sufficient to prove that the bit representation of `HL_h` leads to a position `pos_Leaf_h = 2^{BitRepresentation(HL_h)}` 
which corresponds to a default value `DeafVal`

### Using Summation SMTs to show membership and non-membership 
Computation of F and G is supported using zk_SNARKs. For some user h with `(D_h, US_h, TS_h)`, one of the following 
scenarios can arise:

1. D_h was utilized in the computation of AggTS
* In this case, prover supplies a `p_F_h = zkp( Concat [ F( Concat[D_h,US_h] ), TS_h] ) = SLT_h ) ` which can be verified with `vk_F`
* The prover then supplies a series of zk-Merkle-proofs `p_G_1,p_G_2......p_G_l` prove the existence of a series of sibling hashes
`SH_1.....SH_l`, where l is the length of hash string(256 in case of Poseidon and SHA256) which can be verified with `vk_G`.
* Additionally, the prover also supplies selector bit list `b1.....bl`, where each `bt` can be either 0 and 1.

2. D_h was not utilized in computing AggTS
* In this case, prover supplies a `p_F_h = zkp( Concat [ F( Concat[D_h,US_h] ), TS_h] ) = SLT_h )` which can be verified with `vk_F`
* The prover then uses the bit representation of `HL_h = Hash(SLT_h)` given by `pos_Leaf_h` to look up the value corresponding to this position.
* If the prover is honest, then the value at this location must be `Hash(DeafVal) = HLD`. 
* In order to prove that the lookup done by the prover is correct, the prover generates a series of zk-Merkle-proofs for `HLD` 
denoted by `SH_1.....SH_l` and `b1.....bl`
* By checking if `HexRepresentation(b1.....bl) == HL_h`, anyone demonstrate that the Merkle proofs provided by the prover 
indeed correspond to the correct leaf location.
* If the location was non empty, the Merkle root would get violated with a different `SH_1.....SH_l`. 
* If the Merkle proofs were for some other empty location, `HexRepresentation(b1.....bl) != HL_h`

### Proving Set Commitment with Completeness
Consider a set of users `i,j,k` with data values and associated user and transform salts as denoted above. 
We want to show that **The committed SMT root is the result of utilizing exactly this set of user data, and no others.**
To do this the prover needs to reveal the following either publicly or to a trusted set of auditors:
1. The mappings of hash of salted raw values and salted transform values: 
   - `Hash(ConCat(D_i,US_i)):Hash(SLT_i)`
   - `Hash(ConCat(D_j,US_j)):Hash(SLT_j)`
   - `Hash(ConCat(D_k,US_k)):Hash(SLT_k)`
2. zk-SNARKs for leaf level transforms:
   - `p_F_i = zkp( Concat [ F( Concat[D_i,US_i] ), TS_i] ) = SLT_i )`
   - `p_F_j = zkp( Concat [ F( Concat[D_j,US_j] ), TS_j] ) = SLT_j )`
   - `p_F_k = zkp( Concat [ F( Concat[D_k,US_k] ), TS_k] ) = SLT_k )`
3. zk-SNARKs for traversal from each leaf to the root.
   - For a particular zk-SNARK for `SLT_h`, we know that sibling hashes will be the default value `HLD` **unless the 
   sibling is on the path to the root at least one other leaf**.
   - We can recursively examine non-default siblings to exhaustively prove that the source of each non-default sibling appears 
   only from the set of hashes of SLTs revealed above.
   - This process can computationally be a little intense but is one of the most efficient ways of computing completeness short of generating the entire SMT in zkp which would be computationally extremely intense.


## Quickstart

### Prerequisites
Install dependencies prior to running by executing the following command:
`pip install -r requirements.req`

### Environment Variables
There are 4 runtime environment variables that need to be set.
1. `ZKP_MODE`: Determines whether to create the zkSNARKs the Sparse Merkle Trees. This includes both leaf transform and aggregator. Default is 1.
2. `GEN_FULL_PROOF`: Determines whether to create a zkSNARK for each step of the aggregator from leaf to root. 
   Setting this value to 1 will mandate a zkSNARK for each hop. Setting a value of 0 will mean that the mechanism skips 
   generating proofs for levels where no changes in the hash string occur due to default left or right nodes. Default is 0.
3. `SETUP_MRP`: Setup the proving circuit for the MerkleProver aggregator. Default is 0
4. `SETUP_LTR`: Setup the proving circuit for the leaf transformers. Sefault is 0.
5. `ID`: ID for reusing already generated circuits. Default is `NoneType` in Python. 
    For example, if you have a MerkleProver defined as follows:
    ```commandline
    mrp = MerkleProver(prover_name="simple_sum",id=ID,aggregator=aggregator,transformer=transformer,raw_data=raw_data,raw_default_value=raw_default_value,length_transform_salt=transform_salt_shape,setup_mrp=use_zkp&setup_mrp,setup_ltr=use_zkp&setup_ltr)
    ```
    then, if `ID="f63680a8-60ed-11f0-bb59-be70499875d0"` tells MerkleProver that the leaf transform circuits are contained in
    `proofs/simplesum/f63680a8-60ed-11f0-bb59-be70499875d0/ltr_keys` and the aggregator circuits are contained in `proofs/simplesum/f63680a8-60ed-11f0-bb59-be70499875d0/mrp_keys`.

[!IMPORTANT]
The value set to `ID=<id-string>` must correspond to a pre-existing folder name within your directory `proofs/<MerkleProverObject-name>/<id-string>`.
If you dont have this folder, then use leave ID blank and generate the keys and circuit before they can be reused.


### Generating zkSNARKs
If `ID` flag is set, then a new id will be created and used without going through a setup phase. 
If `ID` flag is not set, the framework will attempt to generate a new `ID` 
and eventually carry out the proof setup steps by calling `MerkleProver.setup_proofs(setup_mrp=True,setup_ltr=True)`. 
The resulting circuits and keys will be used for generating proofs.

If `ZKP_MODE` is set, framework will generate proofs for aggregation and leaf transforms for the desired raw data records. 
If `ZKP_MODE` is not set, framework will use the compiled circuits for leaf and aggregator for forward passes at each.

### Running the Program
To run the code simply execute on your command line:
```ID=<your-id-string> ZKP_MODE=1 GEN_FULL_PROOF=1 SETUP_MRP=1 SETUP_LTR=1 python driver.py```
This will run the driver script with all environm

### Dry Runs (without generating zk-SNARKs), a faster and easier method to debug and test.
To quickly get setup, run the driver by executing:

```commandline
ZKP_MODE=0 python driver.py
```
In this case, zk-SNARKS for all steps will not be generated and result of forward passes will be obtained using the, `forward_dry(...)` 
functions at both aggregator and transformer levels. 

The driver has options to invoke multiple leaf level transformations, to invoke them, set the environment variable while running as follows:
```commandline
ZKP_MODE=0 LTR_CHOICE=<your-ltr-choice> python driver.py
```
The allowed values are `"affine","exponent","length","flow-through"`. Default will be `"flow-through"`

## Debugging dimension mismatch errors
You can debug dimension mismatch errors using the following command:
```commandline
python -c 'import onnx; m=onnx.load("proofs/logistic_accuracy/log_acc_length/50324c94-c625-11f0-8da8-be70499875d0/ltr_keys/network.onnx"); print(onnx.helper.printable_graph(m.graph))'
```


# COSMeTIC Prover APIs (ACC / LRT / KS)

This exposes **three Flask APIs** that generate and verify **EZKL proofs** for three tests:

* **`api_acc.py`** → Logistic **Accuracy** test
* **`api_lrt.py`** → Logistic **Likelihood Ratio Test** (**FULL vs REDUCED**)
* **`api_ks.py`** → **Kolmogorov–Smirnov (KS)** test

All three APIs use the same job pattern:

1. **Setup** (build SMTs + compile circuits/keys/settings)
2. **Prove** (generate proofs for a given `user_hash`)
3. **Check job status**
4. **Verify proofs**
5. **Download proofs** (`.zip`)
6. **Download artifacts** (`compiled circuit`, `verification keys`, `settings`) as `.zip`
7. **Delete a job** (and remove proof files)

> **Important**: Setup is required at least once before proofs can be generated, because it builds/loads the model SMTs and prepares artifacts.

---


### HOST and PORT

You must replace:

* `<HOST>` → server IP/hostname
* `<PORT>` → API port (depends on which API you run and env vars)

Default ports:

* ACC: `5012`
* KS: `5013`
* LRT: `5014` 

### Job-based workflow

Proof generation is asynchronous. When you submit a proof request, the API returns a `job_id`. You then:

* Poll `/jobs/<job_id>` until `status == "done"`
* Download proofs and/or verify using that job_id

### What is `user_hash`?

`user_hash` is the **raw hash** identifying the user/record leaf you want to prove inclusion for.

* If the hash exists in the SMT, the prover generates inclusion proofs normally.
* If the hash does not exist in the SMT, the prover still generates a valid proof using default leaf values, following the predefined default-path logic of the tree.

### What is `nonce`?

A `nonce` is the **random input used in the proof path walk**. It must match the shape expected by the circuit.

* If not provided, the server generates a random nonce automatically.
* If provided, send it as a nested list (example: `[[0.0, 0.0, 0.0]]`).

## **Nonce shapes by test**

Each test uses a **different nonce dimensionality**, determined by the underlying circuit:

| Test                            | Nonce Shape | Example                    |
| ------------------------------- | ----------- | -------------------------- |
| **Accuracy (ACC)**              | `(1, 3)`    | `[[0.0, 0.0, 0.0]]`        |
| **Likelihood Ratio Test (LRT)** | `(1, 11)`   | `[[0.0, … (11 values) …]]` |
| **Kolmogorov–Smirnov (KS)**     | `(1, 17)`   | `[[0.0, … (17 values) …]]` |

---

## **Why the nonce is required**

* Ensures **zero-knowledge soundness**
* Prevents **proof correlation across runs**
* Allows repeated proofs for the same record without leakage
* Supports circuit-specific randomness

---

## **Important notes**

* The nonce is **not secret** but must be **well-formed**
* Shape mismatches will result in **proof generation errors**
* The server enforces nonce shape at runtime

---


### What is Setup vs Prove?

* **Setup**: builds SMTs and generates circuit artifacts (compiled circuit, VK, settings).
* **Prove**: creates `.pf` proof files for a specific `user_hash`.

---

## 1) API Overview

### 1.1 Accuracy API (`api_acc.py`)

Purpose: Prove **logistic accuracy** computation using two transformers:

* `length`
* `acc`

### 1.2 LRT API (`api_lrt.py`)

Purpose: Prove Logistic Likelihood Ratio Test comparing:

* `full`
* `reduced`

Also supports downloading a **precomputed abs-gap proof** (if built in your pipeline).

### 1.3 KS API (`api_ks.py`)

Purpose: Prove KS pipeline for:

* `s1` (sample 1 SMT)
* `s2` (sample 2 SMT)

Also supports downloading **precomputed abs-gap proof**.

---

## 2) Setup (build SMTs + circuit artifacts)

### Why setup exists

Setup prepares all heavy artifacts:

* Sparse Merkle Tree build
* EZKL circuit compile
* Proving key / verification key creation
* Settings creation
* Writes `cosmetic.pkl` (serialized state)

### Common setup payload fields

These fields control what gets generated:

| Field            | Meaning                                                        |
| ---------------- | -------------------------------------------------------------- |
| `ID`             | run IDs / prover IDs (example `"1,1"`)                         |
| `ZKP_MODE`       | `1` enables ZKP behavior                                       |
| `GEN_FULL_PROOF` | `1` produce full proof artifacts (more files, more time)       |
| `SETUP_MRP`      | `1` do MRP setup (compile/proving keys depending on your code) |
| `SETUP_LTR`      | `1` do LTR setup                                               |
| `ZKP_SCALER`     | scaling factor for fixed-point / circuit                       |
| `TREE_HEIGHT`    | SMT height (8/16/256 etc.)                                     |
| `TEST_INCLUSION` | optional: run inclusion test during setup                      |
| `TEST_EXCLUSION` | optional: run exclusion test during setup                      |

## Setup invocation modes

The setup endpoint supports **three equivalent invocation modes**. You can choose whichever fits your workflow.

### Mode 1: Explicit JSON setup (recommended for experiments)

In this mode, you explicitly pass all setup parameters in the request body.
This is best when:

* You are running multiple experiments with different configurations
* You want full reproducibility from a single command
* You are scripting or benchmarking different SMT heights / scalers

```bash
curl -X POST "http://<HOST>:<PORT>/<TEST>/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "ID":"1,1",
    "ZKP_MODE":1,
    "GEN_FULL_PROOF":1,
    "SETUP_MRP":1,
    "SETUP_LTR":1,
    "ZKP_SCALER":10,
    "TREE_HEIGHT":8,
    "TEST_INCLUSION":false,
    "TEST_EXCLUSION":false
  }'
```

* All values in the JSON payload **override** any existing environment variables
* The setup process builds:

  * Sparse Merkle Trees
  * EZKL circuits
  * Proving & verification keys
  * Settings files
* The resulting state is serialized to `cosmetic.pkl`

---

### Mode 2: Default setup.

If you do not send any JSON payload, the server automatically runs setup using its built-in defaults.

```bash
curl -X POST "http://<HOST>:<PORT>/<TEST>/setup"
```

**What happens internally**

* The server reads all required configuration from environment variables:

  * `ID`
  * `ZKP_MODE`
  * `GEN_FULL_PROOF`
  * `SETUP_MRP`
  * `SETUP_LTR`
  * `ZKP_SCALER`
  * `TREE_HEIGHT`
* No values are overridden
* Setup runs using the current container configuration

This mode is ideal when:

* Running inside a containerized deployment
* Reusing the same setup across many proof jobs
* Keeping commands minimal for orchestration scripts

---

### Mode 3: Partially override

You may also override only selected fields, while the rest use defaults:

```bash
curl -X POST "http://<HOST>:<PORT>/<TEST>/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "TREE_HEIGHT":16
  }'
```

In this case:

* Only the provided fields are overridden
* All other values fall back to environment variables

---

### Setup command (works for all APIs)

Just change the endpoint: `/acc/setup` or `/lrt/setup` or `/ks/setup`

```bash
curl -X POST "http://<HOST>:<PORT>/<TEST>/setup" \
  -H "Content-Type: application/json" \
  -d '{
    "ID":"1,1",
    "ZKP_MODE":1,
    "GEN_FULL_PROOF":1,
    "SETUP_MRP":1,
    "SETUP_LTR":1,
    "ZKP_SCALER":10,
    "TREE_HEIGHT":8,
    "TEST_INCLUSION":false,
    "TEST_EXCLUSION":false
  }'
```

### What you get back from Setup

The API returns:

* `job_id` (setup runs async)
* status URL

Then you poll job status:

```bash
curl -s "http://<HOST>:<PORT>/jobs/<job-id>"
```

When setup finishes successfully, the job result typically includes:

* elapsed time
* env values used
* output paths (`proof_root`, `cosmetic.pkl`, etc.)

---

## 3) Submit a proof generation job

### Why this exists

This generates `.pf` proof files for a specific `user_hash`.
You submit a request, get `job_id`, then download proofs.

---

### 3.1 ACC: submit proof job (Accuracy)

```bash
curl -X POST "http://<HOST>:<PORT>/prove-hash/" \
  -H "Content-Type: application/json" \
  -d '{
    "smt_list": ["length", "acc"],
    "user_hash": "<RAW_HASH>",
    "nonce": [[0.0, 0.0, 0.0]]
  }'
```

#### What you must change

* `<RAW_HASH>` → the raw hash value string you want to prove
* `nonce`:

  * leave as provided for deterministic testing, OR
  * omit it and the server generates randomly

#### What you get back

* `job_id` for proof generation

---

### 3.2 LRT: submit proof job (Full vs Reduced)

```bash
curl -X POST "http://<HOST>:<PORT>/prove-hash/" \
  -H "Content-Type: application/json" \
  -d '{
    "smt_list": ["full", "reduced"],
    "user_hash": "<RAW_HASH>",
    "nonce": [[0.0, 0.0, 0.0]]
  }'
```

---

### 3.3 KS: submit proof job (s1 vs s2)

```bash
curl -X POST "http://<HOST>:<PORT>/prove-hash/" \
  -H "Content-Type: application/json" \
  -d '{
    "user_hash": "<RAW_HASH>",
    "nonce": [[0.0, 0.0, 0.0]]
  }'
```

---

## 4) Check job status

All APIs use the same endpoint:

```bash
curl -s "http://<HOST>:<PORT>/jobs/<job-id>"
```

### Job status meanings

* `queued` → waiting in executor
* `running` → proofs being generated
* `done` → proofs finished, ready to verify/download
* `error` → something failed (check `error` field)

The job object also stores:

* `active_smts` → which SMT(s) proofs were generated for
* `snapshots` → stats snapshots (if stats logger enabled)

---

## 5) Verify proofs

```bash
curl -s -X POST "http://<HOST>:<PORT>/verify-job/<job-id>"
```

### What verification does

For each `.pf` proof file produced by the job:

* Finds matching `vk` and `settings`
* Runs `ezkl.verify(...)`
* Returns per-proof status and an overall OK

### What you get back

JSON like:

* `ok`: true/false
* `user_hash`
* `results`: list of verified proof files

---

## 6) Download proofs (ZIP)

```bash
curl -OJ "http://<HOST>:<PORT>/jobs/<job-id>/download"
```

### What you receive

A file like:

* `ks_proofs_<job-id>.zip` (KS)
* similar naming for other APIs (depends on implementation)

### ZIP structure

Your code zips proofs into folders by SMT + kind:

```
s1/
  ltr/
    test_<raw_hash>.pf
  mrp/
    test_<raw_hash>_....pf
s2/
  ltr/
  mrp/
```

For ACC/LRT the SMT names differ (`full/reduced`, `acc/length`).

---

## 7) Download precomputed abs-gap proof (KS & LRT)

This returns a single `.pf` file if your pipeline produced it:

```bash
curl -OJ "http://<HOST>:<PORT>/abs-gap-proof"
```

### What you receive

* `proof_1.pf` (or whatever your code names it)
* Used to prove the *abs-gap* statistic generated during setup

---

## 8) Download compiled artifacts (CC / VK / settings)

These are “static” artifacts (built during setup) and can be reused for many proof jobs.

### 8.1 Download compiled circuits (CC)

```bash
curl -X POST "http://<HOST>:<PORT>/fetch-cc" \
  -H "Content-Type: application/json" \
  -d '{
    "smt_list": ["s1", "s2"],
    "which": ["ltr", "mrp"]
  }' -OJ
```

### 8.2 Download verification keys (VK)

```bash
curl -X POST "http://<HOST>:<PORT>/fetch-vk" \
  -H "Content-Type: application/json" \
  -d '{
    "smt_list": ["s1", "s2"],
    "which": ["ltr", "mrp"]
  }' -OJ
```

### 8.3 Download settings

```bash
curl -X POST "http://<HOST>:<PORT>/fetch-settings" \
  -H "Content-Type: application/json" \
  -d '{
    "smt_list": ["s1", "s2"],
    "which": ["ltr", "mrp"]
  }' -OJ
```

### What you receive

Each returns a `.zip` containing files like:

* compiled circuit: typically `*.compiled` 
* verification keys: `*.vk` 
* settings: `settings.json` 

ZIP layout is usually:

```
s1/
  ltr/
    <files>
  mrp/
    <files>
s2/
  ltr/
  mrp/
```

---

## 9) Delete a job (cleanup)

```bash
curl -X DELETE "http://<HOST>:<PORT>/jobs/<job-id>"
```

### What delete does

* Marks job as cancelled
* If job was `done`, your code removes proof files from disk (based on job hash)

---

## 10) What you need to change when using these APIs

### Always change

* `<HOST>` and `<PORT>`
* `user_hash`
* sometimes `smt_list` (ACC/LRT)
* `TREE_HEIGHT` / `ZKP_SCALER` depending on your experiment
* `SETUP_MRP`/`SETUP_LTR` if you want faster setup vs full artifact generation

### When to omit `nonce`

If you don’t care about deterministic runs:

* Remove `"nonce": ...` entirely and server generates one.



## Running the Prover API Stack (Docker Compose)

This repository provides a two-container Docker stack defined in:

`docker-compose.yml` – runs the prover APIs and the stats logger

`Makefile` – builds the required Docker images locally

1. **`zkpprover`**
   Runs the three Flask APIs that generate/verify EZKL proofs:

   * ACC on `5012`
   * KS on `5013`
   * LRT on `5014`

2. **`prover-stats-logger`**
   Collects runtime stats (CPU/memory + Docker container stats) during proof generation and saves snapshots.

Both containers share a single Docker volume called **`results_data`**, so proof outputs and stats logs are stored together.

---

### 1) Prerequisites

Make sure you have:

* Docker installed
* Docker Compose installed (`docker compose ...`)
* These ports available on your machine:

  * `5012`, `5013`, `5014` (prover APIs)
  * `5003` (stats logger)

---

### 2) Start the stack

From the directory containing `docker-compose.yml`, run:

```bash
docker compose up -d
```

Check that both containers are running:

```bash
docker ps
```

---

### 3) What the environment variables do

The prover container uses:

* `API_acc_port`, `API_ks_port`, `API_lrt_port`
  Controls which ports the Flask APIs listen on inside the container.

* `STATS_LOGGER_URL`
  The prover calls this URL to trigger snapshot collection (example: `http://prover-stats-logger:5003`).

* `TARGET_CONTAINER`
  Tells the stats logger which container to monitor by name (here: `zkpprover`).

The stats logger uses:

* `SAMPLE_INTERVAL`
  How often to sample process stats (seconds).

* `DOCKER_SCRAPE_INTERVAL`
  How often to scrape Docker container stats (seconds).

---

### 4) Where results are stored

The stack uses a shared Docker volume:

* Prover writes proof outputs to: `/app/results`
* Stats logger writes logs to: `/prover-stats-logger/results`

Both map to the same named volume: `results_data`.

> If you want results to appear in a local folder on the host (instead of a Docker-managed volume), replace the volume with a bind mount, e.g. `./results:/app/results`.

---

### 5) Stop the stack

```bash
docker compose down
```

To remove volumes too (deletes saved results):

```bash
docker compose down -v
```

---

## Building the Docker images (Makefile)

If you are modifying code and want to rebuild images locally, use the Makefile.

### Build everything

```bash
make build
```

This builds:

* `anon2026dpeval/cosmeticprover:latest`
* `anon2026dpeval/cosmeticstatslogger:latest`

### Build only prover

```bash
make build-prover
```

### Build only stats logger

```bash
make build-statslogger
```

After building, bring the stack up:

```bash
docker compose up -d
```
---

## Docker Images Availability (Docker Hub)

All COSMeTIC services are **prebuilt and publicly available on Docker Hub**.
Users **do not need to build images locally** unless they are modifying the code.

### Docker Hub Images

The following images are published and maintained:

* **COSMeTIC Prover**

  ```
  anon2026dpeval/cosmeticprover:latest
  ```

* **COSMeTIC Stats Logger**

  ```
  anon2026dpeval/cosmeticstatslogger:latest
  ```

These images are referenced in `docker-compose.yml` and can be pulled directly.

---

### Important: Docker Login Required

Docker Hub enforces **strict pull rate limits** for unauthenticated users.
If you do **not** log in, you may encounter errors such as:

```
toomanyrequests: You have reached your pull rate limit
```

To avoid this, **log in to Docker before pulling images**.

```bash
docker login
```

Once authenticated, image pulls will succeed without rate limiting.

---

### Pull images manually

If you want to pull images explicitly before starting Docker Compose:

```bash
docker pull anon2026dpeval/cosmeticprover:latest
docker pull anon2026dpeval/cosmeticstatslogger:latest
```
