"""Resource and GPU logic tests; native-device fixtures are never hardware acceptance."""

from copy import deepcopy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from materiasim.engines.gromacs.device import (build_capabilities, offload_arguments, resolve_device,
                                             verify_offload, visible_devices)
from materiasim.runtime.control import control_root, inspect_control, supervise, usage, watch
from materiasim.specs.execution import cpu_profile, validate_profile
from materiasim.storage import content_hash, read_json, write_json
from materiasim.workflows.migration import load_executable
from materiasim.workflows.validation import validate_resolved

ROOT = Path(__file__).resolve().parents[2]
GPU_REPORT = ("Mapping of GPU IDs to the 2 GPU tasks in the 1 rank on this node:\n"
              "  PP:0,PME:0\nPP tasks will do (non-perturbed) short-ranged interactions on the GPU\n"
              "PP task will update and constrain coordinates on the CPU\nPME tasks will do all aspects on the GPU\n")


class ExecutionProfileTests(unittest.TestCase):
    """Use isolated journals and explicit synthetic driver/log fixtures for all non-CPU claims."""

    def setUp(self):
        """Create an independent resource contract and existing scientific input."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.spec, self.sources, _, _ = load_executable(ROOT / "examples/packed_zil_water.json")
        self.profile = cpu_profile()
        self.spec["execution_profile"] = self.profile
        self.run = self.root / "runs/fixture"

    def gpu(self):
        """Select an explicit force-offload policy for static tests only."""
        profile = deepcopy(self.profile)
        profile.update(device="gpu", gpu_id=0, dynamics_offload=dict(nb="gpu", pme="gpu", bonded="cpu", update="cpu"))
        return profile

    def test_cpu_and_gpu_static_validation_never_probe_devices(self):
        """GPU document legality is independent of device availability and never starts a tool."""
        with patch("subprocess.run", side_effect=AssertionError("tool called")):
            validate_resolved(self.spec, self.sources)
            self.spec["execution_profile"] = self.gpu()
            validate_resolved(self.spec, self.sources)

    def test_invalid_profile_fields_and_unbounded_values(self):
        """CPU/GPU conflicts, implicit auto policies, unknown knobs and nonfinite budgets fail."""
        for key, value in (("threads", True), ("gpu_id", 0), ("workflow_seconds", 5),
                           ("analysis_seconds", float("inf")), ("shell", "echo unsafe")):
            profile = dict(self.profile, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_profile(profile)
        profile = self.gpu()
        profile["dynamics_offload"]["nb"] = "auto"
        with self.assertRaises(ValueError):
            validate_profile(profile)

    def test_minimization_is_explicit_cpu_and_gpu_flags_are_arrays(self):
        """EM uses CPU by policy, not fallback; MD maps only the selected single visible device."""
        args, policy = offload_arguments(self.gpu(), dict(type="minimization"))
        self.assertEqual(set(policy.values()), {"cpu"})
        self.assertNotIn("-gpu_id", args)
        args, _ = offload_arguments(self.gpu(), dict(type="dynamics"))
        self.assertEqual(args, ["-nb", "gpu", "-pme", "gpu", "-bonded", "cpu", "-update", "cpu", "-gpu_id", "0"])

    def test_gpu_unavailable_never_falls_back(self):
        """A disabled build or unknown driver inventory rejects the requested GPU before mdrun."""
        with self.assertRaisesRegex(ValueError, "CUDA"):
            resolve_device(self.gpu(), dict(build_capabilities=dict(gpu="disabled", mpi="thread_mpi")))
        engine = dict(build_capabilities=dict(gpu="CUDA", mpi="thread_mpi"))
        with patch("materiasim.engines.gromacs.device.visible_devices", return_value=dict(status="unknown", devices=[])):
            with self.assertRaisesRegex(ValueError, "unavailable"):
                resolve_device(self.gpu(), engine)

    def test_device_visibility_uses_uuid_without_global_mutation(self):
        """An explicit CUDA visibility list is respected and the child alone receives one full UUID."""
        result = subprocess.CompletedProcess([], 0, "0, GPU-aaaa, Fixture A\n1, GPU-bbbb, Fixture B\n", "")
        with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "GPU-bbbb"}), \
                patch("shutil.which", return_value="/fixture/nvidia-smi"), patch("subprocess.run", return_value=result):
            devices = visible_devices()
            self.assertEqual(devices["devices"][0]["uuid"], "GPU-bbbb")
            resolved = resolve_device(self.gpu(), dict(build_capabilities=dict(gpu="CUDA", mpi="thread_mpi")))
            self.assertEqual(resolved["environment"], dict(CUDA_VISIBLE_DEVICES="GPU-bbbb"))
            self.assertEqual(os.environ["CUDA_VISIBLE_DEVICES"], "GPU-bbbb")

    def test_unknown_build_and_driver_format(self):
        """Unrecognized capability/driver data stays unknown, not optimistically available."""
        self.assertEqual(build_capabilities("other version format")["gpu"], "unknown")
        with patch("shutil.which", return_value=None):
            self.assertEqual(visible_devices()["status"], "unknown")

    def test_gpu_evidence_requires_mapping_and_each_requested_offload(self):
        """Known startup text passes only the declared policy; utilization or stale generic text cannot."""
        policy = self.gpu()["dynamics_offload"]
        self.assertTrue(verify_offload(GPU_REPORT, policy)["gpu_used"])
        for text in ("GPU detected", GPU_REPORT.replace("PP:0", "PP:1"),
                     GPU_REPORT.replace("PME tasks will do all aspects on the GPU", ""),
                     GPU_REPORT.replace("coordinates on the CPU", "coordinates on the GPU")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                verify_offload(text, policy)
        with self.assertRaises(ValueError):
            verify_offload(GPU_REPORT, self.profile["dynamics_offload"])

    def fake_operation(self, module, request, event, paths, profile, seconds):
        """Record a metadata-only supervisor fixture; no actual Run or MD outcome is represented."""
        write_json(event / "result.json", dict(fixture="metadata only"))
        return dict(returncode=0, stop_reason=None, elapsed_seconds=2, storage_bytes=usage(paths))

    def test_all_operation_kinds_share_cumulative_journal(self):
        """Build, execution and analysis each consume the same persisted allowance."""
        with patch("materiasim.runtime.control.watch", side_effect=self.fake_operation):
            for action in ("build", "run", "analyze"):
                supervise(self.run, self.spec, "fixture", action, {})
        _, ledger = inspect_control(self.run, self.profile, content_hash(self.spec))
        self.assertEqual([e["action"] for e in ledger["events"]], ["build", "run", "analyze"])
        self.assertEqual(sum(e["charged_seconds"] for e in ledger["events"]), 6)
        self.assertIsNone(ledger["active"])
        self.assertFalse(self.run.exists())

    def test_crashed_supervisor_retains_reservation(self):
        """Unfinished handoff cannot reset budget or trigger another child."""
        with patch("materiasim.runtime.control.watch", side_effect=RuntimeError("fixture crash")):
            with self.assertRaises(RuntimeError):
                supervise(self.run, self.spec, "fixture", "build", {})
        ledger = read_json(control_root(self.run) / "ledger.json")
        self.assertEqual(ledger["events"][0]["charged_seconds"], 625)
        with self.assertRaisesRegex(ValueError, "Uncertain"):
            inspect_control(self.run, self.profile, content_hash(self.spec))

    def test_reset_journal_cannot_hide_existing_event(self):
        """Erasing events in the ledger differs from the durable operation directory inventory."""
        with patch("materiasim.runtime.control.watch", side_effect=self.fake_operation):
            supervise(self.run, self.spec, "fixture", "build", {})
        target = control_root(self.run) / "ledger.json"
        value = read_json(target)
        value["events"] = []
        write_json(target, value)
        with self.assertRaisesRegex(ValueError, "differs"):
            inspect_control(self.run, self.profile, content_hash(self.spec))

    def test_low_disk_stops_before_worker(self):
        """Disk refusal creates only an admission journal, never a native process or a Run."""
        with patch("shutil.disk_usage", return_value=shutil_disk(1)), \
                patch("materiasim.runtime.control.watch") as worker:
            with self.assertRaisesRegex(ValueError, "allowance exhausted"):
                supervise(self.run, self.spec, "fixture", "build", {})
            worker.assert_not_called()
        self.assertFalse(self.run.exists())


def shutil_disk(free):
    """Create only the disk-query interface consumed by admission tests."""
    from collections import namedtuple
    return namedtuple("Disk", "total used free")(1024, 1023, free)


if __name__ == "__main__":
    unittest.main()
