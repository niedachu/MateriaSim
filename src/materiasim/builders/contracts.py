"""Validate a native builder's typed handoff before publishing a ready Run."""

from materiasim.specs.composition import declared_counts
from materiasim.storage import read_json, verify_hashes


def validate_result(root, spec, result):
    """Require persisted mapping, requested counts and typed artifacts to match the returned result."""
    if result.mapping != read_json(root / "build/atom_mapping.json"):
        raise ValueError("Builder mapping differs from its persisted handoff")
    if result.system != read_json(root / "build/resolved_system.json"):
        raise ValueError("Builder system differs from its persisted handoff")
    if result.system["engine"] != spec["interaction_bundle"]["engine"]:
        raise ValueError("Builder engine differs from the selected model bundle")
    for key in ("counts", "atom_count", "charge_e", "box_nm"):
        if result.mapping[key] != result.system[key]:
            raise ValueError(f"Builder system/mapping mismatch: {key}")
    for name, count in declared_counts(spec).items():
        if result.mapping["counts"].get(name) != count:
            raise ValueError("Builder changed an explicitly requested component count")
    for role in ("coordinates", "topology", "mapping"):
        artifact = result.system[role]
        if role != "mapping" and not artifact["format"]:
            raise ValueError("Builder artifact format is missing")
        verify_hashes(root, {artifact["path"]: artifact["sha256"]})
