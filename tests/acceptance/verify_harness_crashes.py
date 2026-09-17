"""Bounded real MD tests of parent death, full worker-group loss and detached-client exit."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from materiasim.harness import journal, service, snapshots, supervisor
from materiasim.research.plan import external_output
from materiasim.research.resources import storage_bytes
from materiasim.runtime.family import kill, launch
from materiasim.runtime.state import source_identity
from materiasim.storage import inventory, read_json, run_lock, write_json


def child(root):
    """Run an actual supervisor with a test-only signal that kills its own retained child group."""
    children = []

    def capture(arguments, **options):
        """Retain only this process's actual worker handle for the full-loss test."""
        process, owner = launch(arguments, **options)
        if not owner:
            raise AssertionError("Acceptance supervisor must own its worker group")
        children.append((process, owner))
        return process, owner

    def lose_group(signum, frame):
        """Simulate abrupt disappearance of the owned worker tree and this supervisor, without cleanup."""
        if len(children) != 1:
            raise AssertionError("No unique owned worker to interrupt")
        kill(*children[0])
        os.kill(os.getpid(), signal.SIGKILL)

    signal.signal(signal.SIGUSR1, lose_group)
    with patch("materiasim.harness.supervisor.launch", side_effect=capture):
        supervisor.run(root)


def create(root, name, research=False):
    """Freeze an unchanged existing target with a fresh 300-second, 256-MiB authorization."""
    repository = Path(__file__).resolve().parents[2]
    source = repository / "studies/mixed_builders_smoke/automation.json"
    sidecar = source
    if not research:
        value = read_json(repository / "studies/zil_count_smoke/automation.json")
        value["target"] = dict(kind="experiment", path=str(repository / "examples/v3/packed_zil_water.json"))
        sidecar = root / "inputs" / (name + ".json")
        write_json(sidecar, value)
    campaign = root / name
    grant = dict(contract_version=1, subject=snapshots.preview(sidecar)["automation"]["id"],
        actor="user-authorized-harness-fault-acceptance", output_root=str(campaign),
        expires_utc=(datetime.now(timezone.utc) + timedelta(seconds=390)).isoformat(),
        allowed_actions=["execute", "resume"], total_seconds=300, storage_bytes=268435456)
    path = root / "inputs" / (name + "-authorization.json")
    write_json(path, grant)
    snapshots.create(sidecar, path, campaign)
    return campaign


def wait_for_nvt(campaign, process):
    """Observe the new owned Campaign's native NVT only; fail if it exits or times out first."""
    deadline = time.monotonic() + 90
    while process.poll() is None and time.monotonic() < deadline:
        logs = list((campaign / "work").glob("**/stages/nvt/md.log"))
        if logs:
            time.sleep(.15)
            return logs[0].parents[2]
        time.sleep(.02)
    raise AssertionError("Native NVT not observed while supervisor was alive")


def reconcile_when_quiet(campaign):
    """Wait for the actual worker lock to release, then reconcile without retrying any computation."""
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        try:
            with run_lock(campaign / "worker_guard"):
                break
        except RuntimeError:
            time.sleep(.1)
    else:
        raise TimeoutError("Worker did not relinquish its guard after parent loss")
    try:
        return supervisor.reconcile(campaign)
    except RuntimeError as error:
        if "Uncertain operation without receipt" not in str(error):
            raise
        return service.status(campaign)


