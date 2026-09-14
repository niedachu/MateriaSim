"""Read real completed Runs, exercise external analysis and save bounded M1 acceptance evidence."""

import argparse
import csv
from pathlib import Path

from materials_sim.analysis import analyze
from materials_sim.files import read_json, sha256, verify_hashes, write_json
from materials_sim.records import stage_ids
from materials_sim.schema import load_spec
from materials_sim.state import source_identity, verify_run


def file_identity(root):
    """Return every regular file hash, including cache/lock files, without writing the source."""
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(root.rglob("*")) if path.is_file()}


def effective_parameters(path):
    """Read native grompp's complete effective parameter output, ignoring explanatory comments."""
    values = {}
    for raw in path.read_text().splitlines():
        line = raw.split(";", 1)[0].strip()
        if line:
            key, value = line.split("=", 1)
            key = key.strip().lower().replace("_", "-")
            if key in values:
                raise AssertionError("Duplicate effective parameter")
            values[key] = value.strip()
    return values


def compare_effective(old, new):
    """Require physical equality; record only inactive gen-seed differences with gen-vel=no."""
    differences = {key: dict(before=old.get(key), after=new.get(key))
                   for key in set(old) | set(new) if old.get(key) != new.get(key)}
    inactive = {}
    # grompp resolves a default random seed even when velocity generation is disabled.
    # This exception is inapplicable to NVT's active, explicitly fixed velocity seed.
    if old.get("gen-vel") == new.get("gen-vel") == "no" and "gen-seed" in differences:
        inactive["gen-seed"] = differences.pop("gen-seed")
    if differences:
        raise AssertionError(f"Effective physical parameters changed: {differences}")
    return dict(physical_parameters_equal=True, parameters=len(new), inactive_seed_differences=inactive)


def main():
    """Validate supplied historical/baseline/renamed Runs; create only new external analysis/evidence."""
    parser = argparse.ArgumentParser()
    for name in ("historical", "baseline", "renamed", "historical_hashes", "historical_analysis",
                 "historical_reference", "output"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    old_spec, old_manifest = verify_run(args.historical)
    spec, manifest = verify_run(args.baseline)
    variant, variant_manifest = verify_run(args.renamed)
    for root in (args.historical, args.baseline, args.renamed):
        if read_json(root / "status.json")["status"] != "completed":
            raise AssertionError("Acceptance requires completed real Runs")
    if source_identity() != manifest["implementation"] or source_identity() != variant_manifest["implementation"]:
        raise AssertionError("Acceptance code differs from actual execution code")
    if manifest["engine"] != old_manifest["engine"]:
        raise AssertionError("Baseline comparison changed native engine")
    preserved = []
    for relative, digest in old_manifest["hashes"].items():
        if relative.startswith("inputs/") or relative in ("build/atom_mapping.json", "build/solvated.gro", "build/system.top"):
            if sha256(args.baseline / relative) != digest:
                raise AssertionError(f"Baseline scientific input changed: {relative}")
            preserved.append(relative)
    effective = {}
    for stage in stage_ids(old_spec):
        old = effective_parameters(args.historical / "stages" / stage / "resolved.mdp")
        new = effective_parameters(args.baseline / "stages" / stage / "resolved.mdp")
        effective[stage] = compare_effective(old, new)
        if sha256(args.historical / "stages" / stage / "processed.top") != sha256(args.baseline / "stages" / stage / "processed.top"):
            raise AssertionError("Expanded interaction topology changed")
    before_variant = file_identity(args.renamed)
    no_tasks = analyze(args.renamed, args.output / "disabled_analysis")
    if no_tasks != [] or (args.output / "disabled_analysis").exists():
        raise AssertionError("Empty requests unexpectedly performed analysis")
    request = dict(spec["analysis_requests"][0], id="middle_stage", stage_id="sample")
    analysis = Path(analyze(args.renamed, args.output / "analyses", request)[0])
    report = read_json(analysis / "report.json")
    if report["stage_id"] != "sample" or report["frames"] != 11:
        raise AssertionError("Non-prod intermediate-stage analysis failed")
    failure = dict(request, id="invalid_selection", config=dict(request["config"], water_oxygen_selection="name DOES_NOT_EXIST"))
    try:
        analyze(args.renamed, args.output / "failed_analysis", failure)
    except ValueError as error:
        failure_message = str(error)
        if "one oxygen per molecule" not in failure_message:
            raise
    else:
        raise AssertionError("Invalid selection unexpectedly succeeded")
    statuses = list((args.output / "failed_analysis").glob("*/status.json"))
    if len(statuses) != 1 or read_json(statuses[0])["status"] != "failed":
        raise AssertionError("Analysis failure lacks independent failure status")
    if before_variant != file_identity(args.renamed):
        raise AssertionError("Analysis modified the source Run")
    expected = read_json(args.historical_hashes)
    verify_hashes(args.historical, expected)
    if expected != file_identity(args.historical):
        raise AssertionError("Historical file inventory changed")
    original_report = read_json(args.historical_reference / "report.json")
    if original_report["spec_hash"] != old_manifest["spec_hash"]:
        raise AssertionError("Historical reference belongs to another specification")
    old_csv = args.historical_reference / "hydration_counts.csv"
    with old_csv.open() as left, (args.historical_analysis / "hydration_counts.csv").open() as right:
        old_rows, new_rows = list(csv.DictReader(left)), list(csv.DictReader(right))
    if old_rows != new_rows:
        raise AssertionError("Historical frame counts changed")
    legacy_spec = Path(__file__).resolve().parents[1] / "examples/zil_smoke.json"
    load_spec(legacy_spec)  # Recheck all original asset hashes after execution.
    result = dict(status="passed", scientific_quality="not_assessed", engine=manifest["engine"],
                  implementation=source_identity(), unchanged_baseline_inputs=preserved,
                  effective_mdp_comparison=effective, historical_files_unchanged=len(expected),
                  historical_frames_equal=len(old_rows), empty_analysis_no_output=True,
                  independent_analysis_failure=failure_message, nonprod_analysis=str(analysis),
                  baseline_run=str(args.baseline), renamed_run=str(args.renamed),
                  baseline_stages={name: read_json(args.baseline / "stages" / name / "stage.json")["evidence"]
                                   for name in stage_ids(spec)},
                  renamed_stages={name: read_json(args.renamed / "stages" / name / "stage.json")["evidence"]
                                  for name in stage_ids(variant)})
    write_json(args.output / "acceptance.json", result)
    print(args.output / "acceptance.json")


if __name__ == "__main__":
    main()
