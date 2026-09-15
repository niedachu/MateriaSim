"""Audit real research evidence, independent contact counts and non-destructive replay guards."""

import argparse
import shutil
from pathlib import Path
from unittest.mock import patch

from materiasim.storage import read_json, sha256, write_json
from materiasim.research.batch import run, validate_batch
from materiasim.research.compare import compare, task_reports
from materiasim.research.plan import external_output
from materiasim.runtime.state import verify_run
from tests.acceptance.verify_m1_evidence import file_identity
from tests.acceptance.verify_m3_evidence import reference_counts


def audit(batch, output):
    """Verify a completed batch, then mutate only a new disposable copy for negative tests."""
    batch = Path(batch).resolve()
    output = external_output(output, [batch])
    output.mkdir(parents=True, exist_ok=False)
    plan, ledger = validate_batch(batch)
    before = file_identity(batch)
    report = compare(batch)
    if report["status"] != "engineering_complete" or len(report["tasks"]) != 4:
        raise AssertionError("Expected the four completed declared research tasks")
    checks = []
    for task, record in zip(plan["tasks"], ledger["tasks"]):
        root = batch / "runs" / record["run_id"]
        spec, manifest = verify_run(root)
        mapping = read_json(root / "build/atom_mapping.json")
        counts = {c["id"]: c["count"] for c in spec["components"]}
        if {k: v for k, v in mapping["counts"].items() if k != "SOL"} != counts:
            raise AssertionError("Actual composition differs from task")
        reference = []
        for analysis in task_reports(batch, task, record, required=True):
            folder = Path(analysis["analysis_dir"])
            reference.append(reference_counts(folder, output / "reference" / task["id"] / folder.name))
        checks.append(dict(task_id=task["id"], run_id=record["run_id"], atom_count=mapping["atom_count"],
                           counts=mapping["counts"], manifest_sha256=sha256(root / "manifest.json"),
                           source_identity=manifest["implementation"], independent_reference=reference))
    with patch("materiasim.research.batch.supervise", side_effect=AssertionError("Duplicate worker")):
        run(batch / "plan", batch.parent, ledger["gmx"], ledger["packmol"])
    if before != file_identity(batch):
        raise AssertionError("Query, independent analysis or replay modified batch evidence")
    guard = output / "disposable-guard"
    shutil.copytree(batch, guard)
    analysis = next((guard / "analyses/task-000").iterdir())
    csv = analysis / "component_contacts.csv"
    csv.write_bytes(csv.read_bytes() + b"999,999\n")
    rejected = compare(guard)
    if rejected["status"] != "incomplete" or rejected["aggregates"] or len(rejected["tasks"]) != 4:
        raise AssertionError("Tampered analysis was silently accepted or omitted")
    original_analysis = next((batch / "analyses/task-000").iterdir())
    shutil.copyfile(original_analysis / csv.name, csv)
    write_json(analysis / "status.json", dict(status="failed", error="isolated acceptance fixture"))
    failed = compare(guard)
    if failed["status"] != "incomplete" or failed["aggregates"] or len(failed["tasks"]) != 4:
        raise AssertionError("Failed analysis was silently accepted or omitted")
    if before != file_identity(batch):
        raise AssertionError("Negative fixture modified the real batch")
    result = dict(status="passed", plan_hash=plan["plan_hash"], tasks=checks,
                  replay_created_no_work=True, source_batch_unchanged=True,
                  tampered_csv_rejected=True, failed_analysis_reported=True,
                  scientific_quality="not_assessed")
    write_json(output / "acceptance.json", result)
    return output / "acceptance.json"


def main():
    """Require an explicit real batch and a new external acceptance directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(audit(args.batch, args.output))


if __name__ == "__main__":
    main()
