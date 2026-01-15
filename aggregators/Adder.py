import torch, ezkl, time, os, json, asyncio
import torch.nn as nn

class Adder(nn.Module):
    def __init__(self,size=0,length_with_nonce=1,):

        self.flipper_mask = torch.tensor([0.0])
        self.length_with_nonce = length_with_nonce
        super(Adder, self).__init__()

        self.size = size
        self.mrp_path = None
        self.mrp_settings_path = None
        self.mrp_compiled_model_path = None
        self._async_srs = None
        self._async_compile = None

    def _convert_float_array_to_tensor(self, h_array,):
        h = [float(x) for x in h_array]
        h = torch.tensor(h).reshape(self.size)
        return h

    def _convert_tensor_to_float_array(self,h_tensor):
        h_flat_tensor = [t.detach().cpu().flatten() for t in h_tensor]
        h_flat_tensor = torch.cat(h_flat_tensor, dim=0)
        h = h_flat_tensor.tolist()
        return h

    def setup_proof(self,model,default_value,model_path,settings_path,compiled_model_path,vk_path,pk_path,py_run_args):
        current_value = torch.zeros_like(default_value)
        sibling_value = torch.zeros_like(default_value)
        sel = torch.tensor([0.0])
        nonce = torch.zeros_like(default_value)
        torch.onnx.export(model, (current_value,sibling_value,sel,nonce,), model_path,
                          input_names=[], output_names=["out"],
                          do_constant_folding=True, opset_version=15, export_params=True)

        settings_generation_time = time.time()
        res = ezkl.gen_settings(model_path, settings_path, py_run_args=py_run_args)
        assert res == True
        settings_generation_time = time.time() - settings_generation_time

        compile_circuit_time = time.time()
        res = ezkl.compile_circuit(model_path, compiled_model_path, settings_path)
        assert res == True
        compile_circuit_time = time.time() - compile_circuit_time

        circuit_setup_time = time.time()
        res = ezkl.setup(compiled_model_path, vk_path, pk_path, )
        circuit_setup_time = time.time() - circuit_setup_time

        assert res == True
        assert os.path.isfile(vk_path)
        assert os.path.isfile(pk_path)
        assert os.path.isfile(settings_path)

    def dump_data_for_proof_gen(self,left_val,right_val,sel,nonce,data_path,rf=1000):

        left_array = self._convert_tensor_to_float_array(left_val)
        right_array = self._convert_tensor_to_float_array(right_val)
        sel_array = self._convert_tensor_to_float_array(sel)
        nonce_array = self._convert_tensor_to_float_array(nonce)
        # parent_array = self._convert_tensor_to_float_array(parent)

        input_data_dict = dict(input_data=[left_array,right_array,sel_array,nonce_array,])
        json.dump(input_data_dict, open(data_path, 'w'))

    def _generate_witness(self,settings_path,data_path,compiled_model_path,witness_path):
        witness_generation_time = time.time()
        # compile witness
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        res = loop.run_until_complete(self._async_srs(settings_path))

        res = loop.run_until_complete(self._async_compile(data_path, compiled_model_path, witness_path))
        loop.close()
        assert os.path.isfile(witness_path)
        witness_generation_time = time.time() - witness_generation_time

        with open(witness_path) as witness_file:
            output = json.load(witness_file)
            forward_result = output["pretty_elements"]["rescaled_outputs"][0]
            forward_result_tensor = self._convert_float_array_to_tensor(forward_result)

        return forward_result_tensor

    def extract_raw_value(self, witness_path, ):  # reshape_size, rf=1000

        with open(witness_path, 'r') as file:
            output = json.load(file)
        zk_output = output['pretty_elements']['rescaled_outputs'][0]
        zk_output = self._convert_float_array_to_tensor(zk_output)
        return 1, 0, 0, zk_output

    def forward_dry(self,a, b, sel, nonce,index="ff-ff"):

        mrp_data_path = os.path.join(self.mrp_path, f'input_{index}.json')
        mrp_witness_path = os.path.join(self.mrp_path, f'witness_{index}.json')
        mrp_settings_path = self.mrp_settings_path #os.path.join(self.mrp_path, f'settings.json')
        mrp_compiled_model_path = self.mrp_compiled_model_path #os.path.join(self.mrp_path, f'network.compiled')

        self.dump_data_for_proof_gen(a, b, sel, nonce, mrp_data_path,)

        # res = self._generate_proof(ltr_data_path, self.ltr_settings_path, self.ltr_compiled_model_path, ltr_witness_path, ltr_proof_path, self.ltr_pk_path)
        parent_value = self._generate_witness(mrp_settings_path, mrp_data_path, mrp_compiled_model_path, mrp_witness_path)

        return parent_value

    def forward(self, a, b, sel, nonce):
        """
        consider a random nonce vector obtained using torch.randn(1,len)
        # compute sel_complement = 1-sel
        # if sel==1:
        #     summand_prime = (1-sel)*nonce+summand
        # else
        #     summand_prime = sel*nonce + summand

        say that the following relation is protected by the zk circuit
        parent = sel*nonce + summand + sibling_val

        where sel can be either 0 or 1.

        this means that if the prover generates a proof it ensures that there exists an sel, summand and sibling_val that
        can lead to the same parent_val regardless of a random nonce

        lets analyze this strategy, wlog say real_sel=0:
        if prover flips the bit from real_sel=0 to sel=1, then parent_value is going to be incorrect
        """
        nonce_multiplier = sel * self.flipper_mask
        c = torch.add(a, b) + nonce_multiplier * nonce
        return c


