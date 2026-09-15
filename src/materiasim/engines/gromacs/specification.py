"""Bind neutral v3 records to the existing native molecular backend, without another runner."""

from copy import deepcopy
from pathlib import Path

from materiasim.specs.schema import fields, identifier, integer, number
from materiasim.specs.protocol import validate_stages
from materiasim.engines.gromacs.mdp import mdp_values

FORMATS = {".gro": "gro", ".itp": "gromacs_itp", ".top": "gromacs_top", ".mdp": "gromacs_mdp", ".json": "json"}
BUILDERS = {"prebuilt_solute_water": "gromacs_prebuilt", "prebuilt_mixture_water": "gromacs_prebuilt",
            "packed_liquid": "gromacs_packmol"}


def parameter_asset(stage):
    """Read the v3 native asset binding, retaining exact v2 binding for real historical callers."""
    return stage["engine_parameters"]["asset"] if "engine_parameters" in stage else stage["mdp"]


def physics(values, stage):
    """Extract explicitly interpretable physical declarations from the original native template."""
    dynamics = stage["type"] == "dynamics"
    return dict(timestep_ps=float(values["dt"]) if dynamics else None,
                temperature_k=list(map(float, values["ref-t"].split())) if dynamics and values.get("tcoupl", "no") != "no" else [],
                pressure_bar=list(map(float, values["ref-p"].split())) if dynamics and values.get("pcoupl", "no") != "no" else [],
                force_tolerance_kj_mol_nm=None if dynamics else float(values["emtol"]))


def native_view(spec):
    """Project validated v3 model/boundary records into native builder arguments, keeping stage identity intact."""
    if spec["schema_version"] == 2:
        return spec
    result = deepcopy(spec)
    from materiasim.specs.v3 import asset_documents
    for owner in asset_documents(spec):
        for item in owner["files"]:
            if FORMATS.get(Path(item["name"]).suffix) != item["format"]:
                raise ValueError("Native asset format/name mismatch")
    bundle = result["interaction_bundle"]
    parameters = bundle.pop("engine_parameters")
    fields(parameters, ("force_field", "library_hash", "water_model"), "GROMACS bundle parameters")
    bundle.update(parameters)
    identifier(bundle["force_field"], "force_field")
    if not isinstance(bundle["force_field"], str) or not bundle["force_field"].endswith(".ff"):
        raise ValueError("GROMACS force field must name a frozen .ff library")
    allowed_scope = ("engineering_only", "reviewed") if spec["purpose"] != "engineering_smoke" else ("engineering_only",)
    if bundle["water_model"] != "tip3p" or bundle["validation_scope"] not in allowed_scope:
        raise ValueError("Only the existing engineering TIP3P bundle is implemented")
    from materiasim.specs.v3 import digest
    digest(bundle["library_hash"], "library_hash")
    if not 1 <= len(spec["components"]) <= 8:
        raise ValueError("Native engineering subset requires 1–8 components")
    for component in result["components"]:
        integer(component["count"], 1, 100, "native component count")
        if component["id"] == "SOL" or component["model"]["resolution"] not in ("unspecified", "atomistic"):
            raise ValueError("Explicit SOL models and coarse-grained models are not implemented")
        model = component["model"]
        own = {item["name"]: item["format"] for item in model["files"]}
        if own[model["coordinates"]] != "gro" or own[model["topology"]] not in ("gromacs_top", "gromacs_itp"):
            raise ValueError("Unsupported native model asset formats")
        if "gromacs_mdp" in own.values():
            raise ValueError("Protocol parameters cannot belong to a molecular model")
    scenario = result["scenario"]
    vectors = scenario["boundary"]["vectors_nm"]
    if scenario["boundary"]["periodic"] != [True] * 3 or any(vectors[i][j] != 0 for i in range(3) for j in range(3) if i != j):
        raise ValueError("Native builders require orthorhombic three-dimensional periodic boxes")
    box = [vectors[i][i] for i in range(3)]
    for length in box:
        number(length, 3, 6, "native box_nm")
    if BUILDERS.get(scenario["kind"]) != scenario["builder"]["id"]:
        raise ValueError("Scenario/builder combination is not implemented")
    config = scenario["builder"]["config"]
    expected = {"prebuilt_solute_water": (), "prebuilt_mixture_water": ("solvent_count", "structure"),
                "packed_liquid": ("seed", "tolerance_nm", "max_iterations", "solvent", "groups")}[scenario["kind"]]
    fields(config, expected, "native builder config")
    if "solvent_count" in config:
        integer(config["solvent_count"], 1, 6000, "solvent_count")
        structure = config["structure"]
        fields(structure, ("coordinates", "topology", "files"), "native structure")
        own = {item["name"]: item["format"] for item in structure["files"]}
        if own.get(structure["coordinates"]) != "gro" or own.get(structure["topology"]) != "gromacs_top":
            raise ValueError("Prebuilt structure requires declared GRO/topology formats")
    result["scenario"] = dict(kind=scenario["kind"], box_nm=box, **config)
    return result


def validate_native_protocol(spec, sources):
    """Check v3 physical declarations and native stage policy without silently overriding conflicting physics."""
    stages = spec["protocol"]["stages"]
    legacy = []
    formats = {item["name"]: item["format"] for item in spec["protocol"]["files"]}
    for stage in stages:
        value = {k: v for k, v in stage.items() if k not in ("engine_parameters", "physics", "outputs", "sampling")}
        name = parameter_asset(stage)
        value["mdp"] = name
        legacy.append(value)
        if formats[name] != "gromacs_mdp" or stage["physics"] != physics(mdp_values(sources[name]), stage):
            raise ValueError("Stage physics/format conflicts with the native parameter asset")
        available = {"coordinates", "log"} if stage["type"] == "minimization" else {"coordinates", "log", "energy", "trajectory", "checkpoint"}
        if not set(stage["outputs"]) <= available:
            raise ValueError("Requested output roles are unavailable for the native stage")
    validate_stages(legacy, spec["purpose"])
