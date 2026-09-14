#!/usr/bin/env python3
"""Validate charge and atom-order invariants in MOL2 and GROMACS ITP files."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable


def summarize_atomic_charges(
    charges: Iterable[float],
    expected_charge: float,
    net_charge_tolerance: float,
    max_abs_atomic_charge: float,
) -> dict[str, float | int | bool]:
    """Apply a conservative sanity screen without claiming force-field validity."""
    values = [float(value) for value in charges]
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("atomic charges are empty or contain non-finite values")
    if net_charge_tolerance <= 0 or max_abs_atomic_charge <= 0:
        raise ValueError("charge validation tolerances must be positive")
    total = math.fsum(values)
    if abs(total - expected_charge) > net_charge_tolerance:
        raise ValueError(
            f"total charge {total:.8f} differs from expected {expected_charge:.8f} "
            f"by more than {net_charge_tolerance}"
        )
    maximum_absolute = max(abs(value) for value in values)
    return {
        "minimum_atomic_charge_e": min(values),
        "maximum_atomic_charge_e": max(values),
        "maximum_absolute_atomic_charge_e": maximum_absolute,
        "rms_atomic_charge_e": math.sqrt(math.fsum(value * value for value in values) / len(values)),
        "atoms_exceeding_absolute_limit": sum(
            abs(value) > max_abs_atomic_charge for value in values
        ),
        "max_abs_atomic_charge_limit_e": max_abs_atomic_charge,
        "passed_conservative_magnitude_screen": maximum_absolute <= max_abs_atomic_charge,
    }


def parse_mol2_atoms(path: Path) -> list[dict[str, str | float | int]]:
    atoms: list[dict[str, str | float | int]] = []
    in_atoms = False
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if stripped == "@<TRIPOS>ATOM":
            in_atoms = True
            continue
        if stripped.startswith("@<TRIPOS>") and in_atoms:
            break
        if not in_atoms or not stripped:
            continue
        fields = stripped.split()
        if len(fields) < 9:
            raise ValueError(f"invalid MOL2 atom line {line_number}: {raw_line}")
        atoms.append(
            {
                "index": int(fields[0]),
                "name": fields[1],
                "atom_type": fields[5],
                "charge": float(fields[8]),
            }
        )
    if not atoms:
        raise ValueError(f"no MOL2 atoms found in {path}")
    return atoms


def parse_itp_atoms(path: Path) -> list[dict[str, str | float | int]]:
    atoms: list[dict[str, str | float | int]] = []
    section = ""
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[] ").lower()
            continue
        if section != "atoms" or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 7:
            raise ValueError(f"invalid ITP atom line {line_number}: {raw_line}")
        atoms.append(
            {
                "index": int(fields[0]),
                "atom_type": fields[1],
                "residue": fields[3],
                "name": fields[4],
                "charge": float(fields[6]),
            }
        )
    if not atoms:
        raise ValueError(f"no ITP atoms found in {path}")
    return atoms


def validate_atom_table(atoms: list[dict[str, str | float | int]], expected_charge: float, tolerance: float) -> dict:
    indices = [int(atom["index"]) for atom in atoms]
    if indices != list(range(1, len(atoms) + 1)):
        raise ValueError("atom indices must be contiguous and one-based")
    if any(not str(atom["name"]).strip() for atom in atoms):
        raise ValueError("empty atom name found")
    if any(not str(atom["atom_type"]).strip() for atom in atoms):
        raise ValueError("empty atom type found")
    charge = math.fsum(float(atom["charge"]) for atom in atoms)
    if abs(charge - expected_charge) > tolerance:
        raise ValueError(
            f"total charge {charge:.8f} differs from expected {expected_charge:.8f} by more than {tolerance}"
        )
    return {"atom_count": len(atoms), "total_charge_e": charge}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mol2", type=Path, required=True)
    parser.add_argument("--itp", type=Path)
    parser.add_argument("--expected-charge", type=float, default=0.0)
    parser.add_argument("--tolerance", type=float, default=1e-4)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.tolerance <= 0:
        raise ValueError("tolerance must be positive")

    mol2_atoms = parse_mol2_atoms(args.mol2)
    report = {"mol2": validate_atom_table(mol2_atoms, args.expected_charge, args.tolerance)}
    if args.itp is not None:
        itp_atoms = parse_itp_atoms(args.itp)
        report["itp"] = validate_atom_table(itp_atoms, args.expected_charge, args.tolerance)
        mol2_names = [str(atom["name"]) for atom in mol2_atoms]
        itp_names = [str(atom["name"]) for atom in itp_atoms]
        if mol2_names != itp_names:
            raise ValueError("MOL2 and ITP atom names/order do not match")
        report["mol2_itp_atom_order_match"] = True

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
