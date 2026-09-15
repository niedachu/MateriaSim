"""Bounded real CPU regression for registered components, preserving all failed evidence."""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from materiasim.engines.gromacs.command import engine_info
from materiasim.engines.gromacs.compile import verify_native_prepared
from materiasim.engines.prepared import read_prepared
from materiasim.research.plan import external_output
from materiasim.runtime.state import source_identity, verify_run
from materiasim.storage import read_json, write_json
from materiasim.workflows.analysis import analyze
from materiasim.workflows.build import build
from materiasim.workflows.execute import execute
from tests.acceptance.audit_asset_dependencies import audit_experiment
from tests.acceptance.verify_architecture_a import CASES, check_budget
from tests.acceptance.verify_m1_evidence import file_identity
from tests.acceptance.verify_m3_evidence import audit_run

PREBUILT = ("zil_smoke_v2", "cat_ani_smoke")


def check_preparations(root, engine):
    """Audit every real compiled handoff and prove each stage was compiled exactly once."""
    spec, _ = verify_run(root)
    result = []
    for stage in spec["protocol"]["stages"]:
        prepared = read_prepared(root, stage["id"])
        verify_native_prepared(root, stage, engine, prepared)
        commands = list((root / "attempts").glob(f"*/compile-{stage['id']}/command.json"))
        if len(commands) != 1 or read_json(commands[0])["returncode"] != 0:
            raise AssertionError("Stage was not compiled exactly once successfully")
        result.append(dict(stage_id=stage["id"], contract_version=prepared.contract_version,
                           compile_count=1, dependency_files=len(prepared.dependency_hashes),
                           input_roles=sorted(prepared.inputs), artifact_roles=sorted(prepared.artifacts)))
    return result


def check_recovery_preparation(output, resume, engine):
    """Compare actual interrupted/final preparations and verify native append without recompilation."""
    batch = Path(resume["batch_dir"])
    tasks = read_json(batch / "ledger.json")["tasks"]
    checks = {task["run_id"]: check_preparations(batch / "runs" / task["run_id"], engine) for task in tasks}
    first = batch / "runs" / tasks[0]["run_id"]
    before = read_json(output / "research_resume/interruption.json")["nvt_seal"]
    after = read_json(first / "stages/nvt/stage.json")
    if before["preparation"] != after["preparation"] or before["hashes"] != after["hashes"]:
        raise AssertionError("Checkpoint recovery changed the compiled input contract")
    append = list((first / "attempts").glob("resume-*/run-nvt/command.json"))
    if len(append) != 1:
        raise AssertionError("Expected one native NVT resume command")
    argv = read_json(append[0])["argv"]
    if "-append" not in argv or "-cpi" not in argv:
        raise AssertionError("Recovery did not consume the existing checkpoint with native append")
    return dict(compiled_input_unchanged=True, native_append=True, runs=checks)


def check_prebuilt(root, output, repository):
    """Compare the registered hydration analyzer with the retained case implementation on identical frames."""
    before = file_identity(root)
    spec, manifest = verify_run(root)
    analyses = analyze(root, output / "analysis")
    if len(analyses) != 1:
        raise AssertionError("Expected one explicitly declared hydration request")
    analysis = Path(analyses[0])
    reference = output / "reference"
    args = [sys.executable, "-B", "-m", "tests.acceptance.compare_analysis",
            str(root), str(analysis), str(repository / "zwitterion_hydration_md/analysis/hydration_count.py"),
            str(reference)]
    with (output / "reference.stdout").open("w") as stdout, (output / "reference.stderr").open("w") as stderr:
        subprocess.run(args, check=True, stdout=stdout, stderr=stderr, timeout=120)
    if before != file_identity(root):
        raise AssertionError("Analysis changed the source Run")
    report = read_json(analysis / "report.json")
    if report["result_contract"]["method"] != "hydration_contacts":
        raise AssertionError("Hydration did not use the common result contract")
    return dict(run=str(root), run_id=manifest["run_id"], scenario=spec["scenario"]["kind"],
                mapping=read_json(root / "build/resolved_system.json"), analysis=str(analysis),
                source_run_unchanged=True, reference=read_json(reference / "comparison.json"))


def main():
    """Create a new external evidence root and run exactly six cases plus two recovery tasks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = external_output(args.output)
    output.mkdir(parents=True, exist_ok=False)
    repository = Path(__file__).resolve().parents[2]
    examples = repository / "examples"
    started = time.monotonic()
    engine = engine_info("gmx")
    names = (*CASES, *PREBUILT)
    dependencies = [audit_experiment(examples / f"{name}.json", engine) for name in names]
    report = dict(status="running", implementation=source_identity(), engine=engine, runs=[],
                  pending=list(names) + ["research_resume_two_tasks"], scientific_quality="not_assessed",
                  limits=dict(threads=2, max_wall_seconds=1800, max_output_bytes=1024**3),
                  not_covered=["GPU", "Linux", "new materials", "scientific validation"])
    write_json(output / "dependencies_before.json", dependencies)
    write_json(output / "acceptance.json", report)
    try:
        with (output / "unit.stdout").open("w") as stdout, (output / "unit.stderr").open("w") as stderr:
            subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
                           cwd=repository, check=True, stdout=stdout, stderr=stderr, timeout=120)
        for name in names:
            check_budget(output, started)
            root = Path(build(examples / f"{name}.json", output / "runs"))
            print(f"built {root.name}", flush=True)
            check_budget(output, started)
            result = execute(root, threads=2, max_wall_seconds=180)
            if result["status"] != "completed":
                raise AssertionError("Case did not complete in its single bounded execution")
            check_budget(output, started)
            checked = (audit_run(root, output / "checks" / name) if name in CASES else
                       check_prebuilt(root, output / "checks" / name, repository))
            checked["prepared_stages"] = check_preparations(root, engine)
            report["runs"].append(checked)
            report["pending"].remove(name)
            write_json(output / "acceptance.json", report)
            print(f"verified {name}", flush=True)
        check_budget(output, started)
        with (output / "resume.stdout").open("w") as stdout, (output / "resume.stderr").open("w") as stderr:
            subprocess.run([sys.executable, "-B", "-m", "tests.acceptance.verify_research_resume",
                            "--output", str(output / "research_resume")],
                           check=True, stdout=stdout, stderr=stderr,
                           timeout=min(600, max(1, 1800 - (time.monotonic() - started))))
        report["resume"] = read_json(output / "research_resume/acceptance.json")
        report["recovery_preparation"] = check_recovery_preparation(output, report["resume"], engine)
        report["pending"].remove("research_resume_two_tasks")
        after = [audit_experiment(examples / f"{name}.json", engine) for name in names]
        write_json(output / "dependencies_after.json", after)
        if dependencies != after or report["implementation"] != source_identity():
            raise AssertionError("Dependencies or implementation changed during acceptance")
        check_budget(output, started)
        report.update(status="passed", dependency_identity_unchanged=True)
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        report["output_bytes"] = sum(p.stat().st_size for p in output.rglob("*") if p.is_file())
        write_json(output / "acceptance.json", report)
    print(output / "acceptance.json", flush=True)


if __name__ == "__main__":
    main()
