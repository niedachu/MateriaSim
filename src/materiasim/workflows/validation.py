"""Read-only composition of format parsing and actual component applicability checks."""

from materiasim.analysis.registry import validate_requests
from materiasim.engines.registry import get_engine
from materiasim.errors import MateriaSimError
from materiasim.scenarios.registry import get_scenario
from materiasim.specs.schema import read_spec


def validate_resolved(spec, sources):
    """Validate actual engine, assembly and analysis compatibility without creating a Run."""
    if spec["schema_version"] == 3:
        from materiasim.specs.v3 import validate_document
        validate_document(spec)
    engine = get_engine(spec["interaction_bundle"]["engine"])
    if spec["purpose"] not in engine.purposes:
        raise MateriaSimError("UNSUPPORTED_COMBINATION", "Purpose is not implemented for this engine", field="purpose")
    scenario = get_scenario(spec["scenario"]["kind"])
    if engine.id not in scenario.engines:
        raise MateriaSimError("UNSUPPORTED_COMBINATION", "Scenario does not support the selected engine", field="scenario")
    engine.validate(spec, sources)
    from materiasim.specs.purpose import validate_policy
    validate_policy(spec, sources)
    scenario.validate(spec, sources)
    validate_requests(spec["analysis_requests"], spec["protocol"]["stages"])


def load_spec(path):
    """Resolve versioned files and verify applicable components, returning spec, sources and hash."""
    spec, sources, identity = read_spec(path)
    if spec["schema_version"] != 1:
        validate_resolved(spec, sources)
    return spec, sources, identity
