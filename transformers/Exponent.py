import torch, ezkl, time, os, json, asyncio
import torch.nn as nn

class Exponent(nn.Module):
    def __init__(self,exponent=1,size=0,length_transform_salt=0,):

        super(Exponent, self).__init__()
        self.length_transform_salt = length_transform_salt
        self.exponent_tensor = torch.tensor([exponent],dtype=torch.float32)
        self.exponent = exponent
        self.size=size
        self.hash_func = None
        self.default_value = None
        self.ltr_path = None
        self.ltr_settings_path = None
        self.ltr_compiled_model_path = None
        self._async_srs =None
        self._async_compile=None


    def _convert_float_array_to_tensor(self, h_array,):
        h = [float(x) for x in h_array]
        h = torch.tensor(h).reshape(self.size)
        return h

    def _convert_tensor_to_float_array(self, h_tensor):
        h_flat_tensor = [t.detach().cpu().flatten() for t in h_tensor]
        h_flat_tensor = torch.cat(h_flat_tensor, dim=0)
        h = h_flat_tensor.tolist()
        return h

    def setup_proof(self, model, default_value, model_path, settings_path, compiled_model_path, vk_path, pk_path,py_run_args):
        current_value = torch.zeros_like(default_value)
        exponent = self.exponent_tensor
        salt = torch.zeros(self.length_transform_salt).reshape(1, self.length_transform_salt)
        torch.onnx.export(model, (current_value, salt,exponent), model_path,
                          input_names=[], output_names=["out"],
                          do_constant_folding=True, opset_version=16, export_params=True)

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

    def dump_data_for_proof_gen(self, raw_value,salt,data_path,):
        exponent = self.exponent_tensor
        raw_value_array = self._convert_tensor_to_float_array(raw_value)
        salt_array = self._convert_tensor_to_float_array(salt)
        exponent_array = self._convert_tensor_to_float_array(exponent)

        input_data_dict = dict(input_data=[raw_value_array, salt_array,exponent_array])
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


    def extract_raw_value(self, proof_path, ):

        with open(proof_path, 'r') as file:
            output = json.load(file)
        zk_output = output['pretty_public_inputs']['rescaled_outputs'][3]
        return 1, 0, 0, zk_output


    def forward_dry(self,a,salt,use_witness_file=True):
        exponent = self.exponent_tensor

        if use_witness_file:
            raw_value_hash = self.hash_func(a)

            ltr_data_path = os.path.join(self.ltr_path, f'input_{raw_value_hash}.json')
            ltr_witness_path = os.path.join(self.ltr_path, f'witness_{raw_value_hash}.json')
            ltr_settings_path = self.ltr_settings_path
            ltr_compiled_model_path = self.ltr_compiled_model_path

            self.dump_data_for_proof_gen(a,salt,ltr_data_path)

            forward_result_vector = self._generate_witness(ltr_settings_path, ltr_data_path, ltr_compiled_model_path, ltr_witness_path)
        else:
            forward_result_vector = self.forward(a, salt,exponent)

        return forward_result_vector

    def forward(self,a,salt,exponent):
        e = exponent.to(torch.int64).reshape(())
        result = torch.where(
            e == 0, torch.ones_like(a),
            torch.where(
                e == 1, a,
                torch.where(
                    e == 2, a * a,
                    torch.where(
                        e == 3, a * a * a,
                        torch.where(
                            e == 4, a * a * a * a,
                            torch.zeros_like(a)  # fallback if exponent not 0–4
                        )
                    )
                )
            )
        )
        result = torch.cat([result, salt], dim=1)
        return result