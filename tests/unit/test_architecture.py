"""Responsibility-boundary and actual subprocess regressions for architecture batch A."""

import ast
import copy
import json
import os
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from materiasim.builders.regions import validate_regions
from materiasim.engines.gromacs.coordinates import write_gro
from materiasim.engines.gromacs.mdp import validate_protocol
from materiasim.storage import read_json
from materiasim.engines.gromacs.command import command
from materiasim.specs.protocol import validate_stages
from materiasim.runtime.process import CommandFailed, run_command
from materiasim.workflows.validation import load_spec
from materiasim.runtime.state import source_identity
from materiasim.engines.gromacs.topology import gro_atoms

MODULE = Path(__file__).resolve().parents[2]


class ArchitectureTests(unittest.TestCase):
    """Verify extracted components independently and protect their actual integration boundaries."""

    def setUp(self):
        """Allocate a private directory for child processes and disposable coordinate files."""
        temporary = tempfile.TemporaryDirectory(prefix="materials-architecture-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.tool = dict(executable=sys.executable, version="test-python")

    def test_process_arguments_stdin_and_logs(self):
        """Spaces and Unicode stay literal arguments; input and separate logs survive a real child."""
        script = "import json,sys; print(json.dumps([sys.argv[1:],sys.stdin.read()])); print('diagnostic',file=sys.stderr)"
        record = self.root / "record 空格"
        result = run_command(self.tool, ["-B", "-c", script, "一个 argument", "$(not_a_shell)"],
                             self.root, record, seconds=5, stdin="input text")
        self.assertEqual(json.loads((record / "stdout.log").read_text()),
                         [["一个 argument", "$(not_a_shell)"], "input text"])
        self.assertEqual((record / "stderr.log").read_text(), "diagnostic\n")
        self.assertEqual(read_json(record / "command.json"), result)
        self.assertFalse(result["interrupted"])

    def test_generic_process_does_not_inject_gromacs_environment(self):
        """A packer-like child inherits the caller environment without synthetic GMXLIB settings."""
        script = "import os; print(os.environ.get('GMXLIB', 'absent'))"
        with patch.dict(os.environ, {}, clear=True):
            run_command(self.tool, ["-B", "-c", script], self.root, self.root / "record", seconds=5)
        self.assertEqual((self.root / "record/stdout.log").read_text().strip(), "absent")

    def test_gromacs_adapter_preserves_frozen_library_environment(self):
        """Only the GROMACS adapter injects frozen lookup and the existing backup policy."""
        script = "import json,os; print(json.dumps([os.environ['GMXLIB'],os.environ['GMX_MAXBACKUP']]))"
        inputs = self.root / "frozen inputs"
        command(self.tool, ["-B", "-c", script], self.root, self.root / "record", inputs, seconds=5)
        self.assertEqual(json.loads((self.root / "record/stdout.log").read_text()), [str(inputs.resolve()), "-1"])

    def test_process_failure_keeps_exit_evidence(self):
        """A nonzero child fails explicitly while retaining its return code and diagnostic log."""
        record = self.root / "failed"
        with self.assertRaisesRegex(RuntimeError, "failed \\(7\\)"):
            run_command(self.tool, ["-B", "-c", "import sys; print('failure',file=sys.stderr); sys.exit(7)"],
                        self.root, record, seconds=5)
        self.assertEqual(read_json(record / "command.json")["returncode"], 7)
        self.assertEqual((record / "stderr.log").read_text(), "failure\n")

    def test_process_record_cannot_be_reused(self):
        """An existing command record refuses a second process instead of overwriting old evidence."""
        record = self.root / "record"
        record.mkdir()
        with patch("materiasim.runtime.process.subprocess.Popen") as spawn:
            with self.assertRaises(FileExistsError):
                run_command(self.tool, [], self.root, record)
        spawn.assert_not_called()

    def test_timeout_restores_signal_handlers(self):
        """A real timed-out child is terminated and the caller's original handlers are restored."""
        previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        with self.assertRaises(RuntimeError):
            run_command(self.tool, ["-B", "-c", "import time; time.sleep(30)"], self.root,
                        self.root / "timeout", seconds=.15)
        self.assertTrue(read_json(self.root / "timeout/command.json")["interrupted"])
        self.assertEqual(previous, {sig: signal.getsignal(sig) for sig in previous})

    def test_signal_exit_one_is_not_generic_success(self):
        """A real child returning one after TERM retains typed failure metadata for native validation."""
        script = "import signal,time,sys; signal.signal(signal.SIGTERM, lambda s,f: sys.exit(1)); time.sleep(30)"
        with self.assertRaises(CommandFailed) as raised:
            run_command(self.tool, ["-B", "-c", script], self.root, self.root / "signal-one", seconds=.3)
        self.assertEqual(raised.exception.result["returncode"], 1)
        self.assertTrue(raised.exception.result["interrupted"])

    def test_stage_contract_does_not_read_mdp(self):
        """Linear stage validation works independently of engine-file parsing or file availability."""
        spec, _, _ = load_spec(MODULE / "examples/zil_smoke_v2.json")
        stages = copy.deepcopy(spec["protocol"]["stages"])
        for stage in stages:
            stage["mdp"] = "not_on_disk.mdp"
        with patch.object(Path, "read_text", side_effect=AssertionError("Unexpected file read")):
            validate_stages(stages)
        with self.assertRaisesRegex(ValueError, "declared protocol asset"):
            validate_protocol(stages, {})

    def test_engine_protocol_still_rejects_incompatible_mdp(self):
        """Separating stage contracts must not bypass integrator and velocity/continuation checks."""
        spec, sources, _ = load_spec(MODULE / "examples/zil_smoke_v2.json")
        wrong = self.root / "wrong.mdp"
        wrong.write_text("pbc=xyz\nintegrator=steep\n")
        name = spec["protocol"]["stages"][1]["mdp"]
        with self.assertRaisesRegex(ValueError, "Unsupported integrator"):
            validate_protocol(spec["protocol"]["stages"], dict(sources, **{name: wrong}))

    def test_region_contract_has_no_model_dependency(self):
        """Count and placement checks use explicit geometry, without requiring a topology or force field."""
        groups = [dict(id="region", component_id="A", count=2, min_nm=[0, 0, 0], max_nm=[3, 3, 3])]
        validate_regions({"A": 2}, groups, [3, 3, 3])
        with self.assertRaisesRegex(ValueError, "totals differ"):
            validate_regions({"A": 3}, groups, [3, 3, 3])

    def test_gro_writer_retains_order_and_nm(self):
        """Engine-owned serialization preserves the checked molecular order and nm coordinate scale."""
        path = self.root / "packed.gro"
        atoms = [dict(molecule_id="A:1", resname="A", name="C", xyz_nm=[.1, .2, .3]),
                 dict(molecule_id="A:2", resname="A", name="C", xyz_nm=[1.1, 1.2, 1.3])]
        write_gro(path, atoms, [3, 3, 3])
        result, box = gro_atoms(path)
        self.assertEqual([atom["xyz_nm"] for atom in result], [a["xyz_nm"] for a in atoms])
        self.assertEqual(box, [3, 3, 3])

    def test_dependency_direction(self):
        """Shared execution, region and stage contracts cannot import scientific engine modules."""
        for name in ("runtime/process.py", "builders/regions.py", "specs/protocol.py", "builders/packmol.py"):
            tree = ast.parse((MODULE / "src/materiasim" / name).read_text())
            imports = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            with self.subTest(module=name):
                self.assertFalse(any("gromacs" in item or "config_v2" in item for item in imports))
        tree = ast.parse((MODULE / "src/materiasim/workflows/analysis.py").read_text())
        self.assertFalse(any(isinstance(node, ast.ImportFrom) and node.module == "materiasim.specs.experiment"
                             for node in ast.walk(tree)))

    def test_nested_sources_are_frozen(self):
        """All new responsibility modules remain covered by strict recursive execution identity."""
        identity = source_identity()
        for name in ("runtime/process.py", "engines/gromacs/mdp.py", "engines/gromacs/parameters.py",
                     "engines/gromacs/coordinates.py", "builders/regions.py", "specs/analysis.py",
                     "specs/composition.py", "scenarios/packed.py"):
            self.assertIn(name, identity)


if __name__ == "__main__":
    unittest.main()
