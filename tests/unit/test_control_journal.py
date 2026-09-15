"""Durable metadata fault injection, explicitly separate from physical MD acceptance."""

from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from materiasim.runtime.control import control_root, inspect_control, supervise, usage, watch
from materiasim.runtime.journal import validate_journal
from materiasim.specs.execution import cpu_profile
from materiasim.storage import content_hash, inventory, read_json, sha256, write_json


class ControlJournalTests(unittest.TestCase):
    """Exercise real journal serialization with metadata-only workers; no fake MD results."""

    def setUp(self):
        """Allocate an isolated fixture with the same resource contract used by the example."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.run = self.root / "runs/fixture"
        self.profile = cpu_profile()
        self.spec = dict(execution_profile=self.profile, fixture="not a scientific experiment")
        self.control = control_root(self.run)

    def operation(self, module, request, event, paths, profile, seconds):
        """Validate the active worker handoff and persist only a clearly marked fixture result."""
        ledger = validate_journal(self.control, self.run, profile, content_hash(self.spec), allow_active=True)
        self.assertEqual(ledger["active"], event.name)
        write_json(event / "result.json", dict(fixture="metadata only"))
        return dict(returncode=0, stop_reason=None, elapsed_seconds=2, storage_bytes=usage(paths))

    def create(self, actions=("build",)):
        """Create closed fixture events through the real supervisor, without subprocess execution."""
        with patch("materiasim.runtime.control.watch", side_effect=self.operation):
            for action in actions:
                output = self.root / "analysis" if action == "analyze" else None
                args = dict(output_root=str(output)) if output else {}
                supervise(self.run, self.spec, "fixture", action, args, analysis_output=output)
        return read_json(self.control / "ledger.json")

    def inspect(self):
        """Return the validated fixture ledger without mutating its evidence."""
        return inspect_control(self.run, self.profile, content_hash(self.spec))[1]

    def event_path(self, ledger, index=0):
        """Locate an event only from the exact identity emitted by the fixture supervisor."""
        return self.control / "events" / ledger["events"][index]["id"]

    def test_new_records_bind_order_requests_results_and_outputs(self):
        """All actions bind to the same versioned identity and separately hashed result evidence."""
        ledger = self.create(("build", "run", "analyze"))
        self.assertEqual(self.inspect(), ledger)
        self.assertEqual(ledger["contract_version"], 2)
        self.assertEqual(ledger["outputs"], [str(self.root / "analysis")])
        previous = None
        for index, entry in enumerate(ledger["events"]):
            folder = self.event_path(ledger, index)
            request = read_json(folder / "request.json")
            self.assertEqual(request["sequence"], index)
            self.assertEqual(request["previous_outcome_sha256"], previous)
            self.assertEqual(entry["request_sha256"], sha256(folder / "request.json"))
            self.assertEqual(entry["result_sha256"], sha256(folder / "result.json"))
            previous = entry["outcome_sha256"]

    def test_malformed_ledger_rejected_before_worker_without_rewrite(self):
        """Invalid lists, booleans-as-versions and control identities cannot reach another worker."""
        ledger = self.create()
        for key, value in (("events", {}), ("events", [None]), ("outputs", {}),
                           ("contract_version", True), ("id", "../other"), ("active", "unknown")):
            with self.subTest(key=key, value=value):
                write_json(self.control / "ledger.json", dict(ledger, **{key: value}))
                before = inventory(self.control.parent, [self.control.name])
                with patch("materiasim.runtime.control.watch") as worker, self.assertRaises(ValueError):
                    supervise(self.run, self.spec, "fixture", "run", {})
                worker.assert_not_called()
                self.assertEqual(before, inventory(self.control.parent, [self.control.name]))

    def test_nonfinite_negative_and_boolean_charges_rejected(self):
        """Even matching rewritten outcomes cannot turn malformed accounting into valid credit."""
        ledger = self.create()
        folder = self.event_path(ledger)
        original = read_json(folder / "outcome.json")
        for value in (-1, True, "2"):
            with self.subTest(value=value):
                changed = deepcopy(ledger)
                write_json(folder / "outcome.json", dict(original, elapsed_seconds=value))
                changed["events"][0].update(charged_seconds=value, outcome_sha256=sha256(folder / "outcome.json"))
                write_json(self.control / "ledger.json", changed)
                with self.assertRaises(ValueError):
                    self.inspect()
        write_json(self.control / "ledger.json", ledger)
        # Standard JSON exponent overflow is distinct from the prohibited NaN/Infinity tokens.
        text = (self.control / "ledger.json").read_text().replace('"charged_seconds": 2', '"charged_seconds": 1e999')
        (self.control / "ledger.json").write_text(text)
        with self.assertRaises(ValueError):
            self.inspect()

    def test_request_and_result_mutation_is_detected(self):
        """Changed child arguments or a modified successful return cannot silently pass inspection."""
        ledger = self.create()
        folder = self.event_path(ledger)
        for filename in ("request.json", "result.json"):
            original = read_json(folder / filename)
            write_json(folder / filename, dict(original, fixture_mutation=True))
            with self.subTest(filename=filename), self.assertRaisesRegex(ValueError, "changed"):
                self.inspect()
            write_json(folder / filename, original)

    def test_duplicate_reordered_and_orphan_events_rejected(self):
        """Directory inventory plus request sequence catches duplicates, reordering and pre-ledger crash leftovers."""
        ledger = self.create(("build", "run", "analyze"))
        for events in (ledger["events"] * 2, [ledger["events"][0], ledger["events"][2], ledger["events"][1]]):
            write_json(self.control / "ledger.json", dict(ledger, events=events))
            with self.assertRaises(ValueError):
                self.inspect()
        write_json(self.control / "ledger.json", ledger)
        (self.control / "events/operation-orphan").mkdir()
        with self.assertRaisesRegex(ValueError, "differs"):
            self.inspect()

    def test_grant_predecessor_and_profile_binding_rejected(self):
        """Request validation checks semantics even when its file hash is consistently rewritten."""
        ledger = self.create(("build", "run"))
        folder = self.event_path(ledger, 1)
        original = read_json(folder / "request.json")
        for key, value in (("seconds", 1), ("previous_outcome_sha256", "0" * 64),
                           ("profile", {}), ("action", "analyze"), ("control_id", "0" * 32),
                           ("sequence", True), ("control_version", 1)):
            with self.subTest(key=key):
                changed = deepcopy(ledger)
                write_json(folder / "request.json", dict(original, **{key: value}))
                changed["events"][1]["request_sha256"] = sha256(folder / "request.json")
                write_json(self.control / "ledger.json", changed)
                with self.assertRaises(ValueError):
                    self.inspect()

    def test_success_and_stop_flags_must_match_outcome(self):
        """Changed success/stop flags cannot reclassify a durable worker outcome."""
        ledger = self.create()
        for key, value in (("successful", False), ("successful", 1), ("stop_reason", "cancelled"),
                           ("closed", 1), ("action", "unknown")):
            with self.subTest(key=key):
                changed = deepcopy(ledger)
                changed["events"][0][key] = value
                write_json(self.control / "ledger.json", changed)
                with self.assertRaises(ValueError):
                    self.inspect()

    def test_analysis_output_inventory_cannot_be_dropped(self):
        """Registered analysis roots are reconstructed from the durable request history."""
        ledger = self.create(("build", "run", "analyze"))
        write_json(self.control / "ledger.json", dict(ledger, outputs=[]))
        with self.assertRaisesRegex(ValueError, "output inventory"):
            self.inspect()

    def test_open_reservation_requires_full_charge_and_active_last_event(self):
        """Crash evidence is reserved, never settled as zero or treated as an idle journal."""
        with patch("materiasim.runtime.control.watch", side_effect=RuntimeError("fixture crash")):
            with self.assertRaises(RuntimeError):
                supervise(self.run, self.spec, "fixture", "build", {})
        with self.assertRaisesRegex(ValueError, "Uncertain"):
            self.inspect()
        ledger = read_json(self.control / "ledger.json")
        validate_journal(self.control, self.run, self.profile, content_hash(self.spec), allow_active=True)
        ledger["events"][0]["charged_seconds"] = 0
        write_json(self.control / "ledger.json", ledger)
        with self.assertRaisesRegex(ValueError, "reservation changed"):
            validate_journal(self.control, self.run, self.profile, content_hash(self.spec), allow_active=True)

    def test_legacy_control_reads_without_upgrade_or_new_operation(self):
        """A version-one metadata fixture retains its real old shape; missing new hashes are not invented."""
        ledger = self.create(("build", "run"))
        ledger["contract_version"] = 1
        for index, entry in enumerate(ledger["events"]):
            folder = self.event_path(ledger, index)
            request = read_json(folder / "request.json")
            for key in ("control_version", "sequence", "previous_outcome_sha256"):
                del request[key]
            write_json(folder / "request.json", request)
            for key in ("request_sha256", "result_sha256"):
                del entry[key]
        write_json(self.control / "ledger.json", ledger)
        before = inventory(self.control.parent, [self.control.name])
        self.assertEqual(self.inspect(), ledger)
        with patch("materiasim.runtime.control.watch") as worker, self.assertRaisesRegex(ValueError, "read-only"):
            supervise(self.run, self.spec, "fixture", "analyze", {})
        worker.assert_not_called()
        self.assertEqual(before, inventory(self.control.parent, [self.control.name]))

    def test_control_binding_rejects_version_or_id_change(self):
        """A manifest cannot be rebound to a replacement control ledger."""
        ledger = self.create()
        self.run.mkdir()
        write_json(self.run / "manifest.json", dict(operation_control=dict(contract_version=2, id=ledger["id"])))
        self.inspect()
        write_json(self.run / "manifest.json", dict(operation_control=dict(contract_version=1, id=ledger["id"])))
        with self.assertRaisesRegex(ValueError, "binding changed"):
            self.inspect()

    def test_symlink_roots_and_metadata_are_rejected(self):
        """The root itself, not only descendants, must remain on the registered storage path."""
        ledger = self.create()
        link = self.root / "linked"
        link.symlink_to(self.control, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            usage([str(link)])
        with self.assertRaisesRegex(ValueError, "Symlink"):
            usage([str(link / "missing")])
        folder = self.event_path(ledger)
        target = folder / "result.json"
        original = target.with_suffix(".original")
        target.rename(original)
        target.symlink_to(original)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.inspect()

    def test_fast_worker_still_faces_final_budget_check(self):
        """A process exiting before the first poll cannot evade storage/disk/wall admission."""
        event = self.root / "event"
        event.mkdir()
        process = unittest.mock.Mock(spec=subprocess.Popen)
        process.poll.return_value = 0
        process.returncode = 0
        disk = type("Disk", (), {"free": 2**30})()
        for size, free, seconds, expected in ((self.profile["storage_bytes"], 2**30, 100, "storage_budget"),
                                               (0, 0, 100, "disk_reserve"), (0, 2**30, 1, "wall_budget")):
            disk.free = free
            with self.subTest(reason=expected), patch("subprocess.Popen", return_value=process), \
                    patch("materiasim.runtime.control.cleanup"), \
                    patch("materiasim.runtime.control.usage", return_value=size), \
                    patch("shutil.disk_usage", return_value=disk), \
                    patch("materiasim.runtime.control.time.monotonic", side_effect=[0, 2]):
                outcome = watch("fixture", event / "request.json", event, [], self.profile, seconds)
            self.assertEqual(outcome["stop_reason"], expected)
            self.assertEqual(outcome["returncode"], 0)


if __name__ == "__main__":
    unittest.main()
