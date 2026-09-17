"""Real POSIX pipe EOF and bounded storage failures, without native simulations."""

import os
import signal
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests.unit import test_harness as fixtures
from materiasim.errors import MateriaSimError
from materiasim.harness import journal, operations, snapshots, supervisor
from materiasim.harness.liveness import SupervisorConnection


class LivenessTests(unittest.TestCase):
    """Use owned pipes and real short-lived children; never signal a PID loaded from disk."""

    setUp = fixtures.HarnessTests.setUp
    create = fixtures.HarnessTests.create
    intent = fixtures.HarnessTests.intent

    def test_startup_eof_denies_worker(self):
        """Parent death before worker setup cannot accidentally establish a new parent identity."""
        reader, writer = os.pipe()
        os.close(writer)
        with self.assertRaises(MateriaSimError) as error:
            with SupervisorConnection(reader):
                self.fail("Disconnected worker started")
        self.assertEqual(error.exception.code, "SUPERVISOR_LOST")
        with self.assertRaises(OSError):
            os.fstat(reader)

    def test_file_is_not_a_liveness_pipe(self):
        """Arbitrary files and standard streams cannot replace the inherited control channel."""
        path = self.root / "not-pipe"
        path.touch()
        with path.open("rb") as stream, self.assertRaises(ValueError):
            SupervisorConnection(stream.fileno())
        with self.assertRaises(ValueError):
            SupervisorConnection(0)

    def test_eof_blocks_next_operation(self):
        """The synchronous boundary also rejects EOF if the monitor has not yet delivered SIGTERM."""
        self.create()
        self.intent()
        reader, writer = os.pipe()
        connection = SupervisorConnection(reader)
        os.close(writer)
        try:
            with self.assertRaises(MateriaSimError):
                operations.boundary(self.campaign, snapshots.load(self.campaign), False,
                                    "task-000", "build", connection)
            self.assertEqual(journal.status(self.campaign)["last_boundary"], {})
        finally:
            os.close(reader)

    def test_real_child_receives_cooperative_stop_on_eof(self):
        """Closing the sole supervisor writer delivers SIGTERM in an actual isolated test child."""
        reader, writer = os.pipe()
        script = """import signal,sys,time
from materiasim.harness.liveness import SupervisorConnection
seen=[]
signal.signal(signal.SIGTERM,lambda s,f: seen.append(s))
with SupervisorConnection(int(sys.argv[1])):
    print('ready',flush=True)
    deadline=time.monotonic()+5
    while not seen and time.monotonic()<deadline: time.sleep(.01)
assert seen==[signal.SIGTERM],seen
"""
        child = subprocess.Popen([sys.executable, "-B", "-c", script, str(reader)],
                                 pass_fds=(reader,), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        os.close(reader)
        try:
            import select
            self.assertTrue(select.select([child.stdout], [], [], 5)[0])
            self.assertEqual(child.stdout.readline().strip(), "ready")
            os.close(writer)
            writer = None
            _, error = child.communicate(timeout=8)
            self.assertEqual(child.returncode, 0, error)
        finally:
            if writer is not None:
                os.close(writer)
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)
            child.stdout.close()
            child.stderr.close()

    def test_normal_teardown_does_not_signal(self):
        """Normal worker shutdown closes its descriptor and cannot later receive a monitor signal."""
        reader, writer = os.pipe()
        try:
            with patch("materiasim.harness.liveness.os.kill") as kill:
                with SupervisorConnection(reader) as connection:
                    connection.check()
                    self.assertFalse(os.get_inheritable(reader))
                kill.assert_not_called()
        finally:
            os.close(writer)

    def test_sqlite_full_preserves_committed_state(self):
        """SQLite's own page limit produces a real SQLITE_FULL without filling any filesystem."""
        self.create()
        with self.assertRaises(sqlite3.OperationalError) as error:
            with journal.transaction(self.campaign) as db:
                pages = db.execute("PRAGMA page_count").fetchone()[0]
                db.execute(f"PRAGMA max_page_count={pages}")
                # Large invalid insertion is never committed: exercise the storage engine, not event validation.
                db.execute("INSERT INTO events VALUES (1, ?, 'test')", ("x" * 1048576,))
        self.assertIn("full", str(error.exception).lower())
        self.assertEqual(supervisor.reconcile(self.campaign)["sequence"], 0)


if __name__ == "__main__":
    unittest.main()
