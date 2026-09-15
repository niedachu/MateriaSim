"""Real SIGTERM-to-checkpoint batch recovery, using two explicitly declared short tasks."""

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

from materiasim.storage import read_json, write_json
from materiasim.research.batch import register, run, status
from materiasim.research.compare import compare
from materiasim.research.plan import external_output, plan


def exercise(output, research_source=None):
    """Interrupt the first real NVT worker, preserve its seal, then resume the same registered Run."""
    output = external_output(output)
    output.mkdir(parents=True, exist_ok=False)
    source = (Path(research_source).resolve() if research_source is not None else
              Path(__file__).resolve().parents[2] / "studies/zil_count_smoke/research.json")
    definition = read_json(source)
    definition["id"] = "zil_batch_resume_acceptance"
    definition["question"] = "SIGTERM 后同一研究批次能否保留 NVT 检查点并在尝试上限内恢复？"
    definition["hypothesis"] = "首任务真实中断后恢复原 Run，第二任务正常完成，登记目标不变。"
    if research_source is None:
        definition["limits"]["max_tasks"] = 2
    for case in definition["cases"]:
        case["experiment"] = str(source.parent / case["experiment"])
        if research_source is None:
            case["repeats"] = case["repeats"][:1]
    write_json(output / "source/research.json", definition)
    plan(output / "source/research.json", output / "plan")
    batch = register(output / "plan", output / "batches", "gmx", "packmol")
    first = read_json(batch / "ledger.json")["tasks"][0]["run_id"]
    args = [sys.executable, "-B", "-m", "materiasim", "research", "run", str(output / "plan"),
            "--output-root", str(output / "batches")]
    with (output / "interruption.stdout").open("w") as out, (output / "interruption.stderr").open("w") as err:
        process = subprocess.Popen(args, stdout=out, stderr=err)
        deadline = time.monotonic() + 60
        log = batch / "runs" / first / "stages/nvt/md.log"
        try:
            while process.poll() is None and not log.exists() and time.monotonic() < deadline:
                time.sleep(.05)
            if process.poll() is not None or not log.exists():
                raise AssertionError("No running NVT was observed; checkpoint coverage not established")
            time.sleep(.5)
            process.send_signal(signal.SIGTERM)
            code = process.wait(timeout=60)
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=60)
    interrupted = status(batch)
    seal = read_json(batch / "runs" / first / "stages/nvt/stage.json")
    write_json(output / "interruption.json", dict(returncode=code, status=interrupted, nvt_seal=seal))
    if code == 0 or interrupted["tasks"][0]["status"] != "interrupted" or seal["status"] != "interrupted":
        raise AssertionError("Actual in-stage checkpoint interruption did not occur")
    if not 0 < seal["evidence"]["step"] < seal["evidence"]["target_step"]:
        raise AssertionError("Checkpoint is not inside the declared NVT target")
    resumed = run(output / "plan", output / "batches", resume=True)
    report = compare(batch)
    if report["status"] != "engineering_complete" or resumed["tasks"][0]["run_id"] != first:
        raise AssertionError("Batch resume failed or replaced the registered Run")
    ledger = read_json(batch / "ledger.json")
    if [e["action"] for e in ledger["events"] if e["index"] == 0] != ["build", "run", "resume", "analyze"]:
        raise AssertionError("Unexpected duplicate build/execution after recovery")
    write_json(output / "acceptance.json", dict(status="passed", interruption=seal["evidence"],
               same_run_resumed=True, batch_dir=str(batch), comparison=report,
               charged_seconds=ledger["charged_seconds"], scientific_quality="not_assessed"))
    return output / "acceptance.json"


def main():
    """Run only when an explicit new external output is provided; this command launches small MD."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--research-source", type=Path, help="Explicit bounded source; retain all its declared repeats")
    args = parser.parse_args()
    print(exercise(args.output, args.research_source))


if __name__ == "__main__":
    main()
