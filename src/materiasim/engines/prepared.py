"""Serializable compiled-stage handoff checks, independent of native file syntax."""

from dataclasses import asdict

from materiasim.engines.contracts import PreparedStage
from materiasim.errors import MateriaSimError
from materiasim.specs.schema import fields, identifier
from materiasim.storage import content_hash, read_json, verify_hashes


def read_prepared(root, stage_id):
    """Read an explicitly recorded contract; never infer one for an old compiled stage."""
    identifier(stage_id, "stage.id")
    path = root / "stages" / stage_id / "stage.json"
    seal = read_json(path)
    if "preparation" not in seal:
        raise MateriaSimError("RESUME_INCOMPATIBLE", "Stage has no compiled-input contract; retain its original implementation",
                             category="integrity", evidence_refs=[str(path)])
    value = seal["preparation"]
    fields(value, PreparedStage.__dataclass_fields__, "prepared stage")
    return PreparedStage(**value)


def validate_prepared(root, stage, engine_id, prepared):
    """Check returned/persisted identity and every typed asset before handing it to an engine."""
    if type(prepared.contract_version) is not int or prepared.contract_version != 1:
        raise ValueError("Unsupported prepared-stage contract version")
    if prepared.engine != engine_id or content_hash(prepared.stage) != content_hash(stage):
        raise MateriaSimError("INTEGRITY_MISMATCH", "Prepared stage differs from the requested engine/protocol",
                             category="integrity", field="stage")
    seal = read_json(root / "stages" / stage["id"] / "stage.json")
    if asdict(prepared) != seal.get("preparation"):
        raise ValueError("Prepared stage differs from its persisted handoff")
    for collection in (prepared.inputs, prepared.artifacts):
        if not isinstance(collection, dict) or not collection:
            raise ValueError("Prepared stage requires explicit input and output roles")
        for role, asset in collection.items():
            identifier(role, "artifact role")
            fields(asset, ("path", "format", "sha256"), "prepared artifact")
            identifier(asset["format"], "artifact format")
            verify_hashes(root, {asset["path"]: asset["sha256"]})
    expected = {asset["path"]: asset["sha256"] for asset in prepared.artifacts.values()}
    if expected != seal["hashes"]:
        raise ValueError("Prepared artifact roles differ from the compiled inventory")
    for asset in prepared.inputs.values():
        if prepared.dependency_hashes.get(asset["path"]) != asset["sha256"]:
            raise ValueError("Prepared input is missing from its dependency closure")
    verify_hashes(root, prepared.dependency_hashes)
