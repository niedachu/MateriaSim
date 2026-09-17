"""One existing experiment or research workflow, never a second numerical runner."""

import signal
import sys
from pathlib import Path

from materiasim.harness import journal
from materiasim.harness.snapshots import load, verify_tools
from materiasim.storage import content_hash, inventory, read_json, run_lock, write_json
from materiasim.errors import MateriaSimError
from materiasim.harness.failures import PauseRequested, failure


def boundary(root, manifest, resume, task_id, action, connection=None):
    """Admit an operation under current control and, for live workers, the supervisor connection."""
    from materiasim.harness.service import check_authority
    with journal.transaction(root) as db:
        if connection is not None:
            connection.check()
        state, _ = journal.read(db)
        check_authority(manifest, state, resume)
        if state["request"] == "pause" or (state.get("agent_enabled") and state.get("last_boundary")):
            raise PauseRequested()
        journal.append(db, "boundary", dict(operation_id=state["active"]["operation_id"],
                                           task_id=task_id, action=action))


def progress(root, manifest, status):
    """Seal current canonical progress at a safe pause/interruption boundary without rerunning work."""
    if manifest["automation"]["target"]["kind"] == "research":
        from materiasim.research.batch import status as batch_status
        from materiasim.research.plan import load_plan
        frozen = load_plan(root / "snapshot")
        state = batch_status(root / "work/batches" / frozen["plan_hash"])
        if state["active"]:
            raise ValueError("Cannot seal a pause with an unsettled core operation")
    else:
        from materiasim.runtime.state import verify_run
        run = root / "work/runs/experiment"
        state = dict(status="not_started")
        if run.exists():
            verify_run(run)
            state = read_json(run / "status.json")
    return dict(status=status, progress=state, progress_hash=content_hash(inventory(root, ["work"])))


def inspect_result(root, manifest):
    """Reverify existing canonical outputs without building, running or analyzing anything."""
    if manifest["automation"]["target"]["kind"] == "research":
        from materiasim.research.compare import compare
        from materiasim.research.plan import load_plan
        frozen = load_plan(root / "snapshot")
        return compare(root / "work/batches" / frozen["plan_hash"])
    from materiasim.runtime.state import verify_run
    from materiasim.analysis.locations import generations
    from materiasim.research.compare import verified_report
    run = root / "work/runs/experiment"
    spec, identity = verify_run(run)
    state = read_json(run / "status.json")["status"]
    if state != "completed":
        return dict(status=state, run_dir=str(run))
    reports = [verified_report(p, run, spec, identity) for p in generations(root / "work/analyses")]
    if sorted(r["request_hash"] for r in reports) != sorted(content_hash(r) for r in spec["analysis_requests"]):
        raise ValueError("Configured analyses are incomplete or duplicated")
    return dict(status="engineering_complete", run_dir=str(run),
                reports=[dict(path=r["analysis_dir"], sha256=r["report_sha256"]) for r in reports],
                scientific_quality="not_assessed")


def experiment(root, manifest, resume, connection):
    """Advance a frozen experiment under its supervisor connection, preserving existing work."""
    from materiasim.workflows.build import build
    from materiasim.workflows.execute import execute
    from materiasim.workflows.analysis import analyze
    from materiasim.runtime.state import verify_run
    run = root / "work/runs/experiment"
    if not run.exists():
        # A control directory without its Run indicates interrupted construction.
        if (root / "work/runs/.materiasim-operations/experiment").exists():
            raise ValueError("Uncertain previous construction; no automatic rebuild")
        boundary(root, manifest, resume, "experiment", "build", connection)
        build(root / "snapshot/experiment.json", root / "work/runs",
              manifest["tools"]["gmx"], manifest["tools"]["packmol"], run_id="experiment")
    spec, identity = verify_run(run)
    state = read_json(run / "status.json")["status"]
    if state in ("ready", "interrupted"):
        if state == "interrupted" and not resume:
            return progress(root, manifest, "interrupted")
        boundary(root, manifest, resume, "experiment", "resume" if state == "interrupted" else "run", connection)
        execute(run, state == "interrupted", manifest["tools"]["gmx"])
    state = read_json(run / "status.json")["status"]
    if state != "completed":
        return progress(root, manifest, state)
    analyses = root / "work/analyses"
    if spec["analysis_requests"] and not analyses.exists():
        boundary(root, manifest, resume, "experiment", "analyze", connection)
        analyze(run, analyses)
    return inspect_result(root, manifest)


def perform(root, manifest, resume, connection):
    """Delegate the selected target under a live connection and return canonical core evidence."""
    if manifest["automation"]["target"]["kind"] == "experiment":
        return experiment(root, manifest, resume, connection)
    from materiasim.research.batch import run
    from materiasim.research.compare import compare
    def gate(task_id, action):
        """Admit one existing research operation using current Campaign authority."""
        boundary(root, manifest, resume, task_id, action, connection)

    result = run(root / "snapshot", root / "work/batches", manifest["tools"]["gmx"],
                 manifest["tools"]["packmol"], resume=resume, before_operation=gate)
    return compare(Path(result["batch_dir"]))


def main():
    """Execute a live supervisor's outstanding intent under a lock, then seal one receipt."""
    from materiasim.harness.liveness import SupervisorConnection
    root, operation_id = Path(sys.argv[1]).resolve(), sys.argv[2]
    def stop(signum, frame):
        """Stop between nested supervised operations; their own handlers preserve in-flight evidence."""
        raise RuntimeError("Campaign worker received cooperative stop")

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    from materiasim.specs.schema import identifier
    identifier(operation_id, "operation id")
    with run_lock(root / "worker_guard"):
        manifest = load(root, current=True)
        state = journal.status(root)
        active = state["active"]
        if not active or active["operation_id"] != operation_id:
            raise ValueError("Worker has no registered operation")
        folder = root / "operations" / operation_id
        if (folder / "result.json").exists():
            raise ValueError("Worker operation already has a receipt")
        try:
            from materiasim.harness.service import check_authority
            with SupervisorConnection(int(sys.argv[3])) as connection:
                check_authority(manifest, state, active["resume"])
                verify_tools(manifest)
                result = perform(root, manifest, active["resume"], connection)
            receipt = dict(operation_id=operation_id, ok=True, result=result)
        except PauseRequested:
            receipt = dict(operation_id=operation_id, ok=True, result=progress(root, manifest, "paused"))
        except (ValueError, OSError, RuntimeError) as error:
            if isinstance(error, MateriaSimError) and error.code == "RUN_INTERRUPTED":
                receipt = dict(operation_id=operation_id, ok=True, result=progress(root, manifest, "interrupted"))
            else:
                phase = journal.status(root).get("last_boundary", {}).get("action", "admission")
                receipt = dict(operation_id=operation_id, ok=False, error=failure(error, phase))
        write_json(folder / "result.json", receipt)
        return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
