import torch
import os
import pickle
import ezkl
import time
import csv
from datetime import datetime
from merkletree.MerkleProver import MerkleProver
from aggregators.Adder import Adder

from transformers.Length import Length   # not used here but kept if you want it later
from transformers.LogisticLogLikelihood import LogLogLikelihood
from postaggregators.LRTStatistic import LRTStatistic

from utils.data import RegressionData, create_inclusion_case, create_users


class LogisticLRT:
    def __init__(self, proof_root_path: str = "./proofs/"):

        # ---- global flags / env ----
        self.SCALING_DOWN = True

        self.use_zkp = int(os.environ.get("ZKP_MODE", 1))
        self.gen_full_proof = int(os.environ.get("GEN_FULL_PROOF", 1))
        self.setup_mrp = int(os.environ.get("SETUP_MRP", 1))
        self.setup_ltr = int(os.environ.get("SETUP_LTR", 1))
        self.zkp_scale = int(os.environ.get("ZKP_SCALER", 12))
        self.tree_height = int(os.environ.get("TREE_HEIGHT", 256))

        # IDs for full and reduced MRPs
        self.id_full = None
        self.id_red = None
        self.id = os.environ.get("ID", None)
        if self.id is not None:
            id_arr = self.id.split(",")
            self.id_full = id_arr[0]
            self.id_red = id_arr[1]

        self.ltr_choice = "logistic_lrt"

        # shapes
        self.full_record_shape = 6
        self.reduced_record_shape = 2
        self.salt_shape = 2
        self.transform_salt_shape = 2

        self.full_total_shape = self.salt_shape + self.full_record_shape
        self.reduced_total_shape = self.salt_shape + self.reduced_record_shape
        self.transform_total_shape = 1 + self.transform_salt_shape
        self.rand_bit = 1

        # whether to actually build full SMT or use a fixed ll_full
        self.consider_smt_full = True
        self.setup_lrt = True
        self.prove_lrt = True

        # proof root
        self.proof_root_path = os.path.join(proof_root_path, self.ltr_choice)

        # placeholders
        self.beta_full = None
        self.beta_reduced = None

        self.raw_data_full = None
        self.raw_data_reduced = None

        self.raw_default_value_full = None
        self.raw_default_value_reduced = None

        self.mask_full = None
        self.mask_reduced = None

        self.mrp_full = None
        self.mrp_reduced = None

        self.lrt_stat = None
        self.printmessage = None

        # build everything
        self.buildAllSMT()

        #self.process_data()

    def process_data(
        self,
        data_file_name: str = "./data/data_for_logreg_small.pkl",
        coefficients_file_name: str = "./data/logreg_glm_fits.pkl",
    ):
        # prepare betas
        with open(coefficients_file_name, "rb") as f:
            out = pickle.load(f)

        print(out)

        beta_full = torch.tensor(out["beta_full"], dtype=torch.float32)
        beta_reduced = torch.tensor(out["beta_reduced"], dtype=torch.float32)

        # prepare data
        lrd = RegressionData(
            file_path=data_file_name,
            add_intercept=True,
            n_features=None,
            to_tensor=True,
            max_tries=100000,
            random_state=110,
        )

        X_train_full, y_train = lrd.prepare_train_data(n_samples=None)

        # Scaling down
        if self.SCALING_DOWN:
            n_samples = 12
            n_params = 5

            X_train_full = X_train_full[:n_samples, :n_params]
            y_train = y_train[:n_samples]
            beta_full = beta_full[:n_params]


            X_train_reduced = X_train_full[:, :1]  #intercept-only model
            beta_reduced = beta_reduced[:1]

            print(f"Scaled down to {n_samples} samples and {n_params} parameters.")
            print(f"X_train_full shape: {X_train_full.shape}")
            print(f"X_train_reduced shape: {X_train_reduced.shape}")
            print(f"y_train shape: {y_train.shape}")
            print(f"beta_full shape: {beta_full.shape}")
            print(f"beta_reduced shape: {beta_reduced.shape}")
        else:
            # if not scaling down, reduced model uses only first column of X_full
            X_train_reduced = X_train_full[:, :1]

        # raw_data for both models
        raw_data_full = create_users(
            x_values=X_train_full,
            y_values=y_train,
            salt_shape=self.salt_shape,
            transform_salt_shape=self.transform_salt_shape,
            rand_bit=self.rand_bit,
            seed=110,
        )

        raw_data_reduced = raw_data_full

        raw_default_value_full = torch.zeros_like(raw_data_full[0]["value"])
        raw_default_value_reduced = torch.zeros_like(raw_data_reduced[0]["value"])

        mask_full = torch.ones_like(raw_data_full[0]["value"])[:, :beta_full.shape[0]]
        mask_reduced = torch.zeros_like(raw_data_full[0]["value"])[:,:beta_reduced.shape[0]]
        mask_reduced[0,0] = 1

        return (
            beta_full,
            beta_reduced,
            mask_full,
            mask_reduced,
            raw_data_full,
            raw_data_reduced,
            raw_default_value_full,
            raw_default_value_reduced,
        )

    # ------------------------------------------------------------------
    # SMT constructors
    # ------------------------------------------------------------------
    def create_smt_full(self, beta_full, mask_full, raw_data_full, raw_default_value_full):
        aggregator_full = Adder()
        transformer_ll_full = LogLogLikelihood(
            length_transform_salt=self.transform_salt_shape,
            beta=beta_full,
            mask=mask_full
        )

        mrp_full = MerkleProver(
            prover_name="ll_full",
            id=self.id_full,
            aggregator=aggregator_full,
            transformer=transformer_ll_full,
            raw_data=raw_data_full,
            raw_default_value=raw_default_value_full,
            length_transform_salt=self.transform_salt_shape,
            setup_mrp=self.use_zkp & self.setup_mrp,
            setup_ltr=self.use_zkp & self.setup_ltr,
            root_path=self.proof_root_path,
            tree_height=self.tree_height,
            zkp_scale=self.zkp_scale
        )
        mrp_full._build_smt()
        print("Log-Likelihood Full Model Root Value:", mrp_full.root_value)
        print("Log-Likelihood Full Model Root Hash:", mrp_full.root_hash)
        return mrp_full

    def create_smt_reduced(self, beta_reduced, mask_reduced, raw_data_reduced, raw_default_value_reduced):
        aggregator_reduced = Adder()
        transformer_ll_reduced = LogLogLikelihood(
            length_transform_salt=self.transform_salt_shape,
            beta=beta_reduced,
            mask = mask_reduced
        )

        mrp_reduced = MerkleProver(
            prover_name="ll_reduced",
            id=self.id_red,
            aggregator=aggregator_reduced,
            transformer=transformer_ll_reduced,
            raw_data=raw_data_reduced,
            raw_default_value=raw_default_value_reduced,
            length_transform_salt=self.transform_salt_shape,
            setup_mrp=self.use_zkp & self.setup_mrp,
            setup_ltr=self.use_zkp & self.setup_ltr,
            root_path=self.proof_root_path,
            tree_height=self.tree_height,
            zkp_scale=self.zkp_scale
        )
        mrp_reduced._build_smt()
        print("Log-Likelihood Reduced Model Root Value:", mrp_reduced.root_value)
        print("Log-Likelihood Reduced Model Root Hash:", mrp_reduced.root_hash)
        return mrp_reduced

    def buildAllSMT(self):
        (
            beta_full,
            beta_reduced,
            mask_full,
            mask_reduced,
            raw_data_full,
            raw_data_reduced,
            raw_default_value_full,
            raw_default_value_reduced,
        ) = self.process_data()
        print(mask_full,mask_reduced)
        self.mask_full = mask_full
        self.mask_reduced = mask_reduced
        self.beta_full = beta_full
        self.beta_reduced = beta_reduced
        self.raw_data_full = raw_data_full
        self.raw_data_reduced = raw_data_reduced
        self.raw_default_value_full = raw_default_value_full
        self.raw_default_value_reduced = raw_default_value_reduced

        # full model SMT
        if self.consider_smt_full:
            self.mrp_full = self.create_smt_full(
                self.beta_full,self.mask_full, self.raw_data_full, self.raw_default_value_full
            )
            ll_full = self.mrp_full.root_value
        else:
            ll_full = 1e-1 * torch.ones(1, self.full_total_shape + self.transform_salt_shape)
            ll_full[0][0] = -8.9528e01

        # reduced model SMT
        self.mrp_reduced = self.create_smt_reduced(
            self.beta_reduced, self.mask_reduced, self.raw_data_reduced, self.raw_default_value_reduced
        )
        ll_reduced = self.mrp_reduced.root_value

        # keep printer just like LogisticAccuracy
        self.printmessage = self.mrp_full._print_section_header if self.mrp_full else None
        # LRT statistic post-aggregator
        self.lrt_stat = LRTStatistic(
            outdir_name=f"./proofs/{self.ltr_choice}/abs_gap_zk_api",
            reduced_dim=1 + self.transform_salt_shape,
            full_dim=1 + self.transform_salt_shape,
            zkp_scale=self.zkp_scale,
            setup=self.setup_lrt,
            prove=self.prove_lrt,
        )

        result, ok, failed = self.lrt_stat.forward(ll_full, ll_reduced, run_id=1)
        print("\nSummary:")
        print(f"  Generated proof for run_id: {result['run_id']}")
        print(f"  LRT Statistic: {result['lrt']}")
        print(f"  Verified OK: {ok}")
        if failed:
            print(f"  Failed: {len(failed)}")

    # ------------------------------------------------------------------
    # Inclusion / exclusion helpers – 2 MRPs
    # ------------------------------------------------------------------
    def create_inc_exc_test_case(self, mrp, raw_data, mode="inc"):
        test_data_record = create_inclusion_case(raw_data, 2)

        if mode == "exc":
            real_value, real_salt = test_data_record["value"][:1], test_data_record["value"][1:]
            fake_user_value = torch.randn_like(real_value)
            fake_transform_salt = self.rand_bit * torch.randint(
                high=2 ** 5 - 1,
                size=(self.salt_shape,),
            )

            test_data_record = {
                "name": "fake_user",
                "value": torch.cat([fake_user_value, real_salt], dim=0),
                "transform_salt": fake_transform_salt,
            }

        _, raw_hash = mrp.transform_individual_data_record(raw_test_record=test_data_record)
        return raw_hash

    def test_inclusion(self, mrp, raw_hash_present, total_shape, nonce=None):
        transformed_hash = mrp.map_rawhash_transformedhash.get(raw_hash_present, "ff")

        if transformed_hash == "ff":
            print(f"RawHash:{raw_hash_present} not in MRP Full SMT")
            return

        mrp.test_inclusion(transformed_hash)
        if nonce is None:
            nonce = torch.randn_like(mrp.root_value)
            # nonce = torch.randn(total_shape).reshape(1, total_shape)

        mrp.path_walk(
            raw_value_hash=raw_hash_present,
            nonce=nonce,
            use_zkp=self.use_zkp,
            gen_full_proof=self.gen_full_proof,
        )

    def constructInExTestcases(self, mode="inc"):
        raw_hash_present_full = None
        if self.mrp_full is not None:
            raw_hash_present_full = self.create_inc_exc_test_case(
                self.mrp_full, self.raw_data_full, mode
            )
        raw_hash_present_red = self.create_inc_exc_test_case(
            self.mrp_reduced, self.raw_data_reduced, mode
        )

        return raw_hash_present_full, raw_hash_present_red

    def runTestInExForAllSMTs(self, mode="inc"):
        raw_hash_present_full, raw_hash_present_red = self.constructInExTestcases(mode)

        # full SMT
        if self.mrp_full is not None and raw_hash_present_full is not None:
            self.test_inclusion(
                self.mrp_full,
                raw_hash_present_full,
                total_shape=self.full_total_shape + self.transform_salt_shape,
            )

        # reduced SMT
        self.test_inclusion(
            self.mrp_reduced,
            raw_hash_present_red,
            total_shape=self.reduced_total_shape + self.transform_salt_shape,
        )

    # ------------------------------------------------------------------
    # Save / load – same style as LogisticAccuracy
    # ------------------------------------------------------------------
    def saveClass(self):
        cosmet_save_path = f"./proofs/{self.ltr_choice}/cosmetic.pkl"
        with open(cosmet_save_path, "wb") as f:
            pickle.dump(self, f)

    def save(self):
        self.saveClass()

    def _strip_pyrunargs(self, obj):
        """
        Recursively removes any ezkl.PyRunArgs / PyRunArgs objects from an object tree.
        """

        # Direct match: module-based OR name-based (handles 'builtins.PyRunArgs')
        try:
            if isinstance(obj, ezkl.PyRunArgs):
                return None
        except Exception:
            # in case ezkl.PyRunArgs is not defined in this version
            pass

        # Fallback: match by class name only
        if type(obj).__name__ == "PyRunArgs":
            return None

        # Dict
        if isinstance(obj, dict):
            return {k: self._strip_pyrunargs(v) for k, v in obj.items()}

        # List / tuple
        if isinstance(obj, (list, tuple)):
            cleaned = [self._strip_pyrunargs(v) for v in obj]
            return type(obj)(cleaned)

        # Object with attributes
        if hasattr(obj, "__dict__"):
            for attr in list(obj.__dict__.keys()):
                setattr(obj, attr, self._strip_pyrunargs(getattr(obj, attr)))
            return obj

        # Everything else is fine
        return obj

    def __getstate__(self):
        state = self.__dict__.copy()

        # Clean MRPs
        if "mrp_full" in state and state["mrp_full"] is not None:
            state["mrp_full"] = self._strip_pyrunargs(state["mrp_full"])
        if "mrp_reduced" in state and state["mrp_reduced"] is not None:
            state["mrp_reduced"] = self._strip_pyrunargs(state["mrp_reduced"])

        # Clean LRTStatistic instance (this is where PyRunArgs likely lives)
        if "lrt_stat" in state and state["lrt_stat"] is not None:
            state["lrt_stat"] = self._strip_pyrunargs(state["lrt_stat"])

        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

        self.mrp_full._prepare_proofs()
        self.mrp_reduced._prepare_proofs()

    @staticmethod
    def load(cosmet_save_path: str):
        if os.path.exists(cosmet_save_path):
            with open(cosmet_save_path, "rb") as f:
                return pickle.load(f)
        else:
            raise FileNotFoundError(f"File not found: {cosmet_save_path}")

    # ------------------------------------------------------------------
    # Public entry – mirrors LogisticAccuracy.run
    # ------------------------------------------------------------------
    def run(self, TEST_INCLUSION: bool = False, TEST_EXCLUSION: bool = False):

        if TEST_INCLUSION:
            if self.printmessage:
                self.printmessage("INCLUSION TEST: Picking raw data value that exists")
            self.runTestInExForAllSMTs(mode="inc")

        if TEST_EXCLUSION:
            if self.printmessage:
                self.printmessage("EXCLUSION TEST: Picking raw data value that does not exist")
            self.runTestInExForAllSMTs(mode="exc")
