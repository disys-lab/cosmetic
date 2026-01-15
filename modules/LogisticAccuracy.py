import torch
import os
import pickle
import ezkl
import csv,time
from datetime import datetime
from merkletree.MerkleProver import MerkleProver
from aggregators.Adder import Adder
from transformers.Length import Length
from transformers.LogisticFunction import LogisticRegression
from utils.data import RegressionData, create_inclusion_case, create_users

class LogisticAccuracy:
    def __init__(self,proof_root_path="./proofs/"):

        self.SCALING_DOWN = True

        self.use_zkp = int(os.environ.get("ZKP_MODE",1))
        self.gen_full_proof = int(os.environ.get("GEN_FULL_PROOF",1))
        self.setup_mrp = int(os.environ.get("SETUP_MRP",1))
        self.zkp_scale = int(os.environ.get("ZKP_SCALER",10))
        self.setup_ltr = int(os.environ.get("SETUP_LTR",1))
        self.tree_height = int(os.environ.get("TREE_HEIGHT", 256))

        self.id_length = None
        self.id_acc = None

        self.id = os.environ.get("ID",None)
        if self.id is None:
            self.id_length=None
            self.id_acc=None
        else:
            id_arr = self.id.split(",")
            self.id_length = id_arr[0]
            self.id_acc = id_arr[1]
        self.ltr_choice = "logistic_accuracy"

        self.record_shape = 21
        self.salt_shape = 2
        self.transform_salt_shape=2

        self.transform_total_shape = 1 + self.transform_salt_shape
        self.rand_bit=1

        self.proof_root_path = os.path.join(proof_root_path,self.ltr_choice) #f"./proofs/{self.ltr_choice}"
        self.mrp1 = None
        self.mrp2 = None

        self.beta_full =None
        self.raw_data = None
        self.raw_default_value_acc = None
        self.raw_default_value_length = None

        self.printmessage = None

        self.buildAllSMT()

    def process_data(self,data_file_name="./data/data_for_logreg_small.pkl",coefficients_file_name="./data/logreg_glm_fits.pkl",scaling_down=True, n_samples=12,):

        # prepare betas
        with open(coefficients_file_name, "rb") as f:
            out = pickle.load(f)

        print(out)

        beta_full = out["beta_full"]
        beta_full = torch.tensor(beta_full, dtype=torch.float32)


        # prepare data
        lrd = RegressionData(file_path=data_file_name,add_intercept=True,n_features=None,to_tensor=True,max_tries=100000,random_state=110)

        X_test, y_test = lrd.prepare_test_data(n_samples=None)

        # Scaling down
        if scaling_down:
            X_test = X_test[:n_samples]
            y_test = y_test[:n_samples]

        raw_data = create_users(x_values=X_test,y_values=y_test,salt_shape=2,transform_salt_shape=2,rand_bit=1,seed=110)

        raw_default_value_length = torch.zeros_like(raw_data[0]["value"])
        raw_default_value_acc = torch.zeros_like(raw_data[0]["value"])

        print(f"Scaling down to first {n_samples} samples for testing.")
        print(f"X_test shape: {X_test.shape}, y_test shape: {y_test.shape}")
        print(f"Using beta: {beta_full}")
        print("-----")
        return beta_full,raw_data,raw_default_value_acc,raw_default_value_length

    def create_smt_length(self,raw_data,raw_default_value):
        aggregator_length_SMT = Adder()

        # Computing length
        transformer_length = Length(length_transform_salt=self.transform_salt_shape)

        self.mrp1 = MerkleProver(
            prover_name=f"log_acc_length",
            id=self.id_length,
            aggregator=aggregator_length_SMT,
            transformer=transformer_length,
            raw_data=raw_data,
            raw_default_value=raw_default_value,
            length_transform_salt=self.transform_salt_shape,
            setup_mrp=self.use_zkp & self.setup_mrp,
            setup_ltr=self.use_zkp & self.setup_ltr,
            root_path=self.proof_root_path,
            tree_height=self.tree_height,
            zkp_scale=self.zkp_scale
        )

        self.mrp1._build_smt()
        N = self.mrp1.root_value[0, 0].reshape(1, -1)
        print(f"Length={N}")
        return self.mrp1

    def create_smt_acc(self,beta_full,mrp1,raw_data,raw_default_value):
        aggregator_acc_SMT = Adder()

        # Finding accuracy
        transformer_logreg = LogisticRegression(length_transform_salt=self.transform_salt_shape, beta=beta_full,sample_size=mrp1.root_value)

        self.mrp2 = MerkleProver(
            prover_name=f"log_acc",
            id=self.id_acc,
            aggregator=aggregator_acc_SMT,
            transformer=transformer_logreg,
            raw_data=raw_data,
            raw_default_value=raw_default_value,
            length_transform_salt=self.transform_salt_shape,
            setup_mrp=self.use_zkp & self.setup_mrp,
            setup_ltr=self.use_zkp & self.setup_ltr,
            root_path=self.proof_root_path,
            tree_height=self.tree_height,
            zkp_scale=self.zkp_scale
        )

        self.mrp2._build_smt()
        print(f"Accuracy={self.mrp2.root_value[0, 0].item()}")
        return self.mrp2

    def buildAllSMT(self):
        beta_full, raw_data, raw_default_value_acc, raw_default_value_length = self.process_data()

        self.beta_full = beta_full
        self.raw_data = raw_data
        self.raw_default_value_acc = raw_default_value_acc
        self.raw_default_value_length = raw_default_value_length
        self.mrp1 = self.create_smt_length(self.raw_data, self.raw_default_value_length)
        self.mrp2 = self.create_smt_acc(self.beta_full, self.mrp1, self.raw_data, self.raw_default_value_acc)
        self.printmessage = self.mrp1._print_section_header

    def create_inc_exc_test_case(self,mrp,raw_data,mode="inc"):
        test_data_record = create_inclusion_case(raw_data, 2)

        if mode == "exc":
            real_value, real_salt = test_data_record["value"][:1], test_data_record["value"][1:]
            fake_user_value = torch.randn_like(real_value)
            fake_transform_salt = self.rand_bit * torch.randint(high=2 ** 5 - 1, size=(self.salt_shape,))

            test_data_record = {
                "name": 'fake_user',
                "value": torch.cat([fake_user_value, real_salt], dim=0),
                "transform_salt": fake_transform_salt
            }

        _, raw_hash = mrp.transform_individual_data_record(raw_test_record=test_data_record)
        return raw_hash

    def test_inclusion(self,mrp,raw_hash_present,total_transform_salt_shape,nonce1=None):

        transformed_hash =mrp.map_rawhash_transformedhash.get(raw_hash_present,"ff")

        if transformed_hash == "ff":
            print(f"RawHash:{raw_hash_present} not in MRP Full SMT")
            return

        mrp.test_inclusion(transformed_hash)
        if nonce1 is None:
            nonce1 = torch.randn(total_transform_salt_shape).reshape(1, total_transform_salt_shape)
        mrp.path_walk(raw_value_hash=raw_hash_present, nonce=nonce1, use_zkp=self.use_zkp, gen_full_proof=self.gen_full_proof)

    def constructInExTestcases(self,mode="inc"):
        raw_hash_present_length = self.create_inc_exc_test_case(self.mrp1, self.raw_data, mode)
        raw_hash_present_acc = self.create_inc_exc_test_case(self.mrp2, self.raw_data,mode)

        return raw_hash_present_length,raw_hash_present_acc

    def runTestInExForAllSMTs(self,mode="inc"):
        raw_hash_present_length,raw_hash_present_acc = self.constructInExTestcases(mode)
        self.test_inclusion(self.mrp1,raw_hash_present_length,total_transform_salt_shape=self.transform_total_shape)

        self.test_inclusion(self.mrp2,raw_hash_present_acc,total_transform_salt_shape=self.transform_total_shape)

    def saveClass(self):
        cosmet_save_path = f"./proofs/{self.ltr_choice}/cosmetic.pkl"
        with open(cosmet_save_path, "wb") as f:
            pickle.dump(self, f)

    def save(self):
        self.saveClass()

    def _strip_pyrunargs(self,obj):
        """
        Recursively removes any ezkl.PyRunArgs objects from an object tree.
        """
        # Direct match
        if isinstance(obj, ezkl.PyRunArgs):
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

        # Clean mrp1/mrp2
        if "mrp1" in state:
            state["mrp1"] = self._strip_pyrunargs(state["mrp1"])
        if "mrp2" in state:
            state["mrp2"] = self._strip_pyrunargs(state["mrp2"])

        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.mrp1._prepare_proofs()
        self.mrp2._prepare_proofs()

    @staticmethod
    def load(cosmet_save_path):
        if os.path.exists(cosmet_save_path):
            with open(cosmet_save_path, "rb") as f:
                return pickle.load(f)
        else:
            raise FileNotFoundError(f"File not found: {cosmet_save_path}")


    def run(self, TEST_INCLUSION=False,TEST_EXCLUSION=False):

        if TEST_INCLUSION:
            self.printmessage("INCLUSION TEST: Picking raw data value that exists")
            self.runTestInExForAllSMTs()

        if TEST_EXCLUSION:
            self.printmessage("EXCLUSION TEST: Picking raw data value that does not exist")
            self.runTestInExForAllSMTs(mode="exc")

