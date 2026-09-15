"""Check GRO ordering against GROMACS-preprocessed molecule definitions."""

import math
import re
from pathlib import Path


def gro_atoms(path):
    """Read atom names and nm coordinates from a standard fixed-width GRO file."""
    lines = Path(path).read_text().splitlines()
    count = int(lines[1])
    if count < 1 or len(lines) != count + 3:
        raise ValueError(f"Invalid GRO atom count: {path}")
    atoms = []
    for row in lines[2:-1]:
        xyz = [float(row[start:start + 8]) for start in (20, 28, 36)]
        if not all(math.isfinite(value) for value in xyz):
            raise ValueError("Non-finite coordinate")
        atoms.append({"resname": row[5:10].strip(), "name": row[10:15].strip(), "xyz_nm": xyz})
    return atoms, [float(value) for value in lines[-1].split()]


def section_rows(path):
    """Yield section and tokens from data rows, ignoring comments/directives."""
    section = None
    for raw in Path(path).read_text().splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        header = re.fullmatch(r"\[\s*(\w+)\s*\]", line)
        if header:
            section = header.group(1)
        else:
            yield section, line.split()


def molecule_counts(path):
    """Return the explicit ordered [molecules] counts, rejecting duplicates."""
    result = {}
    for section, row in section_rows(path):
        if section != "molecules":
            continue
        if len(row) != 2 or row[0] in result or int(row[1]) < 1:
            raise ValueError("Invalid or duplicate molecule count")
        result[row[0]] = int(row[1])
    if not result:
        raise ValueError("No explicit molecules in topology")
    return result


def atom_mapping(processed_topology, coordinates, initial_counts, require_solvent=True):
    """Expand explicit atoms, verify ordering/neutrality, and enforce the declared water policy."""
    types = {}
    molecule = None
    for section, row in section_rows(processed_topology):
        if section == "moleculetype":
            molecule = row[0]
            if molecule in types:
                raise ValueError(f"Duplicate molecule type: {molecule}")
            types[molecule] = []
        elif section == "atoms":
            if molecule is None or len(row) < 8:
                raise ValueError("Explicit per-atom charge and mass required")
            mass, charge = float(row[7]), float(row[6])
            if mass <= 0 or not math.isfinite(mass) or not math.isfinite(charge):
                raise ValueError("Invalid atom mass/charge")
            if int(row[0]) != len(types[molecule]) + 1:
                raise ValueError("Nonsequential atom numbers")
            types[molecule].append({"resname": row[3], "name": row[4], "residue_index": int(row[2]),
                                    "charge_e": charge, "mass_u": mass})
    counts = molecule_counts(processed_topology)
    if {key: value for key, value in counts.items() if key != "SOL"} != initial_counts:
        raise ValueError("Built solute counts differ from model card")
    if require_solvent and counts.get("SOL", 0) < 1:
        raise ValueError("No solvent was added")
    if not require_solvent and "SOL" in counts:
        raise ValueError("Unexpected water in a dry scenario")
    mapping = []
    for name, count in counts.items():
        if name not in types or not types[name]:
            raise ValueError(f"No atoms for molecule {name}")
        for instance in range(count):
            for index, atom in enumerate(types[name]):
                mapping.append(dict(atom, component_id=name, molecule_id=f"{name}:{instance + 1}",
                                    atom_uid=f"{name}:{instance + 1}:{index + 1}",
                                    engine_atom_index=len(mapping) + 1))
    coordinates_atoms, box = gro_atoms(coordinates)
    if len(mapping) != len(coordinates_atoms):
        raise ValueError("Coordinate/topology atom count mismatch")
    for expected, actual in zip(mapping, coordinates_atoms):
        if expected["name"][:5] != actual["name"] or expected["resname"][:5] != actual["resname"]:
            raise ValueError(f"Coordinate/topology order mismatch at {expected['engine_atom_index']}")
    if len(box) != 3 or not all(math.isfinite(value) and value > 0 for value in box):
        raise ValueError("v1 requires a finite orthorhombic box")
    charge = sum(atom["charge_e"] for atom in mapping)
    if abs(charge) > 0.001:
        raise ValueError(f"Non-neutral box ({charge} e); explicit ions required")
    return {"atoms": mapping, "counts": counts, "atom_count": len(mapping),
            "charge_e": charge, "box_nm": box}
