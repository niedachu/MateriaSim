"""Read-only, version-consistent evidence inventory with explicit missing/invalid task records."""

from pathlib import Path

from materiasim.errors import MateriaSimError
from materiasim.harness import journal
from materiasim.harness.contracts import TERMINAL
from materiasim.harness.snapshots import load
from materiasim.storage import contained, inventory, read_json, sha256


def check_file(root, relative, digest, issues):
    """Append a path-specific missing/corrupt-file issue without modifying the evidence."""
    try:
        path = contained(root, relative)
        actual = sha256(path)
        if digest is not None and actual != digest:
            issues.append(dict(path=relative, kind="digest_mismatch"))
    except (ValueError, OSError) as error:
        issues.append(dict(path=relative, kind="missing_or_unreadable", detail=str(error)))


def task_rows(root, manifest):
    """Return every declared task even when an entire batch or its ledger is missing."""
    research = manifest["automation"]["target"]["kind"] == "research"
    count = len(manifest["composition"]["selections"])
    rows = [dict(task_id=f"task-{i:03d}" if research else "experiment", status="not_started") for i in range(count)]
    try:
        if research:
            from materiasim.research.plan import load_plan
            from materiasim.research.compare import compare
            frozen = load_plan(root / "snapshot")
            batch = root / "work/batches" / frozen["plan_hash"]
            if batch.exists():
                return compare(batch)["tasks"]
        else:
            from materiasim.harness.operations import inspect_result
            from materiasim.runtime.state import verify_run
            run = root / "work/runs/experiment"
            if run.exists():
                state = read_json(run / "status.json")["status"]
                rows[0]["status"] = state
                if state in ("ready", "interrupted", "completed"):
                    verify_run(run)
                if state == "completed":
                    rows[0]["result"] = inspect_result(root, manifest)
    except (ValueError, OSError, KeyError) as error:
        for row in rows:
            row.update(status="invalid_or_incomplete_evidence", error=str(error))
    return rows


def controls(root, manifest, rows, issues):
    """Verify required whole-operation control ledgers for each available sealed Run."""
    from materiasim.runtime.state import verify_run
    from materiasim.runtime.control import inspect_control
    if manifest["automation"]["target"]["kind"] == "research":
        folder = root / "work/batches" / manifest["target"]["plan_hash"] / "runs"
    else:
        folder = root / "work/runs"
    for row in rows:
        if row["status"] not in ("ready", "interrupted", "completed"):
            continue
        run = folder / row.get("run_id", "experiment")
        try:
            spec, identity = verify_run(run)
            if spec["execution_profile"]["contract_version"] >= 2:
                _, ledger = inspect_control(run, spec["execution_profile"], identity["spec_hash"])
                if ledger["active"] is not None:
                    raise ValueError("Unsettled whole-operation control ledger")
        except (ValueError, OSError, KeyError) as error:
            issues.append(dict(task_id=row["task_id"], kind="invalid_core_control", detail=str(error)))


def evidence(root):
    """Audit a quiescent Campaign without writes; incomplete evidence can never certify closure."""
    root = Path(root).resolve()
    manifest = load(root, check_snapshot=False)
    db = journal.connect(root)
    try:
        state, events = journal.read(db)
    finally:
        db.close()
    if state["active"] or state["status"] not in TERMINAL | {"paused", "needs_human_review", "waiting_for_agent"}:
        raise MateriaSimError("EVIDENCE_NOT_QUIESCENT", "Account for active work before auditing", category="control")
    issues = []
    for relative, digest in manifest["snapshot_hashes"].items():
        check_file(root, relative, digest, issues)
    directories = ["snapshot", "work", "operations", "launches"]
    files = inventory(root, directories)
    unexpected = set(k for k in files if k.startswith("snapshot/")) - manifest["snapshot_hashes"].keys()
    issues.extend(dict(path=p, kind="untracked_snapshot_file") for p in sorted(unexpected))
    for event in events:
        data = event["data"]
        if event["kind"] == "outcome":
            relative = "operations/" + data["operation_id"] + "/result.json"
            if data["receipt_sha256"] is not None:
                check_file(root, relative, data["receipt_sha256"], issues)
            else:
                issues.append(dict(path=relative, kind="no_worker_receipt"))
        if event["kind"] == "intent":
            for name in ("stdout.log", "stderr.log"):
                check_file(root, "operations/" + data["operation_id"] + "/" + name, None, issues)
        if event["kind"] == "launch":
            for name in ("stdout.log", "stderr.log"):
                check_file(root, "launches/" + data["launch_id"] + "/" + name, None, issues)
    rows = task_rows(root, manifest)
    controls(root, manifest, rows, issues)
    for row in rows:
        if row["status"] == "invalid_or_incomplete_evidence":
            issues.append(dict(task_id=row["task_id"], kind="invalid_task", detail=row["error"]))
    if journal.status(root)["sequence"] != state["sequence"] or inventory(root, directories) != files:
        raise MateriaSimError("EVIDENCE_CHANGED", "Campaign changed during audit; read again", category="integrity")
    complete = not issues and all(r["status"] == "completed" for r in rows)
    return dict(contract_version=2, manifest_sha256=sha256(root / "manifest.json"),
                event_head=events[-1]["sha256"], events=events, files=files, tasks=rows, issues=issues,
                status=state["status"], scientific_quality="not_assessed", archive="not_exported",
                closure="completed_tasks_verified" if complete else "incomplete_or_failed",
                integrity="verified_inventory; failed and unstarted work is not certified complete")
