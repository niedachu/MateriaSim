"""Executable v3 contracts, exact native migration, source identity and bounded resource regressions."""

import copy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from materiasim.cli import main
from materiasim.engines.gromacs.specification import native_view, parameter_asset
from materiasim.engines.gromacs.mdp import stage_values
from materiasim.runtime.budget import execution_grant
from materiasim.runtime.identity import implementation, physical_hash, make_identities
from materiasim.runtime.state import source_identity, verify_execution, verify_run
from materiasim.specs.v3 import default_profile, validate_document
from materiasim.storage import content_hash, inventory, read_json, sha256, write_json
from materiasim.workflows.migration import load_executable, portable_document
from materiasim.workflows.validation import load_spec, validate_resolved
from materiasim.workflows.execute import execute

ROOT = Path(__file__).resolve().parents[2]


class V3Tests(unittest.TestCase):
    """Use existing parameter assets read-only; synthetic mutations live only in isolated directories."""

    def setUp(self):
        """Resolve the existing three-component example into an isolated v3 input document."""
        temporary = tempfile.TemporaryDirectory(prefix="materiasim-v3-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = ROOT / "examples/packed_mixture_water.json"
        self.spec, self.sources, self.identity, self.migration = load_executable(self.source)

    def test_all_existing_examples_migrate_without_physical_override(self):
        """The six executable v2 examples retain bytes and identical effective native MDP values."""
        for path in sorted((ROOT / "examples").glob("*.json")):
            if read_json(path)["schema_version"] != 2:
                continue
            before = sha256(path)
            old, sources, _ = load_spec(path)
            current, new_sources, _, report = load_executable(path)
            self.assertEqual(sources, new_sources)
            self.assertEqual(sha256(path), before)
            self.assertEqual(report["source_schema"], 2)
            self.assertEqual(current["schema_version"], 3)
            for left, right in zip(old["protocol"]["stages"], current["protocol"]["stages"]):
                self.assertEqual(stage_values(sources[left["mdp"]], left),
                                 stage_values(sources[parameter_asset(right)], right))

    def test_portable_v3_roundtrip_preserves_identity(self):
        """Typed assets resolve after moving a self-contained v3 experiment, without original absolute paths."""
        folder = self.root / "input with spaces"
        (folder / "assets").mkdir(parents=True)
        for name, source in self.sources.items():
            shutil.copyfile(source, folder / "assets" / name)
        document = portable_document(self.spec, {name: "assets/" + name for name in self.sources})
        write_json(folder / "experiment.json", document)
        moved = self.root / "迁移 副本"
        shutil.copytree(folder, moved)
        result, _, identity, report = load_executable(moved / "experiment.json")
        self.assertEqual(result, self.spec)
        self.assertEqual(identity, self.identity)
        self.assertEqual(report["source_schema"], 3)
        self.assertEqual(report["transformations"], [])

    def test_migration_is_read_only_and_deterministic(self):
        """Preview does not query a native tool, invent provenance, or change source documents."""
        before = {item["path"]: sha256(item["path"]) for item in self.migration["documents"].values()}
        with patch("subprocess.run", side_effect=AssertionError("native tool queried")):
            other = load_executable(self.source)
        self.assertEqual(other[0], self.spec)
        self.assertEqual(other[3], self.migration)
        self.assertTrue(all(c["model"]["provenance"] == dict(status="not_provided", references=[]) for c in self.spec["components"]))
        self.assertEqual(before, {path: sha256(path) for path in before})

    def test_protocol_physics_conflict_is_rejected(self):
        """A neutral temperature/dt declaration cannot override conflicting native template values."""
        for key, value in (("timestep_ps", .001), ("temperature_k", [999]), ("pressure_bar", [100])):
            changed = copy.deepcopy(self.spec)
            changed["protocol"]["stages"][1]["physics"][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "physics/format conflicts"):
                validate_resolved(changed, self.sources)

    def test_missing_or_unknown_contract_fields_rejected(self):
        """Unknown science fields and omitted units do not receive inferred defaults."""
        changed = copy.deepcopy(self.spec)
        changed["extra"] = 1
        with self.assertRaises(ValueError):
            validate_document(changed)
        changed = copy.deepcopy(self.spec)
        del changed["protocol"]["stages"][1]["physics"]["timestep_ps"]
        with self.assertRaises(ValueError):
            validate_document(changed)

    def test_invalid_box_builder_and_gpu_are_not_capabilities(self):
        """Generic representations never imply a native unsupported combination is usable."""
        variants = []
        changed = copy.deepcopy(self.spec)
        changed["scenario"]["boundary"]["vectors_nm"][0][1] = .2
        variants.append(changed)
        changed = copy.deepcopy(self.spec)
        changed["scenario"]["builder"]["id"] = "polymer"
        variants.append(changed)
        changed = copy.deepcopy(self.spec)
        changed["execution_profile"]["device"] = "gpu"
        variants.append(changed)
        for changed in variants:
            with self.subTest(spec=changed["scenario"]["builder"]["id"]), self.assertRaises(ValueError):
                validate_resolved(changed, self.sources)

    def test_model_identity_cannot_be_changed_without_bundle_coverage(self):
        """Adding model metadata or changing declared resolution changes its exact bundle identity."""
        changed = copy.deepcopy(self.spec)
        changed["components"][0]["model"]["resolution"] = "coarse_grained"
        with self.assertRaisesRegex(ValueError, "exact model identities"):
            validate_document(changed)
        changed["interaction_bundle"]["model_hashes"] = {c["id"]: content_hash(c["model"]) for c in changed["components"]}
        with self.assertRaisesRegex(ValueError, "coarse-grained"):
            validate_resolved(changed, self.sources)

    def test_native_asset_format_and_library_path_rejected(self):
        """Format tags cannot hide native includes behind an uninspected extension or absolute library path."""
        changed = copy.deepcopy(self.spec)
        changed["protocol"]["files"][0]["format"] = "json"
        with self.assertRaisesRegex(ValueError, "format/name mismatch"):
            native_view(changed)
        changed = copy.deepcopy(self.spec)
        changed["interaction_bundle"]["engine_parameters"]["force_field"] = "/outside.ff"
        with self.assertRaises(ValueError):
            native_view(changed)

    def test_bad_v3_cli_has_machine_error(self):
        """Malformed asset-owner shapes fail as input errors rather than unhandled Python tracebacks."""
        changed = portable_document(self.spec, self.sources)
        changed["components"] = None
        path = self.root / "bad.json"
        write_json(path, changed)
        with redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(["validate", str(path)]), 1)
        self.assertEqual(json.loads(error.getvalue())["error"]["code"], "INVALID_SPEC")

    def test_analysis_and_resources_do_not_change_physical_identity(self):
        """Execution resources and analysis selection have separate identities from the modeled system."""
        changed = copy.deepcopy(self.spec)
        changed["analysis_requests"] = []
        changed["execution_profile"]["threads"] = 1
        self.assertEqual(physical_hash(changed), physical_hash(self.spec))
        changed["components"][0]["count"] += 1
        self.assertNotEqual(physical_hash(changed), physical_hash(self.spec))

    def test_execution_dependency_closure_separates_analysis(self):
        """An analysis edit leaves execution compatible; an imported compile/storage edit does not."""
        package = self.root / "package"
        shutil.copytree(ROOT / "src/materiasim", package, ignore=shutil.ignore_patterns("__pycache__"))
        baseline = implementation("execution", package)
        self.assertFalse(any(name.startswith("analysis/") for name in baseline))
        for name in ("engines/gromacs/compile.py", "runtime/budget.py", "storage.py"):
            self.assertIn(name, baseline)
        target = package / "analysis/hydration.py"
        target.write_text(target.read_text() + "\n# isolated analysis fixture\n")
        self.assertEqual(implementation("execution", package), baseline)
        target = package / "engines/gromacs/compile.py"
        target.write_text(target.read_text() + "\n# isolated compiler fixture\n")
        self.assertNotEqual(implementation("execution", package), baseline)

    def test_new_transitive_dependency_is_included(self):
        """A newly imported project helper must enter the executable closure instead of being silently omitted."""
        package = self.root / "package"
        shutil.copytree(ROOT / "src/materiasim", package, ignore=shutil.ignore_patterns("__pycache__"))
        target = package / "runtime/process.py"
        target.write_text(target.read_text() + "\nfrom materiasim.runtime.fixture_helper import value\n")
        (package / "runtime/fixture_helper.py").write_text("value = 1\n")
        self.assertIn("runtime/fixture_helper.py", implementation("execution", package))

    def test_run_budget_counts_attempts_and_refuses_reset(self):
        """Execution grants are finite and deleting the ledger cannot grant another attempt."""
        profile = default_profile()
        for action in ("run", "resume"):
            with execution_grant(self.root, profile, 10, action) as (attempt, seconds):
                self.assertTrue(attempt.is_dir())
                self.assertEqual(seconds, 10)
        before = inventory(self.root, ["attempts"])
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            with execution_grant(self.root, profile, 10, "resume"):
                self.fail("extra attempt admitted")
        self.assertEqual(before, inventory(self.root, ["attempts"]))
        # Mutate only the disposable ledger to exercise an attempted budget reset.
        write_json(self.root / "execution.json", dict(contract_version=1, events=[], active=None))
        with self.assertRaisesRegex(ValueError, "differs from existing attempts"):
            with execution_grant(self.root, profile, 10, "resume"):
                self.fail("reset admitted")

    def test_cumulative_time_and_uncertain_handoff_refuse_execution(self):
        """Spent wall time and an unclosed reservation cannot be refreshed by resume."""
        profile = default_profile()
        with execution_grant(self.root, profile, 10, "run"):
            record = read_json(self.root / "execution.json")
            self.assertEqual(record["events"][0]["charged_seconds"], 35)
        record["events"][0].update(charged_seconds=350, closed=True)
        record["active"] = None
        write_json(self.root / "execution.json", record)
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            with execution_grant(self.root, profile, 10, "resume"):
                self.fail("spent budget admitted")
        record["active"] = record["events"][0]["attempt"]
        write_json(self.root / "execution.json", record)
        with self.assertRaisesRegex(ValueError, "Uncertain"):
            with execution_grant(self.root, profile, 10, "resume"):
                self.fail("uncertain handoff admitted")

    def ready_metadata(self):
        """Create metadata-only identity fixtures; these JSON files are explicitly not a simulated system."""
        write_json(self.root / "build/resolved_system.json", dict(fixture="not a simulation"))
        write_json(self.root / "resolved_spec.json", self.spec)
        for name, record in self.migration["documents"].items():
            target = self.root / "provenance/source_documents" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(record["path"], target)
        write_json(self.root / "provenance/migration.json", self.migration)
        engine = dict(sha256="fixture", version="fixture", platform="fixture")
        write_json(self.root / "manifest.json", dict(schema_version=3, spec_hash=self.identity,
            engine=engine, implementation=source_identity(), identities=make_identities(self.root, self.spec, engine),
            hashes=inventory(self.root, ["inputs", "build", "provenance"])))
        write_json(self.root / "status.json", dict(status="ready"))

    def test_v3_execution_uses_scoped_identity_not_whole_package(self):
        """Read integrity is independent of current code; execution rejects only a changed executable closure."""
        self.ready_metadata()
        verify_run(self.root)
        with patch("materiasim.runtime.state.source_identity", return_value={"analysis/hydration.py": "changed"}):
            verify_execution(self.root)
        changed = dict(implementation("execution"), **{"storage.py": "changed"})
        with patch("materiasim.runtime.state.implementation", return_value=changed):
            with self.assertRaisesRegex(ValueError, "Implementation changed"):
                verify_execution(self.root)

    def test_v3_cannot_drop_prepared_evidence(self):
        """A new-format seal cannot pretend to be an old stage to evade the preparation requirement."""
        self.ready_metadata()
        paths = [f"stages/em/{name}" for name in ("input.tpr", "resolved.mdp", "processed.top")]
        for path in paths:
            write_json(self.root / path, dict(fixture="not native output"))
        write_json(self.root / "stages/em/stage.json", dict(stage_id="em", engine="gromacs", status="prepared",
                   hashes={path: sha256(self.root / path) for path in paths}))
        with self.assertRaisesRegex(ValueError, "v3 stage requires"):
            verify_run(self.root)

    def test_profile_conflicts_fail_before_engine_query(self):
        """An execution request cannot override frozen threads or raise the per-attempt wall limit."""
        self.ready_metadata()
        with patch("materiasim.workflows.execute.get_engine", side_effect=AssertionError("native query reached")):
            for kwargs in (dict(threads=1), dict(max_wall_seconds=181)):
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    execute(self.root, **kwargs)
        self.assertFalse((self.root / "attempts").exists())

    def test_migration_provenance_is_part_of_run_integrity(self):
        """Changing an original-source snapshot blocks integrity verification without changing scientific files."""
        self.ready_metadata()
        (self.root / "provenance/source_documents/experiment.json").write_text("changed fixture")
        with self.assertRaisesRegex(ValueError, "Frozen artifact changed"):
            verify_run(self.root)


if __name__ == "__main__":
    unittest.main()
