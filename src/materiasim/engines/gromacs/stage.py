"""GROMACS prepared-input execution, result assessment and checkpoint append."""

import math
import re
from materiasim.runtime.capacity import copy_file, preflight
from pathlib import Path

from materiasim.storage import inventory, read_json, sha256, write_json
from materiasim.engines.gromacs.command import checkpoint, command
from materiasim.engines.gromacs.compile import verify_native_prepared
from materiasim.engines.gromacs.mdp import mdp_values
from materiasim.engines.gromacs.topology import gro_atoms
from materiasim.runtime.process import CommandFailed
from materiasim.errors import MateriaSimError


def check_numerics(log):
    """Reject numerical warnings/nonfinite output, allowing defined epsilon-rf infinity."""
    # Infinite reaction-field dielectric is an input convention, not a computed energy.
    checked = re.sub(r"^\s*epsilon-rf\s*=\s*inf\s*$", "", log, flags=re.M)
    if re.search(r"LINCS WARNING|constraint failure|\bnan\b|\binf\b", checked, re.I):
        raise MateriaSimError("NUMERICAL_FAILURE", "Numerical warning or nonfinite result in GROMACS log",
                              category="numerical")


def assess_stage(root, stage, engine):
    """Return actual completion evidence, respecting absolute step and ps time origins."""
    folder = root / "stages" / stage["id"]
    log = (folder / "md.log").read_text()
    check_numerics(log)
    if stage["type"] == "minimization":
        gro_atoms(folder / "md.gro")
        match = re.search(r"converged to Fmax <\s*([\d.eE+-]+) in\s+(\d+) steps", log)
        if not match:
            raise MateriaSimError("MINIMIZATION_NOT_CONVERGED", "Energy minimization did not meet its force criterion",
                                  category="numerical", evidence_refs=[str(folder / "md.log")])
        return dict(complete=True, actual_steps=int(match.group(2)), fmax_threshold=float(match.group(1)))
    actual = checkpoint(engine, folder / "md.cpt")
    expected_atoms = read_json(root / "build/atom_mapping.json")["atom_count"]
    dt = float(mdp_values(root / "build" / f"{stage['id']}.mdp")["dt"])
    if actual["atom_count"] != expected_atoms or not math.isfinite(actual["time_ps"]):
        raise ValueError("Checkpoint atom count/time is invalid")
    target_step = stage["step_origin"] + stage["steps"]
    if not stage["step_origin"] <= actual["step"] <= target_step:
        raise ValueError("Checkpoint step exceeds the declared target")
    # GROMACS time = tinit + dt * absolute_step, including nonzero init-step.
    if abs(actual["time_ps"] - (stage["time_origin_ps"] + actual["step"] * dt)) > 1e-6:
        raise ValueError("Checkpoint time does not match the declared timestep")
    complete = actual["step"] == target_step
    # Budget stops can leave a checkpoint but no final-coordinate GRO.
    if complete:
        gro_atoms(folder / "md.gro")
    for name in ("md.xtc", "md.edr", "md.log", "md.cpt"):
        if not (folder / name).is_file() or (folder / name).stat().st_size == 0:
            raise ValueError(f"Missing stage output: {name}")
    return dict(actual, complete=complete, target_step=target_step,
                target_time_ps=stage["time_origin_ps"] + target_step * dt)


def preserve_stage(root, stage, attempt, evidence):
    """Admit and hash an independent output generation before publishing its immutable seal."""
    folder = root / "stages" / stage
    seal = read_json(folder / "stage.json")
    outputs = {key: value for key, value in inventory(root, [f"stages/{stage}"]).items()
               if key not in seal["hashes"] and not key.endswith("/stage.json")}
    archive = attempt / f"outputs-{stage}"
    preflight([root / relative for relative in outputs], archive)
    archive.mkdir()
    for relative in outputs:
        copy_file(root / relative, archive / Path(relative).name)
    archived = inventory(root, [archive.relative_to(root).as_posix()])
    generations = seal.get("archive_generations", [])
    generations.append(dict(contract_version=1, directory=archive.relative_to(root).as_posix(), hashes=archived))
    seal["archive_generations"] = generations
    seal.update(status="completed" if evidence["complete"] else "interrupted", outputs=outputs,
                evidence=evidence, last_attempt=attempt.name)
    roles = {"coordinates": ("md.gro", "gro"), "trajectory": ("md.xtc", "xtc"),
             "checkpoint": ("md.cpt", "gromacs_checkpoint"), "energy": ("md.edr", "edr"),
             "log": ("md.log", "text")}
    seal["artifacts"] = {
        role: dict(path=f"stages/{stage}/{name}", sha256=outputs[f"stages/{stage}/{name}"], format=kind)
        for role, (name, kind) in roles.items() if f"stages/{stage}/{name}" in outputs}
    seal["mapping"] = dict(path="build/atom_mapping.json", sha256=sha256(root / "build/atom_mapping.json"))
    seal["units"] = dict(length="nm", time="ps", energy="kJ/mol")
    write_json(folder / "stage.json", seal)


def execute_stage(root, prepared, engine, attempt, threads, remaining, checkpoint_interval_minutes=.01, profile=None):
    """Consume a compiled contract and run/append it; execution never invokes grompp."""
    stage = prepared.stage
    name = stage["id"]
    folder = root / "stages" / name
    seal = read_json(folder / "stage.json")
    args = ["mdrun", "-s", "input.tpr", "-deffnm", "md", "-ntmpi", "1", "-ntomp", threads,
            "-nb", "cpu", "-pme", "cpu", "-cpt", checkpoint_interval_minutes, "-maxh", remaining / 3600]
    policy, overrides = None, {}
    if profile is not None and profile["contract_version"] in (2, 3):
        from materiasim.engines.gromacs.device import offload_arguments
        flags, policy = offload_arguments(profile, stage)
        args = args[:9] + flags + args[13:]
        overrides = engine["execution_device"].get("environment", {})
    if seal["status"] == "interrupted":
        args.extend(["-cpi", "md.cpt", "-append"])
    elif seal["status"] != "prepared":
        raise ValueError(f"Cannot execute stage in state {seal['status']}")
    elif list(folder.glob("md.*")):
        raise ValueError("Untracked stage output exists; refusing overwrite")
    verify_native_prepared(root, stage, engine, prepared)
    record = attempt / f"run-{name}"
    try:
        result = command(engine, args, folder, record, root / "inputs", seconds=remaining + 15, overrides=overrides)
    except CommandFailed as error:
        # Native GROMACS 2026.3 can return 1 after a graceful TERM checkpoint.
        # This is not a general nonzero-exit waiver: assess_stage below still checks
        # numerics, frozen atom identity, target step/time and every required output.
        result = error.result
        if (stage["type"] != "dynamics" or result["returncode"] != 1 or not result["interrupted"]
                or "Received the TERM signal" not in (record / "stderr.log").read_text()):
            raise
    evidence = assess_stage(root, stage, engine)
    if policy is not None:
        from materiasim.engines.gromacs.device import verify_offload
        evidence["execution"] = verify_offload((record / "stderr.log").read_text(), policy)
        evidence["execution"]["device"] = engine["execution_device"]
    preserve_stage(root, name, attempt, evidence)
    return evidence["complete"], result["interrupted"]
