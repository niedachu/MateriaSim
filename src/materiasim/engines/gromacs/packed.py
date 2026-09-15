"""Packmol-to-GROMACS integration; no duplicate simulation or checkpoint runner."""

import shutil

from materiasim.engines.gromacs.parameters import collect_models
from materiasim.engines.gromacs.coordinates import write_gro
from materiasim.storage import content_hash, sha256, write_json
from materiasim.engines.gromacs.command import command
from materiasim.engines.gromacs.stage import compile_stage
from materiasim.builders.packmol import pack
from materiasim.engines.gromacs.prebuilt import verify_processed_models
from materiasim.specs.composition import declared_counts
from materiasim.engines.gromacs.topology import atom_mapping


def prepare_packed(root, spec, sources, engine, attempt, candidate):
    """Freeze, pack, optionally fill TIP3P, compile, and preserve requested/actual molecular identities."""
    from materiasim.engines.gromacs.build import snapshot

    snapshot(root, spec, sources, engine)
    inputs, built = root / "inputs", root / "build"
    frozen = {name: inputs / name for name in sources}
    _, models = collect_models(spec, frozen)
    packed = pack(spec, models, built, attempt, candidate)
    write_gro(built / "boxed.gro", packed, spec["scenario"]["box_nm"])
    water = spec["scenario"]["solvent"]["kind"] == "tip3p_fill"
    if water:
        command(engine, ["solvate", "-cp", built / "boxed.gro", "-cs", inputs / "spc216.gro",
                         "-o", built / "solvated.gro", "-p", built / "system.top"],
                inputs, attempt / "solvate", inputs, seconds=60)
    else:
        # The retained stage adapter consumes this filename; its name does not imply water.
        shutil.copyfile(built / "boxed.gro", built / "solvated.gro")
    first = spec["protocol"]["stages"][0]
    compile_stage(root, first, engine, attempt)
    processed = root / "stages" / first["id"] / "processed.top"
    mapping = atom_mapping(processed, built / "solvated.gro", declared_counts(spec), require_solvent=water)
    if mapping["atom_count"] > 20000 or mapping["box_nm"] != spec["scenario"]["box_nm"]:
        raise ValueError("Built box exceeds engineering bounds or differs from requested box")
    verify_processed_models(spec, frozen, processed)
    for target, original in zip(mapping["atoms"], packed):
        if target["atom_uid"] != original["atom_uid"]:
            raise ValueError("Engine mapping differs from packing molecule order")
        target.update(group_id=original["group_id"], group_instance_id=original["group_instance_id"])
    for atom in mapping["atoms"][len(packed):]:
        atom.update(group_id="solvent_fill", group_instance_id=atom["molecule_id"])
    write_json(built / "atom_mapping.json", mapping)
    write_json(built / "resolved_system.json", dict(engine="gromacs", scenario=spec["scenario"],
        requested_counts=declared_counts(spec), counts=mapping["counts"], atom_count=mapping["atom_count"],
        charge_e=mapping["charge_e"], box_nm=mapping["box_nm"],
        molecule_fractions={name: count / sum(mapping["counts"].values()) for name, count in mapping["counts"].items()},
        composition_policy="integer solutes; explicit water fill or none; no concentration inference",
        bundle_hash=content_hash(spec["interaction_bundle"]),
        mapping=dict(path="build/atom_mapping.json", sha256=sha256(built / "atom_mapping.json")),
        coordinates=dict(path="build/solvated.gro", format="gro", sha256=sha256(built / "solvated.gro")),
        topology=dict(path="build/system.top", format="gromacs_top", sha256=sha256(built / "system.top"))))
    return mapping
