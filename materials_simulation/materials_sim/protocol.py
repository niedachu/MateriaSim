"""Derive small engineering protocols without editing accepted source MDPs."""

from pathlib import Path

ALLOWED = set("""integrator define nsteps emtol emstep cutoff-scheme nstlist verlet-buffer-tolerance
rlist vdwtype vdw-modifier rvdw dispcorr coulombtype rcoulomb fourierspacing pme-order ewald-rtol
pbc constraints dt continuation constraint-algorithm lincs-iter lincs-order tcoupl tc-grps tau-t
ref-t pcoupl pcoupltype tau-p ref-p compressibility gen-vel gen-temp gen-seed nstxout nstvout
nstfout nstxout-compressed compressed-x-precision nstenergy nstlog comm-mode nstcomm comm-grps
tinit init-step""".split())


def mdp_values(path):
    """Read supported MDP keys, refusing unknown external-input or protocol features."""
    result = {}
    for raw in Path(path).read_text().splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        key = key.lower().replace("_", "-")
        if key in result or key not in ALLOWED:
            raise ValueError(f"Unsupported or duplicate MDP key: {key}")
        result[key] = value
    if result.get("pbc") != "xyz":
        raise ValueError("Only periodic 3D protocols are implemented")
    return result


def stage_values(source, stage):
    """Return effective MDP and recorded overrides for an explicitly typed stage."""
    values = mdp_values(source)
    minimize = stage["type"] == "minimization"
    if values.get("integrator") != ("steep" if minimize else "md"):
        raise ValueError(f"Unsupported integrator for {stage}")
    if not minimize and not 0 < float(values["dt"]) <= 0.002:
        raise ValueError("Engineering protocol requires dt <= 0.002 ps")
    changes = {"nsteps": str(stage["steps"])}
    if not minimize:
        generate = stage["velocities"] == "generate"
        if values.get("gen-vel") != ("yes" if generate else "no"):
            raise ValueError("MDP gen-vel conflicts with explicit velocity handoff")
        if values.get("continuation") != ("no" if generate else "yes"):
            raise ValueError("MDP continuation conflicts with explicit state handoff")
        changes.update(nstlog="100", nstenergy="100", **{"nstxout-compressed": "100"})
        changes.update(tinit=str(stage["time_origin_ps"]), **{"init-step": str(stage["step_origin"])})
        if generate:
            changes["gen-seed"] = str(stage["seed"])
    values.update(changes)
    return values, changes


def derive_mdp(source, destination, stage):
    """Write engineering MDP from a stage descriptor, preserving the source bytes."""
    values, changes = stage_values(source, stage)
    Path(destination).write_text("; Engineering smoke only; source MDP retained in inputs.\n" +
                                "\n".join(f"{key} = {value}" for key, value in values.items()) + "\n")
    return changes


def validate_stages(stages, sources):
    """Check linear stage IDs, state inheritance and bounded targets against source MDPs."""
    from .schema import fields, identifier, integer, number

    if not isinstance(stages, list) or not 2 <= len(stages) <= 8:
        raise ValueError("Engineering protocol requires 2–8 explicit stages")
    seen, previous = set(), None
    for stage in stages:
        fields(stage, ("id", "type", "mdp", "steps", "input", "velocities", "seed",
                       "time_origin_ps", "step_origin"), "stage")
        identifier(stage["id"], "stage.id")
        identifier(stage["mdp"], "stage.mdp")
        if stage["id"] in seen:
            raise ValueError("Duplicate stage ID")
        seen.add(stage["id"])
        if stage["type"] not in ("minimization", "dynamics"):
            raise ValueError("Unsupported stage type")
        minimize = stage["type"] == "minimization"
        if minimize != (previous is None):
            raise ValueError("Current protocol starts with one minimization, followed by dynamics")
        integer(stage["steps"], 1, 5000 if minimize else 2000, "stage.steps")
        integer(stage["step_origin"], 0, 1000000, "step_origin")
        number(stage["time_origin_ps"], 0, 1000000, "time_origin_ps")
        fields(stage["input"], ("stage_id", "kind"), "stage.input")
        if stage["input"]["stage_id"] != (previous["id"] if previous else None):
            raise ValueError("Input must reference the immediately preceding stage, or initial build")
        expected_velocity = "none" if minimize else ("generate" if previous["type"] == "minimization" else "inherit")
        expected_input = "checkpoint" if expected_velocity == "inherit" else "coordinates"
        if stage["velocities"] != expected_velocity or stage["input"]["kind"] != expected_input:
            raise ValueError("Invalid coordinate/velocity/checkpoint inheritance")
        if expected_velocity == "generate":
            integer(stage["seed"], 1, 2147483646, "velocity seed")
        elif stage["seed"] is not None:
            raise ValueError("Only velocity generation accepts a seed")
        if minimize and (stage["time_origin_ps"] != 0 or stage["step_origin"] != 0):
            raise ValueError("Minimization does not have a dynamics time origin")
        if stage["mdp"] not in sources:
            raise ValueError("Stage MDP must be a declared protocol asset")
        stage_values(sources[stage["mdp"]], stage)
        previous = stage
