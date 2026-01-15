# MaxGap.py
import asyncio
import json
import os.path
import sys
from pathlib import Path
import glob
import time
import torch
import ezkl

EPS = 1e-6  # avoid divide-by-zero in CDFs


class AbsGapModel(torch.nn.Module):
    def __init__(self, nbins=1):
        super(AbsGapModel, self).__init__()
        self.nbins = nbins

    def forward(self, aval, bval):
        # Use only first nbins entries as the histogram
        a = aval[:, :self.nbins]
        b = bval[:, :self.nbins]
        cdf_a = a.cumsum(dim=-1) / (a.sum() + EPS)
        cdf_b = b.cumsum(dim=-1) / (b.sum() + EPS)
        diff = torch.abs(cdf_a - cdf_b)
        return torch.max(diff)


class MaxAbsGap:
    """
    Self-contained (no snapshots):
      - Takes SMT vectors directly (e.g., mrp.root_value).
      - Sets nbins from the first call as min(len(a), len(b)) unless provided explicitly.
      - Overwrites ONNX/ezkl artifacts in a single outdir if nbins changes.
    """
    def __init__(self, outdir_name="abs_gap_zk_api", zkp_scale=10, shape=None, nbins: int | None = None, trailer_extras:int = 2,):
        # Note: `shape` kept for API parity, but nbins drives the circuit shape.
        self.base_outdir = Path(outdir_name)
        self.base_outdir.mkdir(parents=True, exist_ok=True)
        self.zkp_scale = zkp_scale
        self.trailer_extras = trailer_extras  # how many non-bin fields at the end


        # runtime state
        self.nbins = nbins          # if None, inferred from first inputs
        self.OUTDIR = self.base_outdir
        self.onnx_path = self.OUTDIR / "abs_gap.onnx"
        self.compiled_path = self.OUTDIR / "abs_gap.compiled"
        self.settings_path = self.OUTDIR / "settings.json"
        self.calib_path = self.OUTDIR / "calibration.json"
        self.pk_path = self.OUTDIR / "proving.key"
        self.vk_path = self.OUTDIR / "verifying.key"
        self.model = None

        # ezkl settings
        self.py_run_args = ezkl.PyRunArgs()
        self.py_run_args.input_visibility = "hashed"
        self.py_run_args.output_visibility = "public"
        self.py_run_args.param_visibility = "private"
        self.py_run_args.logrows = 20
        self.py_run_args.decomp_legs = 5
        self.py_run_args.decomp_base = 16384
        self.py_run_args.rebase_frac_zero_constants = True
        self.py_run_args.input_scale = self.zkp_scale
        self.py_run_args.param_scale = self.zkp_scale

        # Windows event loop policy
        if sys.platform.startswith("win"):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # We delay export/setup until we see the first inputs (so we know nbins),
        # unless nbins was provided explicitly.

    # ---------------------------
    # Internal helpers
    # ---------------------------

    def _safe_unlink(self, p: Path):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    def _reset_artifacts(self):
        for p in [self.settings_path, self.compiled_path, self.pk_path,
                self.vk_path, self.calib_path]:
            self._safe_unlink(p)

    async def _export_and_setup(self, nbins: int):
        """
        Export ONNX and run full ezkl setup for the given nbins.
        Overwrites artifacts in OUTDIR (single folder).
        """
        self.nbins = nbins
        self.model = AbsGapModel(nbins=self.nbins)

        # Calibration sample with the correct feature size
        a_calib = torch.rand(1, self.nbins+self.trailer_extras) * 15
        b_calib = torch.rand(1, self.nbins+self.trailer_extras) * 15

        # Torch check
        torch_output = self.model.forward(a_calib, b_calib)
        print(f"\n[Torch]   Sup of a-b (nbins={self.nbins}): {torch_output.tolist()}\n")

        # Export ONNX with fixed feature dim = nbins
        torch.onnx.export(
            self.model,
            (a_calib, b_calib),
            str(self.onnx_path),
            export_params=True,
            opset_version=13,
            do_constant_folding=True,
            input_names=["a", "b"],
            output_names=["gap"],
            dynamic_axes={"a": {0: "batch_size"}, "b": {0: "batch_size"}, "gap": {0: "batch_size"}}
        )
        print(f"[OK] Exported ONNX -> {self.onnx_path}")
        self._reset_artifacts()
        # Write calibration.json and full setup
        self._dump_data(a_calib, b_calib)  # creates calibration.json if missing
        await self._setup_once()
        print("[OK] Setup complete for nbins =", self.nbins)

    async def _setup_once(self):
        #assert self.calib_path.exists(), "Call _dump_data(...) before _setup_once()"
        assert ezkl.gen_settings(str(self.onnx_path), str(self.settings_path), py_run_args=self.py_run_args), "gen_settings failed"
        print("[OK] Settings generated.")

        assert ezkl.compile_circuit(str(self.onnx_path), str(self.compiled_path), str(self.settings_path)), "compile_circuit failed"
        print("[OK] Circuit compiled.")
        assert await ezkl.get_srs(settings_path=str(self.settings_path)), "get_srs failed"
        print("[OK] SRS downloaded.")
        assert ezkl.setup(str(self.compiled_path), str(self.vk_path), str(self.pk_path)), "setup failed"
        print("[OK] Keys generated successfully.")

    def _dump_data(self, a_vals: torch.Tensor, b_vals: torch.Tensor, run_id: int | None = None):
        data = {"input_data": [a_vals.reshape(-1).tolist(), b_vals.reshape(-1).tolist()]}
        (self.OUTDIR / "input.json").write_text(json.dumps(data))

        # ALWAYS overwrite calibration to match current nbins
        #self.calib_path.write_text(json.dumps(data))

        if run_id is not None:
            (self.OUTDIR / f"input_run{run_id}.json").write_text(json.dumps(data))

    async def _ensure_ready(self, a_vals: torch.Tensor, b_vals: torch.Tensor):
        total_len = min(int(a_vals.numel()), int(b_vals.numel()))
        inferred = total_len - self.trailer_extras if total_len > self.trailer_extras else total_len
        if inferred <= 0:
            raise ValueError(f"Not enough features after trimming trailer_extras={self.trailer_extras}")
        if self.nbins is None:
            await self._export_and_setup(inferred)
        elif self.nbins != inferred:
            print(f"[Rebuild] nbins changed {self.nbins} -> {inferred}; rebuilding circuit.")
            await self._export_and_setup(inferred)

    async def _generate_proof_for(self, a, b, run_id):
        """
        Returns dict with paths and supremum.
        """
        if not os.path.exists(self.compiled_path) or not os.path.exists(self.pk_path):
            await self._ensure_ready(a, b)

        # Model output (the supremum)
        supremum_value = AbsGapModel(self.nbins).forward(a, b).item()
        print(f"\n[Run {run_id}] a_vals: {a.tolist()}")
        print(f"[Run {run_id}] b_vals: {b.tolist()}")
        print(f"[Run {run_id}] supremum (model output): {supremum_value}")

        witness_path = self.OUTDIR / f"witness_{run_id}.json"
        proof_path   = self.OUTDIR / f"proof_{run_id}.pf"

        # Build witness
        self._dump_data(a, b, run_id=run_id)
        assert await ezkl.gen_witness(str(self.OUTDIR / "input.json"), str(self.compiled_path), str(witness_path)), "gen_witness failed"
        print(f"[OK] Witness file generated : {witness_path}")

        # Prove
        assert ezkl.prove(str(witness_path), str(self.compiled_path), str(self.pk_path), str(proof_path), "single"), "prove failed"
        print(f"[OK] Proof generated : {proof_path}")

        return {
            "run_id": run_id,
            "witness_path": proof_path.with_suffix(".json").with_name(f"witness_{run_id}.json"),
            "proof_path": proof_path,
            "supremum": supremum_value
        }

    def verify_all_with_single_vk(self):
        if self.vk_path is None:
            print("VK not ready yet.")
            return False, []
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
            print("ALL PROOFS VERIFIED ✅")
            return True, []
        else:
            print("❌ Some proofs failed:")
            for pf, reason in failed:
                print(f"  - {pf.name}: {reason}")
            return False, failed

    def forward(self, a_vals, b_vals, run_id=1):
        """
        You can pass SMT root_value tensors here.
        This method will:
          1) Infer nbins from the input lengths (min(len(a), len(b))) unless provided in __init__.
          2) Slice to first nbins.
          3) Compile/setup once; rebuild (overwrite) if nbins changes.
          4) Generate & verify proof.
        """
        result = asyncio.run(self._generate_proof_for(a_vals, b_vals, run_id))
        ok, failed = self.verify_all_with_single_vk()
        return result, ok, failed
