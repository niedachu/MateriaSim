from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from formal.run_production import parse_args, resolve_gmx, stage_frozen_inputs


class PortableEntrypointTests(unittest.TestCase):
    """Ensure the formal launcher is native Python with no Windows paths."""

    def test_production_entrypoint_has_no_shell_dependency(self) -> None:
        """The sole production source contains no workstation-specific path."""
        script = (PROJECT_ROOT / "formal" / "run_production.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("H:\\", script)
        self.assertNotIn("C:\\", script)
        self.assertIn("subprocess.run", script)
        self.assertIn("shutil.which", script)

    def test_start_command_requires_frozen_coordinates(self) -> None:
        """The start action carries explicit run and frozen-coordinate paths."""
        args = parse_args(
            [
                "start",
                "--run-directory",
                "/tmp/ion-pair-run",
                "--solvated-gro",
                "/tmp/frozen-solvated.gro",
            ]
        )
        self.assertEqual(args.action, "start")
        self.assertEqual(args.solvated_gro, Path("/tmp/frozen-solvated.gro"))

    def test_resume_command_uses_the_same_entrypoint(self) -> None:
        """The resume action is exposed without a second platform script."""
        args = parse_args(["resume", "--run-directory", "/tmp/ion-pair-run"])
        self.assertEqual(args.action, "resume")

    def test_explicit_gmx_path_is_platform_independent(self) -> None:
        """The executable resolver accepts an explicit native binary path."""
        self.assertEqual(Path(resolve_gmx(sys.executable)), Path(sys.executable).resolve())

    def test_start_stages_all_frozen_inputs_with_hashes(self) -> None:
        """A new run receives nine inputs and a complete SHA-256 manifest."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            solvated = root / "accepted_solvated.gro"
            solvated.write_text("accepted test coordinates\n", encoding="utf-8")
            run_directory = root / "run_001"
            stage_frozen_inputs(run_directory, solvated)
            manifest_lines = (
                run_directory / "FROZEN_INPUT_MANIFEST.txt"
            ).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(manifest_lines), 9)
            self.assertTrue((run_directory / "solvated.gro").is_file())


if __name__ == "__main__":
    unittest.main()
