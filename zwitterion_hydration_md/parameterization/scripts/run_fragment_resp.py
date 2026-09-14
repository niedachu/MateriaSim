#!/usr/bin/env python3
"""Run capped-fragment HF/6-31G* RESP jobs with zero-charge cap constraints."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import psiresp
from rdkit import Chem

from run_resp import run_until_complete, sha256, write_qm_manifest, write_sdf
from validate_parameters import summarize_atomic_charges


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if config["qm"] != {
        "method": "hf",
        "basis": "6-31g*",
        "geometry_convergence": "gau_tight",
        "gas_phase": True,
    }:
        raise ValueError("fragment RESP must use gas-phase HF/6-31G* with gau_tight optimization")
    if int(config["resp"]["stages"]) != 2:
        raise ValueError("fragment RESP must use two stages")
    if float(config["resp"]["constrain_each_cap_group_charge_e"]) != 0.0:
        raise ValueError("this implementation requires every cap group to be constrained to 0 e")
    return config


def mapped_heavy_indices(molecule: psiresp.Molecule) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for atom in molecule._rdmol.GetAtoms():
        if atom.GetAtomicNum() == 1:
            continue
        atom_map = atom.GetAtomMapNum()
        if atom_map <= 0 or atom_map in mapping:
            raise ValueError("fragment heavy-atom maps must be positive and unique")
        mapping[atom_map] = atom.GetIdx()
    return mapping


def attached_hydrogens(molecule: psiresp.Molecule, atom_index: int) -> list[int]:
    return sorted(
        neighbor.GetIdx()
        for neighbor in molecule._rdmol.GetAtomWithIdx(atom_index).GetNeighbors()
        if neighbor.GetAtomicNum() == 1
    )


def cap_group_indices(
    molecule: psiresp.Molecule, definition: dict[str, Any]
) -> list[list[int]]:
    heavy = mapped_heavy_indices(molecule)
    groups: list[list[int]] = []
    for atom_maps in definition["cap_groups_atom_maps"]:
        indices: set[int] = set()
        for atom_map in atom_maps:
            index = heavy[int(atom_map)]
            indices.add(index)
            indices.update(attached_hydrogens(molecule, index))
        groups.append(sorted(indices))
    return groups


def model_to_target_mapping(
    molecule: psiresp.Molecule, definition: dict[str, Any]
) -> dict[int, int]:
    heavy = mapped_heavy_indices(molecule)
    mapping: dict[int, int] = {}
    for atom_map in definition["retained_atom_maps"]:
        model_index = heavy[int(atom_map)]
        target_index = int(atom_map) - 1
        mapping[model_index] = target_index
        model_h = attached_hydrogens(molecule, model_index)
        # Target hydrogens were appended after 19 heavy atoms. Their explicit
        # mapping is loaded from the validated stage-A CSV, not guessed here.
        if len(model_h) > 3:
            raise ValueError("unexpected retained-atom hydrogen count")
    return mapping


def mapping_from_stage_a(
    mapping_csv: Path, scheme: str, fragment: str
) -> dict[int, int]:
    mapping: dict[int, int] = {}
    with mapping_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["scheme"] != scheme or row["fragment"] != fragment:
                continue
            if row["target_atom_index_zero_based"] == "":
                continue
            model_index = int(row["model_atom_index_zero_based"])
            target_index = int(row["target_atom_index_zero_based"])
            if model_index in mapping:
                raise ValueError("duplicate model atom in stage-A mapping")
            mapping[model_index] = target_index
    if not mapping:
        raise ValueError(f"no stage-A mapping found for {scheme}/{fragment}")
    return mapping


def build_job(
    config: dict[str, Any],
    definition: dict[str, Any],
    work_root: Path,
) -> tuple[psiresp.Job, list[list[int]], dict[int, int]]:
    conformers = config["conformer_generation"]
    options = psiresp.ConformerGenerationOptions(
        n_conformer_pool=int(conformers["initial_pool"]),
        n_max_conformers=int(conformers["selected_max"]),
        rms_tolerance=float(conformers["rms_tolerance_A"]),
        energy_window=float(conformers["energy_window_kcal_mol"]),
        keep_original_conformer=bool(conformers["keep_original"]),
        minimize=str(conformers["minimize"]),
    )
    molecule = psiresp.Molecule.from_smiles(
        definition["smiles"],
        random_seed=int(conformers["random_seed"]),
        charge=int(definition["formal_charge_e"]),
        multiplicity=int(config["target"]["multiplicity"]),
        optimize_geometry=True,
        conformer_generation_options=options,
    )
    molecule.keep_original_orientation = bool(config["orientations"]["keep_original"])
    molecule.generate_transformations(
        n_reorientations=int(config["orientations"]["generated_reorientations"])
    )
    cap_groups = cap_group_indices(molecule, definition)
    direct_mapping = model_to_target_mapping(molecule, definition)
    constraints = psiresp.ChargeConstraintOptions(
        symmetric_atoms_are_equivalent=bool(
            config["resp"]["symmetric_atoms_are_equivalent"]
        )
    )
    for indices in cap_groups:
        constraints.add_charge_sum_constraint_for_molecule(
            molecule,
            charge=float(config["resp"]["constrain_each_cap_group_charge_e"]),
            indices=indices,
        )
    job = psiresp.TwoStageRESP(
        molecules=[molecule],
        working_directory=work_root / "psiresp_working_directory",
        temperature=298.15,
        n_processes=int(config["resources"]["threads"]),
        charge_constraints=constraints,
    )
    job.qm_optimization_options.g_convergence = config["qm"]["geometry_convergence"]
    return job, cap_groups, direct_mapping


def write_fragment_results(
    job: psiresp.Job,
    charges: np.ndarray,
    cap_groups: list[list[int]],
    mapping: dict[int, int],
    config: dict[str, Any],
    config_path: Path,
    scheme: str,
    fragment: str,
    work_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    molecule = job.molecules[0]
    if len(charges) != molecule.n_atoms:
        raise ValueError("RESP charge count does not match fragment atom count")
    cap_indices = {index for group in cap_groups for index in group}
    if cap_indices & set(mapping):
        raise ValueError("cap and retained atom mappings overlap")
    if cap_indices | set(mapping) != set(range(molecule.n_atoms)):
        raise ValueError("cap and retained atoms do not cover the model")

    cap_sums = [math.fsum(float(charges[index]) for index in group) for group in cap_groups]
    tolerance = float(config["validation"]["net_charge_tolerance_e"])
    if any(abs(value) > tolerance for value in cap_sums):
        raise ValueError(f"cap charge constraint failed: {cap_sums}")
    retained_sum = math.fsum(float(charges[index]) for index in mapping)
    expected = int(
        config["schemes"][scheme]["fragments"][fragment]["formal_charge_e"]
    )
    if abs(retained_sum - expected) > tolerance:
        raise ValueError(
            f"retained fragment charge {retained_sum:.8f} differs from {expected}"
        )
    charge_screen = summarize_atomic_charges(
        charges,
        expected_charge=float(expected),
        net_charge_tolerance=tolerance,
        max_abs_atomic_charge=float(config["validation"]["max_abs_atomic_charge_e"]),
    )

    all_csv = output_dir / "model_charges.csv"
    with all_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "model_atom_index_zero_based",
                "element",
                "role",
                "target_atom_index_zero_based",
                "resp_charge_e",
            ]
        )
        for index, (element, charge) in enumerate(zip(molecule.qcmol.symbols, charges)):
            writer.writerow(
                [
                    index,
                    element,
                    "retained" if index in mapping else "cap",
                    mapping.get(index, ""),
                    f"{float(charge):.10f}",
                ]
            )
    retained_csv = output_dir / "retained_charges.csv"
    with retained_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "target_atom_index_zero_based",
                "model_atom_index_zero_based",
                "element",
                "resp_charge_e",
            ]
        )
        for model_index, target_index in sorted(mapping.items(), key=lambda item: item[1]):
            writer.writerow(
                [
                    target_index,
                    model_index,
                    molecule.qcmol.symbols[model_index],
                    f"{float(charges[model_index]):.10f}",
                ]
            )

    for conformer_index in range(len(molecule.conformers)):
        write_sdf(molecule, conformer_index, output_dir / f"conformer_{conformer_index:02d}.sdf")
    config_digest = sha256(config_path)
    write_qm_manifest(work_root, config_sha256=config_digest)
    status = (
        "fragment_resp_complete_pending_assembly"
        if charge_screen["passed_conservative_magnitude_screen"]
        else "fragment_resp_rejected_unphysical_charges"
    )
    metadata = {
        "status": status,
        "scheme": scheme,
        "fragment": fragment,
        "formal_charge_e": expected,
        "atom_count": molecule.n_atoms,
        "retained_atom_count": len(mapping),
        "conformer_count": len(molecule.conformers),
        "orientation_count": molecule.n_orientations,
        "total_resp_charge_e": math.fsum(float(value) for value in charges),
        "retained_resp_charge_e": retained_sum,
        "cap_group_charge_sums_e": cap_sums,
        "cap_groups_model_indices_zero_based": cap_groups,
        "charge_validation": charge_screen,
        "config_sha256": config_digest,
        "large_working_directory": str(work_root),
        "software": {
            "psiresp": psiresp.__version__,
            "rdkit": Chem.rdBase.rdkitVersion,
        },
        "outputs": {
            path.name: sha256(path)
            for path in sorted(output_dir.iterdir())
            if path.is_file() and path.name != "fragment_resp_metadata.json"
        },
    }
    metadata_path = output_dir / "fragment_resp_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    if status != "fragment_resp_complete_pending_assembly":
        raise ValueError(f"{scheme}/{fragment} failed the atomic-charge screen")
    return metadata


def run_one(
    config: dict[str, Any],
    config_path: Path,
    mapping_csv: Path,
    scheme: str,
    fragment: str,
    work_base: Path,
    output_base: Path,
) -> dict[str, Any]:
    definition = config["schemes"][scheme]["fragments"][fragment]
    work_root = work_base / scheme / fragment
    output_dir = output_base / scheme / fragment
    work_root.mkdir(parents=True, exist_ok=True)
    mapping = mapping_from_stage_a(mapping_csv, scheme, fragment)
    job, cap_groups, direct_mapping = build_job(config, definition, work_root)
    if any(mapping.get(index) != target for index, target in direct_mapping.items()):
        raise ValueError("stage-A and PsiRESP heavy-atom mappings disagree")
    charges = run_until_complete(
        job,
        threads=int(config["resources"]["threads"]),
        memory=str(config["resources"]["memory"]),
        scratch=work_root / "psi4_scratch",
    )
    return write_fragment_results(
        job,
        charges,
        cap_groups,
        mapping,
        config,
        config_path,
        scheme,
        fragment,
        work_root,
        output_dir,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--mapping-csv", type=Path, required=True)
    parser.add_argument("--work-base", type=Path, required=True)
    parser.add_argument("--output-base", type=Path, required=True)
    parser.add_argument("--scheme", choices=["methyl", "ethyl"])
    parser.add_argument("--fragment", choices=["sulfonate", "imidazolium", "ether"])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.all == (args.scheme is not None or args.fragment is not None):
        raise ValueError("use either --all or both --scheme and --fragment")
    if not args.all and (args.scheme is None or args.fragment is None):
        raise ValueError("both --scheme and --fragment are required")

    config_path = args.config.resolve()
    config = load_config(config_path)
    if args.all:
        tasks = [
            (scheme, fragment)
            for scheme in ("methyl", "ethyl")
            for fragment in ("sulfonate", "imidazolium", "ether")
        ]
    else:
        tasks = [(args.scheme, args.fragment)]
    completed = []
    for scheme, fragment in tasks:
        print(f"START {scheme}/{fragment}", flush=True)
        if args.validate_only:
            definition = config["schemes"][scheme]["fragments"][fragment]
            setup_root = args.work_base.resolve() / scheme / fragment
            mapping = mapping_from_stage_a(
                args.mapping_csv.resolve(), scheme, fragment
            )
            job, cap_groups, direct_mapping = build_job(config, definition, setup_root)
            if any(mapping.get(index) != target for index, target in direct_mapping.items()):
                raise ValueError("stage-A and PsiRESP heavy-atom mappings disagree")
            if len(job.charge_constraints.charge_sum_constraints) != len(cap_groups):
                raise ValueError("not every cap group produced a PsiRESP charge constraint")
            completed.append(
                {
                    "scheme": scheme,
                    "fragment": fragment,
                    "status": "setup_validated_no_qm",
                    "model_atom_count": job.molecules[0].n_atoms,
                    "retained_atom_count": len(mapping),
                    "cap_groups_model_indices_zero_based": cap_groups,
                    "charge_sum_constraint_count": len(
                        job.charge_constraints.charge_sum_constraints
                    ),
                }
            )
            print(f"VALIDATED {scheme}/{fragment}", flush=True)
            continue
        metadata = run_one(
            config,
            config_path,
            args.mapping_csv.resolve(),
            scheme,
            fragment,
            args.work_base.resolve(),
            args.output_base.resolve(),
        )
        completed.append(
            {
                "scheme": scheme,
                "fragment": fragment,
                "status": metadata["status"],
            }
        )
        print(f"COMPLETE {scheme}/{fragment}", flush=True)
    summary = {
        "status": (
            "fragment_resp_setup_validated_no_qm"
            if args.validate_only
            else "all_requested_fragment_resp_jobs_complete"
        ),
        "tasks": completed,
        "config_sha256": sha256(config_path),
    }
    summary_path = args.output_base.resolve() / (
        "fragment_resp_setup_validation.json"
        if args.validate_only
        else "fragment_resp_run_summary.json"
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(summary_path)


if __name__ == "__main__":
    main()
