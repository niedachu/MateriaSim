"""Native Packmol adapter with explicit PBC, seed, rigid-template and output checks."""

import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

from materiasim.storage import sha256, write_json
from materiasim.runtime.process import run_command


def packmol_info(candidate="packmol"):
    """Read the no-input banner and require native PBC plus the seekable -i interface; never pack on query."""
    executable = shutil.which(str(candidate))
    if executable is None:
        raise FileNotFoundError("Packmol not found; install it explicitly or provide --packmol")
    executable = str(Path(executable).resolve())
    # Packmol has no --version option; empty stdin prints the banner then reports no input.
    result = subprocess.run([executable], input="", capture_output=True, text=True, timeout=10)
    match = re.search(r"Version\s+(\d+)\.(\d+)\.(\d+)", result.stdout + result.stderr)
    if not match or tuple(map(int, match.groups())) < (21, 1, 0):
        raise ValueError("Packmol >=21.1.0 with orthorhombic PBC and -i input is required")
    if sys.platform not in ("darwin", "linux"):
        raise ValueError("Only native macOS/Linux packing is supported")
    return dict(executable=executable, version=".".join(match.groups()), sha256=sha256(executable), platform=sys.platform)


def pdb_template(atoms):
    """Encode a single template in Angstroms without inferring chemical elements or connectivity."""
    rows = []
    for index, atom in enumerate(atoms, 1):
        if len(atom["name"]) > 4 or len(atom["resname"]) > 3:
            raise ValueError("Packing PDB adapter requires <=4-character atom and <=3-character residue names")
        x, y, z = [value * 10 for value in atom["xyz_nm"]]
        rows.append(f"ATOM  {index:5d} {atom['name']:<4} {atom['resname']:>3} A   1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00")
    return "\n".join(rows) + "\nEND\n"


def ordered_instances(spec, models):
    """Expand stable group/molecule IDs in topology component order, retaining regional ownership."""
    instances = []
    for component in spec["components"]:
        ordinal = 0
        for group in spec["scenario"]["groups"]:
            if group["component_id"] != component["id"]:
                continue
            for local in range(1, group["count"] + 1):
                ordinal += 1
                instances.append(dict(component_id=component["id"], molecule_id=f"{component['id']}:{ordinal}",
                    group_id=group["id"], group_instance_id=f"{group['id']}:{local}",
                    template=models[component["id"]]["template"], min_nm=group["min_nm"], max_nm=group["max_nm"]))
    return instances


def read_packed(path, instances):
    """Validate Packmol PDB atom order and return GRO-rounded nm coordinates with stable identities."""
    rows = [line for line in path.read_text().splitlines() if line.startswith(("ATOM  ", "HETATM"))]
    if len(rows) != sum(len(item["template"]) for item in instances):
        raise ValueError("Packmol output atom/count mismatch")
    result, offset = [], 0
    for instance in instances:
        current = []
        for index, atom in enumerate(instance["template"], 1):
            row = rows[offset]
            if (row[12:16].strip(), row[17:20].strip()) != (atom["name"], atom["resname"]):
                raise ValueError("Packmol changed atom identity/order")
            xyz = [round(float(row[start:start + 8]) / 10, 3) for start in (30, 38, 46)]
            if any(not math.isfinite(value) or value < lo - .002 or value > hi + .002
                   for value, lo, hi in zip(xyz, instance["min_nm"], instance["max_nm"])):
                raise ValueError("Packmol coordinate outside declared region")
            current.append(xyz)
            result.append(dict(atom, xyz_nm=xyz, molecule_id=instance["molecule_id"],
                          group_id=instance["group_id"], group_instance_id=instance["group_instance_id"],
                          atom_uid=f"{instance['molecule_id']}:{index}"))
            offset += 1
        # Packmol is a rigid-template placer. Check all intramolecular distances after
        # 0.001 nm GRO rounding; this also catches accidental scaling or damaged ordering.
        original = [atom["xyz_nm"] for atom in instance["template"]]
        for i in range(len(current)):
            for j in range(i):
                if abs(math.dist(current[i], current[j]) - math.dist(original[i], original[j])) > .002:
                    raise ValueError("Packed molecule geometry differs from the rigid template")
    return result


def check_periodic_clashes(atoms, box, tolerance):
    """Reject inter-molecular periodic overlap; return the actual minimum distance in nm."""
    closest = math.inf
    for i, atom in enumerate(atoms):
        for other in atoms[:i]:
            if atom["molecule_id"] == other["molecule_id"]:
                continue
            delta = [abs(a - b) % length for a, b, length in zip(atom["xyz_nm"], other["xyz_nm"], box)]
            distance = math.sqrt(sum(min(value, length - value) ** 2 for value, length in zip(delta, box)))
            closest = min(closest, distance)
            if distance < tolerance - .002:
                raise ValueError("Packmol periodic inter-molecular clash; no automatic reseeding")
    return None if math.isinf(closest) else closest


def pack(spec, models, built, attempt, candidate):
    """Run a bounded fixed-seed packing attempt; return checked nm atoms and save packing evidence."""
    info = packmol_info(candidate)
    scenario = spec["scenario"]
    folder = built / "packing"
    folder.mkdir()
    box = scenario["box_nm"]
    text = ["filetype pdb", "output packed.pdb", "precision 0.000001", f"seed {scenario['seed']}",
            f"tolerance {scenario['tolerance_nm'] * 10}", f"nloop {scenario['max_iterations']}",
            "pbc " + " ".join(str(value * 10) for value in box)]
    for index, component in enumerate(spec["components"]):
        name = f"template_{index}.pdb"
        (folder / name).write_text(pdb_template(models[component["id"]]["template"]))
        for group in scenario["groups"]:
            if group["component_id"] == component["id"]:
                region = " ".join(str(value * 10) for value in group["min_nm"] + group["max_nm"])
                text.extend([f"structure {name}", f" number {group['count']}", f" inside box {region}", "end structure"])
    (folder / "packing.inp").write_text("\n".join(text) + "\n")
    write_json(folder / "tool.json", dict(tool=info, timeout_seconds=60, geometry_tolerance_nm=.002))
    # Packmol rereads its input: a PIPE cannot be rewound. The >=21.1 -i interface
    # opens our frozen regular file, avoiding shell redirection and illegal seek.
    outcome = run_command(info, ["-i", "packing.inp"], folder, attempt / "packmol", seconds=60)
    if outcome["interrupted"] or "Success!" not in (attempt / "packmol/stdout.log").read_text():
        raise ValueError("Packmol did not converge; preserve failed output and revise explicitly")
    atoms = read_packed(folder / "packed.pdb", ordered_instances(spec, models))
    closest = check_periodic_clashes(atoms, box, scenario["tolerance_nm"])
    write_json(folder / "mapping.json", dict(atoms=atoms, minimum_intermolecular_distance_nm=closest,
               group_counts={group["id"]: group["count"] for group in scenario["groups"]}))
    return atoms
