#!/usr/bin/env python3
"""Validate capped RESP fragments and write an auditable target-atom mapping."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from rdkit import Chem
from rdkit.Chem import AllChem


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def net_formal_charge(molecule: Chem.Mol) -> int:
    return sum(atom.GetFormalCharge() for atom in molecule.GetAtoms())


def mapped_heavy_atoms(molecule: Chem.Mol) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for atom in molecule.GetAtoms():
        if atom.GetAtomicNum() == 1:
            continue
        atom_map = atom.GetAtomMapNum()
        if atom_map <= 0:
            raise ValueError(f"heavy atom {atom.GetIdx()} lacks an atom-map number")
        if atom_map in mapping:
            raise ValueError(f"duplicate atom-map number {atom_map}")
        mapping[atom_map] = atom.GetIdx()
    return mapping


def attached_hydrogens(molecule: Chem.Mol, atom_index: int) -> list[int]:
    return sorted(
        neighbor.GetIdx()
        for neighbor in molecule.GetAtomWithIdx(atom_index).GetNeighbors()
        if neighbor.GetAtomicNum() == 1
    )


def embed_for_review(molecule: Chem.Mol, random_seed: int) -> str:
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = random_seed
    parameters.useRandomCoords = True
    status = AllChem.EmbedMolecule(molecule, parameters)
    if status != 0:
        raise RuntimeError("RDKit could not embed a fragment review conformer")
    if AllChem.MMFFHasAllMoleculeParams(molecule):
        AllChem.MMFFOptimizeMolecule(molecule, maxIters=1000)
        return "MMFF94"
    AllChem.UFFOptimizeMolecule(molecule, maxIters=1000)
    return "UFF_fallback"


def build_target(config: dict[str, Any]) -> Chem.Mol:
    target = Chem.MolFromSmiles(config["target"]["smiles"])
    if target is None:
        raise ValueError("target SMILES could not be parsed")
    target = Chem.AddHs(target)
    expected = int(config["target"]["expected_atom_count_with_hydrogens"])
    if target.GetNumAtoms() != expected:
        raise ValueError(f"target has {target.GetNumAtoms()} atoms; expected {expected}")
    if net_formal_charge(target) != int(config["target"]["formal_charge_e"]):
        raise ValueError("target formal charge is incorrect")
    heavy = [atom.GetIdx() for atom in target.GetAtoms() if atom.GetAtomicNum() != 1]
    if heavy != list(range(len(heavy))):
        raise ValueError("target heavy atoms must precede added hydrogens for the map rule")
    return target


def validate_cut_bonds(target: Chem.Mol, config: dict[str, Any]) -> None:
    for begin, end in config["cut_bonds_target_zero_based"]:
        bond = target.GetBondBetweenAtoms(int(begin), int(end))
        if bond is None:
            raise ValueError(f"configured cut bond {begin}-{end} does not exist")
        atoms = (target.GetAtomWithIdx(int(begin)), target.GetAtomWithIdx(int(end)))
        if any(atom.GetAtomicNum() != 6 for atom in atoms):
            raise ValueError(f"configured cut bond {begin}-{end} is not C-C")
        if bond.GetBondType() != Chem.BondType.SINGLE:
            raise ValueError(f"configured cut bond {begin}-{end} is not single")


def fragment_record(
    target: Chem.Mol,
    scheme_name: str,
    fragment_name: str,
    definition: dict[str, Any],
    output_dir: Path,
    random_seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base = Chem.MolFromSmiles(definition["smiles"])
    if base is None:
        raise ValueError(f"cannot parse {scheme_name}/{fragment_name} SMILES")
    if net_formal_charge(base) != int(definition["formal_charge_e"]):
        raise ValueError(f"formal charge mismatch for {scheme_name}/{fragment_name}")
    molecule = Chem.AddHs(base)
    heavy_map = mapped_heavy_atoms(molecule)
    retained_maps = {int(value) for value in definition["retained_atom_maps"]}
    cap_groups = [
        {int(value) for value in group}
        for group in definition["cap_groups_atom_maps"]
    ]
    cap_maps = set().union(*cap_groups)
    if retained_maps & cap_maps:
        raise ValueError(f"retained and cap maps overlap in {scheme_name}/{fragment_name}")
    if retained_maps | cap_maps != set(heavy_map):
        raise ValueError(f"retained/cap maps do not cover {scheme_name}/{fragment_name}")

    atom_rows: list[dict[str, Any]] = []
    mapped_model_indices: set[int] = set()
    for atom_map in sorted(retained_maps):
        model_index = heavy_map[atom_map]
        target_index = atom_map - 1
        target_atom = target.GetAtomWithIdx(target_index)
        model_atom = molecule.GetAtomWithIdx(model_index)
        if model_atom.GetAtomicNum() != target_atom.GetAtomicNum():
            raise ValueError(
                f"element mismatch for atom map {atom_map} in {scheme_name}/{fragment_name}"
            )
        atom_rows.append(
            {
                "scheme": scheme_name,
                "fragment": fragment_name,
                "model_atom_index_zero_based": model_index,
                "target_atom_index_zero_based": target_index,
                "element": model_atom.GetSymbol(),
                "role": "retained_heavy",
                "atom_map": atom_map,
            }
        )
        mapped_model_indices.add(model_index)
        model_hydrogens = attached_hydrogens(molecule, model_index)
        target_hydrogens = attached_hydrogens(target, target_index)
        if len(model_hydrogens) != len(target_hydrogens):
            raise ValueError(
                f"hydrogen-count mismatch for atom map {atom_map}: "
                f"model={len(model_hydrogens)}, target={len(target_hydrogens)}"
            )
        for model_h, target_h in zip(model_hydrogens, target_hydrogens):
            atom_rows.append(
                {
                    "scheme": scheme_name,
                    "fragment": fragment_name,
                    "model_atom_index_zero_based": model_h,
                    "target_atom_index_zero_based": target_h,
                    "element": "H",
                    "role": "retained_hydrogen",
                    "atom_map": atom_map,
                }
            )
            mapped_model_indices.add(model_h)

    cap_group_indices: list[list[int]] = []
    for group in cap_groups:
        indices: set[int] = set()
        for atom_map in group:
            heavy_index = heavy_map[atom_map]
            indices.add(heavy_index)
            indices.update(attached_hydrogens(molecule, heavy_index))
        cap_group_indices.append(sorted(indices))
        for model_index in sorted(indices):
            atom = molecule.GetAtomWithIdx(model_index)
            atom_rows.append(
                {
                    "scheme": scheme_name,
                    "fragment": fragment_name,
                    "model_atom_index_zero_based": model_index,
                    "target_atom_index_zero_based": None,
                    "element": atom.GetSymbol(),
                    "role": "cap",
                    "atom_map": atom.GetAtomMapNum() or None,
                }
            )
            mapped_model_indices.add(model_index)

    if mapped_model_indices != set(range(molecule.GetNumAtoms())):
        missing = sorted(set(range(molecule.GetNumAtoms())) - mapped_model_indices)
        raise ValueError(f"unclassified model atoms in {scheme_name}/{fragment_name}: {missing}")

    method = embed_for_review(molecule, random_seed=random_seed)
    molecule.SetProp("scheme", scheme_name)
    molecule.SetProp("fragment", fragment_name)
    molecule.SetProp("review_geometry_method", method)
    sdf_path = output_dir / f"{scheme_name}_{fragment_name}.sdf"
    writer = Chem.SDWriter(str(sdf_path))
    writer.write(molecule)
    writer.close()

    record = {
        "scheme": scheme_name,
        "fragment": fragment_name,
        "smiles": definition["smiles"],
        "formal_charge_e": int(definition["formal_charge_e"]),
        "atom_count_with_hydrogens": molecule.GetNumAtoms(),
        "retained_atom_maps": sorted(retained_maps),
        "cap_groups_atom_maps": [sorted(group) for group in cap_groups],
        "cap_groups_model_indices_zero_based": cap_group_indices,
        "review_sdf": sdf_path.name,
        "review_geometry_method": method,
        "review_sdf_sha256": sha256(sdf_path),
    }
    return record, atom_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    config_path = args.config.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    target = build_target(config)
    validate_cut_bonds(target, config)

    records: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    target_coverages: dict[str, list[int]] = {}
    random_seed = int(config["conformer_generation"]["random_seed"])
    for scheme_name, scheme in config["schemes"].items():
        scheme_rows: list[dict[str, Any]] = []
        for fragment_name, definition in scheme["fragments"].items():
            record, rows = fragment_record(
                target,
                scheme_name,
                fragment_name,
                definition,
                output_dir,
                random_seed=random_seed,
            )
            records.append(record)
            scheme_rows.extend(rows)
            all_rows.extend(rows)
        coverage = sorted(
            int(row["target_atom_index_zero_based"])
            for row in scheme_rows
            if row["target_atom_index_zero_based"] is not None
        )
        expected = list(range(target.GetNumAtoms()))
        if coverage != expected:
            raise ValueError(f"scheme {scheme_name} does not cover every target atom exactly once")
        fragment_charge = math.fsum(
            int(fragment["formal_charge_e"])
            for fragment in scheme["fragments"].values()
        )
        if fragment_charge != int(config["target"]["formal_charge_e"]):
            raise ValueError(f"fragment charges do not sum to target charge in {scheme_name}")
        target_coverages[scheme_name] = coverage

    csv_path = output_dir / "fragment_atom_mapping.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)

    report = {
        "status": "fragment_definitions_validated_pending_qm",
        "config": str(config_path),
        "config_sha256": sha256(config_path),
        "target_atom_count_with_hydrogens": target.GetNumAtoms(),
        "cut_bonds_target_zero_based": config["cut_bonds_target_zero_based"],
        "scheme_target_coverages_zero_based": target_coverages,
        "fragments": records,
        "mapping_csv": csv_path.name,
        "mapping_csv_sha256": sha256(csv_path),
    }
    report_path = output_dir / "fragment_definition_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report_path)


if __name__ == "__main__":
    main()
