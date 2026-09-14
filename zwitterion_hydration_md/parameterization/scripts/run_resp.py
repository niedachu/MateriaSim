#!/usr/bin/env python3
"""Run the formal multi-conformer, two-stage RESP parameterization.

PsiRESP performs conformer selection, Psi4 input generation, ESP evaluation,
and RESP fitting. This module only validates configuration, executes the
generated Psi4 QCSchema scripts, and writes traceable result files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import shlex
import subprocess
from typing import Any

import numpy as np
import psi4
import psiresp
from rdkit import Chem

from validate_parameters import summarize_atomic_charges


RUNFILE_PATTERN = re.compile(r"commands are in (.+)$")


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if int(config["molecular_charge_e"]) != 0:
        raise ValueError("this project requires a net-neutral zwitterion")
    if int(config["multiplicity"]) != 1:
        raise ValueError("this closed-shell molecule requires multiplicity 1")
    conformers = config["conformer_generation"]
    if int(conformers["initial_pool"]) < 50:
        raise ValueError("initial conformer pool must contain at least 50 attempts")
    if not 5 <= int(conformers["selected_max"]) <= 10:
        raise ValueError("selected_max must be between 5 and 10")
    if config["qm"] != {
        "method": "hf",
        "basis": "6-31g*",
        "geometry_convergence": "gau_tight",
        "gas_phase": True,
    }:
        raise ValueError("formal GAFF2 RESP must use gas-phase HF/6-31G* with gau_tight optimization")
    if int(config["resp"]["stages"]) != 2:
        raise ValueError("formal RESP fit must use two stages")
    validation = config["validation"]
    if float(validation["net_charge_tolerance_e"]) <= 0:
        raise ValueError("net charge tolerance must be positive")
    if float(validation["max_abs_atomic_charge_e"]) <= 0:
        raise ValueError("maximum absolute atomic charge must be positive")
    if int(config["resources"]["threads"]) < 1:
        raise ValueError("threads must be positive")
    if not re.fullmatch(r"[1-9][0-9]*(?:MB|GB)", str(config["resources"]["memory"])):
        raise ValueError("memory must use a positive integer followed by MB or GB")
    return config


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_job(config: dict[str, Any], work_root: Path) -> psiresp.Job:
    conformers = config["conformer_generation"]
    generation_options = psiresp.ConformerGenerationOptions(
        n_conformer_pool=int(conformers["initial_pool"]),
        n_max_conformers=int(conformers["selected_max"]),
        rms_tolerance=float(conformers["rms_tolerance_A"]),
        energy_window=float(conformers["energy_window_kcal_mol"]),
        keep_original_conformer=bool(conformers["keep_original"]),
        minimize=str(conformers["minimize"]),
    )
    molecule = psiresp.Molecule.from_smiles(
        config["smiles"],
        random_seed=1,
        charge=int(config["molecular_charge_e"]),
        multiplicity=int(config["multiplicity"]),
        optimize_geometry=True,
        conformer_generation_options=generation_options,
    )
    molecule.keep_original_orientation = bool(config["orientations"]["keep_original"])
    molecule.generate_transformations(
        n_reorientations=int(config["orientations"]["generated_reorientations"])
    )

    job = psiresp.TwoStageRESP(
        molecules=[molecule],
        working_directory=work_root / "psiresp_working_directory",
        temperature=float(config["temperature_K"]),
        n_processes=int(config["resources"]["threads"]),
        charge_constraints={
            "symmetric_atoms_are_equivalent": bool(
                config["resp"]["symmetric_atoms_are_equivalent"]
            )
        },
    )
    job.qm_optimization_options.g_convergence = config["qm"]["geometry_convergence"]
    return job


def generated_runfile_from_exit(error: SystemExit) -> Path:
    match = RUNFILE_PATTERN.search(str(error))
    if match is None:
        raise RuntimeError(f"PsiRESP stopped without reporting a run file: {error}")
    return Path(match.group(1)).resolve()


def qcschema_inputs_from_runfile(runfile: Path) -> list[str]:
    inputs: list[str] = []
    for raw_line in runfile.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        command = shlex.split(line)
        if len(command) != 3 or command[:2] != ["psi4", "--qcschema"]:
            raise ValueError(f"unexpected command in PsiRESP run file: {line}")
        if Path(command[2]).name != command[2]:
            raise ValueError(f"QCSchema input must be a local filename: {command[2]}")
        inputs.append(command[2])
    if not inputs:
        raise ValueError(f"no QCSchema inputs found in {runfile}")
    return inputs


def run_generated_qm(runfile: Path, threads: int, memory: str, scratch: Path) -> None:
    if not runfile.is_file():
        raise FileNotFoundError(f"PsiRESP run file does not exist: {runfile}")
    scratch.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.update(
        {
            "OMP_NUM_THREADS": str(threads),
            "MKL_NUM_THREADS": str(threads),
            "PSI_SCRATCH": str(scratch),
        }
    )
    for filename in qcschema_inputs_from_runfile(runfile):
        subprocess.run(
            [
                "psi4",
                "-n",
                str(threads),
                "--memory",
                memory,
                "--scratch",
                str(scratch),
                "--qcschema",
                filename,
            ],
            cwd=runfile.parent,
            env=environment,
            check=True,
        )


def run_until_complete(
    job: psiresp.Job, threads: int, memory: str, scratch: Path
) -> np.ndarray:
    # Forking after Psi4/MKL has been imported can leave idle pool workers that
    # never terminate. Spawn gives every PsiRESP ESP worker a clean runtime.
    multiprocessing.set_start_method("spawn", force=True)
    job.generate_conformers()
    try:
        job.optimize_geometries()
    except SystemExit as error:
        runfile = generated_runfile_from_exit(error)
        run_generated_qm(runfile, threads=threads, memory=memory, scratch=scratch)
        try:
            job.optimize_geometries()
        except SystemExit as repeated:
            raise RuntimeError("PsiRESP geometry optimization did not finish after execution") from repeated

    job.generate_orientations()
    try:
        charges = np.asarray(job.compute_esps_and_charges()[0], dtype=float)
    except SystemExit as error:
        runfile = generated_runfile_from_exit(error)
        run_generated_qm(runfile, threads=threads, memory=memory, scratch=scratch)
        try:
            charges = np.asarray(job.compute_esps_and_charges()[0], dtype=float)
        except SystemExit as repeated:
            raise RuntimeError("PsiRESP single-point stage did not finish after execution") from repeated
    if not np.all(np.isfinite(charges)):
        raise ValueError("RESP returned a non-finite charge")
    return charges


def write_qm_manifest(work_root: Path, config_sha256: str) -> None:
    working_directory = work_root / "psiresp_working_directory"
    qcschema_files = sorted(working_directory.rglob("*.msgpack"))
    if not qcschema_files:
        raise ValueError("no Psi4 QCSchema files found for the QM manifest")
    manifest = {
        "config_sha256": config_sha256,
        "qcschema_file_count": len(qcschema_files),
        "qcschema_files": [
            {
                "path": str(path.relative_to(work_root)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in qcschema_files
        ],
    }
    (work_root / "qm_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def atom_names(molecule: psiresp.Molecule) -> list[str]:
    counters: dict[str, int] = {}
    names: list[str] = []
    for symbol in molecule.qcmol.symbols:
        counters[symbol] = counters.get(symbol, 0) + 1
        names.append(f"{symbol}{counters[symbol]}")
    return names


def terminal_indices(molecule: psiresp.Molecule) -> tuple[int, int]:
    rdkit_molecule = molecule.to_rdkit()
    sulfur = [atom.GetIdx() for atom in rdkit_molecule.GetAtoms() if atom.GetAtomicNum() == 16]
    if len(sulfur) != 1:
        raise ValueError(f"expected one sulfur atom, found {len(sulfur)}")
    sulfur_index = sulfur[0]
    distances = Chem.GetDistanceMatrix(rdkit_molecule)[sulfur_index]
    carbon_indices = [
        atom.GetIdx() for atom in rdkit_molecule.GetAtoms() if atom.GetAtomicNum() == 6
    ]
    terminal_carbon = max(carbon_indices, key=lambda index: (distances[index], index))
    return sulfur_index, terminal_carbon


def representative_conformers(molecule: psiresp.Molecule) -> dict[str, int]:
    if len(molecule.conformers) < 3:
        raise ValueError("at least three optimized conformers are required")
    sulfur_index, terminal_carbon = terminal_indices(molecule)
    lengths = np.array(
        [
            np.linalg.norm(
                conformer.coordinates[sulfur_index] - conformer.coordinates[terminal_carbon]
            )
            for conformer in molecule.conformers
        ]
    )
    order = np.argsort(lengths, kind="stable")
    return {
        "folded": int(order[0]),
        "intermediate": int(order[len(order) // 2]),
        "extended": int(order[-1]),
    }


def write_sdf(molecule: psiresp.Molecule, conformer_index: int, path: Path) -> None:
    rdkit_molecule = Chem.Mol(molecule._rdmol)
    rdkit_molecule.RemoveAllConformers()
    coordinates = molecule.conformers[conformer_index].coordinates
    conformer = Chem.Conformer(rdkit_molecule.GetNumAtoms())
    for atom_index, (x, y, z) in enumerate(coordinates):
        conformer.SetAtomPosition(atom_index, (float(x), float(y), float(z)))
    rdkit_molecule.AddConformer(conformer, assignId=True)
    for name, charge, atom in zip(atom_names(molecule), molecule.charges, rdkit_molecule.GetAtoms()):
        atom.SetProp("_TriposAtomName", name)
        atom.SetDoubleProp("RESPCharge", float(charge))
    Chem.CreateAtomDoublePropertyList(rdkit_molecule, "RESPCharge")
    Chem.MolToMolFile(rdkit_molecule, str(path), kekulize=False)


def write_results(
    job: psiresp.Job,
    charges: np.ndarray,
    config: dict[str, Any],
    config_path: Path,
    work_root: Path,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    molecule = job.molecules[0]
    names = atom_names(molecule)
    charge_path = output_dir / "resp_charges.csv"
    charge_lines = ["atom_index,atom_name,element,resp_charge_e"]
    for index, (name, symbol, charge) in enumerate(
        zip(names, molecule.qcmol.symbols, charges), start=1
    ):
        charge_lines.append(f"{index},{name},{symbol},{charge:.10f}")
    charge_path.write_text("\n".join(charge_lines) + "\n", encoding="utf-8")

    charge_file = output_dir / "resp_charges.txt"
    charge_file.write_text("\n".join(f"{charge:.10f}" for charge in charges) + "\n", encoding="utf-8")

    representatives = representative_conformers(molecule)
    sulfur_index, terminal_carbon = terminal_indices(molecule)
    conformer_records = []
    for conformer_index, conformer in enumerate(molecule.conformers):
        length = float(
            np.linalg.norm(
                conformer.coordinates[sulfur_index] - conformer.coordinates[terminal_carbon]
            )
        )
        conformer_records.append(
            {
                "index": conformer_index,
                "sulfur_to_terminal_carbon_A": length,
                "representative_class": next(
                    (label for label, index in representatives.items() if index == conformer_index),
                    None,
                ),
            }
        )
    for label, conformer_index in representatives.items():
        write_sdf(molecule, conformer_index, output_dir / f"zil_{label}.sdf")

    total_charge = math.fsum(float(value) for value in charges)
    config_digest = sha256(config_path)
    charge_screen = summarize_atomic_charges(
        charges,
        expected_charge=float(config["molecular_charge_e"]),
        net_charge_tolerance=float(config["validation"]["net_charge_tolerance_e"]),
        max_abs_atomic_charge=float(config["validation"]["max_abs_atomic_charge_e"]),
    )
    charge_screen_passed = bool(charge_screen["passed_conservative_magnitude_screen"])
    metadata = {
        "status": (
            "resp_fit_complete_pending_review"
            if charge_screen_passed
            else "resp_fit_complete_rejected_unphysical_charges"
        ),
        "smiles": config["smiles"],
        "atom_count": len(charges),
        "conformer_count": len(molecule.conformers),
        "orientation_count": molecule.n_orientations,
        "total_resp_charge_e": total_charge,
        "charge_validation": charge_screen,
        "representative_terminal_atoms_zero_based": {
            "sulfur": sulfur_index,
            "terminal_carbon": terminal_carbon,
        },
        "conformers": conformer_records,
        "config": config,
        "config_sha256": config_digest,
        "software": {
            "psiresp": psiresp.__version__,
            "psi4": psi4.__version__,
            "rdkit": Chem.rdBase.rdkitVersion,
        },
        "large_working_directory": str(work_root),
        "outputs": {
            path.name: sha256(path)
            for path in sorted(output_dir.iterdir())
            if path.is_file() and path.name != "resp_metadata.json"
        },
    }
    (output_dir / "resp_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    write_qm_manifest(work_root, config_sha256=config_digest)
    if not charge_screen_passed:
        raise ValueError(
            "RESP fit was recorded but rejected: maximum absolute atomic charge "
            f"{charge_screen['maximum_absolute_atomic_charge_e']:.6f} e exceeds the "
            f"conservative {charge_screen['max_abs_atomic_charge_limit_e']:.6f} e screen"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    config_path = args.config.resolve()
    work_root = args.work_root.resolve()
    output_dir = args.output_dir.resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    config = load_config(config_path)
    threads = int(config["resources"]["threads"])
    job = build_job(config, work_root)
    charges = run_until_complete(
        job,
        threads=threads,
        memory=str(config["resources"]["memory"]),
        scratch=work_root / "psi4_scratch",
    )
    write_results(job, charges, config, config_path, work_root, output_dir)
    print(output_dir / "resp_metadata.json")


if __name__ == "__main__":
    main()
