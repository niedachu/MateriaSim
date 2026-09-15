"""Role-indexed analysis input resolution and versioned result envelopes."""

from materiasim.runtime.records import stage_artifact
from materiasim.storage import contained


def resolve_inputs(root, spec, stage_id, analyzer):
    """Resolve the requested sealed formats before output creation; never manufacture missing data."""
    result = {}
    for role, kind in analyzer.inputs:
        if role == "mapping":
            if kind != "json":
                raise ValueError("Unsupported atom mapping format")
            path = contained(root, "build/atom_mapping.json")
            if not path.is_file():
                raise ValueError("Missing atom mapping")
        else:
            path = stage_artifact(root, spec, stage_id, role, expected_format=kind)
        result[role] = (path, f"{role}.{kind}")
    return result


def result_envelope(report, request, identity):
    """Attach common source/method metadata while retaining each algorithm's numerical report."""
    if report["run_id"] != identity["run_id"] or report["spec_hash"] != identity["spec_hash"]:
        raise ValueError("Analysis result refers to a different source")
    return dict(contract_version=1, method=request["kind"], source_run_id=identity["run_id"],
                source_spec_hash=identity["spec_hash"], request_hash=identity["request_hash"],
                scientific_quality=report["scientific_quality"],
                time_unit="ps", frames=report["frames"], time_range_ps=report["time_range_ps"],
                method_versions=report["versions"])
