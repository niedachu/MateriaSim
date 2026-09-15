"""Whole-operation resource supervision outside immutable MD Runs and analysis inputs."""

import os
import signal
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from materiasim.storage import contained, content_hash, read_json, run_lock, sha256, write_json
from materiasim.errors import MateriaSimError
from materiasim.runtime.journal import LIMITS, storage_path, validate_journal
from materiasim.runtime.family import launch, kill, cleanup


def control_root(run):
    """Locate the portable sibling control journal; Run and control tree must travel together."""
    run = Path(run).resolve()
    return contained(run.parent, ".materiasim-operations/" + run.name)


def usage(paths):
    """Count distinct registered output trees, rejecting links instead of following external storage."""
    seen, size = set(), 0
    for root in paths:
        for path in storage_path(str(root)).rglob("*"):
            if path.is_symlink():
                raise ValueError("Symlink in supervised storage")
            try:
                if path.is_file() and path not in seen:
                    seen.add(path)
                    size += path.stat().st_size
            except FileNotFoundError:
                # Atomic metadata replacement can retire its temporary file during sampling.
                continue
    return size


def inspect_control(run, profile, spec_hash):
    """Return a read-only validated control root/ledger, including historical contract v1."""
    root = control_root(run)
    return root, validate_journal(root, run, profile, spec_hash)


def watch(module, request, event, paths, profile, seconds):
    """Supervise one normal workflow subprocess including startup, Python work, native tools and exit."""
    cancelled, reason = [], None

    def stop(signum, frame):
        """Ask the worker to stop, leaving native checkpoint handling to the existing runner."""
        cancelled.append(signum)

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    started, process, owner = time.monotonic(), None, False
    try:
        with (event / "stdout.log").open("w") as out, (event / "stderr.log").open("w") as err:
            process, owner = launch([sys.executable, "-B", "-m", module, str(request)],
                                    stdout=out, stderr=err, stdin=subprocess.DEVNULL)
            while process.poll() is None:
                if cancelled:
                    reason = "cancelled"
                elif time.monotonic() - started >= seconds:
                    reason = "wall_budget"
                elif usage(paths) >= profile["storage_bytes"]:
                    reason = "storage_budget"
                elif shutil.disk_usage(event).free < profile["min_free_bytes"]:
                    reason = "disk_reserve"
                if reason:
                    process.send_signal(signal.SIGTERM)
                    break
                time.sleep(.1)
            try:
                process.wait(timeout=profile["termination_grace_seconds"])
            except subprocess.TimeoutExpired:
                kill(process, owner)
                process.wait()
                reason = "worker_did_not_stop"
    finally:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=profile["termination_grace_seconds"])
            except subprocess.TimeoutExpired:
                kill(process, owner)
                process.wait()
        if process is not None:
            cleanup(process, owner)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    elapsed, size = time.monotonic() - started, usage(paths)
    # A fast worker may finish between samples; successful exit does not waive its budget.
    if reason is None:
        if elapsed >= seconds:
            reason = "wall_budget"
        elif size >= profile["storage_bytes"]:
            reason = "storage_budget"
        elif shutil.disk_usage(event).free < profile["min_free_bytes"]:
            reason = "disk_reserve"
    return dict(returncode=process.returncode, stop_reason=reason, elapsed_seconds=elapsed, storage_bytes=size)


