"""Local Campaign contracts, immutable scope and fail-closed recovery; no MD in unit tests."""

import tempfile
import sys
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from materiasim.harness import journal, service, snapshots, supervisor
from materiasim.harness.contracts import authorization, bounded_json
from materiasim.plugins.builtin import catalog, resolve, verify
from materiasim.storage import inventory, read_json, run_lock, write_json

ROOT = Path(__file__).resolve().parents[2]
SIDECAR = ROOT / "studies/zil_count_smoke/automation.json"


class HarnessTests(unittest.TestCase):
    """Use real source/frozen inputs, mocking only executable identity probes and worker boundaries."""

    def setUp(self):
        """Allocate isolated output and grant paths, never touching retained user evidence."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.campaign = self.root / "campaign with spaces"
        self.grant = dict(contract_version=1, subject="zil_count_smoke_rules", actor="unit-test-user",
            output_root=str(self.campaign), expires_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            allowed_actions=["execute", "resume"], total_seconds=300, storage_bytes=134217728)
        self.grant_path = self.root / "authorization.json"

    def create(self, sidecar=SIDECAR):
        """Freeze genuine inputs without launching native processes."""
        write_json(self.grant_path, self.grant)
        with patch("materiasim.engines.gromacs.command.engine_info", return_value={"test_identity": "gmx"}), \
                patch("materiasim.builders.packmol.packmol_info", return_value={"test_identity": "packmol"}):
            snapshots.create(sidecar, self.grant_path, self.campaign)
        return self.campaign

    def intent(self):
        """Persist one reservation and its output folder to model a crash after intent commit."""
        active = dict(operation_id="op-test", owner_token="test-owner", resume=False, reserved_seconds=300)
        (self.campaign / "operations/op-test").mkdir()
        with journal.transaction(self.campaign) as db:
            journal.append(db, "intent", active)
        return active

    def test_preview_read_only_and_capabilities_match_real_registries(self):
        """Preflight must resolve both real studies without spawning tools or writing source files."""
        before = inventory(ROOT, ["studies"])
        with patch("subprocess.Popen", side_effect=AssertionError("unexpected subprocess")):
            for name in ("zil_count_smoke", "mixed_builders_smoke"):
                result = snapshots.preview(ROOT / "studies" / name / "automation.json")
                self.assertEqual(result["task_count"], 4)
                self.assertEqual(result["environment"], "not_checked")
                self.assertLessEqual(set(result["composition"]["enabled"]), catalog().keys())
        self.assertEqual(before, inventory(ROOT, ["studies"]))

    def test_capability_allowlist_fail_closed(self):
        """Missing, unknown or duplicate capabilities cannot reach any executor."""
        self.create()
        manifest = snapshots.load(self.campaign)
        specs = snapshots.specs_at(self.campaign, manifest)
        enabled = manifest["composition"]["enabled"]
        for value in ([], enabled + ["engine:unknown"], enabled + enabled):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve(specs, value)
        with patch("materiasim.plugins.builtin.source_identity", return_value={"different": "implementation"}):
            with self.assertRaisesRegex(ValueError, "changed"):
                verify(specs, manifest["composition"])

    def test_grant_scope_expiry_unknown_fields(self):
        """Authorization is explicit, bounded and bound to the exact target directory."""
        authorization(self.grant, self.grant["subject"], self.campaign)
        for key, value in (("output_root", str(self.root / "other")), ("total_seconds", True),
                           ("expires_utc", "2000-01-01T00:00:00+00:00"), ("extra", True)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                authorization(dict(self.grant, **{key: value}), self.grant["subject"], self.campaign)

    def test_prepare_only_or_unknown_automation_rejected(self):
        """A preparation directory is not a runnable target and unknown knobs fail validation."""
        value = read_json(SIDECAR)
        path = self.root / "recipe.json"
        value["target"]["path"] = "missing-experiment.json"
        write_json(path, value)
        with self.assertRaisesRegex(ValueError, "preparation-only"):
            snapshots.preview(path)
        value["shell_command"] = "anything"
        write_json(path, value)
        with self.assertRaises(ValueError):
            snapshots.preview(path)

    def test_manifest_snapshot_and_status_are_read_only(self):
        """Frozen identity checks reject altered bytes and status writes no projection files."""
        self.create()
        before = inventory(self.campaign, ["snapshot", "work", "operations"])
        self.assertEqual(service.status(self.campaign)["status"], "ready")
        self.assertEqual(before, inventory(self.campaign, ["snapshot", "work", "operations"]))
        snapshots.load(self.campaign, current=True)
        path = self.campaign / "snapshot/plan.json"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaises(ValueError):
            snapshots.load(self.campaign)

    def test_single_experiment_freezes_without_research_definition(self):
        """Ordinary experiments use the same capability and grant flow as study packages."""
        value = read_json(SIDECAR)
        value["target"] = dict(kind="experiment", path=str(ROOT / "examples/v3/packed_zil_water.json"))
        source = self.root / "inputs/automation.json"
        write_json(source, value)
        self.create(source)
        self.assertEqual(len(snapshots.specs_at(self.campaign, snapshots.load(self.campaign, current=True))), 1)

    def test_control_idempotency_staleness_and_no_terminal_reopen(self):
        """Repeated request is safe, changed payload/stale sequence fails, revoked scope stays closed."""
        self.create()
        state = service.control(self.campaign, "pause", "pause-1", 0)
        self.assertEqual(state["status"], "paused")
        self.assertEqual(service.control(self.campaign, "pause", "pause-1", 0), state)
        with self.assertRaisesRegex(ValueError, "Idempotency"):
            service.control(self.campaign, "cancel", "pause-1", 0)
        with self.assertRaisesRegex(ValueError, "Stale"):
            service.control(self.campaign, "resume", "resume-stale", 0)
        state = service.control(self.campaign, "resume", "resume-1", state["sequence"])
        self.assertEqual(state["status"], "ready")
        state = service.control(self.campaign, "revoke", "revoke-1", state["sequence"])
        self.assertEqual(state["status"], "cancelled")
        with self.assertRaises(ValueError):
            service.control(self.campaign, "resume", "resume-2", state["sequence"])
        self.assertEqual([r["status"] for r in service.evidence(self.campaign)["tasks"]], ["not_started"] * 4)

    def test_cancel_wins_over_worker_completion(self):
        """A concurrent worker success cannot overwrite an already committed user cancellation."""
        self.create()
        active = self.intent()
        state = service.control(self.campaign, "cancel", "cancel-1", 1)
        self.assertEqual(state["status"], "cancelling")
        self.assertIsNotNone(state["active"])
        receipt = dict(operation_id=active["operation_id"], ok=True, result=dict(status="engineering_complete"))
        write_json(self.campaign / "operations/op-test/result.json", receipt)
        state = supervisor.settle(self.campaign, active, receipt, 1.2, None)
        self.assertEqual(state["status"], "cancelled")
        self.assertIsNone(state["active"])

    def test_transaction_rollback_and_event_tampering(self):
        """Failed persistence does not leave a projected transition, and tampered history is rejected."""
        self.create()
        with self.assertRaises(OSError), journal.transaction(self.campaign) as db:
            journal.append(db, "control", dict(action="pause", request_id="p", expected_sequence=0))
            raise OSError("injected storage failure")
        self.assertEqual(journal.status(self.campaign)["sequence"], 0)
        with journal.transaction(self.campaign) as db:
            db.execute("UPDATE events SET hash='corrupt' WHERE seq=0")
        with self.assertRaisesRegex(ValueError, "hash"):
            journal.status(self.campaign)

    def test_unknown_handoff_no_resubmission_and_live_worker_no_takeover(self):
        """No receipt means manual review, and a live writer is never killed by a saved PID."""
        self.create()
        active = self.intent()
        with patch("materiasim.harness.supervisor.watch", side_effect=AssertionError("resubmitted")):
            with self.assertRaisesRegex(RuntimeError, "Uncertain"):
                supervisor.run(self.campaign)
        state = journal.status(self.campaign)
        self.assertEqual(state["status"], "needs_human_review")
        self.assertEqual(state["active"]["reserved_seconds"], 300)
        with run_lock(self.campaign / "worker_guard"), self.assertRaises((ValueError, RuntimeError)):
            supervisor.recover(self.campaign, active)

    def test_recovery_charges_reservation_once(self):
        """Crash after worker failure conservatively charges full allowance without replaying work."""
        self.create()
        active = self.intent()
        write_json(self.campaign / "operations/op-test/result.json",
                   dict(operation_id="op-test", ok=False, error={"code": "TEST_FAILURE"}))
        self.assertEqual(supervisor.run(self.campaign)["charged_seconds"], 300)
        self.assertEqual(supervisor.run(self.campaign)["charged_seconds"], 300)

    def test_forged_success_receipt_requires_canonical_results(self):
        """A receipt cannot certify absent Run/analysis evidence during crash recovery."""
        self.create()
        self.intent()
        write_json(self.campaign / "operations/op-test/result.json",
                   dict(operation_id="op-test", ok=True, result=dict(status="engineering_complete")))
        with self.assertRaises((ValueError, OSError)):
            supervisor.run(self.campaign)
        self.assertIsNotNone(journal.status(self.campaign)["active"])

    def test_budget_and_second_supervisor_cannot_launch(self):
        """Too little stop-grace allowance and an existing supervisor both prevent a new worker."""
        self.grant["total_seconds"] = 30
        self.create()
        with run_lock(self.campaign / "supervisor"), self.assertRaises((ValueError, RuntimeError)):
            supervisor.run(self.campaign)
        with patch("materiasim.harness.supervisor.watch", side_effect=AssertionError("launched")):
            self.assertEqual(supervisor.run(self.campaign)["status"], "budget_exhausted")

    def test_malformed_json_and_nonfinite_reservations(self):
        """Duplicate keys, oversized requests and nonfinite accounting fields are rejected."""
        path = self.root / "bad.json"
        for body in ('{"a":1,"a":2}', '"' + "a" * (2 * 1024 * 1024) + '"'):
            path.write_text(body)
            with self.assertRaises(ValueError):
                bounded_json(path)
        self.create()
        with journal.transaction(self.campaign) as db:
            with self.assertRaises(ValueError):
                journal.append(db, "intent", dict(operation_id="bad", owner_token="test", resume=False,
                                                  reserved_seconds=float("inf")))

    def test_pause_waits_for_settlement_and_resume_preserves_charges(self):
        """Pause does not clear an in-flight reservation or reset already consumed time."""
        self.create()
        active = self.intent()
        state = service.control(self.campaign, "pause", "pause-live", 1)
        self.assertEqual(state["status"], "pause_requested")
        with self.assertRaises(ValueError):
            service.control(self.campaign, "resume", "too-early", state["sequence"])
        receipt = dict(operation_id="op-test", ok=True, result=dict(status="engineering_complete"))
        write_json(self.campaign / "operations/op-test/result.json", receipt)
        state = supervisor.settle(self.campaign, active, receipt, 3, None)
        self.assertEqual(state["status"], "paused")
        state = service.control(self.campaign, "resume", "resume-valid", state["sequence"])
        self.assertEqual(state["charged_seconds"], 3)
        self.assertEqual(state["operations"], 1)

    def test_tool_identity_change_and_insufficient_disk_rejected(self):
        """Native identity and copy capacity are checked without executing any simulated system."""
        self.create()
        with patch("materiasim.engines.gromacs.command.engine_info", return_value={"test_identity": "changed"}):
            with self.assertRaisesRegex(ValueError, "GROMACS"):
                snapshots.verify_tools(snapshots.load(self.campaign))
        other = self.root / "disk-full"
        self.grant["output_root"] = str(other)
        write_json(self.grant_path, self.grant)
        with patch("materiasim.harness.snapshots.shutil.disk_usage") as disk:
            disk.return_value.free = 0
            with self.assertRaisesRegex(ValueError, "Insufficient"):
                snapshots.create(SIDECAR, self.grant_path, other)
        self.assertFalse(other.exists())

    def test_cancel_owned_non_md_process_group(self):
        """Exercise actual cooperative/forced group cleanup using a sleeping test process, never GROMACS."""
        from materiasim.runtime.family import launch
        self.create()
        active = self.intent()
        started = threading.Event()

        def sleeper(arguments, **options):
            """Replace only the MD worker with a dedicated, owned non-MD test subprocess."""
            child = launch([sys.executable, "-c", "import time; time.sleep(30)"], **options)
            started.set()
            return child

        def cancel():
            """Wait for this test's child launch and submit a versioned cancellation request."""
            if started.wait(5):
                service.control(self.campaign, "cancel", "cancel-process", 1)

        thread = threading.Thread(target=cancel)
        thread.start()
        try:
            with patch("materiasim.harness.supervisor.launch", side_effect=sleeper), \
                    patch("materiasim.harness.supervisor.GRACE_SECONDS", .2):
                state = supervisor.watch(self.campaign, snapshots.load(self.campaign), active)
        finally:
            thread.join(timeout=5)
        self.assertEqual(state["status"], "cancelled")
        self.assertIsNone(state["active"])
        self.assertGreater(state["charged_seconds"], 0)

    def test_configuration_identity_changes_rejected(self):
        """Even a numerically innocuous scientific configuration change invalidates composition identity."""
        self.create()
        manifest = snapshots.load(self.campaign)
        specs = snapshots.specs_at(self.campaign, manifest)
        specs[0]["id"] += "_changed"
        with self.assertRaisesRegex(ValueError, "changed"):
            verify(specs, manifest["composition"])


if __name__ == "__main__":
    unittest.main()
