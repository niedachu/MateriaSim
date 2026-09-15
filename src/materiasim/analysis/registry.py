"""Actual analyzers and input contracts; no mandatory hydration workflow."""

from dataclasses import dataclass
from typing import Callable

from materiasim.analysis.hydration import hydration_contacts
from materiasim.analysis.component_contacts import component_contacts
from materiasim.errors import MateriaSimError
from materiasim.specs.analysis import analysis_requests, validate_contacts
from materiasim.specs.schema import validate_analysis
from materiasim.storage import read_json
from materiasim.analysis.observations import component_observations, hydration_observations


@dataclass(frozen=True)
class Analyzer:
    """Bind a real algorithm to its config validator and accepted input-role formats."""

    id: str
    validate: Callable
    calculate: Callable
    inputs: tuple
    result_files: tuple
    metrics: tuple
    observations: Callable


CONTACT_INPUTS = (("coordinates", "gro"), ("trajectory", "xtc"), ("mapping", "json"))


def calculate_hydration(inputs, config, output, identity):
    """Adapt role-indexed private files to the unchanged water-contact algorithm."""
    return hydration_contacts(inputs["coordinates"], inputs["trajectory"],
                              read_json(inputs["mapping"]), config, output, identity)


def calculate_components(inputs, config, output, identity):
    """Adapt role-indexed private files to the unchanged unique-molecule algorithm."""
    return component_contacts(inputs["coordinates"], inputs["trajectory"],
                              read_json(inputs["mapping"]), config, output, identity)


ANALYZERS = {
    "hydration_contacts": Analyzer("hydration_contacts", validate_analysis, calculate_hydration, CONTACT_INPUTS,
        (("hydration_counts.csv", "csv_sha256"),), (("mean_union_water_contacts", "water_molecules"),), hydration_observations),
    "component_contacts": Analyzer("component_contacts", validate_contacts, calculate_components, CONTACT_INPUTS,
        (("component_contacts.csv", "csv_sha256"),), (("mean_unique_molecule_pairs", "molecule_pairs"),), component_observations),
}


def get_analyzer(name):
    """Return an installed implementation descriptor, not a guarantee dependencies are present."""
    if name not in ANALYZERS:
        raise MateriaSimError("UNSUPPORTED_COMBINATION", f"Analysis not implemented: {name}", field="analysis.kind")
    return ANALYZERS[name]


def validate_requests(requests, stages):
    """Check request shape and stage references, then run each actual method's validator."""
    analysis_requests(requests, stages)
    for request in requests:
        get_analyzer(request["kind"]).validate(request["config"])
    return requests
