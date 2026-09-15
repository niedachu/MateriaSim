"""New-Run orchestration; native construction belongs to the GROMACS adapter."""

import uuid
from pathlib import Path

from materiasim.storage import source_root, inventory, run_lock, utc_now, write_json
from materiasim.engines.gromacs.command import engine_info
from materiasim.engines.gromacs.build import prepare_system
from materiasim.specs.schema import identifier, load_spec
from materiasim.runtime.state import new_attempt, set_status, source_identity


def build(spec_path, run_root, candidate="gmx", packmol_candidate="packmol", *, run_id=None):
    """Create a v2 Run; optional run_id is a batch's already reserved exclusive target."""
    spec, sources, spec_hash = load_spec(spec_path)
    if spec["schema_version"] != 2:
        raise ValueError("v1 is read-only; use the separate v2 example to create a new Run")
    engine = engine_info(candidate)
    run_root = Path(run_root).resolve()
    protected_source = source_root()
    if run_root == protected_source or protected_source in run_root.parents:
        raise ValueError("Run root must be outside framework source")
    for source in sources.values():
        if run_root == source.parent or source.parent in run_root.parents:
            raise ValueError("Run root must not be inside an input directory")
    if run_id is not None:
        identifier(run_id, "reserved run_id")
    root = run_root / (run_id or (spec["id"] + "-" + uuid.uuid4().hex))
    root.mkdir(parents=True, exist_ok=False)
    with run_lock(root):
        attempt = new_attempt(root, "build")
        set_status(root, "building", attempt=attempt.name)
        try:
            mapping = prepare_system(root, spec, sources, engine, attempt, packmol_candidate)
            write_json(root / "resolved_spec.json", spec)
            write_json(root / "manifest.json", dict(schema_version=2, created_utc=utc_now(),
                       run_id=root.name, spec_hash=spec_hash, engine=engine,
                       sources={name: str(path) for name, path in sources.items()},
                       hashes=inventory(root, ["inputs", "build"]), implementation=source_identity()))
            set_status(root, "ready", attempt=attempt.name, atom_count=mapping["atom_count"])
        except Exception as error:
            set_status(root, "failed", attempt=attempt.name, error=str(error))
            raise
    return str(root)
