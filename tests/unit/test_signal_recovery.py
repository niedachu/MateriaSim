"""The native signal exit exception cannot waive failed physics or ordinary command errors."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from materiasim.storage import write_json
from materiasim.engines.gromacs.stage import execute_stage
from materiasim.runtime.process import CommandFailed


class SignalRecoveryTests(unittest.TestCase):
    """Exercise only the native exit adapter; final checkpoint behavior has real-tool acceptance."""

    def setUp(self):
        """Allocate a prepared-stage fixture and explicit recorded native stderr."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.stage = dict(id="nvt", type="dynamics")
        write_json(self.root / "stages/nvt/stage.json", dict(status="prepared"))
        self.attempt = self.root / "attempts/run-fixture"
        self.record = self.attempt / "run-nvt"
        self.record.mkdir(parents=True)
        (self.record / "stderr.log").write_text("Received the TERM signal, stopping within 200 steps\n")

    def test_only_observed_native_signal_exit_is_admitted(self):
        """A marker alone, a different exit code, or minimization cannot become recoverable."""
        for code, interrupted, kind in ((1, False, "dynamics"), (2, True, "dynamics"), (1, True, "minimization")):
            error = CommandFailed("failed", dict(returncode=code, interrupted=interrupted))
            with self.subTest(code=code, interrupted=interrupted, kind=kind):
                with patch("materiasim.engines.gromacs.stage.command", side_effect=error), \
                        patch("materiasim.engines.gromacs.stage.assess_stage") as assess:
                    with self.assertRaises(CommandFailed):
                        execute_stage(self.root, dict(self.stage, type=kind), {}, self.attempt, 2, 10)
                    assess.assert_not_called()

    def test_signal_exit_still_requires_valid_checkpoint_and_numerics(self):
        """Native signal exit reaches, but cannot bypass, the normal stage evidence validator."""
        error = CommandFailed("signal", dict(returncode=1, interrupted=True))
        with patch("materiasim.engines.gromacs.stage.command", side_effect=error), \
                patch("materiasim.engines.gromacs.stage.assess_stage", side_effect=ValueError("bad checkpoint")), \
                patch("materiasim.engines.gromacs.stage.preserve_stage") as preserve:
            with self.assertRaisesRegex(ValueError, "bad checkpoint"):
                execute_stage(self.root, self.stage, {}, self.attempt, 2, 10)
            preserve.assert_not_called()

    def test_exit_one_without_native_signal_message_still_fails(self):
        """An externally interrupted but otherwise failed command remains a failure."""
        (self.record / "stderr.log").write_text("Fatal error: fixture\n")
        error = CommandFailed("failed", dict(returncode=1, interrupted=True))
        with patch("materiasim.engines.gromacs.stage.command", side_effect=error):
            with self.assertRaises(CommandFailed):
                execute_stage(self.root, self.stage, {}, self.attempt, 2, 10)
