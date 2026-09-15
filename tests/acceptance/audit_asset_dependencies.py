"""Read-only dependency inventory for the current v1/v2 experiment migration."""

import argparse
import json
from pathlib import Path

from materiasim.storage import inventory, read_json, sha256
from materiasim.engines.gromacs.command import engine_info
from materiasim.engines.gromacs.build import LIBRARY_FILES, library_identity
from materiasim.workflows.validation import load_spec


def audit_experiment(path, engine):
    """Return verified config, asset and full installed-library identities for one experiment path."""
    path = Path(path).resolve()
    spec, sources, identity = load_spec(path)
    raw = read_json(path)
    references = [path]
    if spec["schema_version"] == 1:
        references.append((path.parent / raw["model"]).resolve())
        force_field = spec["model"]["force_field"]
        expected_library = None
    else:
        references.extend((path.parent / item["model"]).resolve() for item in raw["components"])
        references.extend((path.parent / raw[key]).resolve() for key in ("protocol", "interaction_bundle"))
        force_field = spec["interaction_bundle"]["force_field"]
        expected_library = spec["interaction_bundle"]["library_hash"]
    library = Path(engine["data_prefix"]) / "share/gromacs/top"
    library_hash = library_identity(library, force_field)
    if expected_library is not None and expected_library != library_hash:
        raise ValueError("Installed library differs from the declared experiment bundle")
    library_files = inventory(library, [force_field])
    library_files.update({name: sha256(library / name) for name in LIBRARY_FILES})
    return dict(experiment=str(path), schema_version=spec["schema_version"], spec_hash=identity,
                documents={str(item): sha256(item) for item in sorted(set(references))},
                assets={name: dict(source=str(source), sha256=sha256(source))
                        for name, source in sorted(sources.items())},
                library=dict(root=str(library), sha256=library_hash, files=library_files),
                note="Library inventory includes the full frozen tree, not only active includes.")


def main():
    """Print JSON identities for explicit experiment paths; never construct or modify a Run."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiments", type=Path, nargs="+")
    parser.add_argument("--gmx", default="gmx")
    args = parser.parse_args()
    engine = engine_info(args.gmx)
    result = dict(engine=engine, experiments=[audit_experiment(path, engine) for path in args.experiments])
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
