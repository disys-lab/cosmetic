import hashlib, torch, ezkl

class SparseMerkleTree:
    def __init__(self,tree_height=256,aggregator_numeric_check=None,transformer_numeric_check=None,default_value=None,length_transform_salt=10,zkp_scale=8,ZERO_SEL=None,rf=1000):
        self.tree_height = tree_height
        self.zkp_scale=zkp_scale
        self.ZERO_SEL=ZERO_SEL
        self.rf = rf
        self.length_transform_salt = length_transform_salt
        self.tree = {}
        self.tree_only_hashes = {}
        self.leaves = None
        self.total_leaves = 0

        self.aggregator = aggregator_numeric_check

        #self.transformer_numeric_check = transformer_numeric_check
        self.transformer = transformer_numeric_check


        self.hash_func = self.poseidon_hash
        self.transformer.hash_func = self.hash_func

        self.current_full_proof_values = {}

        self.raw_default_value_with_user_salt = default_value
        self.raw_length_with_user_salt = default_value.shape[1]

        # self.transformer_numeric_check.length_transform_salt = length_transform_salt
        self.default_transform_salt = torch.zeros(length_transform_salt).reshape(1,self.length_transform_salt)
        self.default_value = self.transformer.forward_dry(default_value,self.default_transform_salt,)
        self.default_string = self.hash_func(self.default_value)
        self.default_nonce_value = torch.zeros_like(self.default_value)

        self.length_with_ts_salt = self.default_value.shape[1] #default_value.shape[1]
        self.aggregator.length_with_nonce = self.length_with_ts_salt

        self.level_defaults = []
        self.values_defaults = []
        self.default_hashes()

    def reverse_binary_list(self,binary_list):
        size=len(binary_list)
        reverse_binary_list = [binary_list[size - i-1] for i in range(size)]
        return reverse_binary_list

    def hex_to_binary_str(self,hex_str):
        binary_str = bin(int(hex_str, 16))[2:].zfill(len(hex_str) * 4)
        return binary_str

    def binary_list_to_hex(self,bit_list):
        binary_str = ''.join(str(bit) for bit in bit_list)
        # Remove leading zeros if any (to avoid misinterpretation)
        hex_str = hex(int(binary_str, 2))[2:]  # remove '0x' prefix
        # Optionally, pad with 0 if binary_str length is not a multiple of 4
        expected_hex_len = (len(binary_str) + 3) // 4
        return hex_str.zfill(expected_hex_len)

    def hex_to_binary_list(self,hex_str):

        binary_str = self.hex_to_binary_str(hex_str)

        bit_list = [int(b) for b in binary_str]

        return bit_list

    def bit_list_to_uint(self,bit_list):
        binary_str = ''.join(str(b) for b in bit_list)

        # Convert to integer
        unsigned_int = int(binary_str, 2)

        return unsigned_int

    def obtain_leaf_index(self,leaf):
        leaf_bit_list = self.hex_to_binary_list(leaf)
        leaf_pos = self.bit_list_to_uint(leaf_bit_list)
        return leaf_pos

    def sha256(self,x):
        return hashlib.sha256(x).digest().hex()

    def sha8(self,x,):
        hex_str = hashlib.sha256(x).digest().hex()
        l = int(2*(self.tree_height)/8)
        return hex_str[:l]

    def poseidon_hash(self,x_tensor,print_log=False):

        x_tensor2 = x_tensor * 1024
        x_list = x_tensor2.to(torch.int64).detach().cpu().flatten().tolist()
        x_felt = [ezkl.float_to_felt(int(v), scale=0) for v in x_list]

        poseidon_digest = ezkl.poseidon_hash(x_felt)

        if print_log:
            print(f"Actual Tensor:{x_tensor}")
            print(f"FELT value: {x_felt}")
            print(f"Scaled Integer list:{x_list}")
            print(f"Poseidon Digest Hash: {poseidon_digest}")
            #print(x_list, poseidon_digest)
        l = int(2 * (self.tree_height) / 8)
        return poseidon_digest[0][:l]

    def poseidon_hash_old(self,x_tensor):
        # x_tensor = torch.round(x_tensor * self.rf) / self.rf
        x_flat_tensor = [t.detach().cpu().flatten() for t in x_tensor]
        x_flat_tensor = torch.cat(x_flat_tensor, dim=0)
        x_list = x_flat_tensor.tolist()
        x_felt = [ezkl.float_to_felt(x,scale=self.zkp_scale) for x in x_list]
        poseidon_digest = ezkl.poseidon_hash(x_felt)
        l = int(2 * (self.tree_height) / 8)
        return poseidon_digest[0][:l]

    def hash_node(self,left_value, right_value, left_hash="ff", right_hash="ff",sel=None,nonce=None):
        if sel is None:
            sel = self.ZERO_SEL
        if nonce is None:
            nonce = self.default_nonce_value
        #left hash and right hash are for future use in case we would like to concatenate the hashes as well
        left_tensor = left_value
        right_tensor = right_value

        if left_hash == "ff":
            left_hash = self.hash_func(left_value)

        if right_hash == "ff":
            right_hash = self.hash_func(right_value)

        summand = self.aggregator.forward_dry(left_tensor,right_tensor,sel,nonce,index=f"{left_hash}-{right_hash}")

        return self.hash_func(summand), summand

    def default_hashes(self):
        self.level_defaults = [{"hash":self.default_string,"value":self.default_value}]
        for j in range(self.tree_height):
            parent_hash, parent_value = self.hash_node(self.level_defaults[-1]["value"], self.level_defaults[-1]["value"],self.level_defaults[-1]["hash"], self.level_defaults[-1]["hash"],)
            self.level_defaults.append({"hash":parent_hash,"value":parent_value})
            print(f"Default node at tree level : {j} => {parent_hash}")

    def build_tree(self,leaves,):
        for hashed_leaf in leaves:
            leaf = hashed_leaf["hash"]
            leaf_pos = self.obtain_leaf_index(leaf)

            self.tree[(0,leaf_pos)] = {"hash":leaf,"value":hashed_leaf["value"]}
            self.tree_only_hashes[(0, leaf_pos)] = {"hash": leaf}

            cur_idx = leaf_pos
            for level in range(self.tree_height):
                sib_idx = cur_idx ^ 1
                left, right = (cur_idx & 1 == 0), (cur_idx & 1 == 1)

                l_dict = self.tree.get((level, cur_idx if left else sib_idx), self.level_defaults[level])
                r_dict = self.tree.get((level, sib_idx if left else cur_idx), self.level_defaults[level])

                l_hash = l_dict["hash"]
                r_hash = r_dict["hash"]

                l_value = l_dict["value"]
                r_value = r_dict["value"]

                parent_hash, parent_value = self.hash_node( l_value, r_value,l_hash, r_hash,)

                assert parent_hash == self.hash_func(parent_value)

                self.tree[(level + 1, cur_idx // 2)] = {"hash":parent_hash,"value": parent_value}
                self.tree_only_hashes[(level + 1, cur_idx // 2)] = {"hash":parent_hash,}

                cur_idx = cur_idx // 2

    def get_inclusion_exclusion_proof(self,seek_index):
        """
        seek_index is the index we seek to test inclusion/exclusion for a particular leaf_hash value
        seek index is derived from a public deterministic function called obtain_leaf_index(leaf_hash)
        if leaf does not exist, the threat is the following:
            1. the prover might select another leaf_hash node leaf_hash2 which also does not exist
            2. the prover might supply a valid proof for leaf_hash2 and claim it does not exist.
        this can be detected as follows using zk-SNARK path_prove:
            1. examine the zk-SNARK along the way of the valid proof supplied by the prover
            2. trace the path and determine a bitstring from the inputs contained in each zkSNARK for valid proof nodes
            3. check if the bitstring maps to the leaf_hash
        basically, this strategy is relying on these facts:
            1. the path to the root encodes the leaf_hash
            2. the path can be surmised from the series of inputs for the zkSNARK generated each node. For each zkSNARK
               bit=1 if left input is sibling,
               bit=0 if right input is sibling
               next input is determined by current output
        in doing so, we do not need to reveal the tree also.
        """

        pass

    def get_inclusion_proof(self,leaf,):
        path = []
        selectors = []
        index = self.obtain_leaf_index(leaf)
        cur_idx = index
        for level in range(self.tree_height):
            sib_idx = cur_idx ^ 1
            sibling = self.tree.get((level, sib_idx), self.level_defaults[level])
            path.append({"hash":sibling["hash"],"value":sibling["value"]})
            selectors.append(cur_idx % 2)
            cur_idx //= 2

        root = self.tree.get((self.tree_height, 0), self.level_defaults[self.tree_height])
        full_proof_values={
            "leaf_value": self.tree.get((0, index), self.level_defaults[0])["value"],#self.tree[(0,index)],
            "siblings_value": [h["value"] for h in path],
            "root_value": root["value"],
            "selectors": selectors,
        }

        value_path = [full_proof_values["leaf_value"]] + full_proof_values["siblings_value"] + [full_proof_values["root_value"]]

        value_path = torch.cat(value_path, dim=0)

        full_proof_values["path_tensor"] = value_path.reshape(self.tree_height+2,self.length_with_ts_salt)

        self.current_full_proof_values = full_proof_values
        full_proof_hashes = {
            "leaf_hash": self.tree.get((0, index), self.level_defaults[0])["hash"],
            "siblings_hash": [{"hash": h["hash"]} for h in path],
            "root_hash": root["hash"],
            "selectors": selectors,
        }
        leaf_hash = self.tree.get((0, index), self.level_defaults[0])["hash"]
        #hash_path = [leaf_hash]
        # hash_path = hash_path + [h["hash"] for h in path]
        hash_path = [h["hash"] for h in path]
        hash_path.append(root["hash"])
        return hash_path, full_proof_values, full_proof_hashes

    def verify_proof(self, leaf_value, siblings_values, selectors, root_value):
        leaf_hash = self.hash_func(leaf_value)
        node = leaf_hash
        if leaf_hash != self.default_string:
            hash_path = [leaf_hash]
            key_present = True
        else:
            hash_path = [self.default_string]
            key_present = False
        summand = leaf_value
        index = 0
        #nonce = torch.randn(self.length_with_nonce+self.length_transform_salt)
        nonce = torch.randn(self.length_with_ts_salt)
        for sibling, sel in zip(siblings_values, selectors):
            sibling_value = siblings_values[index]
            sibling_hash = self.hash_func(sibling_value)
            hash_path.append(sibling_hash)
            assert sibling_hash == self.hash_func(sibling_value)
            if sel == 1:
                node, summand = self.hash_node(left_value=sibling_value, right_value= summand,left_hash=sibling_hash, right_hash=node,sel=torch.tensor([1.0]),nonce=nonce)
            else:
                node, summand = self.hash_node(left_value=summand, right_value=sibling_value,left_hash=node,right_hash=sibling_hash,sel=torch.tensor([0.0]),nonce=nonce)
            index = index+1
        proof_valid = node == self.hash_func(root_value)
        #assert proof_valid
        hash_path.append(node)
        return proof_valid, key_present,hash_path

    def test_inclusion(self,key):

        full_proof_hashes,_,_ = self.get_inclusion_proof(key, )

        proof_valid,key_present,hash_path = self.verify_proof(
                                                              self.current_full_proof_values["leaf_value"],
                                                              self.current_full_proof_values["siblings_value"],
                                                              self.current_full_proof_values["selectors"],
                                                              self.current_full_proof_values["root_value"]
                                                            )

        return proof_valid,key_present,hash_path, full_proof_hashes,self.current_full_proof_values["selectors"]
