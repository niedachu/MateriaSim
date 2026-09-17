"""Offline scripted-provider acceptance: five unchanged CPU smoke Runs, not a real model eval."""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from materiasim.harness import agent_service, journal, service, snapshots, supervisor
from materiasim.harness.contracts import TERMINAL
from materiasim.research.plan import external_output
from materiasim.research.resources import storage_bytes
from materiasim.runtime.state import source_identity
from materiasim.storage import inventory, read_json, run_lock, write_json


def cli(*arguments):
    """Use an actual separate local client process, without sockets, SDKs or model calls."""
    result = subprocess.run([sys.executable, "-B", "-m", "materiasim", "--json-envelope", "campaign", *map(str, arguments)],
                            capture_output=True, text=True, timeout=30, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)["result"]


def await_boundary(campaign, end):
    """Wait for settled work; never reinterpret an active reservation as a completed task."""
    while time.monotonic() < end:
        state = journal.status(campaign)
        if not state["active"] and state["status"] in TERMINAL | {"waiting_for_agent", "paused", "needs_human_review"}:
            return state
        time.sleep(.1)
    state = journal.status(campaign)
    service.control(campaign, "cancel", "acceptance-deadline", state["sequence"])
    raise TimeoutError("Acceptance wall deadline; cancellation requested")


def await_supervisor_exit(campaign, end):
    """Observe the actual supervisor lock before management starts another owned supervisor."""
    while time.monotonic() < end:
        try:
            with run_lock(campaign / "supervisor"):
                return
        except RuntimeError:
            time.sleep(.1)
    raise TimeoutError("Supervisor did not release its lock")


def decide(campaign, inputs, ordinal, action="continue"):
    """Submit a deterministic fixture decision using only the disclosed progress view."""
    view = cli("agent-read", campaign, "--source", "scripted-provider", "--request-id", f"view-{ordinal}")
    request = dict(contract_version=2, request_id=f"decision-{ordinal}", source="scripted-provider", action=action,
        campaign_hash=view["summary"]["campaign_hash"], expected_sequence=view["expected_sequence"], event_head=view["event_head"],
        expires_utc=view["summary"]["deadline"], reason="offline acceptance fixture; not scientific judgment",
        evidence=dict(view_id=view["view_id"], sha256=view["sha256"]))
    path = inputs / f"decision-{ordinal}.json"
    write_json(path, request)
    first = cli("submit-decision", campaign, path)
    if first != cli("submit-decision", campaign, path) or first["executed"]:
        raise AssertionError("Replay changed admission or falsely claimed execution")
    return first


def create(root, name, sidecar, seconds, timeout=60):
    """Freeze an exact-scope grant and local-only policy; never edit a scientific input."""
    campaign = root / name
    inputs = root / "inputs" / name
    grant = dict(contract_version=1, subject=snapshots.preview(sidecar)["automation"]["id"],
        actor="user-authorized-h3-acceptance", output_root=str(campaign),
        expires_utc=(datetime.now(timezone.utc) + timedelta(seconds=seconds + 90)).isoformat(),
        allowed_actions=["execute", "resume"], total_seconds=seconds, storage_bytes=402653184)
    rule = dict(contract_version=1, agent_id="scripted-provider", allowed_actions=["continue", "pause", "request_review", "stop"],
        decision_timeout_seconds=timeout, max_decisions=16, transport="local", readable_summaries=["progress"])
    write_json(inputs / "authorization.json", grant)
    write_json(inputs / "policy.json", rule)
    snapshots.create(sidecar, inputs / "authorization.json", campaign, agent_policy=inputs / "policy.json")
    return campaign, inputs


