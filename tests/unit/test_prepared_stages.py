"""Compiled-stage provenance and handoff rejection tests using explicitly synthetic files."""

import copy
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from materiasim.engines.gromacs.compile import compile_stage, prepare_stage, verify_native_prepared
from materiasim.engines.gromacs.stage import execute_stage
from materiasim.engines.prepared import read_prepared, validate_prepared
from materiasim.storage import inventory, read_json, sha256, write_json


class PreparedStageTests(unittest.TestCase):
    """Exercise real handoff validators without presenting mock grompp output as a simulation."""

    def setUp(self):
        """Allocate bounded private text fixtures with an explicit native identity and initial stage."""
        temporary = tempfile.TemporaryDirectory(prefix="materiasim-prepared-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.engine = dict(sha256="fixture", version="fixture", platform="fixture")
        self.stage = dict(id="em", type="minimization", input=dict(stage_id=None, kind="coordinates"),
                          mdp="em.mdp", steps=5, velocities="none", seed=None, time_origin_ps=0, step_origin=0)
        write_json(self.root / "inputs/library.json", dict(fixture=True))
        write_json(self.root / "build/system.top", dict(fixture="not a topology"))
        write_json(self.root / "build/solvated.gro", dict(fixture="not coordinates"))
        (self.root / "build/em.mdp").write_text("pbc=xyz\nintegrator=steep\nnsteps=5\n")

    def native_compile(self, engine, args, cwd, record, inputs):
        """Write distinguishable synthetic outputs at the paths passed by the real compiler adapter."""
        for option in ("-o", "-po", "-pp"):
            write_json(Path(args[args.index(option) + 1]), dict(fixture=option))

    def compile(self):
        """Run actual preparation bookkeeping around a synthetic native command result."""
        with patch("materiasim.engines.gromacs.compile.command", side_effect=self.native_compile):
            return compile_stage(self.root, self.stage, self.engine, self.root / "attempts/build")

    def replace_record(self, prepared):
        """Alter only an isolated test seal to test independent semantic checks, never real Run evidence."""
        path = self.root / "stages/em/stage.json"
        seal = read_json(path)
        seal["preparation"] = asdict(prepared)
        write_json(path, seal)

    def test_preparation_roundtrip_and_no_recompile(self):
        """A persisted preparation is reused without tool calls or rewriting its input closure."""
        prepared = self.compile()
        self.assertEqual(read_prepared(self.root, "em"), prepared)
        self.assertIn("inputs/library.json", prepared.dependency_hashes)
        self.assertEqual(prepared.effective_parameters["nsteps"], "5")
        before = inventory(self.root, ["inputs", "build", "stages"])
        with patch("materiasim.engines.gromacs.compile.command") as command:
            self.assertEqual(prepare_stage(self.root, self.stage, self.engine, self.root / "unused"), prepared)
        command.assert_not_called()
        self.assertEqual(before, inventory(self.root, ["inputs", "build", "stages"]))

    def test_stage_or_engine_identity_cannot_change(self):
        """A prepared TPR cannot be reused under different stage goals or native engine identity."""
        prepared = self.compile()
        with self.assertRaisesRegex(ValueError, "requested engine/protocol"):
            validate_prepared(self.root, dict(self.stage, steps=6), "gromacs", prepared)
        with self.assertRaisesRegex(ValueError, "engine identity changed"):
            verify_native_prepared(self.root, self.stage, dict(self.engine, version="changed"), prepared)

    def test_tampered_compiled_input_is_rejected_before_mdrun(self):
        """A changed TPR never reaches the native execution command."""
        prepared = self.compile()
        (self.root / "stages/em/input.tpr").write_text("changed fixture")
        with patch("materiasim.engines.gromacs.stage.command") as command:
            with self.assertRaisesRegex(ValueError, "Frozen artifact changed"):
                execute_stage(self.root, prepared, self.engine, self.root / "attempt", 2, 10)
        command.assert_not_called()

    def test_frozen_library_addition_is_rejected(self):
        """A newly visible conditional include cannot evade the recorded compiler input closure."""
        prepared = self.compile()
        write_json(self.root / "inputs/new.json", dict(fixture=True))
        with self.assertRaisesRegex(ValueError, "dependency closure changed"):
            verify_native_prepared(self.root, self.stage, self.engine, prepared)

    def test_changed_parameters_and_formats_are_rejected(self):
        """Self-consistent JSON cannot claim different effective parameters or native input formats."""
        original = self.compile()
        inputs = copy.deepcopy(original.inputs)
        inputs["coordinates"]["format"] = "pdb"
        for changed, message in ((replace(original, effective_parameters={"nsteps": "9"}), "effective parameters"),
                                 (replace(original, inputs=inputs), "input roles")):
            with self.subTest(message=message):
                self.replace_record(changed)
                with self.assertRaisesRegex(ValueError, message):
                    verify_native_prepared(self.root, self.stage, self.engine, changed)

    def test_changed_input_during_compilation_does_not_get_sealed(self):
        """Compiler success cannot bless dependencies modified while the process was running."""
        def changed(engine, args, cwd, record, inputs):
            """Simulate native success concurrent with an external frozen-input mutation."""
            self.native_compile(engine, args, cwd, record, inputs)
            (self.root / "inputs/library.json").write_text("changed")
        with patch("materiasim.engines.gromacs.compile.command", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "Frozen artifact changed"):
                compile_stage(self.root, self.stage, self.engine, self.root / "attempt")
        self.assertFalse((self.root / "stages/em/stage.json").exists())
        self.assertTrue((self.root / "stages/em/input.tpr").exists())

    def predecessor(self, status="completed"):
        """Write explicit prior-state fixtures and select checkpoint inheritance for a second stage."""
        folder = self.root / "stages/prior"
        for name in ("md.gro", "md.cpt"):
            write_json(folder / name, dict(fixture=name))
        hashes = {f"stages/prior/{name}": sha256(folder / name) for name in ("md.gro", "md.cpt")}
        write_json(folder / "stage.json", dict(status=status, outputs=hashes))
        self.stage["input"] = dict(stage_id="prior", kind="checkpoint")

    def test_checkpoint_handoff_is_explicit_and_hashed(self):
        """A selected prior checkpoint becomes a compiler argument and a frozen dependency."""
        self.predecessor()
        with patch("materiasim.engines.gromacs.compile.command", side_effect=self.native_compile) as command:
            prepared = compile_stage(self.root, self.stage, self.engine, self.root / "attempt")
        args = command.call_args.args[1]
        self.assertEqual(args[args.index("-t") + 1], self.root / "stages/prior/md.cpt")
        self.assertEqual(prepared.inputs["checkpoint"]["format"], "gromacs_checkpoint")
        self.assertIn("stages/prior/md.cpt", prepared.dependency_hashes)

    def test_unfinished_predecessor_is_rejected_before_compile(self):
        """An available checkpoint from an unfinished predecessor is not permission to advance."""
        self.predecessor(status="interrupted")
        with patch("materiasim.engines.gromacs.compile.command") as command:
            with self.assertRaisesRegex(ValueError, "completed predecessor"):
                compile_stage(self.root, self.stage, self.engine, self.root / "attempt")
        command.assert_not_called()
        self.assertFalse((self.root / "stages/em").exists())

    def test_predecessor_checkpoint_tampering_is_rejected(self):
        """A prior checkpoint must match its own output seal, not merely receive a new hash."""
        self.predecessor()
        (self.root / "stages/prior/md.cpt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "Predecessor state differs"):
            self.compile()

    def test_missing_contract_is_not_backfilled(self):
        """An older stage without preparation remains untouched and cannot enter the new executor."""
        write_json(self.root / "stages/em/stage.json", dict(status="prepared"))
        before = inventory(self.root, ["stages"])
        with self.assertRaisesRegex(ValueError, "no compiled-input contract"):
            prepare_stage(self.root, self.stage, self.engine, self.root / "attempt")
        self.assertEqual(before, inventory(self.root, ["stages"]))

    def test_unknown_version_and_path_escape_are_rejected(self):
        """Unknown contract semantics and traversing paths cannot reach native input lookup."""
        original = self.compile()
        inputs = copy.deepcopy(original.inputs)
        inputs["coordinates"]["path"] = "../outside"
        for changed, message in ((replace(original, contract_version=2), "contract version"),
                                 (replace(original, inputs=inputs), "Unsafe artifact path")):
            with self.subTest(message=message):
                self.replace_record(changed)
                with self.assertRaisesRegex(ValueError, message):
                    validate_prepared(self.root, self.stage, "gromacs", changed)


if __name__ == "__main__":
    unittest.main()
