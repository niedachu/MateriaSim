"""Detached local supervision; requests never signal a PID recovered from an old file."""

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from materiasim.harness import journal
from materiasim.harness.contracts import bounded_json, timestamp
from materiasim.harness.service import check_authority
from materiasim.harness.snapshots import load
from materiasim.research.resources import storage_bytes
from materiasim.runtime.family import launch, kill, cleanup
from materiasim.storage import content_hash, run_lock, sha256

GRACE_SECONDS = 90


def verify_receipt(root, manifest, receipt, operation_id):
    """Validate the bounded receipt and recheck successful claims against canonical core evidence."""
    from materiasim.specs.schema import fields
    from materiasim.harness.operations import inspect_result, progress
    if not isinstance(receipt, dict) or type(receipt.get("ok")) is not bool:
        raise ValueError("Worker receipt requires boolean ok")
    fields(receipt, ("operation_id", "ok", "result" if receipt["ok"] else "error"), "receipt")
    if receipt["operation_id"] != operation_id:
        raise ValueError("Worker receipt belongs to another operation")
    if receipt["ok"]:
        result = receipt["result"]
        if not isinstance(result, dict) or not isinstance(result.get("status"), str):
            raise ValueError("Invalid worker result")
        status = result["status"]
        actual = (progress(Path(root), manifest, status) if status in ("paused", "interrupted")
                  else inspect_result(Path(root), manifest))
        if actual != result:
            raise ValueError("Worker receipt differs from canonical evidence")
    elif not isinstance(receipt["error"], dict):
        raise ValueError("Worker failure requires a structured diagnostic")


def verify_resume(root, manifest, events):
    """Require unchanged settled progress before resuming; deleting prior work cannot trigger rebuilding."""
    previous = [e["data"] for e in events if e["kind"] == "outcome"]
    if not previous or previous[-1]["receipt_sha256"] is None:
        raise ValueError("Resume has no sealed worker progress")
    record = previous[-1]
    path = root / "operations" / record["operation_id"] / "result.json"
    if sha256(path) != record["receipt_sha256"]:
        raise ValueError("Settled worker receipt changed")
    receipt = bounded_json(path)
    if not receipt["ok"]:
        raise ValueError("Failed worker cannot resume implicitly")
    verify_receipt(root, manifest, receipt, record["operation_id"])


def outcome(receipt):
    """Map canonical worker results to engineering outcomes without interpreting prose errors."""
    if not receipt["ok"]:
        return "failed", "worker_error; see structured receipt"
    result = receipt["result"]
    if result["status"] == "engineering_complete":
        return "completed", "all_declared_engineering_work_complete"
    if result["status"] in ("paused", "interrupted"):
        return "paused", "verified_core_interruption; explicit resume required"
    return "failed", "engineering_checks_or_execution_incomplete"


def settle(root, active, receipt, elapsed, reason):
    """Settle once after worker exit, retaining cancellation precedence and receipt identity."""
    status, explanation = outcome(receipt) if receipt else ("needs_human_review", "missing_worker_receipt")
    if reason in ("wall_budget", "storage_budget", "disk_reserve", "authorization_expired"):
        status, explanation = "budget_exhausted", reason
    elif reason == "forced_stop":
        status, explanation = "needs_human_review", reason
    elif reason == "cancelled":
        status, explanation = "cancelled", "supervisor_or_user_stop"
    folder = Path(root) / "operations" / active["operation_id"]
    manifest = load(root)
    with journal.transaction(root) as db:
        state = journal.append(db, "outcome", dict(operation_id=active["operation_id"], status=status,
            reason=explanation, charged_seconds=elapsed,
            receipt_sha256=sha256(folder / "result.json") if receipt else None))
        if state.get("agent_enabled") and state["status"] == "paused" and state["request"] is None:
            from materiasim.harness.agent_state import deadline
            state = journal.append(db, "agent_wait", dict(deadline=deadline(manifest)))
        return state


