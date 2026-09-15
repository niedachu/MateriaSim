"""Final bounded framework acceptance; review fixtures test software, never scientific approval."""

import argparse
from pathlib import Path
import time

from materiasim.engines.gromacs.command import engine_info
from materiasim.engines.gromacs.mdp import mdp_values
from materiasim.research.plan import external_output
from materiasim.runtime.capacity import copy_budget, copy_tree
from materiasim.runtime.state import source_identity, verify_execution, verify_run
from materiasim.storage import read_json, write_json
from materiasim.workflows.analysis import analyze
from materiasim.workflows.archive import export_archive, tree_hashes, verify_archive
from materiasim.workflows.build import build
from materiasim.workflows.execute import execute
from materiasim.workflows.migration import portable_document
from tests.acceptance.verify_architecture_a import check_budget
from tests.acceptance.verify_component_boundaries import check_preparations
from tests.acceptance.verify_research_v2 import child
from tests.unit.test_purpose_storage_delivery import reviewed_fixture


def reviewed_run(output, engine):
    """Execute one existing dry ZIL protocol under synthetic model-validation review and profile v3."""
    spec, sources = reviewed_fixture(output / "fixture", engine=engine)
    source = output / "fixture/experiment.json"
    write_json(source, portable_document(spec, sources))
    root = Path(build(source, output / "runs"))
    result = execute(root)
    if result["status"] != "completed":
        raise AssertionError("Reviewed fixture did not complete its existing short protocol")
    analyses = analyze(root, output / "analyses")
    for stage in spec["protocol"]["stages"]:
        values = mdp_values(root / "build" / (stage["id"] + ".mdp"))
        for key, declared in (("nstlog", "log_steps"), ("nstenergy", "energy_steps"),
                              ("nstxout-compressed", "trajectory_steps")):
            if int(values[key]) != stage["sampling"][declared]:
                raise AssertionError("Declared sampling did not reach native input")
    if any(read_json(Path(p) / "report.json")["purpose"] != "model_validation" for p in analyses):
        raise AssertionError("Analysis lost the explicit purpose")
    verify_execution(root)
    return dict(run=str(root), analyses=analyses, stages=check_preparations(root, engine),
                review="SOFTWARE TEST FIXTURE ONLY", scientific_quality="not_assessed")


def archive_checks(root, output):
    """Copy a completed Run/control/analysis bundle, relocate copies and reject isolated corruption."""
    before = tree_hashes(root)
    exported = export_archive(root, output / "archive", 128 * 1024 * 1024)
    with copy_budget([output], 512 * 1024 * 1024, 64 * 1024 * 1024):
        copy_tree(output / "archive", output / "异地 副本")
        copy_tree(output / "archive", output / "corrupted-copy")
    moved = verify_archive(output / "异地 副本")
    if moved["archive_hash"] != exported["archive_hash"]:
        raise AssertionError("Archive identity changed solely because of its new location")
    record = read_json(output / "corrupted-copy/archive.json")
    run_entry = next(e for e in record["entries"] if e["role"] == "run")
    damaged = output / "corrupted-copy" / run_entry["path"] / "stages"
    target = next(damaged.glob("*/md.log"))
    with target.open("ab") as handle:
        handle.write(b"\nISOLATED CORRUPTION TEST\n")
    try:
        verify_archive(output / "corrupted-copy")
    except ValueError as error:
        rejection = str(error)
    else:
        raise AssertionError("Corrupted archive was accepted")
    if before != tree_hashes(root):
        raise AssertionError("Export/relocation changed the active source Run")
    return dict(export=exported, relocated=moved, corruption_rejected=rejection, source_unchanged=True)


def main():
    """Run fourteen regressions plus one reviewed short fixture within thirty minutes and one GiB."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = external_output(args.output)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = dict(status="running", implementation=source_identity(), scientific_quality="not_assessed",
                  limits=dict(tasks=15, threads=2, wall_seconds=1800, storage_bytes=1073741824),
                  pending=["regressions_14", "reviewed_fixture", "archives"],
                  not_tested=["Linux", "GPU", "long production load", "scientific approvals"])
    write_json(output / "acceptance.json", report)
    try:
        child(output, started, "tests.acceptance.verify_research_v2", ["--output", output / "regression"], "regression")
        report["regression"] = read_json(output / "regression/acceptance.json")
        report["pending"].remove("regressions_14")
        write_json(output / "acceptance.json", report)
        print("14 regression tasks passed", flush=True)
        check_budget(output, started)
        report["reviewed_fixture"] = reviewed_run(output / "reviewed", engine_info())
        report["pending"].remove("reviewed_fixture")
        write_json(output / "acceptance.json", report)
        print("model-validation SOFTWARE fixture passed", flush=True)
        check_budget(output, started)
        batch = Path(report["regression"]["mixed_recovery"]["batch_dir"])
        first = read_json(batch / "ledger.json")["tasks"][0]["run_id"]
        root = batch / "runs" / first
        spec, _ = verify_run(root)
        generations = {s["id"]: len(read_json(root / "stages" / s["id"] / "stage.json")["archive_generations"])
                       for s in spec["protocol"]["stages"]}
        if max(generations.values()) < 2:
            raise AssertionError("Recovery did not preserve separate interrupted/final generations")
        report["archive_generations"] = generations
        report["archives"] = archive_checks(root, output / "storage")
        report["pending"].remove("archives")
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
