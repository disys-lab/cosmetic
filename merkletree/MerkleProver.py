import os, time, asyncio, json, ezkl, uuid, datetime
import torch, pickle,json
from .SparseMerkleTree import SparseMerkleTree

class MerkleProver:
    def __init__(self,prover_name="default_mrp",aggregator=None,transformer=None,zkp_scale=10,tree_height=256,raw_default_value=None,raw_data=None,root_path="./proofs/",length_transform_salt=10,setup_mrp=0,setup_ltr=0,id=None,create_timestamp=False):
        self.tree_height = tree_height
        self.name=prover_name
        self.zkp_scale= zkp_scale
        self.ZERO_SEL = torch.tensor([0.0])
        self.ONE_SEL = torch.tensor([1.0])
        self.raw_default_value = raw_default_value
        self.raw_data = raw_data
        self.root = None
        self.root_value = None
        self.root_hash = None
        if id is None:
            setup_ltr=1
            setup_mrp=1
            self.prover_id = str(uuid.uuid1())
            print(f"Creating new prover id:{self.prover_id}")
        else:
            self.prover_id = id
            print(f"Using provided prover id:{self.prover_id}")

        self.mrp_path = os.path.join(root_path, self.name, self.prover_id, "mrp_keys")  # ->mrp stands for location for housing merkle prover zkSNARKS
        self.ltr_path = os.path.join(root_path, self.name, self.prover_id, "ltr_keys")  # ->ltr stands for location housing leaf_transformer zkSNARKS

        os.makedirs(self.mrp_path, exist_ok=True)
        os.makedirs(self.ltr_path, exist_ok=True)

        self.proving_results_folder = self.create_timestamped_folder(create_timestamp=create_timestamp)

        self.mrp_proving_results_folder = os.path.join(root_path, self.name, self.prover_id, self.proving_results_folder,"mrp")
        self.ltr_proving_results_folder = os.path.join(root_path, self.name, self.prover_id, self.proving_results_folder,"ltr")

        os.makedirs(self.mrp_proving_results_folder, exist_ok=True)
        os.makedirs(self.ltr_proving_results_folder, exist_ok=True)

        self._prepare_proofs()


        #aggregator initialization
        self._print_section_header("Aggregator being initialized")
        self.aggregator_numeric_check = aggregator
        self.aggregator_numeric_check.mrp_path = self.mrp_proving_results_folder
        self.aggregator_numeric_check.mrp_settings_path = self.mrp_settings_path
        self.aggregator_numeric_check.mrp_compiled_model_path = self.mrp_compiled_model_path
        self._setup_mrp_proof = self.aggregator_numeric_check.setup_proof
        self.aggregator = self.aggregator_numeric_check
        self._dump_data_for_mrp_proof_gen = self.aggregator_numeric_check.dump_data_for_proof_gen
        self._extract_raw_value_mrp = self.aggregator_numeric_check.extract_raw_value
        self.aggregator_numeric_check._async_srs = self._async_srs
        self.aggregator_numeric_check._async_compile = self._async_compile

        #transformer initialization
        self._print_section_header("Transformer being initialized")
        self.transformer_numeric_check = transformer
        self.transformer = self.transformer_numeric_check
        self.transformer_numeric_check.ltr_path = self.ltr_proving_results_folder
        self.transformer_numeric_check.ltr_settings_path = self.ltr_settings_path
        self.transformer_numeric_check.ltr_compiled_model_path = self.ltr_compiled_model_path
        self._setup_ltr_proof = self.transformer_numeric_check.setup_proof
        self._dump_data_for_ltr_proof_gen = self.transformer_numeric_check.dump_data_for_proof_gen
        self._extract_raw_value_ltr = self.transformer_numeric_check.extract_raw_value
        self.default_transform_salt = torch.zeros(length_transform_salt).reshape(1, length_transform_salt)


        # parameters for transformer class
        self.transformer_numeric_check._async_srs = self._async_srs
        self.transformer_numeric_check._async_compile = self._async_compile
        self.transformed_default_value = self.transformer.forward_dry(raw_default_value,self.default_transform_salt,use_witness_file=False) #self.smt.default_value
        self.transformer_numeric_check.size = self.transformed_default_value.shape
        self.transformed_default_salt = torch.zeros(length_transform_salt).reshape(1, length_transform_salt)
        #prepare and setup the aggregator proof before intializing the SMT
        self.aggregator_numeric_check.size = self.transformed_default_value.shape

        self.setup_proofs(setup_mrp=bool(setup_mrp), setup_ltr=bool(setup_ltr))

        # sparse merkle tree definition
        self._print_section_header("SMT being initialized")
        self.smt = SparseMerkleTree(self.tree_height, self.aggregator_numeric_check,self.transformer_numeric_check,self.raw_default_value,length_transform_salt,zkp_scale=self.zkp_scale,ZERO_SEL=self.ZERO_SEL)

        self.transformed_default_hash = self.smt.default_string

        # transformer forward dry
        self._print_section_header("Setting the Hash Function for Transformer")


        #parameters for aggregator class
        self.aggregator_numeric_check.size = self.transformed_default_value.shape

        self.map_rawhash_transformedhash = {}


        self.gen_full_proof = False

        self.ZERO_SEL_HASH = self.smt.hash_func(self.ZERO_SEL)
        self.ONE_SEL_HASH = self.smt.hash_func(self.ONE_SEL)
        self.tree_only_hashes = None

    def create_timestamped_folder(self,create_timestamp=True):
        """Creates a timestamped folder within the "results" directory."""

        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        result_folder_name = f"proof-results-{timestamp}"

        return result_folder_name

    def _secure_data_acquisition(self):
        transformed_leaves = []
        for x in self.raw_data:
            salt = x["transform_salt"]
            raw_value = x["value"]
            transformed_leaves.append({"raw_value": raw_value, "value": self.transformer.forward_dry(x["value"],salt),"transform_salt":salt})
            x["transform_salt"] = salt

        #map_rawhash_rawvalue: keeps track of raw_hash -> raw_value
        map_rawhash_rawvalue = {}

        # map_rawhash_transformedhash: keeps track of raw_hash -> transformed_hash
        map_rawhash_transformedhash = {}

        #map_rawhash_transformedsalt: keeps track of raw_hash -> transform_salt
        map_rawhash_transformsalt = {}

        #map_rawhash_transformed_value: keeps track of raw_hash -> transformed_value
        map_rawhash_transformedvalue = {}

        for x in transformed_leaves:
            hash_raw_value = self.smt.hash_func(x["raw_value"])
            map_rawhash_rawvalue[hash_raw_value] = x["raw_value"]
            map_rawhash_transformsalt[hash_raw_value] = x["transform_salt"]
            map_rawhash_transformedvalue[hash_raw_value] = x["value"]

        hashed_leaves = []
        for x in transformed_leaves:

            hash_transformed_value = self.smt.hash_func(x["value"],)
            hash_raw_value = self.smt.hash_func(x["raw_value"])

            map_rawhash_transformedhash[hash_raw_value] = hash_transformed_value

            hashed_leaves.append({"hash": hash_transformed_value, "value": x["value"]})

        self.transformed_leaves = transformed_leaves
        self.map_rawhash_rawvalue = map_rawhash_rawvalue
        self.map_rawhash_transformedhash = map_rawhash_transformedhash
        self.map_rawhash_transformsalt = map_rawhash_transformsalt
        self.map_rawhash_transformedvalue = map_rawhash_transformedvalue

        return hashed_leaves

    def transform_individual_data_record(self,raw_test_record=None,record_index=-1):
        transform_default_salt = torch.randn(self.smt.length_transform_salt).reshape(1,self.smt.length_transform_salt)
        if record_index != -1:
            if record_index> len(self.raw_data)-1:
                print("record_index>length of raw data. find a data point within index length")
                return -1,-1
            raw_test_record = self.raw_data[record_index].get("value",self.smt.raw_default_value_with_user_salt).reshape(1,self.smt.raw_length_with_user_salt)
            salt = self.raw_data[record_index].get("transform_salt",transform_default_salt)

        else:
            if raw_test_record is None:
                print("Both raw_test_record=None and record_index=-1. Set one of them to get the correct transformation.")
                return -1,-1
            if not isinstance(raw_test_record,dict):
                print("Data record not of dictionary type. Present record like {\"value\":torch.tensor}")
                return -1,-1
            if "value" not in raw_test_record.keys():
                print("Value not found in dictionary data. Present record like {\"value\":torch.tensor}")
                return -1,-1


            salt = raw_test_record.get("transform_salt", transform_default_salt)
            raw_test_record = raw_test_record["value"].reshape(1,self.smt.raw_length_with_user_salt)

        hash_raw_test_record = self.smt.hash_func(raw_test_record)
        transformed_data_record = self.transformer.forward_dry(raw_test_record,salt)
        hash_transformed_data_record = self.smt.hash_func(transformed_data_record,print_log=True)

        print(f"Mapping Raw:{hash_raw_test_record} => Transformed: {hash_transformed_data_record}")

        return hash_transformed_data_record, hash_raw_test_record

    def _build_smt(self,):
        # 1) acquire data securely and generate hashes of leaves
        hashed_leaves = self._secure_data_acquisition()

        # 2) build the Merkle tree
        self.smt.build_tree(hashed_leaves)

        self.tree_only_hashes = self.smt.tree_only_hashes

        # 3) set root
        self.root = self.smt.tree.get(
            (self.tree_height, 0),
            self.smt.level_defaults[self.tree_height]
        )
        self.root_value = self.root["value"]
        self.root_hash = self.root["hash"]

        # 4) write snapshot (JSON + PKL) into this run’s mrp_proving_results_folder
        snapshot_json = os.path.join(self.mrp_proving_results_folder, "mrp_snapshot.json")
        snapshot_pkl  = os.path.join(self.mrp_proving_results_folder, "mrp_snapshot.pkl")

        # JSON = portable (lists), PKL = fast (tensors)
        self.save_snapshot(snapshot_json, tensors_for_pickle=False)
        self.save_snapshot(snapshot_pkl,  tensors_for_pickle=True)

        print(f"Snapshot saved to: {snapshot_json}")
        print(f"Snapshot saved to: {snapshot_pkl}")


    def test_inclusion(self, transformed_hash,): #this function is publicly exposed

        # if raw_hash not in self.map_rawhash_transformedhash.keys():
        #     return False
        #transformed_hash = self.map_rawhash_transformedhash.get(raw_hash,self.smt.hash_func(self.transformer(self.raw_default_value))) #[raw_hash]
        #print(f"found mapping {raw_hash}:{transformed_hash}")
        print(f"Testing inclusion of {transformed_hash} in the SMT")

        """ #Bear the following in mind:
            #obtain_leaf_index(leaf) is not a secret function
            def obtain_leaf_index(self,leaf):
                leaf_bit_list = self.hex_to_binary_list(leaf)
                leaf_pos = self.bit_list_to_uint(leaf_bit_list)
                return leaf_pos

            #smt.default_string is also not secret
            #tree_only_hashes is publicly shared
        """

        leaf_index = self.smt.obtain_leaf_index(transformed_hash)
        leaf_hash = self.tree_only_hashes.get((0, leaf_index), self.smt.level_defaults[0])["hash"]
        proof_valid,key_present,hash_path, full_proof_hashes, selectors = self.smt.test_inclusion(transformed_hash)
        print(f"Proof Valid: {proof_valid}")
        print(f"Key Present: {key_present}")
        print(f"Hash Path: {hash_path}")
        binary_to_hex_str = self.smt.binary_list_to_hex(self.smt.reverse_binary_list(selectors))
        print(f"Selector Path: {binary_to_hex_str}, Transformed Hash: {transformed_hash}")

        if leaf_hash != self.smt.default_string:
            print(f"leaf hash found: {leaf_hash}")
        else:
            print(f"leaf hash not found, default: {leaf_hash}")

    def _prepare_proofs(self):
        self.mrp_model_path = os.path.join(self.mrp_path, 'network.onnx')
        self.mrp_compiled_model_path = os.path.join(self.mrp_path, 'network.compiled')
        self.mrp_pk_path = os.path.join(self.mrp_path, 'test.pk')
        self.mrp_vk_path = os.path.join(self.mrp_path, 'test.vk')
        self.mrp_settings_path = os.path.join(self.mrp_path, 'settings.json')

        self.ltr_model_path = os.path.join(self.ltr_path, 'network.onnx')
        self.ltr_compiled_model_path = os.path.join(self.ltr_path, 'network.compiled')
        self.ltr_pk_path = os.path.join(self.ltr_path, 'test.pk')
        self.ltr_vk_path = os.path.join(self.ltr_path, 'test.vk')
        self.ltr_settings_path = os.path.join(self.ltr_path, 'settings.json')

        self.py_run_args_mrp = ezkl.PyRunArgs()
        self.py_run_args_mrp.input_visibility = "hashed"
        self.py_run_args_mrp.output_visibility = "hashed"
        self.py_run_args_mrp.param_visibility = "private"  # private by default
        self.py_run_args_mrp.logrows = 20
        self.py_run_args_mrp.decomp_legs = 4   
        self.py_run_args_mrp.decomp_base = 16384  
        self.py_run_args_mrp.input_scale = self.zkp_scale
        self.py_run_args_mrp.param_scale = self.zkp_scale

        self.py_run_args_ltr = ezkl.PyRunArgs()
        self.py_run_args_ltr.input_visibility = "hashed"
        self.py_run_args_ltr.output_visibility = "hashed"
        self.py_run_args_ltr.param_visibility = "private"  
        self.py_run_args_ltr.logrows = 20
        self.py_run_args_ltr.decomp_legs = 4
        self.py_run_args_ltr.decomp_base = 16384  
        self.py_run_args_ltr.rebase_frac_zero_constants = True
        self.py_run_args_ltr.input_scale = self.zkp_scale
        self.py_run_args_ltr.param_scale = self.zkp_scale

    def setup_proofs(self,setup_mrp=False,setup_ltr=False):
        if setup_mrp:
            self._print_section_header("Setup Merkle Route Proofs")
            self._setup_mrp_proof(
                self.aggregator_numeric_check,
                self.transformed_default_value,
                self.mrp_model_path,
                self.mrp_settings_path,
                self.mrp_compiled_model_path,
                self.mrp_vk_path,
                self.mrp_pk_path,
                self.py_run_args_mrp
            )
        if setup_ltr:
            self._print_section_header("Setup Leaf Transform Proofs")
            self._setup_ltr_proof(
                self.transformer_numeric_check,
                self.raw_default_value,
                self.ltr_model_path,
                self.ltr_settings_path,
                self.ltr_compiled_model_path,
                self.ltr_vk_path,
                self.ltr_pk_path,
                self.py_run_args_ltr
            )

    def _print_section_header(self,title, width=80, char="="):
        print(char * width)
        print(f"{title:^{width}}")
        print(char * width)

    async def _async_compile(self,data_path, compiled_model_path, witness_path):
        res = await ezkl.gen_witness(data_path, compiled_model_path, witness_path)
        return res

    async def _async_srs(self,settings_path):
        res = await ezkl.get_srs(settings_path)
        return res


    def _generate_proof(self,data_path, settings_path, compiled_model_path, witness_path, proof_path, pk_path, generate_witness=True):
        print(f"data_path:{data_path}")
        print(f"settings_path:{settings_path}")
        print(f"compiled_model_path:{compiled_model_path}")
        print(f"witness_path:{witness_path}")
        print(f"proof_path:{proof_path}")
        print(f"pk_path:{pk_path}")

        #self._generate_witness(settings_path,data_path,compiled_model_path,witness_path)
        if generate_witness:
            witness_generation_time = time.time()
            # compile witness
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            res = loop.run_until_complete(self._async_srs(settings_path))
            res = loop.run_until_complete(self._async_compile(data_path, compiled_model_path, witness_path))
            loop.close()
            assert os.path.isfile(witness_path)
            witness_generation_time = time.time() - witness_generation_time

        self._print_section_header("MockingFunction")
        result = ezkl.mock(witness_path, compiled_model_path)
        print("Mock result:", result)
        self._print_section_header("ProvingFunction")

        # generate proof
        prove_time = time.time()
        res = ezkl.prove(witness_path, compiled_model_path, pk_path, proof_path, "single", )
        prove_time = time.time() - prove_time

        return res

    def _prove_ltr(self,raw_value_hash,raw_value,transform_salt):
        ltr_data_path = os.path.join(self.ltr_proving_results_folder, f'input_{raw_value_hash}.json')
        ltr_witness_path = os.path.join(self.ltr_proving_results_folder,f'witness_{raw_value_hash}.json')
        ltr_proof_path = os.path.join(self.ltr_proving_results_folder,f'test_{raw_value_hash}.pf')

        if raw_value_hash in self.map_rawhash_transformedvalue.keys():
            transformed_value = self.map_rawhash_transformedvalue[raw_value_hash]
        else:
            transformed_value = self.transformer.forward_dry(raw_value,transform_salt)
        if os.path.exists(ltr_proof_path):
            res = {}
            res["instances"] = [[[""], [""], [""],]]
            with open(ltr_witness_path, 'r') as file:
                output = json.load(file)

            hash_raw_value = output['pretty_elements']['processed_inputs'][0][0]
            res['instances'][0][0] = hash_raw_value

            hash_transform_salt = output['pretty_elements']['processed_inputs'][1][0]
            res['instances'][0][1] = hash_transform_salt

            hash_zk_transformed_value = output['pretty_elements']['processed_outputs'][0][0]
            res['instances'][0][2] = hash_zk_transformed_value


        else:
            generate_witness = False
            if not os.path.exists(ltr_data_path):
                self._dump_data_for_ltr_proof_gen(raw_value,transform_salt,ltr_data_path,)

            if not os.path.exists(ltr_witness_path):
                generate_witness = True

            res = self._generate_proof(ltr_data_path,self.ltr_settings_path,self.ltr_compiled_model_path,ltr_witness_path,ltr_proof_path,self.ltr_pk_path,generate_witness=generate_witness)


        offline_poseidon_digest = self.smt.poseidon_hash(transformed_value)

        print(f"INPUT:  hash(raw_value):                        {res['instances'][0][0]}")
        print(f"INPUT:  hash(transform_salt):                   {res['instances'][0][1]}")
        print(f"INPUT:  hash(zk_transformed_value):             {res['instances'][0][2]}")

        l = int(2 * (self.tree_height) / 8)
        raw_value_hash = res['instances'][0][0][:l]
        transformed_value_hash = res['instances'][0][2][:l]
        return transformed_value_hash,transformed_value,ltr_proof_path,raw_value_hash

    def _prove_mrp(self,index,left_val,right_val,sel,nonce,proof_tag=""):
        mrp_data_path = os.path.join(self.mrp_proving_results_folder, f'input_{index}.json')
        mrp_witness_path = os.path.join(self.mrp_proving_results_folder,f'witness_{index}.json')
        if proof_tag != "":
            mrp_proof_path = os.path.join(self.mrp_proving_results_folder,f'test_{proof_tag}_{index}.pf')
        else:
            mrp_proof_path = os.path.join(self.mrp_proving_results_folder, f'test_{index}.pf')
        if os.path.exists(mrp_proof_path):
            res = {}
            res["instances"] = [[[""], [""], [""], [""], [""]]]
            with open(mrp_witness_path, 'r') as file:
                output = json.load(file)
            hash_left_val = output['pretty_elements']['processed_inputs'][0][0]
            res['instances'][0][0] = hash_left_val

            hash_right_val = output['pretty_elements']['processed_inputs'][1][0]
            res['instances'][0][1] = hash_right_val

            hash_sel = output['pretty_elements']['processed_inputs'][2][0]
            res['instances'][0][2] = hash_sel

            hash_nonce = output['pretty_elements']['processed_inputs'][3][0]
            res['instances'][0][3] = hash_nonce

            hash_parent = output['pretty_elements']['processed_outputs'][0][0]
            res['instances'][0][4] = hash_parent

        else:
            generate_witness = False
            if not os.path.exists(mrp_data_path):
                self._dump_data_for_mrp_proof_gen(left_val, right_val, sel, nonce, mrp_data_path, )

            if not os.path.exists(mrp_witness_path):
                generate_witness = True
            res = self._generate_proof(mrp_data_path, self.mrp_settings_path, self.mrp_compiled_model_path,mrp_witness_path, mrp_proof_path, self.mrp_pk_path, generate_witness=generate_witness)

        add_check,diff,threshold,parent_value = self._extract_raw_value_mrp(mrp_witness_path)

        print(f"INPUT:          hash(left_val):                        {res['instances'][0][0]}")
        print(f"INPUT:          hash(right_val):                       {res['instances'][0][1]}")
        print(f"INPUT:          hash(sel):                             {res['instances'][0][2]}")
        print(f"INPUT:          hash(nonce):                           {res['instances'][0][3]}")
        print(f"OUTPUT:         hash(parent_val):                      {res['instances'][0][4]}")
        print(f"WITNESS-OUTPUT: parent_val:                            {parent_value}")
        l = int(2 * (self.tree_height) / 8)

        sibling_hash = res['instances'][0][1 - sel][:l]
        sel_comp_hash = res['instances'][0][2][:l]
        parent_hash = res['instances'][0][4][:l]

        return parent_hash,mrp_proof_path, sibling_hash, sel_comp_hash, parent_value

    def path_walk(self, data_record=None, raw_value_hash=None, nonce=None, use_zkp=True, gen_full_proof=False, ):
        self.gen_full_proof = gen_full_proof

        if raw_value_hash is None and data_record is None:
            print("Both data_record and raw_value_hash are none. Set at least one of them to proceed")
            exit(-1)

        if data_record is not None:
            raw_value = data_record["value"]
            transform_salt = data_record["transform_salt"]
            raw_value_hash = self.smt.hash_func(raw_value)
            transformed_value = self.transformer_numeric_check.forward_dry(raw_value, transform_salt)
            transformed_hash = self.smt.hash_func(transformed_value)
            print(f"Checking for {raw_value_hash}:{transformed_hash}")

        else:
            raw_value = self.map_rawhash_rawvalue.get(raw_value_hash, self.raw_default_value)
            transform_salt = self.map_rawhash_transformsalt.get(raw_value_hash, self.transformed_default_salt)
            transformed_hash = self.map_rawhash_transformedhash.get(raw_value_hash, self.transformed_default_hash)

        if use_zkp:
            self._prove_ltr(raw_value_hash, raw_value, transform_salt)

        hashes_path, full_proof_values, full_proof_hashes = self.smt.get_inclusion_proof(transformed_hash, )

        selectors = full_proof_values["selectors"]
        siblings_values = full_proof_values["siblings_value"]
        summand = full_proof_values["leaf_value"]
        parent_value = summand

        siblings_hashes = full_proof_hashes["siblings_hash"]

        leaf_hash = full_proof_hashes["leaf_hash"]
        leaf_idx = self.smt.obtain_leaf_index(leaf_hash)

        proven_hash_path = []

        proof_list = []
        sel_hash_list = []
        node_hash = '00'
        index = 0
        skip_proof_step = False

        cur_idx = leaf_idx

        nonce_hash = self.smt.hash_func(nonce)

        for sibling, sel in zip(siblings_values, selectors):
            sibling_value = siblings_values[index]
            sel_tensor = torch.tensor([sel])
            proof_tag = f"{raw_value_hash}_{nonce_hash}_{index}"

            if sel == 1:
                left_hash = self.smt.hash_func(sibling_value)
                right_hash = self.smt.hash_func(summand)
                if self.tree_height == 256:
                    left_hash  = left_hash[:32]
                    right_hash = right_hash[:32]
                hash_index = f"{left_hash}-{right_hash}"
                if use_zkp and (not skip_proof_step or self.gen_full_proof):
                    node_hash, mrp_proof_path, sibling_hash, sel_comp_hash, parent_value = self._prove_mrp(hash_index,sibling_value,summand,sel_tensor,nonce,proof_tag=proof_tag)
                else:
                    node_hash, parent_value = self.smt.hash_node(left_value=sibling_value, right_value=summand,sel=sel_tensor, nonce=nonce)
                    mrp_proof_path = None

            else:
                left_hash = self.smt.hash_func(summand)
                right_hash = self.smt.hash_func(sibling_value)
                if self.tree_height == 256:
                    left_hash  = left_hash[:32]
                    right_hash = right_hash[:32]
                hash_index = f"{left_hash}-{right_hash}"
                if use_zkp and (not skip_proof_step or self.gen_full_proof):
                    node_hash, mrp_proof_path, sibling_hash, sel_comp_hash, parent_value = self._prove_mrp(hash_index,summand,sibling_value,sel_tensor,nonce,proof_tag=proof_tag)
                else:
                    node_hash, parent_value = self.smt.hash_node(left_value=summand, right_value=sibling_value,sel=sel_tensor, nonce=nonce)
                    mrp_proof_path = None

            sibling_hash = siblings_hashes[index]["hash"]
            proven_hash_path.append(sibling_hash)
            proof_list.append(mrp_proof_path)
            sel_comp_hash = self.ONE_SEL_HASH if selectors[index] else self.ZERO_SEL_HASH
            sel_hash_list.append(sel_comp_hash)

            summand = parent_value
            if hashes_path[index] == hashes_path[index + 1] and not self.gen_full_proof:
                skip_proof_step = True
            else:
                skip_proof_step = False
            self._print_section_header(
                f"SKIPPING{index + 1}:{skip_proof_step}\ncurrent_index:{index},hash[{index}]={hashes_path[index]}, hash[{index + 1}] = {hashes_path[index + 1]}, sibling_hash:{sibling_hash},node_hash:{node_hash},sel_hash:{sel_comp_hash}")

            index = index + 1
            cur_idx = cur_idx // 2

        proven_hash_path.append(node_hash)
        print(f"final summand:{summand}")
        print(hashes_path, proven_hash_path)
        print(sel_hash_list)
        zk_sel_list = [1 if sel_hash == self.ONE_SEL_HASH else 0 if sel_hash == self.ZERO_SEL_HASH else -1 for sel_hash
                       in sel_hash_list]
        print(zk_sel_list)
        print(selectors)
        binary_to_hex_str = self.smt.binary_list_to_hex(self.smt.reverse_binary_list(selectors))
        print(f"Selector Path: {binary_to_hex_str}, Transformed Hash: {transformed_hash}")

    def path_walk_old(self,data_record=None,raw_value_hash=None,nonce=None,use_zkp=True,gen_full_proof=False,):
        self.gen_full_proof = gen_full_proof

        if raw_value_hash is None and data_record is None:
            print("Both data_record and raw_value_hash are none. Set at least one of them to proceed")
            exit(-1)

        if data_record is not None:
            raw_value = data_record["value"]
            transform_salt = data_record["transform_salt"]
            raw_value_hash = self.smt.hash_func(raw_value)
            transformed_value = self.transformer_numeric_check.forward_dry(raw_value,transform_salt)
            transformed_hash = self.smt.hash_func(transformed_value)
            print(f"Checking for {raw_value_hash}:{transformed_hash}")

        else:
            raw_value = self.map_rawhash_rawvalue.get(raw_value_hash, self.raw_default_value)
            transform_salt = self.map_rawhash_transformsalt.get(raw_value_hash, self.transformed_default_salt)
            transformed_hash = self.map_rawhash_transformedhash.get(raw_value_hash, self.transformed_default_hash)

        if use_zkp:
            self._prove_ltr(raw_value_hash,raw_value,transform_salt)

        hashes_path,full_proof_values,full_proof_hashes = self.smt.get_inclusion_proof(transformed_hash, )

        selectors = full_proof_values["selectors"]
        siblings_values = full_proof_values["siblings_value"]
        summand = full_proof_values["leaf_value"]
        parent_value = summand

        siblings_hashes = full_proof_hashes["siblings_hash"]

        leaf_hash = full_proof_hashes["leaf_hash"]
        leaf_idx = self.smt.obtain_leaf_index(leaf_hash)

        proven_hash_path = []

        proof_list = []
        sel_hash_list = []
        node_hash = '00'
        index = 0
        skip_proof_step = False

        cur_idx = leaf_idx

        for sibling, sel in zip(siblings_values, selectors):
            sibling_value = siblings_values[index]
            sel_tensor = torch.tensor([sel])
            if not skip_proof_step or self.gen_full_proof:
                prev_summand = summand
                self._print_section_header(f"Generating MRP for {index}")
                if sel == 1:
                    if use_zkp:
                        node_hash, mrp_proof_path,sibling_hash,sel_comp_hash, parent_value = self._prove_mrp(index,sibling_value,summand,sel_tensor,nonce,)
                    else:
                        node_hash,parent_value = self.smt.hash_node(left_value=sibling_value,right_value=summand,sel=sel_tensor,nonce=nonce)
                        mrp_proof_path = None
                        sibling_hash = siblings_hashes[index]["hash"]
                        sel_comp_hash = self.ONE_SEL_HASH
                else:
                    if use_zkp:
                        node_hash, mrp_proof_path,sibling_hash,sel_comp_hash, parent_value = self._prove_mrp(index,summand,sibling_value,sel_tensor,nonce,)
                    else:
                        node_hash,parent_value = self.smt.hash_node(left_value=sibling_value,right_value=summand,sel=sel_tensor,nonce=nonce)
                        mrp_proof_path = None
                        sibling_hash = siblings_hashes[index]["hash"]
                        sel_comp_hash = self.ONE_SEL_HASH if sel==1 else self.ZERO_SEL_HASH

                proven_hash_path.append(sibling_hash)
                proof_list.append(mrp_proof_path)
                sel_hash_list.append(sel_comp_hash)
                print(f"current_summand:{parent_value},prev_summand:{prev_summand},sibling_value:{sibling_value}")
            else:
                if sel==1:
                    node_hash, parent_value = self.smt.hash_node(left_value=sibling_value, right_value=summand, sel=sel_tensor, nonce=nonce)
                else:
                    node_hash, parent_value = self.smt.hash_node(left_value=summand, right_value=sibling_value, sel=sel_tensor, nonce=nonce)
                sibling_hash = siblings_hashes[index]["hash"]
                proven_hash_path.append(sibling_hash)
                proof_list.append(None)
                sel_comp_hash = self.ONE_SEL_HASH if selectors[index] else self.ZERO_SEL_HASH
                sel_hash_list.append(sel_comp_hash)

            summand = parent_value
            if hashes_path[index] == hashes_path[index+1] and not self.gen_full_proof:
                skip_proof_step = True
            else:
                skip_proof_step = False
            self._print_section_header(f"SKIPPING{index+1}:{skip_proof_step}\ncurrent_index:{index},hash[{index}]={hashes_path[index]}, hash[{index+1}] = {hashes_path[index+1]}, sibling_hash:{sibling_hash},node_hash:{node_hash},sel_hash:{sel_comp_hash}")

            index = index + 1
            cur_idx = cur_idx //2

        proven_hash_path.append(node_hash)
        print(f"final summand:{summand}")
        print(hashes_path,proven_hash_path)
        print(sel_hash_list)
        zk_sel_list = [1 if sel_hash == self.ONE_SEL_HASH else 0 if sel_hash == self.ZERO_SEL_HASH else -1 for sel_hash in sel_hash_list]
        print(zk_sel_list)
        print(selectors)
        binary_to_hex_str = self.smt.binary_list_to_hex(self.smt.reverse_binary_list(selectors))
        print(f"Selector Path: {binary_to_hex_str}, Transformed Hash: {transformed_hash}")

    def _build_paths_index(self, as_tensors: bool = False):
        """
        Build a map of inclusion paths for each non-default leaf.

        If as_tensors=True, keep torch.Tensors in the snapshot (good for Pickle).
        If as_tensors=False, convert to Python lists (good for JSON).
        """
        paths = {}
        for (lvl, pos), node in self.tree_only_hashes.items():
            if lvl != 0:
                continue
            leaf_hash = node["hash"]
            if leaf_hash == self.smt.default_string:
                continue

            hashes_path, full_vals, full_hashes = self.smt.get_inclusion_proof(leaf_hash)
            sib_hashes = [x["hash"] for x in full_hashes["siblings_hash"]]

            if as_tensors:
                sib_values = [v.detach().clone().cpu() for v in full_vals["siblings_value"]]
                leaf_value = full_vals["leaf_value"].detach().clone().cpu()
            else:
                sib_values = [v.detach().cpu().tolist() for v in full_vals["siblings_value"]]
                leaf_value = full_vals["leaf_value"].detach().cpu().tolist()

            selectors = full_vals["selectors"]

            paths[leaf_hash] = {
                "siblings_hash": sib_hashes,
                "siblings_value": sib_values,
                "selectors": selectors,
                "leaf_value": leaf_value,
            }
        return paths

    def to_snapshot(self, tensors: bool = False):
        """
        Materialize a Python dict representing this MerkleProver state.

        tensors=False -> JSON-friendly (lists)
        tensors=True  -> tensor-friendly (for Pickle)
        """
        transformer_type = type(self.transformer_numeric_check).__name__
        transformer_params = {}
        if transformer_type == "Affine":
            transformer_params = {
                "slope": getattr(self.transformer_numeric_check, "slope", None).tolist()
                        if hasattr(self.transformer_numeric_check, "slope") else None,
                "intercept": getattr(self.transformer_numeric_check, "intercept", None).tolist()
                            if hasattr(self.transformer_numeric_check, "intercept") else None,
            }

        paths = self._build_paths_index(as_tensors=tensors)

        return {
            "version": "mrp-snap-1",
            "prover_id": self.prover_id,
            "tree": {
                "height": self.tree_height,
                "root_hash": self.root_hash,
                "default_nodes": [
                    self.smt.level_defaults[i]["hash"]
                    for i in range(self.tree_height + 1)
                ],
                "paths": paths,
            },
            "shapes": {
                "record_shape": None,
                "salt_shape": None,
                "transform_salt_shape": getattr(
                    self.transformer_numeric_check, "length_transform_salt", None
                ),
                "zkp_scale": self.zkp_scale,
            },
            "config": {
                "aggregator": type(self.aggregator_numeric_check).__name__,
                "transformer": {
                    "type": transformer_type,
                    "params": transformer_params,
                },
            },
            "maps": {
                "raw_to_tf_hash": getattr(self, "map_rawhash_transformedhash", {}),
            },
        }

    def save_snapshot(self, path: str, tensors_for_pickle: bool = True):
        """
        Save the snapshot.
        - If path ends with '.pkl' or '.pickle' -> Pickle (keeps tensors if tensors_for_pickle=True)
        - Else -> JSON (converts tensors to lists)
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if path.endswith((".pkl", ".pickle")):
            snap = self.to_snapshot(tensors=tensors_for_pickle)
            with open(path, "wb") as f:
                pickle.dump(snap, f, protocol=pickle.HIGHEST_PROTOCOL)
        else:
            # strip accidental .gz if someone passes it
            if path.endswith(".gz"):
                path = path[:-3]
            snap = self.to_snapshot(tensors=False)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snap, f, indent=2)

    def prove_membership_from_snapshot(
        self,
        snapshot_path: str,
        raw_value_tensor,           # torch tensor shape (1, total_shape)
        transform_salt_tensor,      # torch tensor shape (1, transform_salt_shape)
        nonce_tensor,               # torch tensor shape (1, total_shape + transform_salt_shape)
        use_zkp: bool = True,
    ):
        """
        Prove membership for a *single* user record purely from snapshot + user raw input.
        Assumes snapshot contains siblings_value + selectors for each concrete leaf.

        Returns:
            {
               "ltr_proof": "<path>",
               "mrp_proofs": ["<path>", ...],
               "leaf_hash": "<hex>",
               "root_hash": "<hex>"
            }
        """

        # 1) Load snapshot
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snap = json.load(f)

        root_hash_snap = snap["tree"]["root_hash"]
        paths_map = snap["tree"]["paths"]
        transformer_type = snap["config"]["transformer"]["type"]

        # (Optional) sanity: check that our live transformer matches the snapshot
        live_t = type(self.transformer_numeric_check).__name__
        assert live_t == transformer_type, f"Transformer mismatch: live={live_t}, snap={transformer_type}"

        # 2) Compute transformed value for user input (LTR)
        transformed_value = self.transformer_numeric_check.forward_dry(
            raw_value_tensor, transform_salt_tensor
        )
        transformed_hash = self.smt.hash_func(transformed_value)

        if transformed_hash not in paths_map:
            raise ValueError(
                "Transformed hash not found in snapshot paths; this leaf was not part of that tree."
            )

        path_info = paths_map[transformed_hash]
        selectors = path_info["selectors"]                 # bottom->top
        siblings_value_lists = path_info["siblings_value"] # list of lists

        # Convert siblings back to tensors
        siblings_values = [
            torch.tensor(v, dtype=transformed_value.dtype)
            for v in siblings_value_lists
        ]

        # 3) Prove LTR (raw -> transformed) with your caching _prove_ltr
        l = int(2 * (self.tree_height) / 8)
        raw_h_full = self.smt.hash_func(raw_value_tensor)
        raw_h_key = raw_h_full[:l]

        ltr_tfhash, tf_value, ltr_pf_path, raw_hash_short = self._prove_ltr(
            raw_value_hash=raw_h_key,
            raw_value=raw_value_tensor,
            transform_salt=transform_salt_tensor,
        )

        # 4) Prove MRP path bottom->top, reusing your _prove_mrp style
        mrp_proofs = []
        summand = transformed_value

        for i, sel in enumerate(selectors):
            sib_val = siblings_values[i]
            sel_tensor = torch.tensor([sel], dtype=torch.float32)

            # follow the same logic as in your new path_walk()
            if sel == 1:   # leaf is right child
                left_hash = self.smt.hash_func(sib_val)
                right_hash = self.smt.hash_func(summand)
                if self.tree_height == 256:
                    left_hash  = left_hash[:32]
                    right_hash = right_hash[:32]
                hash_index = f"{left_hash}-{right_hash}"

                if use_zkp:
                    parent_hash, mrp_proof_path, _, _, parent_value = self._prove_mrp(
                        hash_index, sib_val, summand, sel_tensor, nonce_tensor,
                        proof_tag=f"{raw_hash_short}_{i}",
                    )
                else:
                    parent_hash, parent_value = self.smt.hash_node(
                        left_value=sib_val,
                        right_value=summand,
                        sel=sel_tensor,
                        nonce=nonce_tensor,
                    )
                    mrp_proof_path = None
            else:          # leaf is left child
                left_hash = self.smt.hash_func(summand)
                right_hash = self.smt.hash_func(sib_val)
                if self.tree_height == 256:
                    left_hash  = left_hash[:32]
                    right_hash = right_hash[:32]
                hash_index = f"{left_hash}-{right_hash}"

                if use_zkp:
                    parent_hash, mrp_proof_path, _, _, parent_value = self._prove_mrp(
                        hash_index, summand, sib_val, sel_tensor, nonce_tensor,
                        proof_tag=f"{raw_hash_short}_{i}",
                    )
                else:
                    parent_hash, parent_value = self.smt.hash_node(
                        left_value=summand,
                        right_value=sib_val,
                        sel=sel_tensor,
                        nonce=nonce_tensor,
                    )
                    mrp_proof_path = None

            mrp_proofs.append(mrp_proof_path)
            summand = parent_value

        return {
            "ltr_proof": ltr_pf_path,
            "mrp_proofs": mrp_proofs,
            "leaf_hash": transformed_hash,
            "root_hash": root_hash_snap,
        }
