"""Nine existing CPU smoke Runs through detached Campaign supervision; no new scientific recipe."""

import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from materiasim.harness import service, snapshots, supervisor
from materiasim.harness.contracts import TERMINAL
from materiasim.research.plan import external_output
from materiasim.research.resources import storage_bytes
from materiasim.runtime.state import source_identity
from materiasim.storage import inventory, read_json, write_json
from materiasim.errors import MateriaSimError


def request_pause(campaign, deadline):
    """Pause after the first admitted suboperation, refreshing only explicitly stale control views."""
    while time.monotonic() < deadline:
        state = service.status(campaign)
        if state.get("last_boundary"):
            try:
                return service.control(campaign, "pause", "acceptance-pause", state["sequence"])
            except MateriaSimError as error:
                if error.code != "STALE_CONTROL":
                    raise
        if state["status"] in TERMINAL:
            raise AssertionError("Target completed before pause boundary was exercised")
        time.sleep(.02)
    raise TimeoutError("No admitted operation observed before pause deadline")


def wait(campaign, deadline):
    """Poll read-only status until quiescent; request controlled cancellation at the acceptance deadline."""
    while True:
        state = service.status(campaign)
        if state["active"] is None and state["status"] in TERMINAL | {"paused", "needs_human_review"}:
            return state
        if time.monotonic() >= deadline:
            service.control(campaign, "cancel", "acceptance-timeout", state["sequence"])
            raise TimeoutError("Acceptance deadline; cancellation requested, evidence retained")
        time.sleep(.5)


def case(root, sidecar, name, seconds, exercise_pause=False):
    """Create one exact-scope local grant, launch detached and audit all finished task rows."""
    campaign = root / name
    grant = dict(contract_version=1, subject=snapshots.preview(sidecar)["automation"]["id"],
        actor="user-authorized-harness-acceptance", output_root=str(campaign),
        expires_utc=(datetime.now(timezone.utc) + timedelta(seconds=seconds + 90)).isoformat(),
        allowed_actions=["execute", "resume"], total_seconds=seconds, storage_bytes=536870912)
    grant_path = root / "inputs" / (name + "-authorization.json")
    write_json(grant_path, grant)
    snapshots.create(sidecar, grant_path, campaign)
    recovery = None
    if name == "mixed":
        from tests.acceptance.harness_faults import interrupt
        recovery = interrupt(campaign, root / "checkpoint-guards")
    launched = supervisor.start(campaign)
    deadline = time.monotonic() + seconds + 90
    if exercise_pause:
        request_pause(campaign, deadline)
    state = wait(campaign, deadline)
    if exercise_pause:
        if state["status"] != "paused":
            raise AssertionError("Pause was not acknowledged at the suboperation boundary")
        before = {p: h for p, h in inventory(campaign, ["work"]).items()
                  if "/inputs/" in p or "/build/" in p or "/provenance/" in p}
        if list((campaign / "work").glob("**/report.json")):
            raise AssertionError("Pause arrived after analysis, not between core operations")
        service.control(campaign, "resume", "acceptance-resume", state["sequence"])
        supervisor.start(campaign)
        state = wait(campaign, deadline)
        after = inventory(campaign, ["work"])
        if any(after.get(p) != h for p, h in before.items()):
            raise AssertionError("Resume overwrote a completed build or input")
    if state["status"] != "completed":
        raise AssertionError(f"Campaign {name} did not complete: {state}")
    # A repeated submission of a settled Campaign cannot start a fresh batch or Run.
    before = inventory(campaign, ["work", "operations"])
    supervisor.run(campaign)
    if before != inventory(campaign, ["work", "operations"]):
        raise AssertionError("Repeated submission changed canonical evidence")
    evidence = service.evidence(campaign)
    if any(row["status"] != "completed" for row in evidence["tasks"]):
        raise AssertionError("Incomplete task evidence in completed Campaign")
    if evidence["issues"] or evidence["closure"] != "completed_tasks_verified":
        raise AssertionError("Campaign audit did not verify evidence closure")
    if recovery and recovery["run_id"] not in [row["run_id"] for row in evidence["tasks"]]:
        raise AssertionError("Recovery replaced the original Run")
    write_json(root / (name + "-evidence.json"), evidence)
    return dict(campaign_dir=str(campaign), launch=launched, state=state,
                tasks=len(evidence["tasks"]), evidence_files=len(evidence["files"]), recovery=recovery)


def main():
    """Run unchanged single/ZIL/CAT-ANI targets serially, capped at 1800 seconds and 2 GiB overall."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = external_output(args.output)
    root.mkdir(parents=True, exist_ok=False)
    repository = Path(__file__).resolve().parents[2]
    started = time.monotonic()
    report = dict(status="running", implementation=source_identity(), campaigns=[],
        limits=dict(tasks=9, threads=2, total_seconds=1800, storage_bytes=2147483648),
        scientific_quality="not_assessed", not_tested=["Linux", "GPU", "external agent", "science validity"])
    write_json(root / "acceptance.json", report)
    try:
        sidecar = read_json(repository / "studies/zil_count_smoke/automation.json")
        sidecar.update(id="single_campaign_smoke", target=dict(kind="experiment",
                       path=str(repository / "examples/v3/packed_zil_water.json")))
        single = root / "inputs/single.json"
        write_json(single, sidecar)
        cases = [("single", single), ("zil", repository / "studies/zil_count_smoke/automation.json"),
                 ("mixed", repository / "studies/mixed_builders_smoke/automation.json")]
        for name, path in cases:
            remaining = min(600, int(1800 - (time.monotonic() - started)))
            if remaining <= 90 or storage_bytes(root) >= 2147483648:
                raise RuntimeError("Acceptance global allowance exhausted")
            result = case(root, path, name, remaining, exercise_pause=name in ("single", "zil"))
            report["campaigns"].append(result)
            write_json(root / "acceptance.json", report)
            print(name + " campaign completed", flush=True)
        if report["implementation"] != source_identity():
            raise AssertionError("Source changed during acceptance")
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
