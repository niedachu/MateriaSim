"""Compile native stages and freeze the exact coordinate/checkpoint/parameter handoff."""

import copy
from dataclasses import asdict

from materiasim.engines.contracts import PreparedStage
from materiasim.engines.prepared import read_prepared, validate_prepared
from materiasim.engines.gromacs.command import command
from materiasim.engines.gromacs.mdp import mdp_values
from materiasim.specs.schema import identifier
from materiasim.storage import contained, inventory, read_json, sha256, verify_hashes, write_json


def native_identity(engine):
    """Return the native identity required for execution, independently of its absolute path."""
    return {key: engine[key] for key in ("sha256", "version", "platform")}


def asset(root, path, format_name):
    """Hash a regular Run-local file and attach the format consumed by the native backend."""
    relative = path.relative_to(root).as_posix()
    return dict(path=relative, format=format_name, sha256=sha256(contained(root, relative)))


def stage_inputs(root, stage):
    """Resolve only the declared completed predecessor; never infer an available checkpoint."""
    identifier(stage["id"], "stage.id")
    previous_id = stage["input"]["stage_id"]
    if previous_id is None:
        if stage["input"]["kind"] != "coordinates":
            raise ValueError("Initial build cannot supply a checkpoint")
        coordinates = root / "build/solvated.gro"
    else:
        identifier(previous_id, "input.stage_id")
        previous = root / "stages" / previous_id
        seal = read_json(previous / "stage.json")
        if seal["status"] != "completed":
            raise ValueError("Stage preparation requires a completed predecessor")
        coordinates = previous / "md.gro"
    paths = {"coordinates": (coordinates, "gro"),
             "topology": (root / "build/system.top", "gromacs_top"),
             "parameters": (root / "build" / f"{stage['id']}.mdp", "gromacs_mdp")}
    if stage["input"]["kind"] == "checkpoint":
        paths["checkpoint"] = (previous / "md.cpt", "gromacs_checkpoint")
    elif stage["input"]["kind"] != "coordinates":
        raise ValueError("Unsupported stage input kind")
    result = {role: asset(root, path, kind) for role, (path, kind) in paths.items()}
    if previous_id is not None:
        for role in ("coordinates", "checkpoint"):
            if role in result:
                recorded = result[role]
                if seal["outputs"].get(recorded["path"]) != recorded["sha256"]:
                    raise ValueError("Predecessor state differs from its sealed output")
    return result


def dependency_closure(root, inputs):
    """Include the whole frozen native lookup tree plus explicitly selected stage inputs."""
    # Conditional topology includes and auxiliary GROMACS tables are conservative dependencies.
    # Mapping is generated after the first compilation and therefore is not a grompp input.
    return dict(inventory(root, ["inputs"]), **{a["path"]: a["sha256"] for a in inputs.values()})


def compile_stage(root, stage, engine, attempt):
    """Compile once and return a persisted PreparedStage, rejecting inputs changed during grompp."""
    inputs = stage_inputs(root, stage)
    dependencies = dependency_closure(root, inputs)
    effective = mdp_values(root / inputs["parameters"]["path"])
    name = stage["id"]
    folder = root / "stages" / name
    folder.mkdir(parents=True, exist_ok=False)
    args = ["grompp", "-f", root / inputs["parameters"]["path"],
            "-c", root / inputs["coordinates"]["path"], "-p", root / inputs["topology"]["path"],
            "-o", folder / "input.tpr", "-po", folder / "resolved.mdp", "-pp", folder / "processed.top"]
    if "checkpoint" in inputs:
        args.extend(["-t", root / inputs["checkpoint"]["path"]])
    command(engine, args, root / "inputs", attempt / f"compile-{name}", root / "inputs")
    verify_hashes(root, dependencies)
    if dependency_closure(root, stage_inputs(root, stage)) != dependencies:
        raise ValueError("Compiler input closure changed during compilation")
    artifacts = {role: asset(root, folder / filename, kind) for role, filename, kind in (
        ("compiled_input", "input.tpr", "gromacs_tpr"),
        ("resolved_parameters", "resolved.mdp", "gromacs_mdp"),
        ("processed_topology", "processed.top", "gromacs_top"))}
    prepared = PreparedStage("gromacs", copy.deepcopy(stage), inputs, artifacts, effective,
                             dependencies, native_identity(engine))
    hashes = {value["path"]: value["sha256"] for value in artifacts.values()}
    write_json(folder / "stage.json", dict(status="prepared", stage_id=name, type=stage["type"],
               engine="gromacs", hashes=hashes, input=stage["input"], preparation=asdict(prepared), archive_generations=[]))
    return prepared


def verify_native_prepared(root, stage, engine, prepared):
    """Check native roles, lookup closure and parameters against a persisted preparation."""
    validate_prepared(root, stage, "gromacs", prepared)
    if prepared.engine_identity != native_identity(engine):
        raise ValueError("Prepared stage engine identity changed")
    expected_inputs = stage_inputs(root, stage)
    if prepared.inputs != expected_inputs or prepared.dependency_hashes != dependency_closure(root, expected_inputs):
        raise ValueError("Prepared native input roles or dependency closure changed")
    folder = root / "stages" / stage["id"]
    expected_artifacts = {role: asset(root, folder / name, kind) for role, name, kind in (
        ("compiled_input", "input.tpr", "gromacs_tpr"),
        ("resolved_parameters", "resolved.mdp", "gromacs_mdp"),
        ("processed_topology", "processed.top", "gromacs_top"))}
    if prepared.artifacts != expected_artifacts:
        raise ValueError("Prepared native artifact roles changed")
    if prepared.effective_parameters != mdp_values(root / prepared.inputs["parameters"]["path"]):
        raise ValueError("Prepared effective parameters differ from the frozen MDP")


def prepare_stage(root, stage, engine, attempt):
    """Compile an absent stage or verify a recorded preparation; never recompile resumed stages."""
    identifier(stage["id"], "stage.id")
    folder = root / "stages" / stage["id"]
    prepared = (read_prepared(root, stage["id"]) if folder.exists()
                else compile_stage(root, stage, engine, attempt))
    verify_native_prepared(root, stage, engine, prepared)
    return prepared
