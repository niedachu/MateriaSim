"""Validate the deliberately narrow, versioned engineering-smoke specification."""

import math
import re
from pathlib import Path

from .files import content_hash, read_json, sha256

STAGES = ("em", "nvt", "npt", "prod")


def fields(value, expected, label):
    """Require an object with exactly the declared keys at a public boundary."""
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{label}: expected fields {sorted(expected)}")


def integer(value, lower, upper, label):
    """Require a bounded integer, excluding JSON booleans."""
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{label}: integer required in [{lower}, {upper}]")


def number(value, lower, upper, label):
    """Require a finite bounded numeric value, excluding booleans."""
    if type(value) not in (int, float) or not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError(f"{label}: finite number required in [{lower}, {upper}]")


def identifier(value, label):
    """Require a portable identifier usable as a file or component name."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", value):
        raise ValueError(f"{label}: invalid identifier")


def validate_analysis(analysis):
    """Validate explicitly provisional hydration selections and cutoffs in nm."""
    fields(analysis, ("water_oxygen_selection", "sites"), "analysis")
    if not isinstance(analysis["water_oxygen_selection"], str) or not analysis["water_oxygen_selection"].strip():
        raise ValueError("Water selection is empty")
    if not isinstance(analysis["sites"], dict) or not analysis["sites"]:
        raise ValueError("At least one hydration site is required")
    for name, site in analysis["sites"].items():
        identifier(name, "site")
        if name in ("time_ps", "union"):
            raise ValueError("Site name collides with reserved analysis output columns")
        fields(site, ("selection", "mode", "cutoff_nm"), name)
        if site["mode"] != "atoms":
            raise ValueError("v1 supports atom-site distances only, not centroid geometry")
        if not isinstance(site["selection"], str) or not site["selection"].strip():
            raise ValueError(f"Empty selection: {name}")
        number(site["cutoff_nm"], 0.01, 1.0, name)


def load_model(path):
    """Resolve and hash every source declared by a local model card."""
    path = Path(path).resolve()
    model = read_json(path)
    fields(model, ("id", "force_field", "coordinates", "topology", "components", "files"), "model")
    identifier(model["id"], "model.id")
    identifier(model["coordinates"], "model.coordinates")
    identifier(model["topology"], "model.topology")
    identifier(model["force_field"], "force_field")
    if not model["force_field"].endswith(".ff"):
        raise ValueError("force_field must name a GROMACS .ff directory")
    if not isinstance(model["components"], dict) or not model["components"]:
        raise ValueError("Explicit initial component counts are required")
    for name, count in model["components"].items():
        identifier(name, "component")
        integer(count, 1, 100, "component count")
    if "SOL" in model["components"]:
        raise ValueError("Initial structure must not contain solvent; v1 adds SOL water")
    if not isinstance(model["files"], list) or not model["files"]:
        raise ValueError("Model files are required")
    sources = {}
    for item in model["files"]:
        fields(item, ("name", "source", "sha256"), "model file")
        name = item["name"]
        identifier(name, "asset name")
        if name in sources:
            raise ValueError(f"Duplicate asset name: {name}")
        if not isinstance(item["source"], str):
            raise ValueError("Asset source must be a path")
        source = (path.parent / item["source"]).resolve()
        if sha256(source) != item["sha256"]:
            raise ValueError(f"Source hash mismatch: {source}")
        sources[name] = source
    for name in (model["coordinates"], model["topology"], *(f"{stage}.mdp" for stage in STAGES)):
        if name not in sources:
            raise ValueError(f"Required asset not declared: {name}")
    return model, sources


def load_spec(path):
    """Read v1 for inspection, or resolve executable v2 with separate model/protocol."""
    path = Path(path).resolve()
    spec = read_json(path)
    if isinstance(spec, dict) and type(spec.get("schema_version")) is int and spec["schema_version"] == 2:
        from .config_v2 import resolve_spec
        return resolve_spec(path, spec)
    fields(spec, ("schema_version", "id", "purpose", "model", "box_nm", "seed", "steps", "analysis"), "experiment")
    if type(spec["schema_version"]) is not int or spec["schema_version"] != 1:
        raise ValueError("Unsupported schema_version")
    if spec["purpose"] != "engineering_smoke":
        raise ValueError("v1 only supports engineering_smoke, not formal research")
    identifier(spec["id"], "experiment.id")
    if not isinstance(spec["box_nm"], list) or len(spec["box_nm"]) != 3:
        raise ValueError("box_nm must contain three orthorhombic lengths")
    for length in spec["box_nm"]:
        number(length, 3.0, 6.0, "box_nm")
    integer(spec["seed"], 1, 2147483646, "seed")
    fields(spec["steps"], STAGES, "steps")
    for name, steps in spec["steps"].items():
        integer(steps, 1, 5000 if name == "em" else 2000, name)
    validate_analysis(spec["analysis"])
    if not isinstance(spec["model"], str):
        raise ValueError("model must reference a model card")
    model, sources = load_model(path.parent / spec["model"])
    # Keep source locations as provenance, not as scientific content identity.
    model = dict(model, files=[{"name": item["name"], "sha256": item["sha256"]} for item in model["files"]])
    resolved = dict(spec, model=model)
    return resolved, sources, content_hash(resolved)
