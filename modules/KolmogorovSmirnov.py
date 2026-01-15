import torch
import os
import pickle
import ezkl
import time
import csv
from datetime import datetime
from merkletree.MerkleProver import MerkleProver
from aggregators.Adder import Adder
from transformers.BinCount import BinCount
from postaggregators.MaxGap import MaxAbsGap
from utils.data import setup_ks_HD_example, create_inclusion_case


class KolmogorovSmirnov:
    def __init__(self, proof_root_path: str = "./proofs/"):

        # ---- global flags / env ----
        self.use_zkp = int(os.environ.get("ZKP_MODE", 1))
        self.gen_full_proof = int(os.environ.get("GEN_FULL_PROOF", 1))
        self.setup_mrp = int(os.environ.get("SETUP_MRP", 1))
        self.setup_ltr = int(os.environ.get("SETUP_LTR", 1))
        self.zkp_scale = int(os.environ.get("ZKP_SCALER", 10))
        self.tree_height = int(os.environ.get("TREE_HEIGHT", 256))
        
        # IDs for the two MRPs (sample 1 and sample 2)
        self.id_s1 = None
        self.id_s2 = None

        self.id = os.environ.get("ID", None)
        if self.id is not None:
            id_arr = self.id.split(",")
            self.id_s1 = id_arr[0]
            self.id_s2 = id_arr[1]

        # label / folder
        self.ltr_choice = "ks"

        # shapes
        self.record_shape = 1
        self.salt_shape = 2
        self.transform_salt_shape = 2
        self.transform_total_shape = 1 + self.transform_salt_shape
        self.rand_bit = 1

        # proof root
        self.proof_root_path = os.path.join(proof_root_path, self.ltr_choice)

        # placeholders
        self.mrp1 = None   # sample 1 SMT
        self.mrp2 = None   # sample 2 SMT

        self.raw_data_s1 = None
        self.raw_data_s2 = None
        self.edges = None
        self.n_bins = None
        self.raw_default_value_s1 = None
        self.raw_default_value_s2 = None
        self.printmessage = None  # will be bound to mrp1._print_section_header
        self.buildAllSMT()

    def process_data(
        self,
        data_path: str = "./data/data_for_ks_test.pkl",
        n_samples: int = 12,
        rand_seed: int = 110,
    ):
        ks_data = setup_ks_HD_example(
            data_path=data_path,
            n_samples=n_samples,
            salt_shape=self.salt_shape,
            transform_salt_shape=self.transform_salt_shape,
            rand_bit=self.rand_bit,
        )

        raw_data_s1 = ks_data[0]
        raw_data_s2 = ks_data[1]
        edges = ks_data[2]
        n_bins = len(edges) - 1

        raw_default_value_s1 = (
            torch.zeros_like(raw_data_s1[0]["value"]) if len(raw_data_s1) > 0 else None
        )
        raw_default_value_s2 = (
            torch.zeros_like(raw_data_s2[0]["value"]) if len(raw_data_s2) > 0 else None
        )

        return (
            raw_data_s1,
            raw_data_s2,
            edges,
            n_bins,
            raw_default_value_s1,
            raw_default_value_s2,
        )

    def create_smt_sample(self, raw_data, raw_default_value, name_suffix, id_val, transformer):
        aggregator = Adder()

        mrp = MerkleProver(
            prover_name=f"simple_sum_bincount_{name_suffix}",
            id=id_val,
            aggregator=aggregator,
            transformer=transformer,
            raw_data=raw_data,
            raw_default_value=raw_default_value,
            length_transform_salt=self.transform_salt_shape,
            setup_mrp=self.use_zkp & self.setup_mrp,
            setup_ltr=self.use_zkp & self.setup_ltr,
            root_path=self.proof_root_path,
            tree_height=self.tree_height,
            zkp_scale=self.zkp_scale
        )
        mrp._build_smt()
        return mrp

    def buildAllSMT(self):
        t_start = time.time()

        (
            self.raw_data_s1,
            self.raw_data_s2,
            self.edges,
            self.n_bins,
            self.raw_default_value_s1,
            self.raw_default_value_s2,
        ) = self.process_data()

        transformer_bincount = BinCount(
            length_transform_salt=self.transform_salt_shape,
            edges=self.edges,
        )

        # Sample 1 SMT
        self.mrp1 = self.create_smt_sample(
            self.raw_data_s1,
            self.raw_default_value_s1,
            "s1",
            self.id_s1,
            transformer_bincount,
        )
        print(f"Sample 1 root_value={self.mrp1.root_value}")
        print(f"Sample 1 Root hash (Length SMT) = {self.mrp1.root_hash}")

        # Sample 2 SMT
        self.mrp2 = self.create_smt_sample(
            self.raw_data_s2,
            self.raw_default_value_s2,
            "s2",
            self.id_s2,
            transformer_bincount,
        )
        print(f"Sample 2 root_value={self.mrp2.root_value}")
        print(f"Sample 2 Root hash (Length SMT) = {self.mrp2.root_hash}")

        # Bind printer (like LogisticAccuracy)
        self.printmessage = self.mrp1._print_section_header

        # Max gap postaggregator
        smt1_root_val = self.mrp1.root_value
        smt2_root_val = self.mrp2.root_value
        max_gap = MaxAbsGap(
            outdir_name=f"./proofs/{self.ltr_choice}/abs_gap_zk_api",
            zkp_scale=self.zkp_scale,
        )
        result, ok, failed = max_gap.forward(smt1_root_val, smt2_root_val, run_id=1)
        print("  MRP1 Root Hash:", self.mrp1.root_hash)
        print("  MRP2 Root Hash:", self.mrp2.root_hash)
        print("\nSummary:")
        print(f"  Generated proof for run_id: {result['run_id']}")
        print(f"  Maximum gap: {result['supremum']}")
        print(f"  Verified OK: {ok}")
        if failed:
            print(f"  Failed: {len(failed)}")

    def create_inc_exc_test_case(self, mrp, raw_data, mode: str = "inc"):
        """
        Build one inclusion or exclusion test record for a given MRP + dataset.
        """
        test_data_record = create_inclusion_case(raw_data, 2)

        if mode == "exc":
            real_value, real_salt = test_data_record["value"][:1], test_data_record["value"][1:]
            fake_user_value = torch.randn_like(real_value)
            fake_transform_salt = self.rand_bit * torch.randint(
                high=2 ** 5 - 1, size=(self.salt_shape,)
            )

            test_data_record = {
                "name": "fake_user",
                "value": torch.cat([fake_user_value, real_salt], dim=0),
                "transform_salt": fake_transform_salt,
            }

        _, raw_hash = mrp.transform_individual_data_record(raw_test_record=test_data_record)
        return raw_hash

    def test_inclusion(self, mrp, raw_hash_present, total_transform_salt_shape,nonce=None):
        """
        Run inclusion proof for a single MRP using a raw hash.
        """
        transformed_hash = mrp.map_rawhash_transformedhash.get(raw_hash_present, "ff")

        if transformed_hash == "ff":
            print(f"RawHash:{raw_hash_present} not in MRP Full SMT")
            return

        mrp.test_inclusion(transformed_hash)
        #nonce = torch.randn(total_transform_salt_shape).reshape(1, total_transform_salt_shape)

        if nonce is None:
            nonce = torch.randn_like(mrp.root_value)
            # nonce = torch.randn(total_transform_salt_shape).reshape(1, total_transform_salt_shape)

        mrp.path_walk(
            raw_value_hash=raw_hash_present,
            nonce=nonce,
            use_zkp=self.use_zkp,
            gen_full_proof=self.gen_full_proof,
        )

    def constructInExTestcases(self, mode: str = "inc"):
        """
        Construct inclusion/exclusion test cases for BOTH MRPs.
        """
        raw_hash_present_s1 = self.create_inc_exc_test_case(self.mrp1, self.raw_data_s1, mode)
        raw_hash_present_s2 = self.create_inc_exc_test_case(self.mrp2, self.raw_data_s2, mode)
        return raw_hash_present_s1, raw_hash_present_s2

    def runTestInExForAllSMTs(self, mode: str = "inc"):
        """
        Run tests on both SMTs (two MRPs), for either inclusion or exclusion.
        """
        raw_hash_present_s1, raw_hash_present_s2 = self.constructInExTestcases(mode)
        self.test_inclusion(
            self.mrp1,
            raw_hash_present_s1,
            total_transform_salt_shape=self.transform_total_shape,
        )
        self.test_inclusion(
            self.mrp2,
            raw_hash_present_s2,
            total_transform_salt_shape=self.transform_total_shape,
        )

    def saveClass(self):
        cosmet_save_path = f"./proofs/{self.ltr_choice}/cosmetic.pkl"
        with open(cosmet_save_path, "wb") as f:
            pickle.dump(self, f)

    def save(self):
        self.saveClass()

    def _strip_pyrunargs(self, obj):
        """
        Recursively removes any ezkl.PyRunArgs objects from an object tree.
        """
        if isinstance(obj, ezkl.PyRunArgs):
            return None

        if isinstance(obj, dict):
            return {k: self._strip_pyrunargs(v) for k, v in obj.items()}

        if isinstance(obj, (list, tuple)):
            cleaned = [self._strip_pyrunargs(v) for v in obj]
            return type(obj)(cleaned)

        if hasattr(obj, "__dict__"):
            for attr in list(obj.__dict__.keys()):
                setattr(obj, attr, self._strip_pyrunargs(getattr(obj, attr)))
            return obj

        return obj

    def __getstate__(self):
        state = self.__dict__.copy()
        if "mrp1" in state:
            state["mrp1"] = self._strip_pyrunargs(state["mrp1"])
        if "mrp2" in state:
            state["mrp2"] = self._strip_pyrunargs(state["mrp2"])
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        # re-attach ezkl run args inside MRPs
        self.mrp1._prepare_proofs()
        self.mrp2._prepare_proofs()

    @staticmethod
    def load(cosmet_save_path: str):
        if os.path.exists(cosmet_save_path):
            with open(cosmet_save_path, "rb") as f:
                return pickle.load(f)
        else:
            raise FileNotFoundError(f"File not found: {cosmet_save_path}")

    def run(self, TEST_INCLUSION: bool = False, TEST_EXCLUSION: bool = False):

        if TEST_INCLUSION:
            self.printmessage("INCLUSION TEST: Picking raw data value that exists")
            self.runTestInExForAllSMTs(mode="inc")

        if TEST_EXCLUSION:
            self.printmessage("EXCLUSION TEST: Picking raw data value that does not exist")
            self.runTestInExForAllSMTs(mode="exc")

