"""Real component-boundary consumers and negative contracts without new scientific models."""

import ast
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import Mock, patch

from materiasim.analysis.registry import ANALYZERS, get_analyzer, validate_requests
from materiasim.builders.contracts import validate_result
from materiasim.capabilities import capabilities
from materiasim.cli import main
from materiasim.engines.contracts import BuildResult, PreparedStage, StageEvidence
from materiasim.engines.registry import ENGINES, get_engine
from materiasim.errors import MateriaSimError
from materiasim.scenarios.registry import SCENARIOS
from materiasim.storage import read_json, sha256, write_json
from materiasim.workflows.analysis import analyze
from materiasim.workflows.execute import execute, execute_protocol
from materiasim.workflows.migration import load_executable
from materiasim.workflows.validation import load_spec, validate_resolved

ROOT = Path(__file__).resolve().parents[2]


class ComponentBoundaryTests(unittest.TestCase):
    """Test registry-backed workflows, preserved guards and machine-readable failure contracts."""

    def setUp(self):
        """Create private test files and resolve one unchanged real engineering configuration."""
        temporary = tempfile.TemporaryDirectory(prefix="materiasim-boundary-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.spec, self.sources, self.digest = load_spec(ROOT / "examples/packed_zil_water.json")

    def test_specs_do_not_import_implementations(self):
        """Pure configuration files cannot acquire engine, algorithm or workflow dependencies."""
        forbidden = ("materiasim.engines", "materiasim.scenarios", "materiasim.analysis",
                     "materiasim.workflows", "materiasim.research", "materiasim.cli")
        for path in (ROOT / "src/materiasim/specs").glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                names = ([node.module or ""] if isinstance(node, ast.ImportFrom) else
                         [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                self.assertFalse(any(name.startswith(forbidden) for name in names), (path, names))

    def test_capability_queries_use_actual_registrations(self):
        """Discovery lists exactly the implemented registrations without launching subprocesses."""
        with patch("subprocess.run", side_effect=AssertionError("query started a process")):
            report = capabilities()
        self.assertEqual({s["id"] for s in report["scenarios"]}, set(SCENARIOS))
        self.assertEqual({s["id"] for s in report["analysis"]}, set(ANALYZERS))
        self.assertEqual({s["id"] for s in report["engines"]}, set(ENGINES))
        self.assertEqual(report["environment"], "not_checked")
        self.assertEqual(report["scientific_quality"], "not_assessed")

    def test_registered_engine_validator_is_consumed(self):
        """Static applicability must run the selected backend's validator, not a duplicate branch."""
        validate = Mock(side_effect=ValueError("fixture backend rejection"))
        with patch.dict(ENGINES, gromacs=replace(get_engine("gromacs"), validate=validate)):
            with self.assertRaisesRegex(ValueError, "fixture backend rejection"):
                validate_resolved(self.spec, self.sources)
        validate.assert_called_once_with(self.spec, self.sources)

    def test_registered_scenario_validator_is_consumed(self):
        """The same scenario advertised by discovery supplies its actual source guard."""
        check = Mock(side_effect=ValueError("fixture scenario rejection"))
        recipe = replace(SCENARIOS["packed_liquid"], validate=check)
        with patch.dict(SCENARIOS, packed_liquid=recipe):
            with self.assertRaisesRegex(ValueError, "fixture scenario rejection"):
                validate_resolved(self.spec, self.sources)
        check.assert_called_once_with(self.spec, self.sources)

    def test_unknown_implementations_have_stable_codes(self):
        """Unimplemented engines and analyzers fail rather than receiving dummy behavior."""
        for getter, value in ((get_engine, "lammps"), (get_analyzer, "unknown_metric")):
            with self.subTest(value=value), self.assertRaises(MateriaSimError) as caught:
                getter(value)
            self.assertEqual(caught.exception.code, "UNSUPPORTED_COMBINATION")

    def test_analyzer_config_cannot_bypass_method_check(self):
        """Separating request shape and method validation preserves cutoff and selection rejection."""
        requests = copy.deepcopy(self.spec["analysis_requests"])
        requests[0]["config"]["cutoff_nm"] = -1
        with self.assertRaises(ValueError):
            validate_requests(requests, self.spec["protocol"]["stages"])
        requests[0]["kind"] = "hydration_contacts"
        requests[0]["config"] = {"water_oxygen_selection": "", "sites": {}}
        with self.assertRaises(ValueError):
            validate_requests(requests, self.spec["protocol"]["stages"])

    def test_execution_consumes_registered_stage_evidence(self):
        """The lifecycle passes the actual registered preparation to execution after verifying it."""
        write_json(self.root / "status.json", dict(status="ready"))
        self.spec, _, _, _ = load_executable(ROOT / "examples/packed_zil_water.json")
        engine = dict(sha256="fixture", version="fixture", platform="fixture")
        inspect = Mock(return_value=engine)
        run_stage = Mock(return_value=StageEvidence(True, False))
        prepare = Mock(side_effect=self.prepare_fixture)
        adapter = replace(get_engine("gromacs"), inspect=inspect, prepare_stage=prepare, run_stage=run_stage)
        with patch.dict(ENGINES, gromacs=adapter), patch(
                "materiasim.workflows.execute.verify_execution",
                return_value=(self.spec, dict(engine=engine))):
            result = execute(self.root)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(run_stage.call_count, len(self.spec["protocol"]["stages"]))
        self.assertEqual(prepare.call_count, run_stage.call_count)
        for call in run_stage.call_args_list:
            self.assertIsInstance(call.args[1], PreparedStage)
            self.assertEqual(call.args[1].engine_identity, engine)
        self.assertEqual(result["scientific_quality"], "not_assessed")

    def prepare_fixture(self, root, stage, engine, attempt):
        """Persist a test-only compiled contract, not real native or scientific output."""
        path = f"stages/{stage['id']}/fixture.json"
        write_json(root / path, dict(fixture=True))
        item = dict(path=path, sha256=sha256(root / path), format="json")
        hashes = {path: item["sha256"]}
        prepared = PreparedStage("gromacs", stage, {"source": item}, {"compiled_input": item},
                                 {}, hashes, engine)
        write_json(root / f"stages/{stage['id']}/stage.json",
                   dict(status="prepared", hashes=hashes, preparation=asdict(prepared)))
        return prepared

    def test_compilation_time_is_charged_before_execution(self):
        """A preparation that consumes the wall budget cannot start a fresh mdrun allowance."""
        write_json(self.root / "status.json", dict(status="ready"))
        self.spec, _, _, _ = load_executable(ROOT / "examples/packed_zil_water.json")
        engine = dict(sha256="fixture", version="fixture", platform="fixture")
        run_stage = Mock()
        adapter = replace(get_engine("gromacs"), inspect=Mock(return_value=engine),
                          prepare_stage=self.prepare_fixture, run_stage=run_stage)
        with patch("materiasim.workflows.execute.time.monotonic", side_effect=[0, 0, 2]):
            result = execute_protocol(self.root, self.spec, adapter, engine, self.spec["execution_profile"],
                                      self.root / "attempts/run-fixture", 1, self.spec["protocol"]["stages"][-1]["id"])
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual(result["reason"], "wall_budget")
        run_stage.assert_not_called()

    def builder_fixture(self):
        """Create explicit non-scientific builder records to exercise the persisted handoff check."""
        mapping = dict(counts={"ZIL": 2}, atom_count=78, charge_e=0, box_nm=[4.5] * 3)
        write_json(self.root / "build/atom_mapping.json", mapping)
        write_json(self.root / "build/coordinates.json", {"fixture": "not coordinates"})
        write_json(self.root / "build/topology.json", {"fixture": "not topology"})
        system = dict(mapping, engine="gromacs")
        for role, name in (("mapping", "atom_mapping.json"), ("coordinates", "coordinates.json"),
                           ("topology", "topology.json")):
            path = "build/" + name
            system[role] = dict(path=path, sha256=sha256(self.root / path), format="json")
        write_json(self.root / "build/resolved_system.json", system)
        return BuildResult(mapping, system)

    def test_builder_handoff_must_match_persisted_evidence(self):
        """A returned count or artifact cannot override what the builder actually persisted."""
        result = self.builder_fixture()
        validate_result(self.root, self.spec, result)
        changed = copy.deepcopy(result.mapping)
        changed["atom_count"] += 1
        with self.assertRaisesRegex(ValueError, "persisted handoff"):
            validate_result(self.root, self.spec, BuildResult(changed, result.system))
        write_json(self.root / "build/coordinates.json", {"changed": True})
        with self.assertRaises(ValueError):
            validate_result(self.root, self.spec, result)

    def test_analyzer_input_formats_are_enforced(self):
        """A method requiring another format cannot treat an XTC fixture as that format."""
        from materiasim.analysis.contracts import resolve_inputs
        stage = self.spec["protocol"]["stages"][-1]["id"]
        write_json(self.root / f"stages/{stage}/stage.json", dict(status="completed",
                   artifacts={"trajectory": dict(path=f"stages/{stage}/md.xtc", format="xtc", sha256="x")}))
        analyzer = replace(get_analyzer("component_contacts"), inputs=(("trajectory", "dcd"),))
        with self.assertRaisesRegex(ValueError, "format"):
            resolve_inputs(self.root, self.spec, stage, analyzer)

    def test_registered_analysis_receives_private_role_files(self):
        """A test-only analyzer runs through the real dispatcher without mutating source files."""
        stage = self.spec["protocol"]["stages"][-1]["id"]
        source = self.root / "run"
        output = self.root / "analyses"
        write_json(source / "status.json", dict(status="completed"))
        write_json(source / "manifest.json", dict(fixture=True))
        write_json(source / "build/atom_mapping.json", dict(fixture=True))
        path = f"stages/{stage}/md.gro"
        write_json(source / path, dict(fixture="not molecular coordinates"))
        digest = sha256(source / path)
        write_json(source / f"stages/{stage}/stage.json", dict(status="completed",
                   artifacts={"coordinates": dict(path=path, format="gro", sha256=digest)},
                   outputs={path: digest}))
        identity = dict(run_id="fixture_run", spec_hash=self.digest)

        def calculate(inputs, config, folder, provenance):
            """Assert private input ownership and return clearly unassessed fixture metadata."""
            self.assertEqual(set(inputs), {"coordinates", "mapping"})
            self.assertTrue(all(folder in p.parents for p in inputs.values()))
            return dict(identity, frames=2, time_range_ps=[0, 1], versions={"fixture": "1"},
                        scientific_quality="not_assessed")

        analyzer = replace(get_analyzer("component_contacts"), id="fixture_metric", calculate=calculate,
                           inputs=(("coordinates", "gro"), ("mapping", "json")))
        request = dict(self.spec["analysis_requests"][0], kind="fixture_metric")
        before = {p.relative_to(source): sha256(p) for p in source.rglob("*") if p.is_file()}
        with patch.dict(ANALYZERS, fixture_metric=analyzer), patch(
                "materiasim.workflows.analysis.verify_run", return_value=(self.spec, identity)):
            outputs = analyze(source, output, request)
        report = read_json(Path(outputs[0]) / "report.json")
        self.assertEqual(report["result_contract"]["method"], "fixture_metric")
        self.assertEqual(before, {p.relative_to(source): sha256(p) for p in source.rglob("*") if p.is_file()})
        self.assertNotIn("fixture_metric", ANALYZERS)

    def test_argument_errors_are_json(self):
        """CLI syntax errors remain machine-readable and do not manufacture recovery permission."""
        for argv in ([], ["run"], ["run", "/absent", "--threads", "not-an-integer"]):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()) as error:
                code = main(argv)
                report = json.loads(error.getvalue())
            self.assertEqual(code, 1)
            self.assertEqual(report["error"]["code"], "INVALID_ARGUMENT")
            self.assertEqual(report["error"]["recoverability"], "not_assessed")

    def test_missing_spec_has_structured_error(self):
        """Missing input files report a resource failure, not a fake validated result."""
        with redirect_stderr(io.StringIO()) as error:
            code = main(["validate", str(self.root / "absent.json")])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(error.getvalue())["error"]["code"], "MISSING_RESOURCE")

    def test_capabilities_cli_is_read_only(self):
        """The actual command serializes the same registry-backed static report."""
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["capabilities"]), 0)
        self.assertEqual(json.loads(output.getvalue()), capabilities())

    def test_missing_native_tool_has_dependency_code(self):
        """A missing GROMACS executable differs from a missing input configuration file."""
        with redirect_stderr(io.StringIO()) as error:
            code = main(["doctor", "--gmx", str(self.root / "absent-gmx")])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(error.getvalue())["error"]["code"], "MISSING_DEPENDENCY")


if __name__ == "__main__":
    unittest.main()
