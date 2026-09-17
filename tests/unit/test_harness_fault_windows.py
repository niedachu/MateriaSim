"""Real non-MD process failures and evidence/accounting edge cases in disposable Campaigns."""

import signal
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from tests.unit import test_harness as fixtures
from materiasim.harness import journal, service, snapshots, supervisor
from materiasim.runtime.family import launch


class FaultWindowTests(unittest.TestCase):
    """Keep native simulations out of failure injection and operate only on owned test children."""

    setUp = fixtures.HarnessTests.setUp
    create = fixtures.HarnessTests.create
    intent = fixtures.HarnessTests.intent

    def test_committed_intent_sigkill_preserves_uncertainty(self):
        """Death after intent commit cannot be mistaken for permission to launch the worker again."""
        self.create()
        script = """import os,signal,sys
from pathlib import Path
from materiasim.harness import journal
root=Path(sys.argv[1])
(root/'operations/op-killed').mkdir()
with journal.transaction(root) as db:
    journal.append(db,'intent',dict(operation_id='op-killed',owner_token='test',resume=False,reserved_seconds=300))
os.kill(os.getpid(),signal.SIGKILL)
"""
        child = subprocess.run([sys.executable, "-B", "-c", script, str(self.campaign)],
                               capture_output=True, timeout=10)
        self.assertEqual(child.returncode, -signal.SIGKILL)
        with patch("subprocess.Popen", side_effect=AssertionError("resubmitted")), \
                self.assertRaisesRegex(RuntimeError, "Uncertain"):
            supervisor.reconcile(self.campaign)
        state = journal.status(self.campaign)
        self.assertEqual(state["status"], "needs_human_review")
        self.assertEqual(state["active"]["reserved_seconds"], 300)

    def test_real_live_worker_lock_prevents_takeover(self):
        """A real child holding the worker guard cannot be replaced or signalled by reconciliation."""
        self.create()
        self.intent()
        ready = self.root / "ready"
        script = """import sys,time
from pathlib import Path
from materiasim.storage import run_lock
with run_lock(Path(sys.argv[1])/'worker_guard'):
    Path(sys.argv[2]).touch()
    time.sleep(20)
"""
        child = subprocess.Popen([sys.executable, "-B", "-c", script, str(self.campaign), str(ready)])
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline and child.poll() is None:
                time.sleep(.02)
            self.assertTrue(ready.exists())
            with patch("os.kill", side_effect=AssertionError("foreign PID signalled")), \
                    self.assertRaises((ValueError, RuntimeError)):
                supervisor.reconcile(self.campaign)
            self.assertIsNone(child.poll())
            self.assertEqual(journal.status(self.campaign)["status"], "executing")
        finally:
            child.terminate()
            child.wait(timeout=5)

    def test_force_stop_owns_group_and_does_not_claim_checkpoint(self):
        """A real TERM-ignoring child is killed only after the shortened test grace, with no success claim."""
        self.create()
        active = self.intent()
        ready = self.root / "ready"
        children = []

        def ignoring_worker(arguments, **options):
            """Launch a dedicated owned test process, waiting until its TERM handler is installed."""
            script = "import signal,sys,time;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(sys.argv[1]).touch();time.sleep(20)"
            process, owner = launch([sys.executable, "-c", script, str(ready)], **options)
            children.append(process)
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline and process.poll() is None:
                time.sleep(.02)
            if not ready.exists():
                process.kill()
                process.wait(timeout=5)
                raise AssertionError("Test process did not install its signal handler")
            return process, owner

        # A resource stop exercises forced_stop without cancellation projection overriding its reason.
        manifest = snapshots.load(self.campaign)
        with patch("materiasim.harness.supervisor.launch", side_effect=ignoring_worker), \
                patch("materiasim.harness.supervisor.GRACE_SECONDS", .2), \
                patch("materiasim.harness.supervisor.shutil.disk_usage") as disk:
            disk.return_value.free = 0
            state = supervisor.watch(self.campaign, manifest, active)
        self.assertEqual(children[0].returncode, -signal.SIGKILL)
        self.assertNotEqual(state["status"], "completed")
        self.assertIsNone(state["active"])
        self.assertFalse((self.campaign / "operations/op-test/result.json").exists())

    def test_launch_log_missing_is_explicit_audit_issue(self):
        """Launch registration requires both logs even when no MD task ever starts."""
        self.create()
        with patch("materiasim.harness.supervisor.subprocess.Popen"):
            result = supervisor.start(self.campaign)
        missing = self.campaign / "launches" / result["launch_id"] / "stderr.log"
        missing.unlink()
        state = journal.status(self.campaign)
        service.control(self.campaign, "cancel", "stop", state["sequence"])
        report = service.evidence(self.campaign)
        self.assertIn(str(missing.relative_to(self.campaign)), [i.get("path") for i in report["issues"]])
        self.assertEqual(len(report["tasks"]), 4)
        self.assertEqual(report["closure"], "incomplete_or_failed")

    def test_logs_consume_budget_before_submission(self):
        """A real test log beyond a reduced test allowance blocks launch rather than resetting capacity."""
        self.create()
        manifest = snapshots.load(self.campaign)
        manifest["authorization"]["storage_bytes"] = 1024
        (self.campaign / "launches/test-owned.log").write_bytes(b"x" * 2048)
        with patch("materiasim.harness.supervisor.load", return_value=manifest), \
                patch("materiasim.harness.supervisor.watch", side_effect=AssertionError("launched")):
            state = supervisor.run(self.campaign)
        self.assertEqual(state["status"], "budget_exhausted")
        self.assertEqual(state["operations"], 0)


if __name__ == "__main__":
    unittest.main()
