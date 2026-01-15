import torch, ezkl, time, os, json, asyncio
import torch.nn as nn

class LogLogLikelihood(nn.Module):
    def __init__(self, size=0, length_transform_salt=0, beta=None, mask=None):
        super(LogLogLikelihood, self).__init__()
        self.length_transform_salt = length_transform_salt
        self.beta = beta
        self.mask=mask
        self.size=size
        self.hash_func = None
        self.default_value = None
        self.ltr_path = None
        self.ltr_settings_path = None
        self.ltr_compiled_model_path = None
        self._async_srs =None
        self._async_compile=None
        self.K=10

    def _convert_float_array_to_tensor(self, h_array,):
        h = [float(x) for x in h_array]
        h = torch.tensor(h).reshape(self.size)
        return h

    def _convert_tensor_to_float_array(self, h_tensor):
        h_flat_tensor = [t.detach().cpu().flatten() for t in h_tensor]
        h_flat_tensor = torch.cat(h_flat_tensor, dim=0)
        h = h_flat_tensor.tolist()
        return h

    def setup_proof(self, model, default_value, model_path, settings_path, compiled_model_path, vk_path, pk_path, py_run_args):
        current_value = torch.zeros_like(default_value)
        salt = torch.zeros(self.length_transform_salt).reshape(1, self.length_transform_salt)
        torch.onnx.export(model, (current_value, salt,self.beta, self.mask), model_path,
                          input_names=[], output_names=["out"],
                          do_constant_folding=False, opset_version=16, export_params=True)

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

    def dump_data_for_proof_gen(self, raw_value, salt,  data_path):
        beta = self.beta
        mask = self.mask
        raw_value_array = self._convert_tensor_to_float_array(raw_value)
        salt_array = self._convert_tensor_to_float_array(salt)
        beta_array = self._convert_tensor_to_float_array(beta)
        mask_array = self._convert_tensor_to_float_array(mask)

        input_data_dict = dict(input_data=[raw_value_array, salt_array, beta_array, mask_array])
        json.dump(input_data_dict, open(data_path, 'w'))

    def _generate_witness(self, settings_path, data_path, compiled_model_path, witness_path):
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


    def extract_raw_value(self, proof_path, ):  # reshape_size, rf=1000

        with open(proof_path, 'r') as file:
            output = json.load(file)
        zk_output = output['pretty_public_inputs']['rescaled_outputs'][3]
        return 1, 0, 0, zk_output


    def forward_dry(self, a, salt, use_witness_file=True):

        beta = self.beta
        mask = self.mask
        if use_witness_file:
            raw_value_hash = self.hash_func(a)
            ltr_data_path = os.path.join(self.ltr_path, f'input_{raw_value_hash}.json')
            ltr_witness_path = os.path.join(self.ltr_path, f'witness_{raw_value_hash}.json')
            ltr_settings_path = self.ltr_settings_path
            ltr_compiled_model_path = self.ltr_compiled_model_path
            self.dump_data_for_proof_gen(a, salt, ltr_data_path)
            forward_result_vector = self._generate_witness(ltr_settings_path, ltr_data_path, ltr_compiled_model_path, ltr_witness_path)
        else:
            forward_result_vector = self.forward(a, salt, beta, mask)

        return forward_result_vector

    def softplus_piecewise(self, eta,):
        K= self.K
        # Polynomial valid on [-K, K]
        a6 = 2.580e-05
        a4 = -2.255e-03
        a2 = 1.121e-01
        a1 = 5.000e-01
        a0 = 7.034e-01

        eta2 = eta * eta
        eta4 = eta2 * eta2
        eta6 = eta4 * eta2

        poly = a6 * eta6 + a4 * eta4 + a2 * eta2 + a1 * eta + a0

        # Start with middle region
        sp = poly

        # Left tail: eta <= -K  → 0
        sp = torch.where(eta <= -K, torch.zeros_like(sp), sp)

        # Right tail: eta >= K  → eta
        sp = torch.where(eta >= K, eta, sp)

        return sp

    def logistic_ll_piecewise(self,eta, y,):
        # y in {0,1}, eta arbitrary
        sp = self.softplus_piecewise(eta,)
        return y * eta - sp

    def forward(self, a, salt,beta, mask):
        beta = beta.reshape(-1, 1)
        x_dim = beta.shape[0]
        total_dim = a.shape[0]

        x = a[:, :x_dim] #->reshape(1,x_dim)  # (1, x_dim)
        y = a[:, x_dim:x_dim+1]     # scalar
        
        eta = (mask * x) @ beta      # (1, 1)

        result = self.logistic_ll_piecewise(eta,y)

        #print(x, y, beta, eta, result)

        zero_mask = torch.all(a == 0, dim=1, keepdim=True)
        result = torch.where(zero_mask, torch.zeros_like(result), result)

        result = torch.cat([result, salt], dim=1)  # (1, num_rows + salt_dim)
        return result
        # result = torch.cat([result, salt], dim=1)  # (1, num_rows + salt_dim)

        # return result

    def forward_log1p(self, a, salt, beta):
        beta = beta.reshape(-1, 1)
        x_dim = beta.shape[0]

        x = a[:, :x_dim]  # (1, x_dim)
        y = a[:, x_dim:x_dim + 1]  # scalar

        eta = x @ beta  # (1, 1)


        #result = self.logistic_ll_piecewise(eta, y)

        result = y * eta - torch.log1p(torch.exp(eta))  #(1, 1)



        zero_mask = torch.all(a == 0, dim=1, keepdim=True)
        result = torch.where(zero_mask, torch.zeros_like(result), result)

        result = torch.cat([result, salt], dim=1)  # (1, num_rows + salt_dim)
        return result


