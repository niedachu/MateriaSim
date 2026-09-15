"""Bounded native single-frame migration check against the preserved CAT/ANI topology."""

import argparse
import shutil
from pathlib import Path

import numpy as np
from MDAnalysis.coordinates.TRR import TRRReader

from materiasim.storage import read_json, sha256, write_json
from materiasim.engines.gromacs.command import command, engine_info
from materiasim.engines.gromacs.mdp import mdp_values
from materiasim.runtime.state import verify_run
from materiasim.engines.gromacs.topology import section_rows
from tests.acceptance.verify_m1_evidence import compare_effective, effective_parameters, file_identity


def evaluate(folder, engine):
    """Compile frozen inputs and return one Potential value and native kJ/mol/nm forces."""
    command(engine, ["grompp", "-f", "single.mdp", "-c", "frame.gro", "-p", "system.top",
                     "-o", "input.tpr", "-po", "resolved.mdp", "-pp", "processed.top"],
            folder, folder / "compile", folder, seconds=60)
    command(engine, ["mdrun", "-s", "input.tpr", "-rerun", "frame.gro", "-deffnm", "rerun",
                     "-ntmpi", "1", "-ntomp", "2", "-nb", "cpu", "-pme", "cpu"],
            folder, folder / "evaluate", folder, seconds=60)
    command(engine, ["energy", "-f", "rerun.edr", "-o", "potential.xvg"],
            folder, folder / "energy", folder, seconds=30, stdin="Potential\n0\n")
    rows = [line.split() for line in (folder / "potential.xvg").read_text().splitlines()
            if line.strip() and not line.startswith(("#", "@"))]
    if len(rows) != 1 or len(rows[0]) != 2:
        raise AssertionError("Expected exactly one potential-energy frame")
    with TRRReader(str(folder / "rerun.trr"), convert_units=False) as reader:
        if len(reader) != 1 or not reader[0].has_forces:
            raise AssertionError("Expected exactly one force frame")
        forces = reader[0].forces.copy().astype(np.float64)
    energy = float(rows[0][1])
    if not np.isfinite(energy) or not np.isfinite(forces).all():
        raise AssertionError("Non-finite energy or force")
    return energy, forces


def main():
    """Compare original and core topologies on the same new Mac frame, not a historical trajectory."""
    parser = argparse.ArgumentParser()
    for name in ("run", "legacy", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    spec, manifest = verify_run(args.run)
    if read_json(args.run / "status.json")["status"] != "completed":
        raise ValueError("Single-frame comparison requires a completed source Run")
    engine = engine_info()
    if engine != manifest["engine"]:
        raise ValueError("Numerical comparison must use the source Run's exact engine")
    before = file_identity(args.run)
    args.output.mkdir(parents=True, exist_ok=False)
    # These tolerances apply only to this same-engine/same-input migration fixture.
    tolerances = dict(energy_abs_kj_mol=0.001, force_rms_kj_mol_nm=0.001,
                      force_max_kj_mol_nm=0.01)
    overrides = {"nsteps": "0", "nstfout": "1", "nstenergy": "1", "nstxout": "1"}
    values = mdp_values(args.run / "build/nvt.mdp")
    values.update(overrides)
    write_json(args.output / "definition.json", dict(run=str(args.run), legacy=str(args.legacy),
               engine=engine, tolerances=tolerances, overrides=overrides,
               coordinate_sha256=sha256(args.run / "stages/em/md.gro"),
               purpose="engineering migration; same new Mac EM frame, not historical reproduction"))
    results = {}
    for label in ("legacy", "core"):
        folder = args.output / label
        folder.mkdir()
        shutil.copytree(args.run / "inputs" / spec["interaction_bundle"]["force_field"],
                        folder / spec["interaction_bundle"]["force_field"])
        for name in ("cat.itp", "ani.itp", "gaff2_atomtypes.itp"):
            source = args.legacy / "topology" / name if label == "legacy" else args.run / "inputs" / name
            shutil.copyfile(source, folder / name)
        source = args.legacy / "formal/input/system.top" if label == "legacy" else args.run / "build/system.top"
        shutil.copyfile(source, folder / "system.top")
        shutil.copyfile(args.run / "stages/em/md.gro", folder / "frame.gro")
        (folder / "single.mdp").write_text("\n".join(f"{key} = {value}" for key, value in values.items()) + "\n")
        results[label] = evaluate(folder, engine)
    left, right = args.output / "legacy", args.output / "core"
    parameters = compare_effective(effective_parameters(left / "resolved.mdp"),
                                   effective_parameters(right / "resolved.mdp"))
    if list(section_rows(left / "processed.top")) != list(section_rows(right / "processed.top")):
        raise AssertionError("Native-preprocessed topology data differ")
    old_energy, old_forces = results["legacy"]
    new_energy, new_forces = results["core"]
    if old_forces.shape != new_forces.shape or new_forces.shape != (8912, 3):
        raise AssertionError("CAT/ANI fixture force/atom count mismatch")
    delta = new_forces - old_forces
    differences = dict(energy_abs_kj_mol=abs(new_energy - old_energy),
                       force_rms_kj_mol_nm=float(np.sqrt(np.mean(delta ** 2))),
                       force_max_kj_mol_nm=float(np.max(np.abs(delta))))
    passed = all(differences[key] <= limit for key, limit in tolerances.items())
    if before != file_identity(args.run):
        raise AssertionError("Single-frame check modified source Run")
    write_json(args.output / "comparison.json", dict(passed=passed, differences=differences,
               tolerances=tolerances, legacy_potential_kj_mol=old_energy,
               core_potential_kj_mol=new_energy, force_atoms=len(new_forces),
               effective_parameters=parameters, processed_topology_equal=True,
               source_run_unchanged=True, evidence_hashes=file_identity(args.output)))
    if not passed:
        raise AssertionError("Single-frame numerical migration tolerances exceeded")
    print(args.output / "comparison.json")


if __name__ == "__main__":
    main()
