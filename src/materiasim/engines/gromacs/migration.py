"""Deterministic conversion of the supported native v2 inputs; no chemical metadata is invented."""

from copy import deepcopy
from pathlib import Path

from materiasim.engines.gromacs.mdp import mdp_values
from materiasim.engines.gromacs.specification import BUILDERS, FORMATS, physics
from materiasim.specs.v3 import default_profile, validate_document
from materiasim.storage import content_hash


def typed_files(owner):
    """Attach native format names to the v2 assets already admitted by the native backend."""
    for item in owner.get("files", []):
        suffix = Path(item["name"]).suffix
        if suffix not in FORMATS:
            raise ValueError(f"No deterministic native format conversion for {item['name']}")
        item["format"] = FORMATS[suffix]


def upgrade(spec, sources):
    """Return v3 scientific content and explicit CPU policy, retaining original asset bytes and stage targets."""
    result = deepcopy(spec)
    result["schema_version"] = 3
    result["execution_profile"] = default_profile()
    for component in result["components"]:
        component["role"] = "unspecified"
        component["model"].update(resolution="unspecified", provenance=dict(status="not_provided", references=[]))
        typed_files(component["model"])
    bundle = result["interaction_bundle"]
    bundle.pop("model_hash", None)
    bundle["model_hashes"] = {c["id"]: content_hash(c["model"]) for c in result["components"]}
    bundle["engine_parameters"] = {key: bundle.pop(key) for key in ("force_field", "library_hash", "water_model")}
    bundle.setdefault("files", [])
    typed_files(bundle)
    scenario = result["scenario"]
    kind, box = scenario.pop("kind"), scenario.pop("box_nm")
    if "structure" in scenario:
        typed_files(scenario["structure"])
    result["scenario"] = dict(kind=kind, boundary=dict(
        vectors_nm=[[box[i] if i == j else 0 for j in range(3)] for i in range(3)], periodic=[True] * 3),
        builder=dict(id=BUILDERS[kind], config=scenario))
    typed_files(result["protocol"])
    for stage in result["protocol"]["stages"]:
        name = stage.pop("mdp")
        stage["engine_parameters"] = dict(engine="gromacs", asset=name)
        stage["physics"] = physics(mdp_values(sources[name]), stage)
        stage["outputs"] = (["coordinates", "log"] if stage["type"] == "minimization" else
                            ["coordinates", "log", "trajectory", "energy", "checkpoint"])
    validate_document(result)
    return result
