"""Run identity, frozen-stage verification and append-only attempt records."""

import uuid
from pathlib import Path

from materiasim.storage import contained, content_hash, inventory, read_json, sha256, utc_now, verify_hashes, write_json
from materiasim.runtime.records import stage_ids
from materiasim.errors import MateriaSimError
from materiasim.engines.prepared import read_prepared, validate_prepared
from materiasim.runtime.identity import implementation, verify_identities


def source_identity():
    """Return the implementation hashes used to prohibit changed-code resume."""
    root = Path(__file__).resolve().parents[1]
    return {path.relative_to(root).as_posix(): sha256(path) for path in sorted(root.rglob("*.py"))}


def verify_run(root):
    """Read either supported Run version and verify artifacts, independently of current code."""
    root = Path(root).resolve()
    manifest = read_json(root / "manifest.json")
    spec = read_json(root / "resolved_spec.json")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] not in (1, 2, 3):
        raise ValueError("Unsupported Run manifest version")
    if type(spec["schema_version"]) is not int or spec["schema_version"] != manifest["schema_version"]:
        raise ValueError("Manifest/spec version mismatch")
    if content_hash(spec) != manifest["spec_hash"]:
        raise ValueError("Resolved specification changed")
    verify_hashes(root, manifest["hashes"])
    directories = ["inputs", "build", "provenance"] if spec["schema_version"] == 3 else ["inputs", "build"]
    if inventory(root, directories) != manifest["hashes"]:
        raise ValueError("Frozen input/build inventory changed")
    if spec["schema_version"] == 3:
        verify_identities(root, spec, manifest)
        migration = read_json(root / "provenance/migration.json")
        if migration["resolved_hash"] != manifest["spec_hash"] or migration["resolved_schema"] != 3:
            raise ValueError("Migration record differs from the resolved experiment")
        for name, document in migration["documents"].items():
            verify_hashes(root, {f"provenance/source_documents/{name}": document["sha256"]})
    completed = read_json(root / "status.json")["status"] == "completed"
    if "storage_contract" in manifest and (type(manifest["storage_contract"]) is not int or manifest["storage_contract"] != 1):
        raise ValueError("Unsupported Run storage contract")
    for name in stage_ids(spec):
        stage = contained(root, f"stages/{name}")
        if completed and not (stage / "stage.json").is_file():
            raise ValueError(f"Completed Run lacks sealed stage: {name}")
        if (stage / "stage.json").exists():
            seal = read_json(stage / "stage.json")
            if "storage_contract" in manifest and "archive_generations" not in seal:
                raise ValueError("Missing storage generation index")
            if seal["status"] not in ("prepared", "completed", "interrupted"):
                raise ValueError("Invalid sealed stage state")
            if completed and seal["status"] != "completed":
                raise ValueError("Completed Run contains incomplete stage")
            verify_hashes(root, seal["hashes"])
            if "outputs" in seal:
                verify_hashes(root, seal["outputs"])
            elif seal["status"] != "prepared":
                raise ValueError("Completed/interrupted stage lacks output hashes")
            if spec["schema_version"] in (2, 3):
                verify_stage_inventory(root, name, seal)
                if spec["schema_version"] == 3 and "preparation" not in seal:
                    raise ValueError("v3 stage requires a recorded preparation")
                # Older v2 seals remain readable, but are never backfilled with inferred provenance.
                if "preparation" in seal:
                    stage = next(item for item in spec["protocol"]["stages"] if item["id"] == name)
                    validate_prepared(root, stage, spec["interaction_bundle"]["engine"], read_prepared(root, name))
    return spec, manifest


def verify_stage_inventory(root, name, seal):
    """Reject untracked output, role changes and corruption of declared independent append generations."""
    if seal["stage_id"] != name or seal["engine"] != "gromacs":
        raise ValueError("Stage identity mismatch")
    expected_compiled = {f"stages/{name}/{item}" for item in ("input.tpr", "resolved.mdp", "processed.top")}
    if set(seal["hashes"]) != expected_compiled:
        raise ValueError("Compiled stage inventory changed")
    actual = inventory(root, [f"stages/{name}"])
    actual.pop(f"stages/{name}/stage.json")
    if actual != dict(seal["hashes"], **seal.get("outputs", {})):
        raise ValueError("Untracked or missing stage output")
    generations = seal.get("archive_generations", [])
    if not isinstance(generations, list):
        raise ValueError("Archive generations must be a list")
    declared = []
    for generation in generations:
        from materiasim.specs.schema import fields, integer
        fields(generation, ("contract_version", "directory", "hashes"), "archive generation")
        integer(generation["contract_version"], 1, 1, "archive version")
        directory = generation["directory"]
        if (not isinstance(directory, str) or len(Path(directory).parts) != 3 or
                not directory.startswith("attempts/") or not directory.endswith("/outputs-" + name)):
            raise ValueError("Invalid archive generation path")
        contained(root, directory)
        declared.append(directory)
        verify_hashes(root, generation["hashes"])
        if inventory(root, [directory]) != generation["hashes"]:
            raise ValueError("Archive generation inventory changed")
    if "archive_generations" in seal:
        actual = {p.relative_to(root).as_posix() for p in (root / "attempts").glob("*/outputs-" + name)}
        if len(declared) != len(set(declared)) or set(declared) != actual:
            raise ValueError("Archive generation index differs from preserved attempts")
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
    """Require v3 and an unchanged execution dependency closure; old Runs remain read-only."""
    spec, manifest = verify_run(root)
    if spec["schema_version"] != 3:
        raise ValueError(f"v{spec['schema_version']} is read-only in this implementation; retain its original code for execution")
    if implementation("execution") != manifest["identities"]["execution"]["implementation"]:
        raise MateriaSimError("RESUME_INCOMPATIBLE", "Implementation changed; this Run cannot be resumed with different code",
                             category="integrity", evidence_refs=[str(Path(root) / "manifest.json")])
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