def supervise(run, spec, module, action, arguments, analysis_output=None):
    """Reserve and account a whole build/run/resume/analyze operation with immutable profile limits."""
    run = Path(run).resolve()
    profile, spec_hash = spec["execution_profile"], content_hash(spec)
    root = control_root(run)
    if action == "build":
        if run.exists():
            raise FileExistsError(run)
        root.mkdir(parents=True, exist_ok=False)
        (root / "worker_guard").mkdir()
        ledger = dict(contract_version=2, id=uuid.uuid4().hex, run_id=run.name,
                      spec_hash=spec_hash, profile_hash=content_hash(profile), events=[], active=None, outputs=[])
        write_json(root / "ledger.json", ledger)
    _, ledger = inspect_control(run, profile, spec_hash)
    if ledger["contract_version"] != 2:
        raise ValueError("Historical workflow control v1 is read-only; do not upgrade its evidence in place")
    with run_lock(root):
        root, ledger = inspect_control(run, profile, spec_hash)
        # The worker also holds a guard, so a killed supervisor cannot race an orphan operation.
        with run_lock(root / "worker_guard"):
            if ledger["events"] and not ledger["events"][-1]["successful"]:
                previous = ledger["events"][-1]
                state = read_json(run / "status.json")["status"] if (run / "status.json").exists() else "uncertain"
                if not (action == "resume" and previous["action"] in ("run", "resume") and
                        previous["stop_reason"] in ("cancelled", "wall_budget") and state == "interrupted"):
                    raise ValueError("Failed workflow operation cannot be retried implicitly")
            spent = sum(e["charged_seconds"] for e in ledger["events"])
            limit = profile[LIMITS[action]]
            seconds = min(limit, profile["workflow_seconds"] - spent - profile["termination_grace_seconds"])
            paths = [str(run), str(root), *ledger["outputs"]]
            if seconds < 1 or usage(paths) >= profile["storage_bytes"] or shutil.disk_usage(root).free < profile["min_free_bytes"]:
                raise MateriaSimError("BUDGET_EXHAUSTED", "Workflow wall/storage/disk allowance exhausted", category="budget")
            if analysis_output is not None:
                output = str(Path(analysis_output).resolve())
                if output not in ledger["outputs"]:
                    ledger["outputs"].append(output)
                    paths.append(output)
                if usage(paths) >= profile["storage_bytes"]:
                    raise MateriaSimError("BUDGET_EXHAUSTED", "Analysis destination already exceeds storage allowance", category="budget")
            event_id = "operation-" + uuid.uuid4().hex
            event = root / "events" / event_id
            event.mkdir(parents=True, exist_ok=False)
            request = dict(arguments=arguments, control=str(root), profile=profile, seconds=seconds,
                           control_id=ledger["id"], expected_spec_hash=spec_hash, action=action,
                           control_version=2, sequence=len(ledger["events"]),
                           previous_outcome_sha256=ledger["events"][-1]["outcome_sha256"] if ledger["events"] else None)
            write_json(event / "request.json", request)
            entry = dict(id=event_id, action=action, closed=False,
                         charged_seconds=seconds + profile["termination_grace_seconds"],
                         request_sha256=sha256(event / "request.json"))
            ledger["events"].append(entry)
            ledger["active"] = event_id
            write_json(root / "ledger.json", ledger)
        outcome = watch(module, event / "request.json", event, paths, profile, seconds)
        result_path = event / "result.json"
        successful = outcome["returncode"] == 0 and outcome["stop_reason"] is None and result_path.is_file()
        write_json(event / "outcome.json", outcome)
        entry.update(closed=True, successful=successful, charged_seconds=outcome["elapsed_seconds"],
                     stop_reason=outcome["stop_reason"], outcome_sha256=sha256(event / "outcome.json"),
                     result_sha256=sha256(result_path) if result_path.exists() else None)
        ledger["active"] = None
        write_json(root / "ledger.json", ledger)
        inspect_control(run, profile, spec_hash)
        if not successful:
            raise RuntimeError(f"Workflow stopped after {action}; inspect {event}")
        return read_json(result_path)


def worker_main(operation):
    """Run only the owning module's concrete implementation, recording result and preserving failures."""
    request_path = Path(sys.argv[1]).resolve()
    request = read_json(request_path)
    root = Path(request["control"])
    with run_lock(root / "worker_guard"):
        ledger = read_json(root / "ledger.json")
        if ledger["active"] != request_path.parent.name or ledger["id"] != request["control_id"]:
            raise ValueError("Worker has no active resource reservation")
        validate_journal(root, root.parent.parent / ledger["run_id"], request["profile"],
                         request["expected_spec_hash"], allow_active=True)
        if ledger["contract_version"] != 2:
            raise ValueError("Historical workflow control is read-only")
        from materiasim.runtime.capacity import copy_budget
        run = root.parent.parent / ledger["run_id"]
        with copy_budget([run, root, *ledger["outputs"]], request["profile"]["storage_bytes"],
                         request["profile"]["min_free_bytes"]):
            result = operation(**request["arguments"], _control=request)
        write_json(request_path.parent / "result.json", result)