def recover(root, active):
    """Reconcile a settled worker only; ambiguous submission retains its reserved budget."""
    # The guard, not an old PID or heartbeat, determines whether a writer remains.
    with run_lock(Path(root) / "worker_guard"):
        path = Path(root) / "operations" / active["operation_id"] / "result.json"
        if not path.is_file():
            with journal.transaction(root) as db:
                state, _ = journal.read(db)
                if state["status"] != "needs_human_review":
                    journal.append(db, "uncertain", dict(operation_id=active["operation_id"]))
            raise RuntimeError("Uncertain operation without receipt; no automatic resubmission")
        receipt = bounded_json(path)
        verify_receipt(root, load(root), receipt, active["operation_id"])
        # No elapsed receipt from the supervisor means the full reservation is retained.
        return settle(root, active, receipt, active["reserved_seconds"], None)


def reconcile(root):
    """Explicitly recover SQLite's own journal and settle evidence; never submit an MD worker."""
    from materiasim.research.plan import external_output
    root = external_output(root)
    manifest = bounded_json(root / "manifest.json")
    payload = dict(manifest)
    digest = payload.pop("manifest_hash")
    if manifest["contract_version"] not in (2, 3) or content_hash(payload) != digest:
        raise ValueError("Reconciliation requires an intact v2/v3 manifest")
    with run_lock(root / "supervisor"):
        with run_lock(root / "worker_guard"):
            # Opening a writable transaction lets SQLite perform hot-journal rollback.
            # Never edit/truncate journal bytes or infer completion from a missing event.
            with journal.transaction(root) as db:
                journal.read(db)
        load(root)
        state = journal.status(root)
        if state["active"]:
            return recover(root, state["active"])
        if state.get("pending_launch"):
            with journal.transaction(root) as db:
                return journal.append(db, "launch_reconciled", dict(launch_id=state["pending_launch"]))
        return state


