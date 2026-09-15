"""Serial registration and budget accounting; authoritative states remain in ordinary Runs."""

import shutil
import uuid
from pathlib import Path

from materiasim.storage import (contained, content_hash, read_json, run_lock, sha256,
                               utc_now, write_json)
from materiasim.specs.schema import identifier
from materiasim.research.plan import external_output, load_plan
from materiasim.research.resources import GRACE_SECONDS, storage_bytes, supervise
from materiasim.runtime.state import verify_run


def register(plan_root, output, gmx, packmol):
    """Reserve a deterministic batch directory and unique Run targets before any build."""
    plan_root = Path(plan_root).resolve()
    plan = load_plan(plan_root)
    root = external_output(output, [plan_root])
    root.mkdir(parents=True, exist_ok=True)
    batch = root / plan["plan_hash"]
    with run_lock(root):
        if batch.exists():
            validate_batch(batch)
            ledger = read_json(batch / "ledger.json")
            if ledger["gmx"] != gmx or ledger["packmol"] != packmol:
                raise ValueError("Registered tool candidates differ; batch is immutable")
            return batch
        if shutil.disk_usage(root).free < plan["research"]["limits"]["storage_bytes"]:
            raise ValueError("Free disk below batch storage reservation")
        batch.mkdir()
        shutil.copytree(plan_root, batch / "plan")
        if load_plan(batch / "plan")["plan_hash"] != plan["plan_hash"]:
            raise ValueError("Plan changed during batch registration")
        (batch / "operation_guard").mkdir()
        records = [dict(task_id=t["id"], run_id="research-" + uuid.uuid4().hex) for t in plan["tasks"]]
        ledger = dict(plan_hash=plan["plan_hash"], gmx=gmx, packmol=packmol, tasks=records,
                      registration_hash=content_hash(records), events=[], active=None,
                      charged_seconds=0, exhausted=False, created_utc=utc_now())
        write_json(batch / "ledger.json", ledger)
    return batch


def validate_batch(batch):
    """Verify plan, task mapping and exact reserved paths before querying or mutating a batch."""
    batch = Path(batch).resolve()
    plan = load_plan(batch / "plan")
    ledger = read_json(batch / "ledger.json")
    if ledger["plan_hash"] != plan["plan_hash"] or content_hash(ledger["tasks"]) != ledger["registration_hash"]:
        raise ValueError("Batch plan or registration identity changed")
    if [r["task_id"] for r in ledger["tasks"]] != [t["id"] for t in plan["tasks"]]:
        raise ValueError("Batch task registration differs from frozen plan")
    run_ids = []
    for record in ledger["tasks"]:
        identifier(record["run_id"], "registered run id")
        contained(batch, "runs/" + record["run_id"])
        run_ids.append(record["run_id"])
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("Duplicate registered Run target")
    return plan, ledger


def task_state(batch, task, record):
    """Read actual Run state and verify identity whenever its seal is available."""
    root = contained(batch, "runs/" + record["run_id"])
    if not root.exists():
        return "not_started"
    if not (root / "status.json").is_file():
        return "uncertain"
    state = read_json(root / "status.json")["status"]
    if state in ("ready", "interrupted", "completed"):
        _, manifest = verify_run(root)
        if manifest["spec_hash"] != task["spec_hash"] or manifest["run_id"] != record["run_id"]:
            raise ValueError("Registered Run identity mismatch")
    return state


def status(batch):
    """Return every declared repeat, including unstarted/failed/uncertain evidence, without writes."""
    batch = Path(batch).resolve()
    plan, ledger = validate_batch(batch)
    rows = []
    for task, record in zip(plan["tasks"], ledger["tasks"]):
        folders = sorted((batch / "analyses" / task["id"]).glob("*/status.json"))
        rows.append(dict(task_id=task["id"], case_id=task["case_id"], repeat=task["repeat"],
                         run_id=record["run_id"], status=task_state(batch, task, record),
                         analysis_states=[read_json(p)["status"] for p in folders]))
    return dict(batch_dir=str(batch), plan_hash=plan["plan_hash"], tasks=rows,
                charged_seconds=ledger["charged_seconds"], active=ledger["active"],
                exhausted=ledger["exhausted"], scientific_quality="not_assessed")


