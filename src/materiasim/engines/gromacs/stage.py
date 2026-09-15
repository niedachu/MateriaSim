"""GROMACS-specific compilation, result assessment and checkpoint append."""

import math
import re
import shutil
from pathlib import Path

from materiasim.storage import inventory, read_json, sha256, write_json
from materiasim.engines.gromacs.command import checkpoint, command
from materiasim.engines.gromacs.mdp import mdp_values
from materiasim.engines.gromacs.topology import gro_atoms
from materiasim.runtime.process import CommandFailed


def compile_stage(root, stage, engine, attempt):
    """Compile frozen MDP and the explicitly selected preceding coordinates/checkpoint."""
    name = stage["id"]
    folder = root / "stages" / name
    folder.mkdir(parents=True, exist_ok=False)
    previous_id = stage["input"]["stage_id"]
    previous = root / "stages" / previous_id if previous_id is not None else None
    coordinates = previous / "md.gro" if previous else root / "build/solvated.gro"
    args = ["grompp", "-f", root / "build" / f"{name}.mdp", "-c", coordinates,
            "-p", root / "build/system.top", "-o", folder / "input.tpr",
            "-po", folder / "resolved.mdp", "-pp", folder / "processed.top"]
    if stage["input"]["kind"] == "checkpoint":
        args.extend(["-t", previous / "md.cpt"])
    command(engine, args, root / "inputs", attempt / f"compile-{name}", root / "inputs")
    hashes = {path.relative_to(root).as_posix(): sha256(path)
              for path in (folder / "input.tpr", folder / "resolved.mdp", folder / "processed.top")}
    write_json(folder / "stage.json", dict(status="prepared", stage_id=name, type=stage["type"],
                                          engine="gromacs", hashes=hashes, input=stage["input"]))


def check_numerics(log):
    """Reject numerical warnings/nonfinite output, allowing defined epsilon-rf infinity."""
    # Infinite reaction-field dielectric is an input convention, not a computed energy.
    checked = re.sub(r"^\s*epsilon-rf\s*=\s*inf\s*$", "", log, flags=re.M)
    if re.search(r"LINCS WARNING|constraint failure|\bnan\b|\binf\b", checked, re.I):
        raise ValueError("Numerical warning or nonfinite result in GROMACS log")


def assess_stage(root, stage, engine):
    """Return actual completion evidence, respecting absolute step and ps time origins."""
    folder = root / "stages" / stage["id"]
    log = (folder / "md.log").read_text()
    check_numerics(log)
    if stage["type"] == "minimization":
        gro_atoms(folder / "md.gro")
        match = re.search(r"converged to Fmax <\s*([\d.eE+-]+) in\s+(\d+) steps", log)
        if not match:
            raise ValueError("Energy minimization did not meet its force criterion")
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
    """Seal outputs with typed roles and retain each attempt's pre-append generation."""
    folder = root / "stages" / stage
    seal = read_json(folder / "stage.json")
    outputs = {key: value for key, value in inventory(root, [f"stages/{stage}"]).items()
               if key not in seal["hashes"] and not key.endswith("/stage.json")}
    archive = attempt / f"outputs-{stage}"
    archive.mkdir()
    for relative in outputs:
        shutil.copyfile(root / relative, archive / Path(relative).name)
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


def execute_stage(root, stage, engine, attempt, threads, remaining):
    """Compile if needed, then run or append from the verified same-stage checkpoint."""
    name = stage["id"]
    folder = root / "stages" / name
    if not folder.exists():
        compile_stage(root, stage, engine, attempt)
    seal = read_json(folder / "stage.json")
    args = ["mdrun", "-s", "input.tpr", "-deffnm", "md", "-ntmpi", "1", "-ntomp", threads,
            "-nb", "cpu", "-pme", "cpu", "-cpt", "0.01", "-maxh", remaining / 3600]
    if seal["status"] == "interrupted":
        args.extend(["-cpi", "md.cpt", "-append"])
    elif seal["status"] != "prepared":
        raise ValueError(f"Cannot execute stage in state {seal['status']}")
    elif list(folder.glob("md.*")):
        raise ValueError("Untracked stage output exists; refusing overwrite")
    record = attempt / f"run-{name}"
    try:
        result = command(engine, args, folder, record, root / "inputs", seconds=remaining + 15)
    except CommandFailed as error:
        # Native GROMACS 2026.3 can return 1 after a graceful TERM checkpoint.
        # This is not a general nonzero-exit waiver: assess_stage below still checks
        # numerics, frozen atom identity, target step/time and every required output.
        result = error.result
        if (stage["type"] != "dynamics" or result["returncode"] != 1 or not result["interrupted"]
                or "Received the TERM signal" not in (record / "stderr.log").read_text()):
            raise
    evidence = assess_stage(root, stage, engine)
    preserve_stage(root, name, attempt, evidence)
    return evidence["complete"], result["interrupted"]
