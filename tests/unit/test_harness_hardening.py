"""Capability graphs, safe boundaries, read-only proposals and durable failure windows."""

import errno
import signal
import sqlite3
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from tests.unit import test_harness as fixtures
from materiasim.errors import MateriaSimError
from materiasim.harness import audit, decisions, journal, operations, service, snapshots, supervisor
from materiasim.harness.failures import PauseRequested, failure
from materiasim.plugins.builtin import catalog, environment
from materiasim.plugins.graph import order
from materiasim.storage import content_hash, inventory, read_json, sha256, write_json


class HardeningTests(unittest.TestCase):
    """Reuse isolated real definitions while keeping failure injections entirely outside user data."""

    setUp = fixtures.HarnessTests.setUp
    create = fixtures.HarnessTests.create
    intent = fixtures.HarnessTests.intent

    def decision(self):
        """Return a current inert proposal referencing one real frozen source file."""
        manifest = snapshots.load(self.campaign)
        db = journal.connect(self.campaign)
        try:
            state, events = journal.read(db)
        finally:
            db.close()
        relative = "snapshot/plan.json"
        return dict(contract_version=1, request_id="proposal-1", source="local-review", action="continue",
            campaign_hash=manifest["manifest_hash"], expected_sequence=state["sequence"], event_head=events[-1]["sha256"],
            expires_utc=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(), reason="Review frozen plan",
            evidence=[dict(path=relative, sha256=sha256(self.campaign / relative))])

    def test_real_dependencies_and_task_conflicts(self):
        """Two builders may be enabled for a study but cannot coexist in one task selection."""
        entries = catalog()
        selected = ["engine:gromacs", "builder:gromacs_packmol", "scenario:packed_liquid"]
        self.assertEqual(order(entries, selected)[-1], "scenario:packed_liquid")
        with self.assertRaisesRegex(MateriaSimError, "Missing/disabled"):
            order(entries, selected[1:])
        mixed = selected + ["builder:gromacs_prebuilt"]
        order(entries, mixed, check_conflicts=False)
        with self.assertRaises(MateriaSimError) as raised:
            order(entries, mixed)
        self.assertEqual(raised.exception.code, "PLUGIN_CONFLICT")

    def test_dependency_cycle_and_bad_contract(self):
        """Dependency cycles and descriptor versions fail before import or execution."""
        entries = catalog()
        entries["engine:gromacs"]["requires"] = ["builder:gromacs_packmol"]
        with self.assertRaises(MateriaSimError) as raised:
            order(entries, ["engine:gromacs", "builder:gromacs_packmol"])
        self.assertEqual(raised.exception.code, "PLUGIN_DEPENDENCY_CYCLE")
        entries = catalog()
        entries["engine:gromacs"]["contract_version"] = 99
        with self.assertRaises(MateriaSimError):
            order(entries, ["engine:gromacs"])

    def test_missing_optional_dependency_does_not_fallback(self):
        """A selected contact analyzer requires its declared distributions, not a substitute analyzer."""
        from importlib.metadata import PackageNotFoundError
        composition = snapshots.preview(fixtures.SIDECAR)["composition"]
        with patch("importlib.metadata.version", side_effect=PackageNotFoundError("missing")):
            with self.assertRaises(FileNotFoundError):
                environment(composition)

    def test_pause_blocks_next_core_operation(self):
        """A committed pause prevents the next build/run/analyze admission and preserves its intent."""
        self.create()
        self.intent()
        manifest = snapshots.load(self.campaign)
        operations.boundary(self.campaign, manifest, False, "task-000", "build")
        state = journal.status(self.campaign)
        service.control(self.campaign, "pause", "p", state["sequence"])
        for action in ("build", "run", "analyze"):
            with self.subTest(action=action), self.assertRaises(PauseRequested):
                operations.boundary(self.campaign, manifest, False, "task-000", action)
        self.assertEqual(journal.status(self.campaign)["last_boundary"]["action"], "build")

    def test_research_uses_boundary_before_build(self):
        """The ordinary batch runner delegates admission without creating a duplicate research loop."""
        from materiasim.research.batch import run
        self.create()
        with patch("materiasim.research.batch.perform", side_effect=AssertionError("build launched")), \
                self.assertRaises(PauseRequested):
            run(self.campaign / "snapshot", self.campaign / "work/batches",
                before_operation=lambda task, action: (_ for _ in ()).throw(PauseRequested()))
        self.assertFalse(list((self.campaign / "work/batches").glob("*/runs")))

    def test_revocation_wins_at_operation_boundary(self):
        """Previously queued work may not cross a new boundary after revocation."""
        self.create()
        self.intent()
        service.control(self.campaign, "revoke", "r", 1)
        with self.assertRaises(MateriaSimError) as raised:
            operations.boundary(self.campaign, snapshots.load(self.campaign), False, "task-000", "build")
        self.assertEqual(raised.exception.code, "AUTHORIZATION_REVOKED")

    def test_decision_validation_is_read_only_and_does_not_execute(self):
        """An accepted proposal validates evidence only; no state event or computation is submitted."""
        self.create()
        path = self.root / "decision.json"
        write_json(path, self.decision())
        before = sha256(self.campaign / "events.sqlite3")
        with patch("subprocess.Popen", side_effect=AssertionError("executed")):
            result = decisions.validate(self.campaign, path)
            self.assertEqual(decisions.validate(self.campaign, path), result)
        self.assertFalse(result["executed"])
        self.assertEqual(sha256(self.campaign / "events.sqlite3"), before)

    def test_stale_forged_expired_and_expansive_decisions_rejected(self):
        """Decision identity, expiry, references and action scope cannot be supplied by prose."""
        self.create()
        original = self.decision()
        variants = [dict(original, expected_sequence=42), dict(original, action="change_force_field"),
                    dict(original, expires_utc="2000-01-01T00:00:00+00:00"),
                    dict(original, campaign_hash="forged"), dict(original, reason="x" * 2001)]
        for ref in (dict(path="../authorization.json", sha256="bad"), dict(path="snapshot/plan.json", sha256="bad")):
            variants.append(dict(original, evidence=[ref]))
        for index, value in enumerate(variants):
            path = self.root / "decision.json"
            write_json(path, value)
            with self.subTest(index=index), self.assertRaises(ValueError):
                decisions.validate(self.campaign, path)

    def test_old_decision_rejected_after_revoke(self):
        """A proposal's earlier valid authorization does not survive user revocation."""
        self.create()
        path = self.root / "decision.json"
        write_json(path, self.decision())
        service.control(self.campaign, "revoke", "r", 0)
        with self.assertRaises(MateriaSimError) as raised:
            decisions.validate(self.campaign, path)
        self.assertEqual(raised.exception.code, "AUTHORIZATION_REVOKED")

    def test_audit_lists_missing_snapshot_and_all_tasks(self):
        """A damaged input is listed explicitly instead of silently excluding its declared tasks."""
        self.create()
        service.control(self.campaign, "cancel", "c", 0)
        path = self.campaign / "snapshot/plan.json"
        path.unlink()  # Deliberately remove only this test-owned copied fixture.
        result = audit.evidence(self.campaign)
        self.assertEqual(len(result["tasks"]), 4)
        self.assertIn("snapshot/plan.json", [i.get("path") for i in result["issues"]])
        self.assertEqual(result["closure"], "incomplete_or_failed")

    def test_audit_race_rejected(self):
        """Changed files across the read window cannot receive a stable evidence summary."""
        self.create()
        service.control(self.campaign, "cancel", "c", 0)
        actual = inventory
        calls = []

        def changed(root, directories):
            """Inject a differing second inventory without modifying any retained data."""
            calls.append(True)
            value = actual(root, directories)
            return dict(value, changed="digest") if len(calls) == 2 else value

        with patch("materiasim.harness.audit.inventory", side_effect=changed), self.assertRaises(MateriaSimError):
            audit.evidence(self.campaign)

    def test_pending_launch_deduplicates_before_worker_intent(self):
        """Concurrent starts cannot allocate unlimited supervisors while the first is still starting."""
        self.create()
        with patch("materiasim.harness.supervisor.subprocess.Popen") as launch:
            launch.return_value.pid = 12345
            supervisor.start(self.campaign)
            result = supervisor.start(self.campaign)
        self.assertEqual(launch.call_count, 1)
        self.assertIsNotNone(result["pending_launch"])

    def test_enospc_before_intent_commit_never_starts_worker(self):
        """Injected full disk during the durable intent leaves no launch or phantom charge."""
        self.create()
        with patch("materiasim.harness.journal.append", side_effect=OSError(errno.ENOSPC, "test full disk")), \
                patch("materiasim.harness.supervisor.watch") as watch, self.assertRaises(OSError):
            supervisor.run(self.campaign)
        watch.assert_not_called()
        self.assertEqual(journal.status(self.campaign)["charged_seconds"], 0)
        self.assertIsNone(journal.status(self.campaign)["active"])

    def test_worker_receipt_then_failed_settlement_keeps_reservation(self):
        """A failed settlement commit cannot free an active reservation or trigger worker replay."""
        self.create()
        active = self.intent()
        receipt = dict(operation_id="op-test", ok=False, error={"code": "TEST"})
        write_json(self.campaign / "operations/op-test/result.json", receipt)
        with patch("materiasim.harness.journal.append", side_effect=OSError(errno.ENOSPC, "test full disk")), \
                self.assertRaises(OSError):
            supervisor.settle(self.campaign, active, receipt, 1, None)
        self.assertEqual(journal.status(self.campaign)["active"], active)
        self.assertEqual(supervisor.reconcile(self.campaign)["charged_seconds"], 300)
        self.assertEqual(supervisor.reconcile(self.campaign)["charged_seconds"], 300)

    def test_sigkill_uncommitted_sqlite_transition_not_replayed(self):
        """Real SIGKILL before commit leaves no acknowledged pause after SQLite journal recovery."""
        self.create()
        script = """import os,signal,sys
from pathlib import Path
from materiasim.harness import journal
with journal.transaction(Path(sys.argv[1])) as db:
    journal.append(db, 'control', dict(action='pause',request_id='uncommitted',expected_sequence=0))
    os.kill(os.getpid(),signal.SIGKILL)
"""
        result = subprocess.run([sys.executable, "-B", "-c", script, str(self.campaign)],
                                capture_output=True, timeout=10)
        self.assertEqual(result.returncode, -signal.SIGKILL)
        state = supervisor.reconcile(self.campaign)
        self.assertEqual(state["sequence"], 0)
        self.assertEqual(state["status"], "ready")

    def test_corrupt_database_never_truncated_or_recreated(self):
        """Unparseable SQLite evidence is preserved byte-for-byte, not reset to a fresh Campaign."""
        self.create()
        path = self.campaign / "events.sqlite3"
        path.write_bytes(b"test-owned-corrupt-database")
        before = sha256(path)
        with self.assertRaises(sqlite3.DatabaseError):
            supervisor.reconcile(self.campaign)
        self.assertEqual(sha256(path), before)

    def test_expired_waiting_campaign_cannot_start(self):
        """Time spent paused need not be charged as CPU, but it cannot extend the grant deadline."""
        self.create()
        manifest = snapshots.load(self.campaign)
        manifest["authorization"]["expires_utc"] = "2000-01-01T00:00:00+00:00"
        with patch("materiasim.harness.supervisor.load", return_value=manifest), self.assertRaises(MateriaSimError):
            supervisor.run(self.campaign)
        self.assertIsNone(journal.status(self.campaign)["active"])

    def test_v1_campaign_is_read_only_not_migrated(self):
        """Persisted first-increment evidence remains readable, but new controls cannot reinterpret it."""
        self.create()
        manifest = snapshots.load(self.campaign)
        manifest["contract_version"] = 1
        with patch("materiasim.harness.service.load", return_value=manifest), self.assertRaisesRegex(ValueError, "read-only"):
            service.control(self.campaign, "pause", "p", 0)
        self.assertEqual(journal.status(self.campaign)["sequence"], 0)

    def test_failure_classification_does_not_guess_numerical_cause(self):
        """A scary native error string is still unknown without a structured numerical finding."""
        result = failure(RuntimeError("LINCS NaN simulation failed"), "run")
        self.assertEqual(result["error"]["category"], "unknown")
        self.assertEqual(failure(OSError(errno.ENOSPC, "disk"), "run")["error"]["category"], "resource")
        self.assertEqual(failure(ValueError("bad report"), "analyze")["error"]["category"], "analysis")
        from materiasim.engines.gromacs.stage import check_numerics
        with self.assertRaises(MateriaSimError) as raised:
            check_numerics("LINCS WARNING")
        self.assertEqual(raised.exception.category, "numerical")

    def paused_progress(self, charged=1):
        """Seal test-owned pre-build batch progress without pretending that any MD has run."""
        from materiasim.research.batch import register
        self.create()
        register(self.campaign / "snapshot", self.campaign / "work/batches", "gmx", "packmol")
        active = self.intent()
        receipt = dict(operation_id="op-test", ok=True,
                       result=operations.progress(self.campaign, snapshots.load(self.campaign), "paused"))
        write_json(self.campaign / "operations/op-test/result.json", receipt)
        state = supervisor.settle(self.campaign, active, receipt, charged, None)
        return state

    def test_deleted_progress_never_rebuilds_on_resume(self):
        """Removing settled work cannot turn resume into a fresh build under the same allowance."""
        state = self.paused_progress()
        ledger = next((self.campaign / "work/batches").glob("*/ledger.json"))
        ledger.unlink()
        service.control(self.campaign, "resume", "r", state["sequence"])
        with patch("materiasim.harness.supervisor.watch", side_effect=AssertionError("restarted")), \
                self.assertRaises((ValueError, OSError)):
            supervisor.run(self.campaign)
        self.assertEqual(journal.status(self.campaign)["operations"], 1)

    def test_resume_keeps_total_budget_and_stops_without_new_work(self):
        """Resuming a valid paused batch does not reset already charged campaign time."""
        state = self.paused_progress(charged=210)
        service.control(self.campaign, "resume", "r", state["sequence"])
        with patch("materiasim.harness.supervisor.watch", side_effect=AssertionError("launched")):
            state = supervisor.run(self.campaign)
        self.assertEqual(state["status"], "budget_exhausted")
        self.assertEqual(state["charged_seconds"], 210)

    def test_successful_paused_receipt_reconciles_without_replay(self):
        """A crash after a valid pause receipt is settled from the exact same frozen progress."""
        from materiasim.research.batch import register
        self.create()
        register(self.campaign / "snapshot", self.campaign / "work/batches", "gmx", "packmol")
        self.intent()
        receipt = dict(operation_id="op-test", ok=True,
                       result=operations.progress(self.campaign, snapshots.load(self.campaign), "paused"))
        write_json(self.campaign / "operations/op-test/result.json", receipt)
        with patch("materiasim.harness.supervisor.watch", side_effect=AssertionError("replayed")):
            state = supervisor.reconcile(self.campaign)
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["charged_seconds"], 300)

    def test_worker_receipt_schema_is_strict(self):
        """Malformed booleans and unknown receipt fields cannot be treated as successful evidence."""
        self.create()
        manifest = snapshots.load(self.campaign)
        for receipt in (dict(operation_id="op-test", ok="false", error={}),
                        dict(operation_id="op-test", ok=False, error={}, extra=True)):
            with self.assertRaises(ValueError):
                supervisor.verify_receipt(self.campaign, manifest, receipt, "op-test")


if __name__ == "__main__":
    unittest.main()
