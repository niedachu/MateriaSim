"""Bounded CPU acceptance for general research and whole-operation resource supervision."""

import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import time

from materiasim.engines.gromacs.command import engine_info
from materiasim.research.batch import run
from materiasim.research.compare import compare
from materiasim.research.plan import external_output, plan
from materiasim.runtime.control import inspect_control
from materiasim.runtime.state import source_identity, verify_execution
from materiasim.storage import read_json, write_json
from materiasim.workflows.migration import load_executable, portable_document
from tests.acceptance.verify_architecture_a import check_budget
from tests.acceptance.verify_component_boundaries import check_preparations


def child(output, started, module, arguments, name):
    """Run an existing bounded acceptance entry and keep complete stdout/stderr on any failure."""
    check_budget(output, started)
    with (output / (name + ".stdout")).open("w") as out, (output / (name + ".stderr")).open("w") as err:
        subprocess.run([sys.executable, "-B", "-m", module, *map(str, arguments)],
                       stdout=out, stderr=err, check=True,
                       timeout=max(1, 1800 - (time.monotonic() - started)))


def audit_batch(batch, engine):
    """Check current implementation, preparations and v2 control request/result/sequence integrity."""
    rows = []
    for record in read_json(batch / "ledger.json")["tasks"]:
        root = batch / "runs" / record["run_id"]
        spec, manifest = verify_execution(root)
        _, ledger = inspect_control(root, spec["execution_profile"], manifest["spec_hash"])
        if ledger["contract_version"] != 2:
            raise AssertionError("New Run did not publish the current workflow control contract")
        actions = [e["action"] for e in ledger["events"]]
        if actions.count("build") != 1 or actions.count("analyze") != bool(spec["analysis_requests"]):
            raise AssertionError("Unexpected operation count or missing resource charge")
        stages = check_preparations(root, engine)
        for stage in stages:
            seal = read_json(root / "stages" / stage["stage_id"] / "stage.json")
            if seal["evidence"]["execution"]["gpu_used"]:
                raise AssertionError("CPU acceptance unexpectedly offloaded to GPU")
        rows.append(dict(run_id=root.name, actions=actions, stages=stages,
                         control_contract_version=ledger["contract_version"],
                         charged_seconds=sum(e["charged_seconds"] for e in ledger["events"]),
                         profile=spec["execution_profile"]))
    return rows


def no_analysis(source, output):
    """Create exactly two explicit execution-only derivatives without changing scientific inputs."""
    definition = deepcopy(read_json(source))
    definition.update(id="no_analysis_acceptance", observables=[])
    definition["limits"]["max_tasks"] = 2
    for index, case in enumerate(definition["cases"]):
        spec, assets, _, _ = load_executable(source.parent / case["experiment"])
        spec["analysis_requests"] = []
        target = output / "source" / f"experiment-{index}.json"
        write_json(target, portable_document(spec, assets))
        case["experiment"] = target.name
        case["repeats"] = case["repeats"][:1]
    write_json(output / "source/research.json", definition)
    plan(output / "source/research.json", output / "plan")
    result = run(output / "plan", output / "batches")
    batch = Path(result["batch_dir"])
    compared = compare(batch)
    if compared["status"] != "engineering_complete" or compared["aggregates"] or (batch / "analyses").exists():
        raise AssertionError("Execution-only research created or required artificial observations")
    return batch, compared


def main():
    """Run 8 unchanged regression tasks, 4 new recovery tasks and 2 execution-only tasks within one budget."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = external_output(args.output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    source = Path(__file__).resolve().parents[2] / "studies/mixed_builders_smoke/research.json"
    report = dict(status="running", implementation=source_identity(), limits=dict(tasks=14, threads=2,
                  wall_seconds=1800, storage_bytes=1073741824), scientific_quality="not_assessed",
                  pending=["existing_8", "mixed_recovery_4", "no_analysis_2"], not_tested=["Linux", "GPU", "scientific convergence"])
    write_json(output / "acceptance.json", report)
    try:
        child(output, started, "tests.acceptance.verify_component_boundaries", ["--output", output / "existing"], "existing")
        report["existing"] = read_json(output / "existing/acceptance.json")
        report["pending"].remove("existing_8")
        write_json(output / "acceptance.json", report)
        print("existing 8 regression tasks passed", flush=True)
        child(output, started, "tests.acceptance.verify_research_resume",
              ["--output", output / "mixed_recovery", "--research-source", source], "mixed")
        mixed = read_json(output / "mixed_recovery/acceptance.json")
        report["mixed_recovery"] = mixed
        report["mixed_audit"] = audit_batch(Path(mixed["batch_dir"]), engine_info())
        report["pending"].remove("mixed_recovery_4")
        write_json(output / "acceptance.json", report)
        print("4 mixed-builder dual-analysis recovery tasks passed", flush=True)
        check_budget(output, started)
        batch, compared = no_analysis(source, output / "no_analysis")
        report["no_analysis"] = compared
        report["no_analysis_audit"] = audit_batch(batch, engine_info())
        report["pending"].remove("no_analysis_2")
        check_budget(output, started)
        if report["implementation"] != source_identity():
            raise AssertionError("Source changed during acceptance")
        report["status"] = "passed"
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