def perform(batch, plan, ledger, index, action):
    """Charge a maximum before launch, replacing it with measured cost only after a clean handoff."""
    limits = plan["research"]["limits"]
    key = {"build": "build_seconds", "analyze": "analysis_seconds",
           "run": "execution_seconds", "resume": "execution_seconds"}[action]
    available = limits["total_seconds"] - ledger["charged_seconds"] - GRACE_SECONDS
    if available < 1 or storage_bytes(batch) >= limits["storage_bytes"]:
        ledger["exhausted"] = True
        write_json(batch / "ledger.json", ledger)
        raise ValueError("Batch wall/storage budget exhausted")
    seconds = min(limits[key], available)
    reserved = seconds + GRACE_SECONDS
    event_id = "event-" + uuid.uuid4().hex
    ledger["active"] = dict(index=index, action=action, event_id=event_id, reserved_seconds=reserved)
    ledger["charged_seconds"] += reserved
    write_json(batch / "ledger.json", ledger)
    result = supervise(batch, index, action, seconds, limits["storage_bytes"], batch / "events" / event_id)
    result.update(index=index, event_id=event_id)
    ledger["events"].append(result)
    ledger["active"] = None
    ledger["charged_seconds"] += result["elapsed_seconds"] - reserved
    ledger["exhausted"] = (result["stop_reason"] in ("storage_budget", "disk_reserve", "worker_did_not_stop")
                           or ledger["charged_seconds"] >= limits["total_seconds"]
                           or result["storage_bytes"] >= limits["storage_bytes"])
    write_json(batch / "ledger.json", ledger)
    if result["returncode"] != 0 or result["stop_reason"] is not None:
        raise RuntimeError(f"Batch stopped after {action}; inspect {batch / 'events' / event_id}")


def recover_handoff(batch, plan, ledger, resume):
    """Recover only sealed handoffs; missing/failed evidence cannot trigger automatic rebuild."""
    active = ledger["active"]
    if active is None:
        return
    if not resume:
        raise ValueError("Unfinished handoff requires explicit --resume and evidence inspection")
    index = active["index"]
    state = task_state(batch, plan["tasks"][index], ledger["tasks"][index])
    allowed = {"build": ("ready",), "run": ("interrupted", "completed"),
               "resume": ("interrupted", "completed"), "analyze": ("completed",)}
    if state not in allowed[active["action"]]:
        raise ValueError("Uncertain/failed handoff; refusing to rebuild or restart automatically")
    if active["action"] == "analyze":
        from materiasim.research.compare import task_reports
        task_reports(batch, plan["tasks"][index], ledger["tasks"][index], required=True)
    ledger["events"].append(dict(active, recovered_handoff=True, cost="full reservation retained"))
    ledger["active"] = None
    write_json(batch / "ledger.json", ledger)


def run(plan_root, output, gmx="gmx", packmol="packmol", resume=False):
    """Run serially or explicitly resume; identical completed plans never launch duplicate tasks."""
    batch = register(plan_root, output, gmx, packmol)
    with run_lock(batch):
        # An orphan worker keeps this guard until it finishes; do not race its evidence.
        with run_lock(batch / "operation_guard"):
            plan, ledger = validate_batch(batch)
            recover_handoff(batch, plan, ledger, resume)
        if ledger["exhausted"]:
            raise ValueError("Batch resources exhausted; no implicit budget expansion")
        for index, (task, record) in enumerate(zip(plan["tasks"], ledger["tasks"])):
            advance_task(batch, plan, ledger, index, task, record, resume)
    return status(batch)


def advance_task(batch, plan, ledger, index, task, record, resume):
    """Advance one registered ordinary Run, stopping at the first unresolved operation."""
    from materiasim.research.compare import task_reports
    state = task_state(batch, task, record)
    history = [e for e in ledger["events"] if e["index"] == index]
    if state == "not_started":
        if history:
            raise ValueError("Prior task operation has no Run evidence; refusing duplicate build")
        perform(batch, plan, ledger, index, "build")
        state = task_state(batch, task, record)
    if state in ("ready", "interrupted"):
        if state == "interrupted" and not resume:
            raise ValueError("Interrupted Run requires explicit research run --resume")
        attempts = sum(e["action"] in ("run", "resume") for e in ledger["events"] if e["index"] == index)
        # Include attempts made directly through the core, not just batch events.
        root = batch / "runs" / record["run_id"]
        actual = sum(p.name.startswith(("run-", "resume-")) for p in (root / "attempts").iterdir())
        if max(attempts, actual) >= plan["research"]["limits"]["max_attempts"]:
            raise ValueError("Run attempt budget exhausted")
        perform(batch, plan, ledger, index, "resume" if state == "interrupted" else "run")
        state = task_state(batch, task, record)
    if state != "completed":
        raise ValueError(f"Batch stopped at {task['id']}: {state}; no automatic retry")
    reports = task_reports(batch, task, record)
    if not reports:
        if any(e["action"] == "analyze" for e in history):
            raise ValueError("Previous analysis has no complete evidence; refusing automatic retry")
        perform(batch, plan, ledger, index, "analyze")
    task_reports(batch, task, record, required=True)