def crash_case(root, name, whole_group=False):
    """Kill only owned test processes during MD, preserving every native and Campaign artifact."""
    campaign = create(root, name, research=not whole_group)
    environment = dict(os.environ)
    environment.pop("MATERIASIM_MANAGED_GROUP", None)
    with (root / (name + "-stdout.log")).open("x") as out, (root / (name + "-stderr.log")).open("x") as err:
        process = subprocess.Popen([sys.executable, "-B", "-m", "tests.acceptance.verify_harness_crashes",
            "--child-root", str(campaign)], stdout=out, stderr=err, env=environment, start_new_session=True)
        try:
            run = wait_for_nvt(campaign, process)
            process.send_signal(signal.SIGUSR1 if whole_group else signal.SIGKILL)
            process.wait(timeout=10)
            if process.returncode != -signal.SIGKILL:
                raise AssertionError("Supervisor was not actually killed")
            state = reconcile_when_quiet(campaign)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=100)
    runs = list((campaign / "work").glob("**/resolved_spec.json"))
    if len(runs) != 1:
        raise AssertionError("Parent loss admitted additional Runs")
    if whole_group:
        if state["status"] != "needs_human_review" or state["active"] is None:
            raise AssertionError("Lost worker receipt did not preserve the uncertain reservation")
        if list((campaign / "operations").glob("*/result.json")):
            raise AssertionError("Full group loss unexpectedly produced a worker receipt")
        before = inventory(campaign, ["work", "operations"])
        try:
            supervisor.run(campaign)
        except RuntimeError as error:
            if "Uncertain" not in str(error):
                raise
        if inventory(campaign, ["work", "operations"]) != before:
            raise AssertionError("Uncertain operation replayed work")
        result = dict(status=state["status"], reservation_preserved=True, receipt_missing=True)
    else:
        if state["active"] is not None or state["status"] != "paused":
            raise AssertionError(f"Parent-loss interruption did not seal canonical progress: {state}")
        seal = read_json(run / "stages/nvt/stage.json")
        if seal["status"] != "interrupted" or not 0 < seal["evidence"]["step"] < 1000:
            raise AssertionError("Parent loss did not interrupt the original native stage")
        events = journal.status(campaign)
        if events["last_boundary"]["action"] != "run":
            raise AssertionError("An operation was admitted after supervisor loss")
        if state["charged_seconds"] != 300:
            raise AssertionError("Unknown supervisor time did not conserve the complete reservation")
        evidence = service.evidence(campaign)
        write_json(root / (name + "-evidence.json"), evidence)
        if evidence["issues"]:
            raise AssertionError("Interrupted Run evidence is not intact")
        result = dict(status=state["status"], checkpoint=seal["evidence"], charged_seconds=300)
    result.update(run_dir=str(run), supervisor_returncode=process.returncode, new_runs=len(runs))
    return result


def detached_case(root):
    """Let the launching CLI actually exit, then observe the independent supervisor finish one Run."""
    from tests.acceptance.verify_harness import wait
    campaign = create(root, "client_exit")
    response = subprocess.run([sys.executable, "-B", "-m", "materiasim", "campaign", "start", str(campaign)],
                              capture_output=True, text=True, timeout=15, check=True)
    write_json(root / "client-launch.json", json.loads(response.stdout))
    state = wait(campaign, time.monotonic() + 300)
    if state["status"] != "completed":
        raise AssertionError("Detached task did not complete after launch client exit")
    evidence = service.evidence(campaign)
    if evidence["issues"] or evidence["closure"] != "completed_tasks_verified":
        raise AssertionError("Detached task evidence did not close")
    write_json(root / "client-exit-evidence.json", evidence)
    return dict(status=state["status"], launch_client_exited=True, new_runs=1)


def main():
    """Execute at most three unchanged native Run designs within 900 seconds and 1 GiB."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child-root", type=Path)
    args = parser.parse_args()
    if args.child_root:
        child(args.child_root)
        return
    if args.output is None:
        parser.error("--output is required")
    root = external_output(args.output)
    root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = dict(status="running", implementation=source_identity(), cases={},
                  limits=dict(actual_runs=3, threads=2, total_seconds=900, storage_bytes=1073741824),
                  scientific_quality="not_assessed")
    try:
        for name, full in (("supervisor_loss", False), ("group_loss", True)):
            report["cases"][name] = crash_case(root, name, full)
            write_json(root / "acceptance.json", report)
            print(name + " passed", flush=True)
        report["cases"]["client_exit"] = detached_case(root)
        if source_identity() != report["implementation"]:
            raise AssertionError("Core source changed during acceptance")
        if time.monotonic() - started > 900 or storage_bytes(root) > 1073741824:
            raise AssertionError("Acceptance exceeded its allowance")
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        report.update(elapsed_seconds=time.monotonic() - started, output_bytes=storage_bytes(root))
        write_json(root / "acceptance.json", report)
    print(root / "acceptance.json", flush=True)


if __name__ == "__main__":
    main()
