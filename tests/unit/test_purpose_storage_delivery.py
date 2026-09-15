"""Explicit review fixtures, copy-fault tests and agent envelopes; no scientific approvals."""

from copy import deepcopy
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from materiasim.cli import main
from materiasim.runtime.capacity import copy_budget, copy_file, copy_tree, preflight
from materiasim.runtime.family import launch, cleanup
from materiasim.specs.execution import cpu_profile, validate_profile
from materiasim.specs.purpose import target_hash, validate_environment, select_tool
from materiasim.storage import content_hash, inventory, read_json, sha256, write_json
from materiasim.workflows.migration import load_executable
from materiasim.workflows.validation import validate_resolved

ROOT = Path(__file__).resolve().parents[2]


def reviewed_fixture(root, purpose="model_validation", engine=None):
    """Build synthetic review evidence outside catalog; caller must never label it scientific approval."""
    spec, sources, _, _ = load_executable(ROOT / "examples/packed_zil_dry.json")
    spec["purpose"] = purpose
    spec["execution_profile"] = dict(cpu_profile(), contract_version=3, tools=dict(gmx="gmx", packmol="packmol"))
    spec["execution_profile"]["storage_bytes"] = 1073741824
    for stage in spec["protocol"]["stages"]:
        stage["sampling"] = dict(contract_version=1, log_steps=100, energy_steps=100, trajectory_steps=100)
    if purpose == "production":
        spec["interaction_bundle"]["validation_scope"] = "reviewed"
        for component in spec["components"]:
            component["role"] = "solute"
            component["model"].update(resolution="atomistic", provenance=dict(status="declared", references=["TEST FIXTURE ONLY"]))
        spec["interaction_bundle"]["model_hashes"] = {c["id"]: content_hash(c["model"]) for c in spec["components"]}
    engine = engine or dict(platform="darwin", version="fixture", sha256="0" * 64)
    policy = dict(contract_version=1, intent="TEST FIXTURE: verify software, not material validity",
                  reviewer="TEST FIXTURE ONLY", reviewed_utc="2026-09-15T00:00:00+00:00", target_hash=target_hash(spec),
                  environment=dict(platform=engine["platform"], engine_version=engine["version"], engine_sha256=engine["sha256"]),
                  files=[], evidence={})
    roles = ("parameter_review", "protocol_review", "applicability_validation" if purpose == "production" else "validation_design")
    for role in roles:
        name = "fixture-" + role + ".json"
        path = root / name
        write_json(path, dict(contract_version=1, kind=role, decision="accepted", target_hash=policy["target_hash"],
                              reviewer=policy["reviewer"], basis="Synthetic SOFTWARE TEST only",
                              limitations="Not a scientific review; do not use for material conclusions"))
        sources[name] = path
        policy["files"].append(dict(name=name, format="json", sha256=sha256(path)))
        policy["evidence"][role] = name
    spec["purpose_policy"] = policy
    return spec, sources


