"""Audit real packed Runs and cross-check molecular contacts with independent minimum-image loops."""

import argparse
import csv
import math
import shutil
from pathlib import Path

from materials_sim.analysis import analyze
from materials_sim.files import read_json, sha256, verify_hashes, write_json
from materials_sim.records import stage_ids
from materials_sim.schema import load_spec
from materials_sim.state import source_identity, verify_run
from verify_m1_evidence import file_identity


def reference_counts(analysis, output):
    """Compare every CSV frame with an independent orthorhombic minimum-image atom loop on private copies."""
    import MDAnalysis as mda

    output.mkdir(parents=True, exist_ok=False)
    for name in ("coordinates.gro", "trajectory.xtc", "mapping.json"):
        shutil.copyfile(analysis / "inputs" / name, output / name)
    mapping = read_json(output / "mapping.json")
    report = read_json(analysis / "report.json")
    config = report["selection"]
    groups = [[i for i, atom in enumerate(mapping["atoms"]) if atom["component_id"] == config[key]]
              for key in ("component_a", "component_b")]
    with (analysis / "component_contacts.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    universe = mda.Universe(str(output / "coordinates.gro"), str(output / "trajectory.xtc"))
    try:
        if len(universe.trajectory) != len(rows):
            raise AssertionError("Reference frame count differs")
        for frame, row in zip(universe.trajectory, rows):
            if any(abs(float(angle) - 90) > 1e-5 for angle in frame.dimensions[3:]):
                raise AssertionError("Reference fixture must be orthorhombic")
            pairs = set()
            for a in groups[0]:
                for b in groups[1]:
                    left, right = mapping["atoms"][a]["molecule_id"], mapping["atoms"][b]["molecule_id"]
                    if left == right:
                        continue
                    delta = [float(frame.positions[a][k]) - float(frame.positions[b][k]) for k in range(3)]
                    delta = [value - float(length) * math.floor(value / float(length) + .5)
                             for value, length in zip(delta, frame.dimensions[:3])]
                    if sum(value ** 2 for value in delta) <= (config["cutoff_nm"] * 10) ** 2:
                        pairs.add(tuple(sorted((left, right))))
            if float(row["time_ps"]) != float(frame.time) or int(row["unique_molecule_pairs"]) != len(pairs):
                raise AssertionError("Independent contact counts differ")
    finally:
        universe.trajectory.close()
    result = dict(equal=True, frames=len(rows), csv_sha256=sha256(analysis / "component_contacts.csv"))
    write_json(output / "comparison.json", result)
    return result


def audit_run(root, output):
    """Verify completed source identity, group ownership and independent analysis without changing the Run."""
    spec, manifest = verify_run(root)
    if manifest["implementation"] != source_identity() or read_json(root / "status.json")["status"] != "completed":
        raise AssertionError("Acceptance requires completed current-source Runs")
    before = file_identity(root)
    mapping = read_json(root / "build/atom_mapping.json")
    expected = {component["id"]: component["count"] for component in spec["components"]}
    if {name: count for name, count in mapping["counts"].items() if name != "SOL"} != expected:
        raise AssertionError("Packed molecule count mismatch")
    for group in spec["scenario"]["groups"]:
        atoms = [atom for atom in mapping["atoms"] if atom["group_id"] == group["id"]]
        if len({atom["molecule_id"] for atom in atoms}) != group["count"]:
            raise AssertionError("Group count mismatch")
    if len({atom["atom_uid"] for atom in mapping["atoms"]}) != mapping["atom_count"]:
        raise AssertionError("Nonunique atom identities")
    dry = spec["scenario"]["solvent"]["kind"] == "none"
    if dry != ("SOL" not in mapping["counts"]):
        raise AssertionError("Solvent policy violated")
    analysis = Path(analyze(root, output / "analysis")[0])
    comparison = reference_counts(analysis, output / "reference" / root.name)
    if before != file_identity(root):
        raise AssertionError("Analysis modified its source Run")
    return dict(run=str(root), atom_count=mapping["atom_count"], counts=mapping["counts"],
                charge_e=mapping["charge_e"], analysis=str(analysis), reference=comparison,
                group_counts={group["id"]: group["count"] for group in spec["scenario"]["groups"]},
                packing_tool=read_json(root / "build/packing/tool.json"),
                minimum_intermolecular_distance_nm=read_json(root / "build/packing/mapping.json")["minimum_intermolecular_distance_nm"],
                stages={name: read_json(root / "stages" / name / "stage.json")["evidence"] for name in stage_ids(spec)},
                source_run_unchanged=True)


def main():
    """Audit the four declared real fixtures and original assets, writing only a new evidence directory."""
    parser = argparse.ArgumentParser()
    for name in ("runs", "legacy", "protected", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    roots = sorted(path for path in args.runs.iterdir() if (path / "manifest.json").is_file())
    expected = {"packed_zil_water", "packed_ions_water", "packed_mixture_water", "packed_zil_dry"}
    if len(roots) != 4 or {read_json(root / "resolved_spec.json")["id"] for root in roots} != expected:
        raise AssertionError("Expected exactly the four declared fixtures")
    protected = read_json(args.protected)
    verify_hashes(args.legacy, protected)
    examples = Path(__file__).resolve().parents[1] / "examples"
    for name in ("zil_smoke.json", "zil_smoke_v2.json", "cat_ani_smoke.json"):
        load_spec(examples / name)
    args.output.mkdir(parents=True, exist_ok=False)
    results = [audit_run(root, args.output) for root in roots]
    write_json(args.output / "acceptance.json", dict(status="passed", scientific_quality="not_assessed",
               protected_legacy_files=len(protected), implementation=source_identity(), runs=results,
               not_tested=["mixed solvents", "Linux", "GPU", "equilibrium", "material properties"]))
    print(args.output / "acceptance.json")


if __name__ == "__main__":
    main()
