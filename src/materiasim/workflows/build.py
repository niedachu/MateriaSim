"""New-Run orchestration; native construction belongs to the GROMACS adapter."""

import uuid
from materiasim.runtime.capacity import copy_file, preflight
from pathlib import Path

from materiasim.storage import source_root, inventory, run_lock, sha256, utc_now, write_json
from materiasim.engines.registry import get_engine
from materiasim.builders.contracts import validate_result
from materiasim.specs.schema import identifier
from materiasim.workflows.migration import load_executable
from materiasim.runtime.identity import make_identities
from materiasim.runtime.state import new_attempt, set_status, source_identity


def build(spec_path, run_root, candidate=None, packmol_candidate=None, *, run_id=None):
    """Create a Run with frozen v3 tool locators and full supervision for profiles v2/v3."""
    spec, _, _, _ = load_executable(spec_path)
    from materiasim.specs.purpose import select_tool
    candidate = select_tool(spec["execution_profile"], "gmx", candidate)
    packmol_candidate = select_tool(spec["execution_profile"], "packmol", packmol_candidate)
    if spec["execution_profile"]["contract_version"] in (2, 3):
        from materiasim.runtime.control import supervise
        from materiasim.research.plan import external_output
        parent = external_output(run_root, [Path(spec_path).resolve().parent])
        name = run_id or (spec["id"] + "-" + uuid.uuid4().hex)
        identifier(name, "run_id")
        return supervise(parent / name, spec, "materiasim.workflows.build", "build",
                         dict(spec_path=str(Path(spec_path).resolve()), run_root=str(parent),
                              candidate=candidate, packmol_candidate=packmol_candidate, run_id=name))
    return _build(spec_path, run_root, candidate, packmol_candidate, run_id=run_id)


def _build(spec_path, run_root, candidate="gmx", packmol_candidate="packmol", *, run_id=None, _control=None):
    """Create a v3 Run from v2/v3 source; run_id is a batch's already reserved exclusive target."""
    spec, sources, spec_hash, migration = load_executable(spec_path)
    if _control is not None and spec_hash != _control["expected_spec_hash"]:
        raise ValueError("Source experiment changed before supervised build")
    adapter = get_engine(spec["interaction_bundle"]["engine"])
    run_root = Path(run_root).resolve()
    protected_source = source_root()
    if run_root == protected_source or protected_source in run_root.parents:
        raise ValueError("Run root must be outside framework source")
    for source in sources.values():
        if run_root == source.parent or source.parent in run_root.parents:
            raise ValueError("Run root must not be inside an input directory")
    engine = adapter.inspect(candidate)
    from materiasim.specs.purpose import validate_environment
    validate_environment(spec, engine)
    if run_id is not None:
        identifier(run_id, "reserved run_id")
    root = run_root / (run_id or (spec["id"] + "-" + uuid.uuid4().hex))
    root.mkdir(parents=True, exist_ok=False)
    with run_lock(root):
        attempt = new_attempt(root, "build")
        set_status(root, "building", attempt=attempt.name)
        try:
            result = adapter.build(root, spec, sources, engine, attempt, packmol_candidate)
            validate_result(root, spec, result)
            mapping = result.mapping
            preflight([d["path"] for d in migration["documents"].values()], root / "provenance")
            for name, document in migration["documents"].items():
                target = root / "provenance/source_documents" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                copy_file(document["path"], target)
                if sha256(target) != document["sha256"] or sha256(document["path"]) != document["sha256"]:
                    raise ValueError("Source document changed while freezing provenance")
            write_json(root / "provenance/migration.json", migration)
            write_json(root / "resolved_spec.json", spec)
            manifest = dict(schema_version=3, storage_contract=1, created_utc=utc_now(),
                       run_id=root.name, spec_hash=spec_hash, engine=engine,
                       sources={name: str(path) for name, path in sources.items()},
                       hashes=inventory(root, ["inputs", "build", "provenance"]), implementation=source_identity(),
                       identities=make_identities(root, spec, engine))
            if _control is not None:
                manifest["operation_control"] = dict(contract_version=_control["control_version"], id=_control["control_id"])
            write_json(root / "manifest.json", manifest)
            set_status(root, "ready", attempt=attempt.name, atom_count=mapping["atom_count"])
        except Exception as error:
            set_status(root, "failed", attempt=attempt.name, error=str(error))
            raise
    return str(root)


if __name__ == "__main__":
    from materiasim.runtime.control import worker_main
    worker_main(_build)
