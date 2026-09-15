"""Strict GROMACS MDP parsing, derivation and protocol binding."""

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


def validate_protocol(stages, sources):
    """Validate the linear stage contract and bind every stage to a declared, compatible MDP."""
    from materiasim.specs.protocol import validate_stages

    validate_stages(stages)
    for stage in stages:
        if stage["mdp"] not in sources:
            raise ValueError("Stage MDP must be a declared protocol asset")
        stage_values(sources[stage["mdp"]], stage)