class PurposeStorageTests(unittest.TestCase):
    """Verify new contracts on isolated metadata and existing read-only molecular assets."""

    def setUp(self):
        """Allocate isolated evidence; originals and catalog are never written."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def test_reviewed_purposes_validate_without_tools(self):
        """Both review branches consume real strict shapes without probing or executing an engine."""
        for purpose in ("model_validation", "production"):
            with self.subTest(purpose=purpose):
                spec, sources = reviewed_fixture(self.root / purpose, purpose)
                with patch("subprocess.run", side_effect=AssertionError("tool invoked")):
                    validate_resolved(spec, sources)

    def test_engineering_bundle_cannot_enter_production(self):
        """Changing only the purpose and its review hash cannot promote engineering-only inputs."""
        spec, sources = reviewed_fixture(self.root, "production")
        spec["interaction_bundle"]["validation_scope"] = "engineering_only"
        spec["purpose_policy"]["target_hash"] = target_hash(spec)
        with self.assertRaisesRegex(ValueError, "engineering_only"):
            validate_resolved(spec, sources)

    def test_scope_changes_and_evidence_mutation_rejected(self):
        """Protocol, count and evidence bytes are all bound to the explicit design review."""
        original, sources = reviewed_fixture(self.root)
        for change in ("count", "steps", "sampling"):
            spec = deepcopy(original)
            if change == "count":
                spec["components"][0]["count"] += 1
            elif change == "steps":
                spec["protocol"]["stages"][-1]["steps"] += 1
            else:
                spec["protocol"]["stages"][-1]["sampling"]["trajectory_steps"] = 50
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "physical design"):
                validate_resolved(spec, sources)
        name = original["purpose_policy"]["evidence"]["parameter_review"]
        write_json(sources[name], dict(changed=True))
        with self.assertRaisesRegex(ValueError, "asset changed"):
            validate_resolved(original, sources)

    def test_non_smoke_targets_keep_explicit_sampling(self):
        """Larger targets are legal only with reviewed scope; sampling is not reset to smoke defaults."""
        from materiasim.engines.gromacs.mdp import stage_values
        from materiasim.engines.gromacs.specification import parameter_asset
        spec, sources = reviewed_fixture(self.root)
        stage = spec["protocol"]["stages"][-1]
        stage["steps"] = 4000
        stage["sampling"]["trajectory_steps"] = 200
        values, changes = stage_values(sources[parameter_asset(stage)], stage)
        self.assertEqual(values["nsteps"], "4000")
        self.assertEqual(values["nstxout-compressed"], "200")
        from materiasim.engines.gromacs.specification import validate_native_protocol
        validate_native_protocol(spec, sources)
        spec["purpose"] = "engineering_smoke"
        with self.assertRaises(ValueError):
            validate_native_protocol(spec, sources)

    def test_minimization_sampling_and_capacity_are_explicit(self):
        """EM output intervals are consumed and its possible frames participate in admission estimates."""
        from materiasim.engines.gromacs.mdp import stage_values
        from materiasim.engines.gromacs.specification import parameter_asset
        from materiasim.specs.purpose import output_estimate
        spec, sources = reviewed_fixture(self.root)
        stage = spec["protocol"]["stages"][0]
        before = output_estimate(spec)
        stage["sampling"].update(log_steps=50, energy_steps=50, trajectory_steps=50)
        values, _ = stage_values(sources[parameter_asset(stage)], stage)
        self.assertEqual([values[k] for k in ("nstlog", "nstenergy", "nstxout-compressed")], ["50"] * 3)
        self.assertGreater(output_estimate(spec), before)

    def test_generation_index_detects_omissions_and_mutations(self):
        """Independent saved generations cannot disappear from the seal or change their saved bytes."""
        from materiasim.runtime.state import verify_stage_inventory
        for name in ("input.tpr", "resolved.mdp", "processed.top"):
            write_json(self.root / "stages/em" / name, dict(fixture=True))
        hashes = inventory(self.root, ["stages/em"])
        directory = "attempts/run-fixture/outputs-em"
        write_json(self.root / directory / "md.log", dict(fixture=True))
        generation = dict(contract_version=1, directory=directory, hashes=inventory(self.root, [directory]))
        seal = dict(stage_id="em", engine="gromacs", status="prepared", hashes=hashes, archive_generations=[generation])
        write_json(self.root / "stages/em/stage.json", seal)
        verify_stage_inventory(self.root, "em", seal)
        with self.assertRaisesRegex(ValueError, "index differs"):
            verify_stage_inventory(self.root, "em", dict(seal, archive_generations=[]))
        write_json(self.root / directory / "md.log", dict(changed=True))
        with self.assertRaisesRegex(ValueError, "Frozen artifact changed"):
            verify_stage_inventory(self.root, "em", seal)

    def test_archive_entry_paths_are_exclusive(self):
        """Malformed roles, traversal and overlapping trees never reach archive input verification."""
        from materiasim.workflows.archive import validate_entries
        (self.root / "runs/one").mkdir(parents=True)
        entry = dict(role="run", original="/original/one", path="runs/one")
        validate_entries(self.root, [entry])
        for changed in ([entry, dict(entry)], [dict(entry, path="../outside")], [dict(entry, role="unknown")]):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_entries(self.root, changed)

    def test_cli_io_errors_are_machine_readable(self):
        """Every public Run evidence entry rejects absent input as a JSON error, without creating outputs."""
        for action in ("status", "report", "run", "resume", "verify-archive"):
            err = io.StringIO()
            with self.subTest(action=action), contextlib.redirect_stderr(err):
                self.assertEqual(main(["--json-envelope", action, str(self.root / "missing")]), 1)
            self.assertIn("code", json.loads(err.getvalue())["error"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_environment_tools_and_budget_are_not_silently_replaced(self):
        """Unknown engine, conflicting CLI tools and inadequate output budget all reject."""
        spec, sources = reviewed_fixture(self.root)
        with self.assertRaisesRegex(ValueError, "environment"):
            validate_environment(spec, dict(platform="linux", version="fixture", sha256="0" * 64))
        self.assertEqual(select_tool(spec["execution_profile"], "gmx"), "gmx")
        with self.assertRaisesRegex(ValueError, "CLI tool"):
            select_tool(spec["execution_profile"], "gmx", "other-gmx")
        spec["execution_profile"]["storage_bytes"] = 1048576
        with self.assertRaisesRegex(ValueError, "output estimate"):
            validate_resolved(spec, sources)

    def test_profile_v3_resources_remain_finite(self):
        """A finite larger allocation is supported; invalid or implicit tools are not."""
        profile = dict(cpu_profile(), contract_version=3, tools=dict(gmx="gmx", packmol="packmol"),
                       max_wall_seconds=3600, total_wall_seconds=7200, workflow_seconds=10800)
        validate_profile(profile)
        for key, value in (("max_wall_seconds", float("inf")), ("storage_bytes", -1), ("tools", {})):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_profile(dict(profile, **{key: value}))

    def test_copy_refusal_precedes_destination_creation(self):
        """Measured copy bytes include existing generations and reserve free disk."""
        source = self.root / "source"
        source.write_bytes(b"12345678")
        target = self.root / "out"
        with copy_budget([self.root], 10, 0), self.assertRaisesRegex(ValueError, "storage allowance"):
            copy_file(source, target)
        self.assertFalse(target.exists())
        disk = type("Disk", (), {"free": 7})()
        with patch("shutil.disk_usage", return_value=disk), self.assertRaisesRegex(ValueError, "free bytes"):
            copy_file(source, target)
        self.assertFalse(target.exists())

    def test_copy_is_independent_and_does_not_overwrite(self):
        """Copied evidence is not a mutable hardlink, and an existing destination is preserved."""
        source = self.root / "source"
        source.write_bytes(b"original")
        target = self.root / "copy"
        copy_file(source, target)
        source.write_bytes(b"changed")
        self.assertEqual(target.read_bytes(), b"original")
        with self.assertRaises(FileExistsError):
            copy_file(source, target)
        self.assertEqual(target.read_bytes(), b"original")

    def test_copy_source_change_and_symlink_tree_rejected(self):
        """A changing source cannot publish an accepted snapshot; links cannot escape copy admission."""
        source = self.root / "source"
        source.mkdir()
        (source / "data").write_bytes(b"data")
        (source / "link").symlink_to(source / "data")
        with self.assertRaisesRegex(ValueError, "link"):
            copy_tree(source, self.root / "copy")
        target = self.root / "copy-file"
        with patch("materiasim.runtime.capacity.sha256", side_effect=["first", "changed"]), self.assertRaisesRegex(ValueError, "Source changed"):
            copy_file(source / "data", target)

    def test_analysis_namespaces_keep_legacy_and_failed_generations(self):
        """Operation folders are flattened explicitly; empty or malformed evidence is rejected."""
        from materiasim.analysis.locations import generations
        (self.root / "legacy").mkdir()
        (self.root / "operation-abc/new").mkdir(parents=True)
        self.assertEqual(set(generations(self.root)), {self.root / "legacy", self.root / "operation-abc/new"})
        (self.root / "operation-empty").mkdir()
        with self.assertRaisesRegex(ValueError, "Empty"):
            generations(self.root)

    def test_agent_envelope_and_missing_arguments(self):
        """Read-only discovery and parse failures use actual versioned JSON, not invented tool names."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(main(["--json-envelope", "tools"]), 0)
        record = json.loads(out.getvalue())
        self.assertTrue(record["ok"])
        self.assertFalse(next(x for x in record["result"]["actions"] if x["action"] == "archive")["read_only"])
        with contextlib.redirect_stderr(err):
            self.assertEqual(main(["archive", "missing"]), 1)
        self.assertEqual(json.loads(err.getvalue())["error"]["code"], "INVALID_ARGUMENT")

    def test_owned_group_cleanup_stops_lingering_descendant(self):
        """A real isolated child that outlives its parent cannot continue writing after owned cleanup."""
        heartbeat = self.root / "heartbeat"
        script = "import pathlib,time; p=pathlib.Path(" + repr(str(heartbeat)) + ");\nwhile True:\n p.write_text(str(time.monotonic())); time.sleep(.02)"
        parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(script) + "]); time.sleep(.2)"
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MATERIASIM_MANAGED_GROUP", None)
            process, owner = launch([sys.executable, "-c", parent], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                process.wait(timeout=5)
            finally:
                cleanup(process, owner)
        self.assertTrue(heartbeat.exists())
        before = heartbeat.read_bytes()
        time.sleep(.1)
        self.assertEqual(before, heartbeat.read_bytes())


if __name__ == "__main__":
    unittest.main()
