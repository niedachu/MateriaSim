"""Audited explicit-GAFF parameter merging and GROMACS topology assembly."""

import math
import re

from materiasim.storage import sha256, write_json
from materiasim.engines.gromacs.prebuilt import molecular_definitions
from materiasim.specs.composition import declared_counts
from materiasim.engines.gromacs.topology import gro_atoms, section_rows


def explicit_rows(path):
    """Reject preprocessor features in user molecular assets instead of guessing macro meaning."""
    for raw in path.read_text().splitlines():
        line = raw.split(";", 1)[0].strip()
        if line.startswith("#"):
            raise ValueError(f"Packing molecular assets must be explicit, without macros/includes: {path.name}")
        if line.startswith("[") and not re.fullmatch(r"\[\s*\w+\s*\]", line):
            raise ValueError("Invalid topology section")
    return list(section_rows(path))


def merge_types(table, rows):
    """Merge complete seven-field atom types, rejecting conflicts and unsupported global sections."""
    for section, row in rows:
        if section != "atomtypes" or len(row) != 7:
            raise ValueError("Only explicit seven-field atomtypes are accepted as global assets")
        if row[4] != "A" or any(not math.isfinite(float(row[i])) for i in (1, 2, 3, 5, 6)):
            raise ValueError("Invalid explicit atom type")
        if float(row[2]) <= 0 or float(row[5]) <= 0 or float(row[6]) < 0:
            raise ValueError("Nonphysical atom mass or Lennard-Jones parameter")
        if row[0] in table and table[row[0]] != row:
            raise ValueError(f"Conflicting atom type: {row[0]}")
        table[row[0]] = row


def collect_models(spec, sources):
    """Return exact molecule blocks/templates and a conflict-free shared type table; no parameter fitting."""
    table, models, total_atoms, charge = {}, {}, 0, 0.0
    for asset in spec["interaction_bundle"]["files"]:
        merge_types(table, explicit_rows(sources[asset["name"]]))
    supported = {"moleculetype", "atoms", "bonds", "pairs", "angles", "dihedrals"}
    for component in spec["components"]:
        model, name = component["model"], component["id"]
        path = sources[model["topology"]]
        rows = explicit_rows(path)
        merge_types(table, [(section, row) for section, row in rows if section == "atomtypes"])
        molecular = [(section, row) for section, row in rows if section != "atomtypes"]
        if any(section not in supported for section, _ in molecular):
            raise ValueError("Unsupported molecular interaction section")
        if set(molecular_definitions(path)) != {name}:
            raise ValueError("Packing model must define exactly its declared molecule")
        atoms = [row for section, row in molecular if section == "atoms"]
        template, _ = gro_atoms(sources[model["coordinates"]])
        if any(len(row) != 8 for row in atoms) or [(a[3], a[4]) for a in atoms] != [(a["resname"], a["name"]) for a in template]:
            raise ValueError("Standalone coordinate/explicit atom identity mismatch")
        validate_molecular_terms(molecular, len(atoms))
        if not {row[1] for row in atoms}.issubset(table):
            raise ValueError("Missing nonbonded atom types")
        total_atoms += len(atoms) * component["count"]
        charge += sum(float(row[6]) for row in atoms) * component["count"]
        models[name] = dict(rows=molecular, template=template, source_sha256=sha256(path))
    if total_atoms > 2000 or abs(charge) > 0.001:
        raise ValueError("Packing requires <=2000 solute atoms and neutral explicit composition")
    return table, models


def validate_molecular_terms(rows, atom_count):
    """Require existing GAFF explicit bonded forms and connected finite-mass single-molecule templates."""
    bonds, neighbors = [], {index: set() for index in range(1, atom_count + 1)}
    shapes = {"bonds": (2, 5, {"1"}), "pairs": (2, 3, {"1"}),
              "angles": (3, 6, {"1"}), "dihedrals": (4, 8, {"1", "4"})}
    atom_indices = []
    for section, row in rows:
        if section == "moleculetype":
            if len(row) != 2 or row[1] != "3":
                raise ValueError("Packed GAFF molecules require nrexcl=3")
        elif section == "atoms":
            atom_indices.append(int(row[0]))
            if not math.isfinite(float(row[6])) or not math.isfinite(float(row[7])) or float(row[7]) <= 0:
                raise ValueError("Invalid explicit charge/mass")
        else:
            arity, length, functions = shapes[section]
            if len(row) != length or row[arity] not in functions:
                raise ValueError("Unsupported or implicit bonded parameters")
            indices = list(map(int, row[:arity]))
            if any(index not in neighbors for index in indices) or len(set(indices)) != len(indices):
                raise ValueError("Invalid bonded atom indices")
            if any(not math.isfinite(float(value)) for value in row[arity + 1:]):
                raise ValueError("Nonfinite bonded parameter")
            if section == "bonds":
                bonds.append(indices)
    if atom_indices != list(neighbors):
        raise ValueError("Nonsequential explicit atom indices")
    for a, b in bonds:
        neighbors[a].add(b)
        neighbors[b].add(a)
    visited, pending = set(), [1]
    while pending:
        index = pending.pop()
        if index not in visited:
            visited.add(index)
            pending.extend(neighbors[index] - visited)
    if len(visited) != atom_count:
        raise ValueError("Packing template contains disconnected molecular fragments")


def render_rows(rows):
    """Serialize ordered explicit section data, retaining repeated dihedral blocks and numeric tokens."""
    lines, previous = [], None
    for section, row in rows:
        if section != previous:
            lines.append(f"\n[ {section} ]")
            previous = section
        lines.append(" ".join(row))
    return "\n".join(lines) + "\n"


def write_topology(spec, sources, inputs, built):
    """Create one defaults/include order and audited derived ITPs without modifying frozen originals."""
    table, models = collect_models(spec, sources)
    force_field = spec["interaction_bundle"]["force_field"]
    defaults = [row for section, row in section_rows(inputs / force_field / "forcefield.itp") if section == "defaults"]
    if defaults != [["1", "2", "yes", "0.5", "0.83333333333333333"]]:
        raise ValueError("Packed GAFF route requires the frozen AMBER defaults")
    library_types = {row[0]: row for section, row in section_rows(inputs / force_field / "ffnonbonded.itp") if section == "atomtypes"}
    for name, row in table.items():
        if name in library_types and library_types[name] != row:
            raise ValueError(f"Atom type conflicts with frozen library: {name}")
    (built / "shared_types.itp").write_text(render_rows([("atomtypes", row) for name, row in table.items() if name not in library_types]))
    lines = [f'#include "{force_field}/forcefield.itp"', '#include "shared_types.itp"']
    provenance = {}
    for index, component in enumerate(spec["components"]):
        model = models[component["id"]]
        name = f"molecule_{index}.itp"
        (built / name).write_text(render_rows(model["rows"]))
        lines.append(f'#include "{name}"')
        provenance[component["id"]] = dict(source_sha256=model["source_sha256"], derived_file=name,
                                           derived_sha256=sha256(built / name))
    if spec["scenario"]["solvent"]["kind"] == "tip3p_fill":
        lines.append(f'#include "{force_field}/tip3p.itp"')
    lines.extend(["\n[ system ]", "Explicit packed molecular engineering box", "\n[ molecules ]"])
    lines.extend(f"{name} {count}" for name, count in declared_counts(spec).items())
    (built / "system.top").write_text("\n".join(lines) + "\n")
    write_json(built / "parameter_assembly.json", dict(defaults=defaults, atomtypes=table,
               molecules=provenance, policy="exact shared types; unchanged molecular tokens; no parameter fitting"))
    return models
