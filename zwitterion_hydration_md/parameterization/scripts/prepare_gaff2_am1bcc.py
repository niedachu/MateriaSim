#!/usr/bin/env python3
"""Generate a staged GAFF2/AM1-BCC topology without touching formal inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil

import parmed as pmd

try:
    from .prepare_gaff2 import (
        mol2_elements,
        read_sdf,
        run_command,
        split_parmed_topology,
        write_gro_from_sdf,
        write_system_topology,
    )
    from .validate_parameters import (
        parse_itp_atoms,
        parse_mol2_atoms,
        summarize_atomic_charges,
        validate_atom_table,
    )
except ImportError:  # Direct script execution from this directory.
    from prepare_gaff2 import (
        mol2_elements,
        read_sdf,
        run_command,
        split_parmed_topology,
        write_gro_from_sdf,
        write_system_topology,
    )
    from validate_parameters import (
        parse_itp_atoms,
        parse_mol2_atoms,
        summarize_atomic_charges,
        validate_atom_table,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def neutralize_mol2(input_path: Path, output_path: Path) -> dict[str, float]:
    """Remove small AM1-BCC serialization residuals without changing relative charges."""
    structure = pmd.load_file(str(input_path))
    original_total = math.fsum(float(atom.charge) for atom in structure.atoms)
    if abs(original_total) > 0.01:
        raise ValueError(
            f"AM1-BCC total charge residual is too large for numerical normalization: "
            f"{original_total:.8f} e"
        )
    correction = -original_total / len(structure.atoms)
    for atom in structure.atoms:
        atom.charge = float(atom.charge) + correction
    structure.save(str(output_path), format="mol2", overwrite=True)

    reread = pmd.load_file(str(output_path))
    final_total = math.fsum(float(atom.charge) for atom in reread.atoms)
    if abs(final_total) > 1e-4:
        raise ValueError(
            f"neutralized MOL2 remains outside charge tolerance: {final_total:.8f} e"
        )
    return {
        "original_total_charge_e": original_total,
        "uniform_correction_per_atom_e": correction,
        "serialized_total_charge_e": final_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-sdf", type=Path, required=True)
    parser.add_argument("--conformer-dir", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--topology-dir", type=Path, required=True)
    args = parser.parse_args()

    input_sdf = args.input_sdf.resolve()
    conformer_dir = args.conformer_dir.resolve()
    work_root = args.work_root.resolve()
    artifact_dir = args.artifact_dir.resolve()
    topology_dir = args.topology_dir.resolve()
    for directory in (work_root, artifact_dir, topology_dir):
        directory.mkdir(parents=True, exist_ok=True)

    sdf_elements, _ = read_sdf(input_sdf)
    raw_mol2 = work_root / "zil_am1bcc_raw.mol2"
    run_command(
        [
            "antechamber", "-i", str(input_sdf), "-fi", "mdl",
            "-o", str(raw_mol2), "-fo", "mol2", "-at", "gaff2",
            "-c", "bcc", "-nc", "0", "-m", "1", "-rn", "ZIL",
            "-eq", "1", "-seq", "n", "-pf", "y", "-s", "2",
        ],
        cwd=work_root,
        log_path=work_root / "antechamber.log",
    )
    if mol2_elements(raw_mol2) != sdf_elements:
        raise ValueError("Antechamber changed atom order relative to the input SDF")

    neutral_mol2 = work_root / "zil_am1bcc.mol2"
    neutralization = neutralize_mol2(raw_mol2, neutral_mol2)
    mol2_atoms = parse_mol2_atoms(neutral_mol2)
    validate_atom_table(mol2_atoms, expected_charge=0.0, tolerance=1e-4)
    charge_screen = summarize_atomic_charges(
        [float(atom["charge"]) for atom in mol2_atoms],
        expected_charge=0.0,
        net_charge_tolerance=1e-4,
        max_abs_atomic_charge=2.0,
    )
    if charge_screen["passed_conservative_magnitude_screen"] is not True:
        raise ValueError("AM1-BCC atomic-charge magnitude screen did not pass")

    sulfonate_oxygen_charges = [
        float(mol2_atoms[index]["charge"]) for index in (0, 17, 18)
    ]
    if max(sulfonate_oxygen_charges) - min(sulfonate_oxygen_charges) > 2e-6:
        raise ValueError("the three sulfonate oxygen charges are not equivalent")

    frcmod = work_root / "zil.frcmod"
    run_command(
        ["parmchk2", "-i", str(neutral_mol2), "-f", "mol2", "-o", str(frcmod), "-s", "gaff2"],
        cwd=work_root,
        log_path=work_root / "parmchk2.log",
    )
    attention_lines = [
        line.strip()
        for line in frcmod.read_text(encoding="utf-8").splitlines()
        if "ATTN" in line.upper() or "USING THE DEFAULT VALUE" in line.upper()
    ]

    tleap_input = work_root / "tleap.in"
    tleap_input.write_text(
        "source leaprc.gaff2\n"
        "ZIL = loadmol2 zil_am1bcc.mol2\n"
        "loadamberparams zil.frcmod\n"
        "check ZIL\n"
        "saveamberparm ZIL zil.prmtop zil.inpcrd\n"
        "savepdb ZIL zil.pdb\n"
        "quit\n",
        encoding="utf-8",
    )
    run_command(
        ["tleap", "-f", tleap_input.name],
        cwd=work_root,
        log_path=work_root / "tleap.stdout.log",
    )

    prmtop = work_root / "zil.prmtop"
    inpcrd = work_root / "zil.inpcrd"
    structure = pmd.load_file(str(prmtop), xyz=str(inpcrd))
    amber_charge = math.fsum(float(atom.charge) for atom in structure.atoms)
    if abs(amber_charge) > 1e-4:
        raise ValueError(f"Amber topology is not net neutral: {amber_charge:.8f} e")
    full_topology = work_root / "zil_full.top"
    structure.save(str(full_topology), format="gromacs", overwrite=True)
    split_parmed_topology(full_topology, topology_dir / "zil.itp")
    write_system_topology(topology_dir / "system.top")

    for label in ("folded", "intermediate", "extended"):
        write_gro_from_sdf(
            prmtop,
            conformer_dir / f"zil_{label}.sdf",
            topology_dir / f"zil_{label}.gro",
        )

    itp_atoms = parse_itp_atoms(topology_dir / "zil.itp")
    validate_atom_table(itp_atoms, expected_charge=0.0, tolerance=1e-4)
    if [atom["name"] for atom in mol2_atoms] != [atom["name"] for atom in itp_atoms]:
        raise ValueError("MOL2 and GROMACS ITP atom names/order differ")

    tracked_work_files = [
        neutral_mol2,
        frcmod,
        prmtop,
        inpcrd,
        work_root / "antechamber.log",
        work_root / "parmchk2.log",
        work_root / "tleap.stdout.log",
        work_root / "leap.log",
    ]
    for source in tracked_work_files:
        if source.is_file():
            shutil.copy2(source, artifact_dir / source.name)

    tracked_outputs = [
        artifact_dir / "zil_am1bcc.mol2",
        artifact_dir / "zil.frcmod",
        artifact_dir / "zil.prmtop",
        artifact_dir / "zil.inpcrd",
        topology_dir / "zil.itp",
        topology_dir / "system.top",
        *(topology_dir / f"zil_{label}.gro" for label in ("folded", "intermediate", "extended")),
    ]
    metadata = {
        "status": "am1bcc_dry_run_complete_pending_smoke_and_parameter_review",
        "charge_model": "AM1-BCC as implemented by AmberTools antechamber",
        "force_field": "GAFF2",
        "input_sdf_sha256": sha256(input_sdf),
        "atom_count": len(mol2_atoms),
        "neutralization": neutralization,
        "charge_validation": charge_screen,
        "sulfonate_oxygen_charges_e": sulfonate_oxygen_charges,
        "amber_total_charge_e": amber_charge,
        "parmchk2_attention_lines": attention_lines,
        "requires_manual_frcmod_review": bool(attention_lines),
        "software": {"ambertools": "24.8", "parmed": pmd.__version__},
        "outputs": {str(path): sha256(path) for path in tracked_outputs},
    }
    metadata_path = artifact_dir / "am1bcc_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(metadata_path)


if __name__ == "__main__":
    main()
