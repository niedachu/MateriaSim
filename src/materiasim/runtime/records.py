"""Read-only versioned stage and artifact access; legacy identity is never rewritten."""

from materiasim.storage import contained, read_json, verify_hashes
from materiasim.specs.schema import identifier


def stage_ids(spec):
    """Return persisted stage order; v1's fixed order applies only to historical reading."""
    if spec["schema_version"] == 1:
        return ["em", "nvt", "npt", "prod"]
    if spec["schema_version"] != 2:
        raise ValueError("Unsupported Run schema")
    ids = [stage["id"] for stage in spec["protocol"]["stages"]]
    for name in ids:
        identifier(name, "stage.id")
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Missing or duplicate stage IDs")
    return ids


def stage_artifact(root, spec, stage_id, role):
    """Resolve a sealed role with hash verification; v1 paths remain explicit legacy evidence."""
    if stage_id not in stage_ids(spec):
        raise ValueError("Unknown analysis stage")
    seal = read_json(contained(root, f"stages/{stage_id}/stage.json"))
    if seal["status"] != "completed":
        raise ValueError("Analysis requires a completed stage")
    if spec["schema_version"] == 1:
        legacy_names = {"coordinates": "md.gro", "trajectory": "md.xtc"}
        if role not in legacy_names:
            raise ValueError("Role unavailable in legacy reader")
        path = f"stages/{stage_id}/{legacy_names[role]}"
        if path not in seal.get("outputs", {}):
            raise ValueError("Legacy artifact lacks a recorded output hash")
        digest = seal["outputs"][path]
    else:
        if role not in seal["artifacts"]:
            raise ValueError(f"Stage artifact missing role: {role}")
        artifact = seal["artifacts"][role]
        expected_format = {"coordinates": "gro", "trajectory": "xtc"}
        if role not in expected_format or artifact["format"] != expected_format[role]:
            raise ValueError("Unsupported analysis artifact format")
        path, digest = artifact["path"], artifact["sha256"]
        if path not in seal["outputs"] or seal["outputs"][path] != digest:
            raise ValueError("Artifact role differs from output seal")
        if not path.startswith(f"stages/{stage_id}/"):
            raise ValueError("Artifact belongs to a different stage")
    verify_hashes(root, {path: digest})
    return contained(root, path)
