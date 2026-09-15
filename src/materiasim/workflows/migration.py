"""Read-only experiment conversion and provenance capture for newly created v3 Runs."""

from pathlib import Path

from materiasim.engines.gromacs.migration import upgrade
from materiasim.specs.v3 import asset_documents
from materiasim.storage import content_hash, read_json, sha256
from materiasim.workflows.validation import load_spec, validate_resolved


def source_documents(path):
    """Return the original experiment/model/bundle/protocol documents whose bytes define provenance."""
    path = Path(path).resolve()
    raw = read_json(path)
    if not isinstance(raw, dict) or type(raw.get("schema_version")) is not int or raw["schema_version"] not in (1, 2, 3):
        raise ValueError("Unsupported experiment source schema")
    documents = {"experiment.json": path}
    if raw["schema_version"] == 2:
        try:
            for key in ("protocol", "interaction_bundle"):
                documents[key + ".json"] = (path.parent / raw[key]).resolve()
            for index, component in enumerate(raw["components"]):
                documents[f"model-{index}.json"] = (path.parent / component["model"]).resolve()
        except (KeyError, TypeError) as error:
            raise ValueError("Malformed v2 source document references") from error
    return documents


def load_executable(path):
    """Resolve v2/v3 into one executable v3 contract, returning sources, identity and conversion evidence."""
    documents = source_documents(path)
    before = {name: dict(path=str(source), sha256=sha256(source)) for name, source in documents.items()}
    spec, sources, source_hash = load_spec(path)
    version = spec["schema_version"]
    if version == 1:
        raise ValueError("v1 is read-only; use an explicit v2 or v3 experiment")
    if version == 2:
        spec = upgrade(spec, sources)
        validate_resolved(spec, sources)
    if any(sha256(documents[name]) != record["sha256"] for name, record in before.items()):
        raise ValueError("Source documents changed during resolution")
    report = dict(contract_version=1, source_schema=version, resolved_schema=3,
                  source_resolved_hash=source_hash, resolved_hash=content_hash(spec), documents=before,
                  transformations=(["typed native assets", "explicit periodic box vectors and builder",
                    "physical declarations extracted from native templates", "explicit CPU execution policy",
                    "missing model provenance/resolution/role kept unspecified"] if version == 2 else []))
    return spec, sources, content_hash(spec), report


def portable_document(spec, sources):
    """Restore explicit asset source paths in an independently writable v3 input document."""
    from copy import deepcopy
    value = deepcopy(spec)
    for owner in asset_documents(value):
        for item in owner["files"]:
            item["source"] = str(sources[item["name"]])
    return value
