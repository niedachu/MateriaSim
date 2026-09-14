"""Audit M2's original assets and real Runs without rewriting scientific evidence."""

import argparse
from pathlib import Path

from materials_sim.files import read_json, sha256, verify_hashes, write_json
from materials_sim.prebuilt import verify_processed_models
from materials_sim.records import stage_ids
from materials_sim.state import source_identity, verify_run
from materials_sim.topology import section_rows
from verify_m1_evidence import compare_effective, effective_parameters


def audit_original_models(legacy):
    """Check independent parameterization provenance, charges and the merged GAFF2 type table."""
    union, models = {}, {}
    for name in ("cat", "ani"):
        folder = legacy / "parameterization/results" / name
        metadata = read_json(folder / f"{name}_metadata.json")
        verify_hashes(folder, metadata["outputs_sha256"])
        if sha256(folder / f"{name}.itp") != sha256(legacy / "topology" / f"{name}.itp"):
            raise AssertionError("Assembled model differs from parameterization")
        types = {row[0]: row for section, row in section_rows(folder / f"{name}_atomtypes.itp")
                 if section == "atomtypes"}
        for key, value in types.items():
            if key in union and union[key] != value:
                raise AssertionError("Conflicting shared atom type")
            union[key] = value
        atoms = [row for section, row in section_rows(folder / f"{name}.itp") if section == "atoms"]
        charge = sum(float(row[6]) for row in atoms)
        if len(atoms) != metadata["atom_count"] or abs(charge - metadata["gromacs_itp_total_charge_e"]) > 1e-12:
            raise AssertionError("Model charge/count changed")
        if not {row[1] for row in atoms}.issubset(types):
            raise AssertionError("Missing standalone atom type")
        models[name] = dict(atom_count=len(atoms), charge_e=charge,
                            attention=metadata["parmchk2_attention_lines"])
    combined = {row[0]: row for section, row in section_rows(legacy / "topology/gaff2_atomtypes.itp")
                if section == "atomtypes"}
    if combined != union:
        raise AssertionError("Global GAFF2 table is not the exact independent-model union")
    return dict(models=models, shared_table_types=len(union), global_table_equal=True)


def compare_zil(baseline, current):
    """Require identical frozen ZIL inputs, mappings, expanded topologies and effective physics."""
    spec, manifest = verify_run(baseline)
    _, current_manifest = verify_run(current)
    if manifest["engine"] != current_manifest["engine"] or manifest["spec_hash"] != current_manifest["spec_hash"]:
        raise AssertionError("ZIL baseline changed engine or experiment")
    count = 0
    for relative, digest in manifest["hashes"].items():
        if relative.startswith("inputs/") or relative in ("build/solvated.gro", "build/system.top", "build/atom_mapping.json"):
            if sha256(current / relative) != digest:
                raise AssertionError(f"ZIL input changed: {relative}")
            count += 1
    stages = {}
    for name in stage_ids(spec):
        old, new = baseline / "stages" / name, current / "stages" / name
        if sha256(old / "processed.top") != sha256(new / "processed.top"):
            raise AssertionError("ZIL expanded topology changed")
        stages[name] = compare_effective(effective_parameters(old / "resolved.mdp"),
                                         effective_parameters(new / "resolved.mdp"))
    return dict(unchanged_inputs=count, effective_stages=stages)


def main():
    """Read explicit asset/hash/baseline/Run paths and create a new bounded acceptance summary."""
    parser = argparse.ArgumentParser()
    for name in ("legacy", "legacy_hashes", "baseline", "zil", "pair", "output"):
        parser.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    args = parser.parse_args()
    protected = read_json(args.legacy_hashes)
    verify_hashes(args.legacy, protected)
    result = dict(scientific_quality="not_assessed", preserved_legacy_files=len(protected),
                  original_models=audit_original_models(args.legacy),
                  zil_regression=compare_zil(args.baseline, args.zil), runs={})
    for label, root in (("zil", args.zil), ("pair", args.pair)):
        spec, manifest = verify_run(root)
        if read_json(root / "status.json")["status"] != "completed":
            raise AssertionError("Real acceptance Run is incomplete")
        if manifest["implementation"] != source_identity():
            raise AssertionError("Running and current source identities differ")
        mapping = read_json(root / "build/atom_mapping.json")
        result["runs"][label] = dict(path=str(root), engine=manifest["engine"],
                    implementation=manifest["implementation"], atom_count=mapping["atom_count"],
                    counts=mapping["counts"], charge_e=mapping["charge_e"],
                    stages={name: read_json(root / "stages" / name / "stage.json")["evidence"]
                            for name in stage_ids(spec)})
        if label == "pair":
            if mapping["counts"] != {"CAT": 1, "ANI": 1, "SOL": 2957} or mapping["atom_count"] != 8912:
                raise AssertionError("CAT/ANI acceptance composition mismatch")
            sources = {path.name: path for path in (root / "inputs").iterdir() if path.is_file()}
            verify_processed_models(spec, sources, root / "stages/em/processed.top")
            defaults = [row for section, row in section_rows(root / "stages/em/processed.top") if section == "defaults"]
            if defaults != [["1", "2", "yes", "0.5", "0.83333333333333333"]]:
                raise AssertionError("Frozen GROMACS 2026.3 AMBER defaults changed")
            result["pair_defaults"] = defaults
    if args.output.exists():
        raise FileExistsError(args.output)
    write_json(args.output, dict(status="passed", **result))
    print(args.output)


if __name__ == "__main__":
    main()
