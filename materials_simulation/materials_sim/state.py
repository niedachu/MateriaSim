"""Run identity, frozen-stage verification and append-only attempt records."""

import uuid
from pathlib import Path

from .files import contained, content_hash, inventory, read_json, sha256, utc_now, verify_hashes, write_json
from .records import stage_ids


def source_identity():
    """Return the implementation hashes used to prohibit changed-code resume."""
    root = Path(__file__).parent
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(root.rglob("*.py"))}


def verify_run(root):
    """Read either supported Run version and verify artifacts, independently of current code."""
    root = Path(root).resolve()
    manifest = read_json(root / "manifest.json")
    spec = read_json(root / "resolved_spec.json")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] not in (1, 2):
        raise ValueError("Unsupported Run manifest version")
    if type(spec["schema_version"]) is not int or spec["schema_version"] != manifest["schema_version"]:
        raise ValueError("Manifest/spec version mismatch")
    if content_hash(spec) != manifest["spec_hash"]:
        raise ValueError("Resolved specification changed")
    verify_hashes(root, manifest["hashes"])
    if inventory(root, ["inputs", "build"]) != manifest["hashes"]:
        raise ValueError("Frozen input/build inventory changed")
    completed = read_json(root / "status.json")["status"] == "completed"
    for name in stage_ids(spec):
        stage = contained(root, f"stages/{name}")
        if completed and not (stage / "stage.json").is_file():
            raise ValueError(f"Completed Run lacks sealed stage: {name}")
        if (stage / "stage.json").exists():
            seal = read_json(stage / "stage.json")
            if seal["status"] not in ("prepared", "completed", "interrupted"):
                raise ValueError("Invalid sealed stage state")
            if completed and seal["status"] != "completed":
                raise ValueError("Completed Run contains incomplete stage")
            verify_hashes(root, seal["hashes"])
            if "outputs" in seal:
                verify_hashes(root, seal["outputs"])
            elif seal["status"] != "prepared":
                raise ValueError("Completed/interrupted stage lacks output hashes")
            if spec["schema_version"] == 2:
                verify_stage_inventory(root, name, seal)
    return spec, manifest


def verify_stage_inventory(root, name, seal):
    """Reject untracked v2 outputs and inconsistent stage role/mapping identities."""
    if seal["stage_id"] != name or seal["engine"] != "gromacs":
        raise ValueError("Stage identity mismatch")
    expected_compiled = {f"stages/{name}/{item}" for item in ("input.tpr", "resolved.mdp", "processed.top")}
    if set(seal["hashes"]) != expected_compiled:
        raise ValueError("Compiled stage inventory changed")
    actual = inventory(root, [f"stages/{name}"])
    actual.pop(f"stages/{name}/stage.json")
    if actual != dict(seal["hashes"], **seal.get("outputs", {})):
        raise ValueError("Untracked or missing stage output")
    if seal["status"] == "prepared":
        return
    for artifact in seal["artifacts"].values():
        if seal["outputs"].get(artifact["path"]) != artifact["sha256"]:
            raise ValueError("Stage artifact identity differs from output seal")
    mapping = seal["mapping"]
    if mapping["path"] != "build/atom_mapping.json":
        raise ValueError("Unknown stage atom mapping")
    verify_hashes(root, {mapping["path"]: mapping["sha256"]})


def verify_execution(root):
    """Require current v2 implementation identity in addition to read-only integrity."""
    spec, manifest = verify_run(root)
    if spec["schema_version"] != 2:
        raise ValueError("v1 is read-only in this implementation; retain its original code for execution")
    if source_identity() != manifest["implementation"]:
        raise ValueError("Implementation changed; this Run cannot be resumed with different code")
    return spec, manifest


def set_status(root, status, **details):
    """Atomically update operational state; attempt records retain its history."""
    value = dict(status=status, updated_utc=utc_now(), **details)
    write_json(Path(root) / "status.json", value)
    return value


def new_attempt(root, action):
    """Create a unique attempt directory, never reusing a previous command log."""
    attempt = Path(root) / "attempts" / (action + "-" + uuid.uuid4().hex)
    attempt.mkdir(parents=True, exist_ok=False)
    return attempt
