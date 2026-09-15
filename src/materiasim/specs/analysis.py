"""Shared optional analysis requests, independent of Experiment schema version."""

from materiasim.specs.schema import fields, identifier, number


def validate_contacts(config):
    """Require explicit component IDs and a finite contact cutoff measured in nm."""
    fields(config, ("component_a", "component_b", "cutoff_nm"), "component contacts")
    for key in ("component_a", "component_b"):
        identifier(config[key], key)
    number(config["cutoff_nm"], .01, 1.0, "cutoff_nm")


def analysis_requests(requests, stages):
    """Validate optional request structure and stage links; method checks belong to registration."""
    if not isinstance(requests, list):
        raise ValueError("analysis_requests must be a list; [] disables analysis")
    ids = set()
    for request in requests:
        fields(request, ("id", "kind", "stage_id", "config"), "analysis request")
        identifier(request["id"], "analysis.id")
        if request["id"] in ids:
            raise ValueError("Duplicate analysis ID")
        ids.add(request["id"])
        if not any(stage["id"] == request["stage_id"] and stage["type"] == "dynamics" for stage in stages):
            raise ValueError("Analysis must reference a declared dynamics stage")
        identifier(request["kind"], "analysis.kind")
        if not isinstance(request["config"], dict):
            raise ValueError("Analysis config must be an object")
    return requests
