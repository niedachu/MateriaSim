"""Fast regression checks; real GROMACS acceptance is documented separately."""

import json
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from materiasim.engines.gromacs.build import check_includes
from materiasim.engines.gromacs.stage import assess_stage, check_numerics, execute_stage
from materiasim.storage import contained, read_json, run_lock, sha256, verify_hashes, write_json
from materiasim.engines.gromacs.mdp import derive_mdp
from materiasim.specs.schema import integer, load_spec, validate_analysis
from materiasim.runtime.state import source_identity
from materiasim.engines.gromacs.topology import atom_mapping


class FrameworkTests(unittest.TestCase):
    """Cover file identity, strict configuration, periodic geometry and writer isolation."""

    def setUp(self):
        """Allocate isolated writable files for each test."""
        self.temporary = tempfile.TemporaryDirectory(prefix="materials-test-")
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def test_duplicate_json_keys(self):
        """Duplicate JSON fields must fail rather than silently select the last value."""
        path = self.root / "input.json"
        path.write_text('{"seed":1,"seed":2}')
        with self.assertRaises(ValueError):
            read_json(path)

    def test_nan_rejected(self):
        """Nonfinite JSON values are not valid configuration."""
        path = self.root / "input.json"
        path.write_text('{"seed":NaN}')
        with self.assertRaises(ValueError):
            read_json(path)

    def test_boolean_not_integer(self):
        """A JSON boolean cannot stand for a step count."""
        with self.assertRaises(ValueError):
            integer(True, 1, 10, "steps")

    def test_input_mutation_rejected(self):
        """A valid hash cannot authorize changed input bytes."""
        path = self.root / "input"
        path.write_text("original")
        hashes = {"input": sha256(path)}
        verify_hashes(self.root, hashes)
        path.write_text("changed")
        with self.assertRaises(ValueError):
            verify_hashes(self.root, hashes)

    def test_traversal_rejected(self):
        """Artifact identities cannot escape a relocated Run root."""
        with self.assertRaises(ValueError):
            contained(self.root, "../outside")

    def test_symlink_rejected(self):
        """Snapshot paths cannot redirect through a symbolic link."""
        (self.root / "alias").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            contained(self.root, "alias/file")

    def test_lock_collision(self):
        """A second process must not obtain a Run's active writer lock."""
        script = "from materiasim.storage import run_lock\nimport sys\nwith run_lock(sys.argv[1]): print('locked')"
        with run_lock(self.root):
            result = subprocess.run([sys.executable, "-B", "-c", script, str(self.root)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("active writer", result.stderr)
        with run_lock(self.root):
            self.assertTrue((self.root / ".writer.lock").is_file())

    def test_unfrozen_include_rejected(self):
        """Native preprocessing must not find undeclared external topology inputs."""
        (self.root / "system.top").write_text('#include "/tmp/external.itp"\n')
        with self.assertRaises(ValueError):
            check_includes(self.root)

    def test_empty_selection_rejected(self):
        """Empty atom selections are rejected at the specification boundary."""
        with self.assertRaises(ValueError):
            validate_analysis(dict(water_oxygen_selection="", sites={}))

    def test_unsupported_centroid_rejected(self):
        """First-round support does not pretend centroid geometry is implemented."""
        with self.assertRaises(ValueError):
            validate_analysis(dict(water_oxygen_selection="name OW", sites={"site":
                              dict(selection="name O", mode="cog", cutoff_nm=.35)}))

    def test_unknown_protocol_key_rejected(self):
        """Unsupported external MDP inputs fail instead of receiving guessed handling."""
        path = self.root / "input.mdp"
        path.write_text("pbc = xyz\npull = yes\n")
        with self.assertRaises(ValueError):
            derive_mdp(path, self.root / "output.mdp", dict(type="dynamics"))

    def test_protocol_source_preserved(self):
        """Smoke derivation retains the original bytes and records duration changes."""
        path = self.root / "input.mdp"
        path.write_text("integrator = md\npbc = xyz\ndt = 0.002\ngen-vel = yes\ncontinuation = no\nnsteps = 500000\n")
        original = sha256(path)
        changes = derive_mdp(path, self.root / "output.mdp", dict(type="dynamics", steps=100,
                             velocities="generate", seed=123, time_origin_ps=0, step_origin=0))
        self.assertEqual(original, sha256(path))
        self.assertEqual(changes["nsteps"], "100")
        self.assertEqual(changes["gen-seed"], "123")

    def test_mapping_checks_order(self):
        """Expanded topology and coordinates must agree atom by atom."""
        top = self.root / "processed.top"
        top.write_text("[ moleculetype ]\nX 1\n[ atoms ]\n1 X 1 X C 1 0 12\n"
                       "[ moleculetype ]\nSOL 1\n[ atoms ]\n1 OW 1 SOL OW 1 0 16\n"
                       "[ molecules ]\nX 1\nSOL 1\n")
        gro = self.root / "system.gro"
        rows = [f"{1:5d}{'X':<5}{'C':>5}{1:5d}{0:8.3f}{0:8.3f}{0:8.3f}",
                f"{2:5d}{'SOL':<5}{'OW':>5}{2:5d}{1:8.3f}{1:8.3f}{1:8.3f}"]
        gro.write_text("test\n2\n" + "\n".join(rows) + "\n3 3 3\n")
        self.assertEqual(atom_mapping(top, gro, {"X": 1})["atom_count"], 2)
        gro.write_text("test\n2\n" + "\n".join(reversed(rows)) + "\n3 3 3\n")
        with self.assertRaises(ValueError):
            atom_mapping(top, gro, {"X": 1})

    def test_code_identity_only_sources(self):
        """Bytecode caches must not become part of frozen implementation identity."""
        self.assertTrue(all(name.endswith(".py") for name in source_identity()))

    def test_dielectric_infinity_is_not_failed_energy(self):
        """GROMACS's defined infinite reaction-field dielectric is a legal input value."""
        check_numerics("   epsilon-rf                     = inf\nPotential Energy = -146570\n")

    def test_nonfinite_result_rejected(self):
        """The dielectric exception must not hide actual nonfinite results or LINCS errors."""
        for log in ("Potential Energy = inf", "Energies\nNaN", "LINCS WARNING"):
            with self.subTest(log=log), self.assertRaises(ValueError):
                check_numerics(log)

    def test_interrupted_checkpoint_does_not_require_final_gro(self):
        """A real -maxh interruption can lack md.gro and remain resumable."""
        folder = self.root / "stages/nvt"
        folder.mkdir(parents=True)
        (self.root / "build").mkdir()
        write_json(self.root / "build/atom_mapping.json", {"atom_count": 10})
        (self.root / "build/nvt.mdp").write_text("pbc = xyz\ndt = 0.002\n")
        for name in ("md.log", "md.edr", "md.xtc", "md.cpt"):
            (folder / name).write_text("test fixture")
        state = dict(step=100, time_ps=.2, atom_count=10)
        stage = dict(id="nvt", type="dynamics", steps=1000, time_origin_ps=0, step_origin=0)
        with patch("materiasim.engines.gromacs.stage.checkpoint", return_value=state):
            self.assertFalse(assess_stage(self.root, stage, {})["complete"])
        with patch("materiasim.engines.gromacs.stage.checkpoint", return_value=dict(state, step=1000, time_ps=2)):
            with self.assertRaises(FileNotFoundError):
                assess_stage(self.root, stage, {})

    def test_reserved_site_name_rejected(self):
        """A site may not replace time or the deduplicated union output."""
        with self.assertRaises(ValueError):
            validate_analysis(dict(water_oxygen_selection="name OW", sites={"union":
                              dict(selection="name O", mode="atoms", cutoff_nm=.35)}))

    def test_untracked_output_cannot_be_overwritten(self):
        """Prepared stage metadata cannot authorize overwriting residual MD output."""
        folder = self.root / "stages/nvt"
        folder.mkdir(parents=True)
        write_json(folder / "stage.json", {"status": "prepared"})
        (folder / "md.log").write_text("untracked output")
        with self.assertRaisesRegex(ValueError, "Untracked stage output"):
            execute_stage(self.root, {"id": "nvt"}, {}, self.root / "attempt", 1, 2)

    def test_unknown_spec_fields(self):
        """Undeclared scenario switches are not silently ignored."""
        path = self.root / "spec.json"
        write_json(path, dict(schema_version=1, unknown=True))
        with self.assertRaises(ValueError):
            load_spec(path)


if __name__ == "__main__":
    unittest.main()