def watch(root, manifest, active):
    """Monitor one owned process group, its authorization and whole-Campaign storage allowance."""
    folder = root / "operations" / active["operation_id"]
    started, process, owner, reason, stopping = time.monotonic(), None, False, None, None
    interrupted = []

    def stop(signum, frame):
        """Record supervisor interruption; the watcher owns cooperative shutdown and accounting."""
        interrupted.append(signum)

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    reader, writer = os.pipe()
    try:
        with (folder / "stdout.log").open("x") as out, (folder / "stderr.log").open("x") as err:
            process, owner = launch([sys.executable, "-B", "-m", "materiasim.harness.operations",
                str(root), active["operation_id"], str(reader)], stdout=out, stderr=err,
                stdin=subprocess.DEVNULL, pass_fds=(reader,))
            os.close(reader)
            reader = None
            while process.poll() is None:
                state = journal.status(root)
                elapsed = time.monotonic() - started
                if state["request"] in ("cancel", "revoke") or interrupted:
                    reason = "cancelled"
                elif datetime.now(timezone.utc) >= timestamp(manifest["authorization"]["expires_utc"]):
                    reason = "authorization_expired"
                elif elapsed >= active["reserved_seconds"] - GRACE_SECONDS:
                    reason = "wall_budget"
                elif storage_bytes(root) >= manifest["authorization"]["storage_bytes"]:
                    reason = "storage_budget"
                elif shutil.disk_usage(root).free < 64 * 1024 * 1024:
                    reason = "disk_reserve"
                if reason and stopping is None:
                    process.send_signal(signal.SIGTERM)
                    stopping = time.monotonic()
                if stopping is not None and time.monotonic() - stopping >= GRACE_SECONDS:
                    kill(process, owner)
                    reason = "forced_stop"
                    break
                time.sleep(.2)
            process.wait()
    finally:
        if reader is not None:
            os.close(reader)
        os.close(writer)
        if process is not None:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.wait(timeout=GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    kill(process, owner)
                    process.wait()
            cleanup(process, owner)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    elapsed = time.monotonic() - started
    if elapsed > active["reserved_seconds"]:
        reason = "wall_budget"
    if storage_bytes(root) >= manifest["authorization"]["storage_bytes"]:
        reason = "storage_budget"
    path = folder / "result.json"
    receipt = bounded_json(path) if path.exists() else None
    if receipt and receipt["operation_id"] != active["operation_id"]:
        raise ValueError("Operation receipt identity mismatch")
    if process.returncode != 0 and receipt and receipt["ok"]:
        raise ValueError("Worker exit conflicts with successful receipt")
    if receipt:
        verify_receipt(root, manifest, receipt, active["operation_id"])
    if shutil.disk_usage(root).free < 64 * 1024 * 1024:
        reason = "disk_reserve"
    if datetime.now(timezone.utc) >= timestamp(manifest["authorization"]["expires_utc"]):
        reason = "authorization_expired"
    return settle(root, active, receipt, elapsed, reason)


def run(root):
    """Supervise a frozen target; agent campaigns wait between individually approved operations."""
    root = Path(root).resolve()
    manifest = load(root, current=True)
    with run_lock(root / "supervisor"):
        state = journal.status(root)
        if state["active"]:
            return recover(root, state["active"])
        if manifest["contract_version"] != 3:
            return advance(root, manifest)
        from materiasim.harness.agent_service import tick
        while True:
            state = tick(root)
            if state["status"] == "waiting_for_agent":
                time.sleep(.2)
            elif state["status"] == "ready":
                advance(root, manifest)
            else:
                return state


def advance(root, manifest):
    """Spend one ready permit under the existing budget and canonical recovery checks."""
    with journal.transaction(root) as db:
        state, events = journal.read(db)
        if state["status"] != "ready":
            return state
        resume = state["operations"] > 0
        check_authority(manifest, state, resume)
        if state.get("agent_enabled"):
            if datetime.now(timezone.utc) >= timestamp(state["permit_expires_utc"]):
                return journal.append(db, "agent_timeout", dict(reason="decision_timeout"))
        if resume:
            verify_resume(root, manifest, events)
        available = manifest["authorization"]["total_seconds"] - state["charged_seconds"]
        if (available <= GRACE_SECONDS or state["operations"] >= manifest["max_invocations"] or
                storage_bytes(root) >= manifest["authorization"]["storage_bytes"]):
            return journal.append(db, "stop", dict(status="budget_exhausted", reason="campaign_budget"))
        operation_id = "op-" + uuid.uuid4().hex
        (root / "operations" / operation_id).mkdir()
        active = dict(operation_id=operation_id, resume=resume, reserved_seconds=available,
                      owner_token=uuid.uuid4().hex)
        journal.append(db, "intent", active)
    return watch(root, manifest, active)


def start(root):
    """Start a detached supervisor and return a launch identity, never an assertion of completion."""
    root = Path(root).resolve()
    manifest = load(root, current=True)
    with run_lock(root / "supervisor"), journal.transaction(root) as db:
        state, _ = journal.read(db)
        if state["status"] not in ("ready", "waiting_for_agent") or state["active"] or state.get("pending_launch"):
            return state
        check_authority(manifest, state, state["operations"] > 0)
        if len(list((root / "launches").iterdir())) >= manifest["max_invocations"]:
            raise ValueError("Supervisor launch allowance exhausted")
        folder = root / "launches" / ("launch-" + uuid.uuid4().hex)
        folder.mkdir()
        journal.append(db, "launch", dict(launch_id=folder.name, host=socket.gethostname(), instance=uuid.uuid4().hex))
    env = dict(os.environ)
    env.pop("MATERIASIM_MANAGED_GROUP", None)
    with (folder / "stdout.log").open("x") as out, (folder / "stderr.log").open("x") as err:
        child = subprocess.Popen([sys.executable, "-B", "-m", "materiasim.harness.supervisor", str(root)],
            stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True, env=env)
    return dict(campaign_dir=str(root), launch_id=folder.name, pid=child.pid,
                status="supervisor_launched", warning="PID is informational, not a recovery authority")


if __name__ == "__main__":
    run(sys.argv[1])
