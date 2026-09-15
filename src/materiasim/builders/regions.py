"""Exact instance counts and orthorhombic nm-region validation."""

from materiasim.specs.schema import fields, identifier, integer, number


def validate_regions(counts_requested, groups, box_nm):
    """Check group IDs, positive counts and nm bounds against resolved composition; return None."""
    if not isinstance(groups, list) or not 1 <= len(groups) <= 16:
        raise ValueError("Expected 1–16 instance groups")
    counts, seen = dict.fromkeys(counts_requested, 0), set()
    for group in groups:
        fields(group, ("id", "component_id", "count", "min_nm", "max_nm"), "instance group")
        identifier(group["id"], "group id")
        if group["id"] in seen or group["id"] == "solvent_fill" or group["component_id"] not in counts:
            raise ValueError("Duplicate group, reserved solvent_fill group, or unknown component")
        seen.add(group["id"])
        integer(group["count"], 1, 100, "group count")
        counts[group["component_id"]] += group["count"]
        if any(not isinstance(group[key], list) or len(group[key]) != 3 for key in ("min_nm", "max_nm")):
            raise ValueError("Region requires three minimum/maximum coordinates in nm")
        for lower, upper, length in zip(group["min_nm"], group["max_nm"], box_nm):
            number(lower, 0, length, "region minimum")
            number(upper, 0, length, "region maximum")
            if lower >= upper:
                raise ValueError("Region minimum must be below maximum")
    if counts != counts_requested:
        raise ValueError("Instance-group totals differ from declared component counts")
