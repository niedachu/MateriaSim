"""Research admission, immutable inputs, serial registration and incomplete evidence guards."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from materiasim.storage import inventory, read_json, write_json
from materiasim.research.schema import expand
from materiasim.research.plan import load_plan, plan
from materiasim.research.batch import register, run, status, perform
from materiasim.research.compare import compare

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / "studies/zil_count_smoke/research.json"


class ResearchTests(unittest.TestCase):
    """Use real frozen specifications; mock only engine-start guards, never scientific success."""

    def setUp(self):
        """Create isolated source variants and explicit external plan/output directories."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.definition = read_json(STUDY)
        for case in self.definition["cases"]:
            case["experiment"] = str(STUDY.parent / case["experiment"])
        self.source = self.root / "source/research.json"
        write_json(self.source, self.definition)

    def freeze(self):
        """Create and return a real four-task closed plan for each isolated test."""
        plan(self.source, self.root / "frozen")
        return self.root / "frozen"

    def reject(self):
        """Assert a modified research definition fails admission without writing outputs."""
        write_json(self.source, self.definition)
        with self.assertRaises(ValueError):
            expand(self.source)

    def test_preview_is_read_only_and_fully_explicit(self):
        """Planning resolves all four seed pairs but does not call an engine or write files."""
        before = inventory(self.root, ["source"])
        with patch("materiasim.engines.gromacs.command.engine_info", side_effect=AssertionError("engine called")):
            result = plan(self.source)
        self.assertEqual(len(result["tasks"]), 4)
        self.assertEqual(inventory(self.root, ["source"]), before)
        self.assertEqual(list(self.root.iterdir()), [self.source.parent])
        self.assertEqual([t["spec"]["scenario"]["seed"] for t in result["tasks"]], [73129, 73130, 73131, 73132])
        self.assertTrue(all(s["seed"] is None for t in result["tasks"] for s in t["spec"]["protocol"]["stages"] if s["velocities"] == "inherit"))

    def test_unknown_repeat_override_rejected(self):
        """Repeats may not change temperature or arbitrary experiment fields."""
        self.definition["cases"][0]["repeats"][0]["temperature"] = 500
        self.reject()

    def test_seed_and_duplicate_guards(self):
        """Reject duplicate pairs, booleans and unbounded/implicit random seeds."""
        for value in (True, -1, 0, 2147483647):
            with self.subTest(value=value):
                self.definition["cases"][0]["repeats"][0]["packing_seed"] = value
                self.reject()
        self.definition["cases"][0]["repeats"][0] = dict(self.definition["cases"][0]["repeats"][1], id="r1")
        self.reject()

    def test_task_and_storage_admission(self):
        """Task, concurrency and storage admission fail before a build."""
        for key, value in (("max_tasks", 3), ("concurrency", 2), ("storage_bytes", 1024 * 1024), ("total_seconds", 1801)):
            original = self.definition["limits"][key]
            with self.subTest(key=key):
                self.definition["limits"][key] = value
                self.reject()
            self.definition["limits"][key] = original

    def test_undeclared_difference_rejected(self):
        """A changed cutoff cannot be hidden inside a count-only comparison."""
        source = Path(self.definition["cases"][1]["experiment"])
        experiment = read_json(source)
        experiment["components"][0]["model"] = str((source.parent / experiment["components"][0]["model"]).resolve())
        for key in ("protocol", "interaction_bundle"):
            experiment[key] = str((source.parent / experiment[key]).resolve())
        experiment["analysis_requests"][0]["config"]["cutoff_nm"] = .6
        variant = self.root / "source/changed.json"
        write_json(variant, experiment)
        self.definition["cases"][1]["experiment"] = str(variant)
        self.reject()

    def test_frozen_plan_relocation_and_tamper(self):
        """Frozen assets resolve after relocation, and changing one byte is rejected."""
        frozen = self.freeze()
        moved = self.root / "relocated with spaces"
        shutil.copytree(frozen, moved)
        self.assertEqual(load_plan(frozen)["plan_hash"], load_plan(moved)["plan_hash"])
        asset = moved / "tasks/task-000/assets/zil.itp"
        asset.write_bytes(asset.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            load_plan(moved)

    def test_no_plan_overwrite_or_source_output(self):
        """Explicit save refuses both an existing frozen plan and a source-local target."""
        frozen = self.freeze()
        with self.assertRaises(FileExistsError):
            plan(self.source, frozen)
        with self.assertRaisesRegex(ValueError, "outside"):
            plan(self.source, self.source.parent / "forbidden")

    def test_registration_is_idempotent_and_status_read_only(self):
        """The same plan returns the same four reserved Run IDs without starting any work."""
        frozen = self.freeze()
        batch = register(frozen, self.root / "batches", "gmx", "packmol")
        before = inventory(batch, ["plan"])
        ledger = read_json(batch / "ledger.json")
        self.assertEqual(batch, register(frozen, self.root / "batches", "gmx", "packmol"))
        self.assertEqual(read_json(batch / "ledger.json"), ledger)
        self.assertEqual([r["status"] for r in status(batch)["tasks"]], ["not_started"] * 4)
        self.assertEqual(inventory(batch, ["plan"]), before)
        report = compare(batch)
        self.assertEqual(len(report["tasks"]), 4)
        self.assertEqual(report["aggregates"], [])
        self.assertEqual(report["status"], "incomplete")

    def test_crashed_handoff_never_rebuilds(self):
        """An operation reserved before a crash cannot silently create another Run."""
        frozen = self.freeze()
        batch = register(frozen, self.root / "batches", "gmx", "packmol")
        ledger = read_json(batch / "ledger.json")
        ledger["active"] = dict(index=0, action="build", event_id="test", reserved_seconds=620)
        ledger["charged_seconds"] = 620
        write_json(batch / "ledger.json", ledger)
        with patch("materiasim.research.batch.supervise", side_effect=AssertionError("worker called")):
            for resume in (False, True):
                with self.subTest(resume=resume), self.assertRaises(ValueError):
                    run(frozen, self.root / "batches", resume=resume)
        self.assertFalse((batch / "runs").exists())

    def test_operation_failure_stops_and_preserves_reservation(self):
        """Worker failure is recorded, unstarted tasks remain visible, and retries are refused."""
        frozen = self.freeze()
        result = dict(action="build", returncode=1, stop_reason=None, elapsed_seconds=.1, storage_bytes=10)
        with patch("materiasim.research.batch.supervise", return_value=result) as worker:
            with self.assertRaises(RuntimeError):
                run(frozen, self.root / "batches")
            self.assertEqual(worker.call_count, 1)
            with self.assertRaisesRegex(ValueError, "no Run evidence"):
                run(frozen, self.root / "batches", resume=True)
            self.assertEqual(worker.call_count, 1)

    def test_total_budget_charged_before_worker_launch(self):
        """A worker crash retains its full granted budget instead of resetting elapsed cost."""
        frozen = self.freeze()
        batch = register(frozen, self.root / "batches", "gmx", "packmol")
        ledger = read_json(batch / "ledger.json")
        with patch("materiasim.research.batch.supervise", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                perform(batch, load_plan(frozen), ledger, 0, "build")
        recorded = read_json(batch / "ledger.json")
        self.assertEqual(recorded["charged_seconds"], 620)
        self.assertEqual(recorded["active"]["action"], "build")


if __name__ == "__main__":
    unittest.main()
