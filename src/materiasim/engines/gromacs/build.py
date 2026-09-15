"""GROMACS prebuilt-solute water-box construction and frozen-library handling."""

import re
import shutil
from pathlib import Path

from materiasim.storage import content_hash, inventory, sha256, write_json
from materiasim.engines.gromacs.command import command
from materiasim.engines.gromacs.stage import compile_stage
from materiasim.engines.gromacs.mdp import derive_mdp
from materiasim.specs.composition import declared_counts
from materiasim.engines.gromacs.prebuilt import structure_assets, validate_prebuilt_sources, verify_processed_models
from materiasim.engines.gromacs.topology import atom_mapping, gro_atoms, molecule_counts

LIBRARY_FILES = ("spc216.gro", "vdwradii.dat", "atommass.dat", "residuetypes.dat")


def check_includes(inputs):
    """Reject external topology dependencies, including unused conditional includes."""
    for path in [*inputs.glob("*.top"), *inputs.rglob("*.itp")]:
        for raw in path.read_text().splitlines():
            line = raw.split(";", 1)[0].strip()
            if not re.match(r"#\s*include\b", line):
                continue
            match = re.fullmatch(r'#\s*include\s+["<]([^">]+)[">]', line)
            if not match:
                raise ValueError(f"Unsupported include expression: {path}")
            relative = Path(match.group(1))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"External include forbidden: {relative}")
            candidates = [path.parent / relative, inputs / relative]
            if not any(candidate.is_file() and not candidate.is_symlink() for candidate in candidates):
                raise ValueError(f"Include is not frozen: {relative}")


def library_identity(library, force_field):
    """Hash the exact force-field tree and auxiliary water/atom library used by this builder."""
    hashes = inventory(library, [force_field])
    for name in LIBRARY_FILES:
        hashes[name] = sha256(library / name)
    return content_hash(hashes)


def snapshot(root, spec, sources, engine):
    """Freeze all component models, structure, protocol and the exact interaction library."""
    bundle = spec["interaction_bundle"]
    inputs = root / "inputs"
    inputs.mkdir()
    for name, source in sources.items():
        shutil.copyfile(source, inputs / name)
    library = Path(engine["data_prefix"]) / "share/gromacs/top"
    force_field = bundle["force_field"]
    if library_identity(library, force_field) != bundle["library_hash"]:
        raise ValueError("Installed interaction library differs from the declared bundle")
    shutil.copytree(library / force_field, inputs / force_field)
    for name in LIBRARY_FILES:
        if name in sources:
            raise ValueError(f"Asset collides with engine library: {name}")
        shutil.copyfile(library / name, inputs / name)
    if library_identity(inputs, force_field) != bundle["library_hash"]:
        raise ValueError("Interaction library changed during snapshot")
    assets = [asset for component in spec["components"] for asset in component["model"]["files"]]
    assets.extend(spec["protocol"]["files"])
    if spec["scenario"]["kind"] == "prebuilt_mixture_water":
        assets.extend(spec["scenario"]["structure"]["files"])
    if "files" in bundle:
        assets.extend(bundle["files"])
    for asset in assets:
        if sha256(inputs / asset["name"]) != asset["sha256"]:
            raise ValueError("Source changed during snapshot")
    check_includes(inputs)
    built = root / "build"
    built.mkdir()
    if spec["scenario"]["kind"] == "packed_liquid":
        from materiasim.engines.gromacs.parameters import write_topology
        write_topology(spec, {name: inputs / name for name in sources}, inputs, built)
        derive_protocol(spec, inputs, built)
        return
    topology = inputs / structure_assets(spec)["topology"]
    water_include = f'#include "{force_field}/tip3p.itp"'
    if water_include not in [line.split(";")[0].strip() for line in topology.read_text().splitlines()]:
        raise ValueError("Topology does not explicitly include the declared TIP3P model")
    if molecule_counts(topology) != declared_counts(spec):
        raise ValueError("Prebuilt topology composition differs from the experiment; assembly is not implemented")
    if spec["scenario"]["kind"] == "prebuilt_mixture_water":
        validate_prebuilt_sources(spec, {name: inputs / name for name in sources})
    shutil.copyfile(topology, built / "system.top")
    derive_protocol(spec, inputs, built)


def derive_protocol(spec, inputs, built):
    """Derive and record the same explicit bounded protocol for prebuilt and packed scenarios."""
    changes = {stage["id"]: derive_mdp(inputs / stage["mdp"], built / f"{stage['id']}.mdp", stage)
               for stage in spec["protocol"]["stages"]}
    write_json(built / "protocol_overrides.json", changes)


def prepare_system(root, spec, sources, engine, attempt, packmol_candidate="packmol"):
    """Prepare the declared fixed/packed scenario and return its validated atom mapping."""
    if spec["scenario"]["kind"] == "packed_liquid":
        from materiasim.engines.gromacs.packed import prepare_packed
        return prepare_packed(root, spec, sources, engine, attempt, packmol_candidate)
    snapshot(root, spec, sources, engine)
    inputs, built = root / "inputs", root / "build"
    box_nm = spec["scenario"]["box_nm"]
    coordinates = inputs / structure_assets(spec)["coordinates"]
    mixture = spec["scenario"]["kind"] == "prebuilt_mixture_water"
    if mixture:
        # The accepted dry mixture already defines its placement and box; do not recenter it.
        shutil.copyfile(coordinates, built / "boxed.gro")
    else:
        command(engine, ["editconf", "-f", coordinates, "-o", built / "boxed.gro", "-c", "-box", *box_nm],
                inputs, attempt / "editconf", inputs)
    solvent_args = ["-maxsol", spec["scenario"]["solvent_count"]] if mixture else []
    command(engine, ["solvate", "-cp", built / "boxed.gro", "-cs", inputs / "spc216.gro",
                     "-o", built / "solvated.gro", "-p", built / "system.top", *solvent_args],
            inputs, attempt / "solvate", inputs)
    atoms, box = gro_atoms(built / "solvated.gro")
    if len(atoms) > 20000 or box != box_nm:
        raise ValueError("Built box exceeds smoke atom limit or differs from specification")
    first = spec["protocol"]["stages"][0]
    compile_stage(root, first, engine, attempt)
    mapping = atom_mapping(root / "stages" / first["id"] / "processed.top", built / "solvated.gro",
                           declared_counts(spec))
    if mixture:
        if mapping["counts"]["SOL"] != spec["scenario"]["solvent_count"]:
            raise ValueError("Solvation did not produce the requested exact solvent count")
        verify_processed_models(spec, {name: inputs / name for name in sources},
                                root / "stages" / first["id"] / "processed.top")
    write_json(built / "atom_mapping.json", mapping)
    write_json(built / "resolved_system.json",
               dict(engine="gromacs", scenario=spec["scenario"], counts=mapping["counts"],
                    atom_count=mapping["atom_count"], charge_e=mapping["charge_e"], box_nm=mapping["box_nm"],
                    model_hashes={item["id"]: content_hash(item["model"]) for item in spec["components"]},
                    bundle_hash=content_hash(spec["interaction_bundle"]),
                    mapping=dict(path="build/atom_mapping.json", sha256=sha256(built / "atom_mapping.json")),
                    coordinates=dict(path="build/solvated.gro", format="gro", sha256=sha256(built / "solvated.gro")),
                    topology=dict(path="build/system.top", format="gromacs_top", sha256=sha256(built / "system.top"))))
    return mapping