def case(root, name, sidecar, seconds):
    """Complete a target one approved core operation at a time, exercising takeover on the single Run."""
    campaign, inputs = create(root, name, sidecar, seconds)
    end = time.monotonic() + seconds + 60
    supervisor.start(campaign)
    ordinal, takeover = 0, False
    state = await_boundary(campaign, end)
    while state["status"] == "waiting_for_agent":
        ordinal += 1
        if name == "single" and state["operations"] == 1 and not takeover:
            decide(campaign, inputs, ordinal, "request_review")
            state = await_boundary(campaign, end)
            if state["status"] != "needs_human_review":
                raise AssertionError("Agent review did not relinquish control")
            await_supervisor_exit(campaign, end)
            agent_service.human(campaign, "continue", "manual-one-operation", state["sequence"])
            supervisor.start(campaign)
            state = await_boundary(campaign, end)
            if state["status"] != "paused" or not state["human_required"]:
                raise AssertionError("Manual step did not retain human control")
            await_supervisor_exit(campaign, end)
            agent_service.human(campaign, "return_to_agent", "human-handback", state["sequence"])
            supervisor.start(campaign)
            takeover = True
        else:
            # No producer process remains between calls: the supervisor must wait, not invent a decision.
            before = inventory(campaign, ["work", "operations"])
            time.sleep(.25)
            if before != inventory(campaign, ["work", "operations"]):
                raise AssertionError("Work advanced without a new decision")
            decide(campaign, inputs, ordinal)
        state = await_boundary(campaign, end)
    if state["status"] != "completed":
        raise AssertionError(f"{name} stopped without completion: {state}")
    await_supervisor_exit(campaign, end)
    evidence = service.evidence(campaign)
    if evidence["issues"] or evidence["closure"] != "completed_tasks_verified":
        raise AssertionError("Canonical task evidence did not close")
    counts = {}
    for event in evidence["events"]:
        if event["kind"] == "boundary":
            operation = event["data"]["operation_id"]
            counts[operation] = counts.get(operation, 0) + 1
    if not counts or any(n != 1 for n in counts.values()) or len(counts) != state["operations"]:
        raise AssertionError("More than one core operation admitted per worker")
    write_json(root / (name + "-evidence.json"), evidence)
    return dict(name=name, campaign_dir=str(campaign), state=state, tasks=len(evidence["tasks"]),
                agent_decisions=ordinal, human_takeover=takeover, boundaries=len(counts))


def lost_provider(root, sidecar):
    """Start a real detached wait supervisor with no provider; it must expire without running MD."""
    campaign, _ = create(root, "lost-provider", sidecar, 120, timeout=1)
    supervisor.start(campaign)
    end = time.monotonic() + 15
    while time.monotonic() < end:
        state = journal.status(campaign)
        if state["status"] == "needs_human_review":
            break
        time.sleep(.1)
    if state["status"] != "needs_human_review" or state["operations"] or state["charged_seconds"]:
        raise AssertionError("Lost provider did not fail closed without compute")
    await_supervisor_exit(campaign, end)
    return dict(campaign_dir=str(campaign), state=state)


def main():
    """Run at most five unchanged smoke Runs serially, with 1200 s / 1 GiB acceptance bounds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = external_output(args.output)
    root.mkdir(parents=True, exist_ok=False)
    repository = Path(__file__).resolve().parents[2]
    started = time.monotonic()
    report = dict(status="running", implementation=source_identity(), campaigns=[],
        limits=dict(tasks=5, threads=2, total_seconds=1200, storage_bytes=1073741824),
        scientific_quality="not_assessed", provider="scripted_local_fixture",
        not_tested=["real agent/model", "DeepSeek", "Linux", "GPU", "scientific validity"])
    write_json(root / "acceptance.json", report)
    try:
        sidecar = read_json(repository / "studies/zil_count_smoke/automation.json")
        sidecar.update(id="single_agent_smoke", target=dict(kind="experiment", path=str(repository / "examples/v3/packed_zil_water.json")))
        single = root / "inputs/single.json"
        write_json(single, sidecar)
        report["lost_provider"] = lost_provider(root, single)
        for name, path in (("single", single), ("research", repository / "studies/zil_count_smoke/automation.json")):
            seconds = min(540, int(1200 - (time.monotonic() - started)))
            if seconds <= 90 or storage_bytes(root) >= 1073741824:
                raise RuntimeError("Global acceptance budget exhausted")
            report["campaigns"].append(case(root, name, path, seconds))
            write_json(root / "acceptance.json", report)
            print(name + " local agent protocol passed", flush=True)
        if source_identity() != report["implementation"]:
            raise AssertionError("Core source changed during acceptance")
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
