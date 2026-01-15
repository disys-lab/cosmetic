import asyncio, os, json, sys, torch, ezkl
from pathlib import Path


class LRT_Test(torch.nn.Module):
    def forward(self, ll_full, ll_reduced):
        ll_full_val = ll_full[0][0]
        ll_reduced_val = ll_reduced[0][0]
        lrt_statistic = -2 * (ll_reduced_val - ll_full_val)
        return lrt_statistic

outdir_name = "lrt_statistic_zk_api"


class LRTStatistic:
    def __init__(self, outdir_name,reduced_dim,full_dim,zkp_scale,setup=True, prove=True):
        self.reduced_dim = reduced_dim
        self.full_dim = full_dim
        self.zkp_scale = zkp_scale
        self.prove = prove
        self.setup = setup
        self.py_run_args = ezkl.PyRunArgs()
        self.py_run_args.input_visibility = "hashed"
        self.py_run_args.output_visibility = "public"
        self.py_run_args.param_visibility = "private"  # private by default
        self.py_run_args.logrows = 20
        self.py_run_args.decomp_legs = 4
        self.py_run_args.decomp_base = 16384
        self.py_run_args.input_scale = self.zkp_scale
        self.py_run_args.param_scale = self.zkp_scale

        self.OUTDIR = Path(outdir_name)
        self.OUTDIR.mkdir(parents=True, exist_ok=True)

        self.onnx_path = self.OUTDIR / "abs_gap.onnx"
        self.compiled_path = self.OUTDIR / "abs_gap.compiled"
        self.settings_path = self.OUTDIR / "settings.json"
        self.calib_path = self.OUTDIR / "calibration.json"

        # Single PK/VK for all proofs
        self.pk_path = self.OUTDIR / "proving.key"
        self.vk_path = self.OUTDIR / "verifying.key"

        self.model = LRT_Test()

        # Set event loop policy for Windows
        if sys.platform.startswith("win"):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        self.export_and_setup()


    def dump_data(self, ll_full, ll_reduced, run_id):
        print(ll_full,ll_reduced)
        model_output = self.model.forward(ll_full, ll_reduced)

        data = {
            "input_data": [
                ll_full.reshape(-1).tolist(),
                ll_reduced.reshape(-1).tolist()
            ],
            "output_data": [
                model_output.reshape(-1).tolist()
            ]
        }
        (self.OUTDIR / "input.json").write_text(json.dumps(data))
        if self.calib_path == self.OUTDIR / "calibration.json":
            self.calib_path.write_text(json.dumps(data))
        if run_id is not None:
            (self.OUTDIR / f"input_run{run_id}.json").write_text(json.dumps(data))


    async def setup_once(self):

        assert self.calib_path.exists(), "Call dump_data(...) before setup_once()"
        assert ezkl.gen_settings(str(self.onnx_path), str(self.settings_path),py_run_args=self.py_run_args), "gen_settings failed"
        print("[OK] Settings generated.")

        assert ezkl.compile_circuit(str(self.onnx_path), str(self.compiled_path), str(self.settings_path)), "compile_circuit failed"
        print("[OK] Circuit compiled.")
        # Make sure your SRS is present/valid at ~/.ezkl/srs/kzgXX.srs if needed
        assert await ezkl.get_srs(settings_path=str(self.settings_path)), "get_srs failed"
        print("[OK] SRS downloaded.")
        assert ezkl.setup(str(self.compiled_path), str(self.vk_path), str(self.pk_path)), "setup failed"
        print("[OK] Keys generated successfully.")


    def export_and_setup(self,):
        """
        Exports ONNX using a random calibration sample and performs ezkl setup once.
        """
        # Use the global model instance for consistency with generate_proof_for
        ll_full, ll_reduced = torch.zeros(1,self.full_dim), torch.zeros(1,self.reduced_dim)

        # Torch run for visibility
        torch_output = self.model.forward(ll_full, ll_reduced)
        print(f"\n[Torch]   lrt stat: {torch_output.tolist()}\n")

        # ONNX export
        torch.onnx.export(
            self.model,
            (ll_full, ll_reduced),
            str(self.onnx_path),
            export_params=True,
            opset_version=13,
            do_constant_folding=True,
            input_names=["ll_full", "ll_reduced"],
            output_names=["gap"],
            dynamic_axes={"ll_full": {0: "batch_size"}, "ll_reduced": {0: "batch_size"}, "gap": {0: "batch_size"}}
        )
        print(f"[OK] Exported ONNX -> {self.onnx_path}")

        # Calibration + setup
        self.dump_data(ll_full, ll_reduced,1)  # creates calibration.json
        if not os.path.exists(self.compiled_path) and not os.path.exists(self.pk_path):
            asyncio.run(self.setup_once())


    async def generate_proof_for(self, ll_full, ll_reduced, run_id,):
        """
        Generate witness & proof for a single (a,b) pair.
        Returns a dict with proof path, witness path, and the model's supremum output.
        """
        # Record inputs and write input.json used by gen_witness
        self.dump_data(ll_full, ll_reduced, run_id=run_id)

        # True model output (the supremum you're proving)
        lrt = self.model.forward(ll_full, ll_reduced).item()
        print(f"\n[Run {run_id}] ll_full: {ll_full}")
        print(f"[Run {run_id}] ll_reduced: {ll_reduced}")
        print(f"[Run {run_id}] LRT Statistic: {lrt}")

        witness_path = self.OUTDIR / f"witness_{run_id}.json"
        proof_path   = self.OUTDIR / f"proof_{run_id}.pf"

        # Build witness from inputs
        assert await ezkl.gen_witness(str(self.OUTDIR / "input.json"), str(self.compiled_path), str(witness_path)), "gen_witness failed"
        print(f"[OK] Witness file generated : {witness_path}")

        # # Create proof using the single PK
        if self.prove:
            assert ezkl.prove(str(witness_path), str(self.compiled_path), str(self.pk_path), str(proof_path), "single"), "prove failed"
            print(f"[OK] Proof generated : {proof_path}")

        return {
            "run_id": run_id,
            "witness_path": witness_path,
            "proof_path": proof_path,
            "lrt": lrt
        }

    def forward(self, ll_full, ll_reduced, run_id=1):
        print(ll_full,ll_reduced)
        """
        Computes the maximum absolute gap for given a and b, generates ZK proof, and verifies.
        Returns the result dict from proof generation and verification status.
        """
        result = asyncio.run(self.generate_proof_for(ll_full, ll_reduced, run_id))
        ok, failed = self.verify_all_with_single_vk()
        return result, ok, failed


    def verify_all_with_single_vk(self):
        proofs = sorted(self.OUTDIR.glob("proof_*.pf"))
        if not proofs:
            print(f"No proof_*.pf files found in {self.OUTDIR}")
            return False, []

        print("\n===== Final verification with SINGLE VK =====")
        failed = []
        for pf in proofs:
            try:
                ok = ezkl.verify(str(pf), str(self.settings_path), str(self.vk_path))
                print(f"[Verify] {pf.name:15} | OK={ok}")
                if not ok:
                    failed.append((pf, "verification returned False"))
            except Exception as e:
                print(f"[Verify] {pf.name:15} | ERROR: {e}")
                failed.append((pf, f"exception: {e}"))

        print("============================================")
        if not failed:
            print("ALL PROOFS VERIFIED")
            return True, []
        else:
            print("Some proofs failed:")
            for pf, reason in failed:
                print(f"  - {pf.name}: {reason}")
            return False, failed
