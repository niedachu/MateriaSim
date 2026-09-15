"""Current periodic molecular-packing scenario and its explicit GROMACS restrictions."""

from materiasim.builders.regions import validate_regions
from materiasim.engines.gromacs.parameters import collect_models
from materiasim.engines.gromacs.mdp import mdp_values
from materiasim.specs.schema import fields, integer, number
from materiasim.specs.composition import declared_counts


def validate_packing(spec, sources):
    """Check explicit nm regions/counts and candidate models before creating a packing Run."""
    scenario = spec["scenario"]
    fields(scenario, ("kind", "box_nm", "seed", "tolerance_nm", "max_iterations", "solvent", "groups"), "packing")
    integer(scenario["seed"], 1, 2147483646, "packing seed")
    integer(scenario["max_iterations"], 1, 500, "packing iterations")
    number(scenario["tolerance_nm"], 0.15, 0.5, "packing tolerance_nm")
    fields(scenario["solvent"], ("kind",), "solvent")
    if scenario["solvent"]["kind"] not in ("tip3p_fill", "none"):
        raise ValueError("Only explicit TIP3P fill or no solvent is implemented")
    validate_regions(declared_counts(spec), scenario["groups"], scenario["box_nm"])
    if "model_hashes" not in spec["interaction_bundle"]:
        raise ValueError("Packing requires an explicit multi-model bundle")
    collect_models(spec, sources)
    if scenario["solvent"]["kind"] == "none":
        for stage in spec["protocol"]["stages"]:
            values = mdp_values(sources[stage["mdp"]])
            if stage["type"] == "dynamics" and values.get("pcoupl") != "no":
                raise ValueError("Dry periodic engineering regression requires fixed volume, pcoupl=no")
        if any(request["kind"] == "hydration_contacts" for request in spec["analysis_requests"]):
            raise ValueError("No-water scenario cannot request hydration")
