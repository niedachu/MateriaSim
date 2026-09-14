#!/usr/bin/env python3
"""Parameterize one charged molecule with GAFF2 + AM1-BCC and export GROMACS files."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

import parmed as pmd


SECTION = re.compile(r"^\s*\[\s*([^]]+)\s*\]")


def run(command: list[str], cwd: Path, log: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}; see {log}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atom_charges(path: Path) -> list[float]:
    structure = pmd.load_file(str(path))
    return [float(atom.charge) for atom in structure.atoms]


def normalize_total_charge(source: Path, destination: Path, expected_charge: float) -> dict[str, float]:
    structure = pmd.load_file(str(source))
    original = math.fsum(float(atom.charge) for atom in structure.atoms)
    residual = expected_charge - original
    if abs(residual) > 0.01:
        raise ValueError(f"AM1-BCC charge residual is too large to normalize: {original:.8f} e")
    correction = residual / len(structure.atoms)
    for atom in structure.atoms:
        atom.charge = float(atom.charge) + correction
    structure.save(str(destination), format="mol2", overwrite=True)
    final = math.fsum(atom_charges(destination))
    if abs(final - expected_charge) > 1e-4:
        raise ValueError(f"serialized charge is {final:.8f} e, expected {expected_charge:.8f} e")
    return {"raw_total_charge_e": original, "uniform_correction_e": correction, "serialized_total_charge_e": final}


def sections(lines: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for index, line in enumerate(lines):
        match = SECTION.match(line)
        if match:
            found.setdefault(match.group(1).strip().lower(), index)
    return found


def extract_gromacs_parts(full_topology: Path, itp_path: Path, atomtypes_path: Path) -> None:
    lines = full_topology.read_text(encoding="utf-8").splitlines()
    found = sections(lines)
    required = {"atomtypes", "moleculetype", "system"}
    missing = required - found.keys()
    if missing:
        raise ValueError(f"GROMACS export lacks sections: {sorted(missing)}")
    atomtypes_path.write_text(
        "; GAFF2 atom types exported by ParmEd\n\n" + "\n".join(lines[found["atomtypes"] : found["moleculetype"]]).rstrip() + "\n",
        encoding="utf-8",
    )
    itp_path.write_text(
        "; GAFF2 molecule parameters exported by ParmEd\n\n" + "\n".join(lines[found["moleculetype"] : found["system"]]).rstrip() + "\n",
        encoding="utf-8",
    )


def parse_itp_charge(path: Path) -> tuple[int, float]:
    in_atoms = False
    count, total = 0, 0.0
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = SECTION.match(raw)
        if match:
            in_atoms = match.group(1).strip().lower() == "atoms"
            continue
        line = raw.split(";", 1)[0].strip()
        if in_atoms and line:
            fields = line.split()
            if len(fields) >= 7:
                count += 1
                total += float(fields[6])
    return count, total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-sdf", type=Path, required=True)
    parser.add_argument("--resname", required=True)
    parser.add_argument("--charge", type=float, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if len(args.resname) > 5:
        raise ValueError("GROMACS residue name must be at most five characters")
    work = args.work_dir.resolve()
    output = args.output_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    raw_mol2 = work / f"{args.prefix}_raw.mol2"
    run([
        "antechamber", "-i", str(args.input_sdf.resolve()), "-fi", "mdl", "-o", str(raw_mol2), "-fo", "mol2",
        "-at", "gaff2", "-c", "bcc", "-nc", str(int(args.charge)), "-m", "1", "-rn", args.resname,
        "-eq", "1", "-seq", "n", "-pf", "y", "-s", "2",
    ], work, work / "antechamber.log")
    mol2 = work / f"{args.prefix}_am1bcc.mol2"
    charge_record = normalize_total_charge(raw_mol2, mol2, args.charge)
    charges = atom_charges(mol2)
    if max(abs(value) for value in charges) > 2.0:
        raise ValueError("conservative atomic-charge magnitude screen failed")
    frcmod = work / f"{args.prefix}.frcmod"
    run(["parmchk2", "-i", str(mol2), "-f", "mol2", "-o", str(frcmod), "-s", "gaff2"], work, work / "parmchk2.log")
    leap = work / "tleap.in"
    leap.write_text(
        "source leaprc.gaff2\n"
        f"{args.resname} = loadmol2 {mol2.name}\n"
        f"loadamberparams {frcmod.name}\n"
        f"check {args.resname}\n"
        f"saveamberparm {args.resname} {args.prefix}.prmtop {args.prefix}.inpcrd\n"
        f"quit\n",
        encoding="utf-8",
    )
    run(["tleap", "-f", leap.name], work, work / "tleap.log")
    prmtop, inpcrd = work / f"{args.prefix}.prmtop", work / f"{args.prefix}.inpcrd"
    structure = pmd.load_file(str(prmtop), xyz=str(inpcrd))
    amber_charge = math.fsum(float(atom.charge) for atom in structure.atoms)
    if abs(amber_charge - args.charge) > 1e-4:
        raise ValueError(f"Amber topology charge {amber_charge:.8f} differs from expected {args.charge:.8f}")
    full_topology = work / f"{args.prefix}_full.top"
    structure.save(str(full_topology), format="gromacs", overwrite=True)
    itp, atomtypes, gro = output / f"{args.prefix}.itp", output / f"{args.prefix}_atomtypes.itp", output / f"{args.prefix}.gro"
    extract_gromacs_parts(full_topology, itp, atomtypes)
    structure.save(str(gro), format="gro", overwrite=True)
    itp_count, itp_charge = parse_itp_charge(itp)
    if itp_count != len(structure.atoms) or abs(itp_charge - args.charge) > 1e-4:
        raise ValueError("GROMACS ITP atom count or charge validation failed")
    attention = [line.strip() for line in frcmod.read_text(encoding="utf-8").splitlines() if "ATTN" in line.upper() or "DEFAULT" in line.upper()]
    copied = []
    for path in (mol2, frcmod, prmtop, inpcrd, work / "antechamber.log", work / "parmchk2.log", work / "tleap.log", work / "leap.log"):
        if path.is_file():
            destination = output / path.name
            shutil.copy2(path, destination)
            copied.append(destination)
    metadata = {
        "status": "complete_pending_pair_assembly_and_cross_engine_validation",
        "resname": args.resname,
        "expected_charge_e": args.charge,
        "atom_count": len(structure.atoms),
        "charge_record": charge_record,
        "amber_total_charge_e": amber_charge,
        "gromacs_itp_total_charge_e": itp_charge,
        "max_abs_atomic_charge_e": max(abs(value) for value in charges),
        "parmchk2_attention_lines": attention,
        "outputs_sha256": {path.name: sha256(path) for path in (itp, atomtypes, gro, *copied)},
    }
    (output / f"{args.prefix}_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
