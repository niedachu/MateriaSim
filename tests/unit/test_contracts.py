"""Versioned configuration, stage handoff and read-only history regression tests."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from materiasim.workflows.analysis import analyze, selected_requests
from materiasim.specs.analysis import analysis_requests
from materiasim.storage import content_hash, read_json, write_json
from materiasim.engines.gromacs.stage import assess_stage
from materiasim.engines.gromacs.mdp import mdp_values, stage_values, validate_protocol
from materiasim.runtime.records import stage_ids
from materiasim.workflows.validation import load_spec
from materiasim.runtime.state import verify_execution, verify_run
from tests.acceptance.verify_m1_evidence import compare_effective

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


class ContractTests(unittest.TestCase):
    """Exercise the implemented v2 subset without requiring an engine process."""

    def setUp(self):
        """Create isolated configurations while keeping real baseline assets read-only."""
        self.temporary = tempfile.TemporaryDirectory(prefix="materials-contract-")
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.spec, self.sources, self.identity = load_spec(EXAMPLES / "zil_smoke_v2.json")
        self.stages = copy.deepcopy(self.spec["protocol"]["stages"])

    def test_separate_contracts(self):
        """No model MDP/count fields remain, and protocol stages share a dynamics type."""
        model = self.spec["components"][0]["model"]
        self.assertNotIn("components", model)
        self.assertFalse(any(item["name"].endswith(".mdp") for item in model["files"]))
        self.assertEqual([s["type"] for s in self.stages].count("dynamics"), 3)
        self.assertEqual(content_hash(self.spec), self.identity)

    def test_repeated_types_and_renamed_ids(self):
        """Semantic behavior follows type/handoff, not familiar EM/NVT/production names."""
        for index, stage in enumerate(self.stages):
            stage["id"] = f"phase_{index}"
            stage["input"]["stage_id"] = None if index == 0 else f"phase_{index - 1}"
        validate_protocol(self.stages, self.sources)
        request = copy.deepcopy(self.spec["analysis_requests"][0])
        request["stage_id"] = "phase_2"
        analysis_requests([request], self.stages)

    def test_duplicate_stage_id(self):
        """Duplicate IDs cannot overwrite a previously compiled stage."""
        self.stages[1]["id"] = self.stages[0]["id"]
        with self.assertRaisesRegex(ValueError, "Duplicate stage ID"):
            validate_protocol(self.stages, self.sources)

    def test_wrong_handoff(self):
        """Skipping a predecessor or discarding inherited velocities is rejected."""
        for field, value in (("stage_id", "em"), ("kind", "coordinates")):
            stages = copy.deepcopy(self.stages)
            stages[2]["input"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_protocol(stages, self.sources)

    def test_velocity_seed_policy(self):
        """Velocity generation is explicit; later stages cannot silently reseed."""
        self.stages[2]["seed"] = 123
        with self.assertRaisesRegex(ValueError, "Only velocity generation"):
            validate_protocol(self.stages, self.sources)

    def test_optional_analysis(self):
        """No analysis requests is valid and dispatch selects no hidden hydration work."""
        self.spec["analysis_requests"] = []
        self.assertEqual(selected_requests(self.spec, None), [])

    def test_invalid_analysis_source(self):
        """An unknown or minimization stage cannot be used as a hydration trajectory."""
        for name in ("unknown", "em"):
            request = dict(self.spec["analysis_requests"][0], stage_id=name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                analysis_requests([request], self.stages)

    def test_nonzero_time_and_step_origins(self):
        """Derived MDP and checkpoint assessment include both tinit and init-step."""
        stage = dict(self.stages[1], time_origin_ps=10, step_origin=100)
        values, _ = stage_values(self.sources[stage["mdp"]], stage)
        self.assertEqual(values["tinit"], "10")
        self.assertEqual(values["init-step"], "100")
        folder = self.root / "stages/nvt"
        folder.mkdir(parents=True)
        write_json(self.root / "build/atom_mapping.json", dict(atom_count=10))
        (self.root / "build/nvt.mdp").write_text("pbc=xyz\ndt=0.002\n")
        for name in ("md.log", "md.xtc", "md.edr", "md.cpt"):
            (folder / name).write_text("unit fixture")
        with patch("materiasim.engines.gromacs.stage.checkpoint", return_value=dict(step=200, time_ps=10.4, atom_count=10)):
            evidence = assess_stage(self.root, stage, {})
        self.assertFalse(evidence["complete"])
        self.assertEqual(evidence["target_step"], 1100)
        self.assertEqual(evidence["target_time_ps"], 12.2)
        with patch("materiasim.engines.gromacs.stage.checkpoint", return_value=dict(step=200, time_ps=.4, atom_count=10)):
            with self.assertRaisesRegex(ValueError, "time does not match"):
                assess_stage(self.root, stage, {})

    def test_effective_physics_preserved(self):
        """Only explicitly documented duration/output/seed/time bookkeeping differs from source."""
        allowed = {"nsteps", "nstlog", "nstenergy", "nstxout-compressed", "gen-seed", "tinit", "init-step"}
        for stage in self.stages:
            before = mdp_values(self.sources[stage["mdp"]])
            after, changes = stage_values(self.sources[stage["mdp"]], stage)
            self.assertLessEqual(set(changes), allowed)
            self.assertEqual({k: v for k, v in before.items() if k not in allowed},
                             {k: v for k, v in after.items() if k not in allowed})

    def test_effective_comparison_keeps_active_seeds_strict(self):
        """Only inactive velocity seeds are reported separately; active seeds/dt remain strict."""
        old = {"gen-vel": "no", "gen-seed": "123", "dt": ".002"}
        report = compare_effective(old, dict(old, **{"gen-seed": "456"}))
        self.assertIn("gen-seed", report["inactive_seed_differences"])
        for changed in ({"gen-vel": "yes", "gen-seed": "456", "dt": ".002"},
                        {"gen-vel": "no", "gen-seed": "456", "dt": ".001"}):
            with self.subTest(changed=changed), self.assertRaises(AssertionError):
                compare_effective(old, changed)
        with self.assertRaises(AssertionError):
            compare_effective(dict(old, **{"gen-vel": "yes"}),
                              dict(old, **{"gen-vel": "yes", "gen-seed": "456"}))

    def test_unsupported_multi_component_rejected(self):
        """The scaffold cannot misreport multi-component assembly as implemented."""
        spec = read_json(EXAMPLES / "zil_smoke_v2.json")
        spec["components"] *= 2
        write_json(self.root / "spec.json", spec)
        with self.assertRaisesRegex(ValueError, "multi-component assembly"):
            load_spec(self.root / "spec.json")

    def history_fixture(self, version=1):
        """Create a minimal ready-state metadata fixture, not simulated scientific evidence."""
        spec = dict(schema_version=1) if version == 1 else self.spec
        write_json(self.root / "resolved_spec.json", spec)
        write_json(self.root / "manifest.json", dict(schema_version=version, spec_hash=content_hash(spec),
                                                   hashes={}, implementation={"old.py": "old"}))
        write_json(self.root / "status.json", dict(status="ready"))
        return spec

    def test_legacy_read_ignores_current_source_identity(self):
        """Reading old identity does not rewrite it, create attempts or obtain a writer lock."""
        self.history_fixture()
        before = sorted(self.root.rglob("*"))
        spec, _ = verify_run(self.root)
        self.assertEqual(stage_ids(spec), ["em", "nvt", "npt", "prod"])
        self.assertEqual(before, sorted(self.root.rglob("*")))
        with self.assertRaisesRegex(ValueError, "v1 is read-only"):
            verify_execution(self.root)
        self.assertFalse((self.root / ".writer.lock").exists())

    def test_changed_code_read_but_no_resume(self):
        """Historical v2 stays readable but is not admitted to the single v3 executor."""
        self.history_fixture(version=2)
        verify_run(self.root)
        with self.assertRaisesRegex(ValueError, "v2 is read-only"):
            verify_execution(self.root)

    def test_missing_completed_stage_rejected(self):
        """A completed status cannot conceal missing historical stage evidence."""
        self.history_fixture()
        write_json(self.root / "status.json", dict(status="completed"))
        with self.assertRaisesRegex(ValueError, "lacks sealed stage"):
            verify_run(self.root)

    def test_analysis_active_run_rejected_without_output(self):
        """Analysis does not auto-run an unfinished simulation or create source-side outputs."""
        self.history_fixture()
        with self.assertRaisesRegex(ValueError, "completed Run"):
            analyze(self.root, self.root / "new_analysis")
        self.assertFalse((self.root / "new_analysis").exists())


if __name__ == "__main__":
    unittest.main()
