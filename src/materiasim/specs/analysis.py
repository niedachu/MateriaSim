"""Shared optional analysis requests, independent of Experiment schema version."""

from materiasim.specs.schema import fields, identifier, validate_analysis


def analysis_requests(requests, stages):
    """Validate optional hydration tasks against concrete dynamics stage IDs."""
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
        if request["kind"] == "hydration_contacts":
            validate_analysis(request["config"])
        elif request["kind"] == "component_contacts":
            from materiasim.analysis.component_contacts import validate_contacts
            validate_contacts(request["config"])
        else:
            raise ValueError("Unsupported analysis kind")
    return requests
