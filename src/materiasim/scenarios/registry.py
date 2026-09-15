"""Implemented scenario requirements and checks shared by discovery and validation."""

from dataclasses import dataclass
from typing import Callable

from materiasim.errors import MateriaSimError
from materiasim.engines.gromacs.prebuilt import validate_prebuilt_sources
from materiasim.scenarios.packed import validate_packing
from materiasim.engines.gromacs.specification import native_view


@dataclass(frozen=True)
class Scenario:
    """Describe an implemented assembly recipe, supported engines and its source validator."""

    id: str
    engines: tuple
    dependencies: tuple
    validate: Callable
    seed_fields: tuple = ()


def validate_solute(spec, sources):
    """Require the single explicitly modeled solute and its declared native input assets."""
    spec = native_view(spec)
    if len(spec["components"]) != 1:
        raise ValueError("prebuilt_solute_water requires one component; multi-component assembly is not implemented")
    model = spec["components"][0]["model"]
    if any(model[key] not in sources for key in ("coordinates", "topology")):
        raise ValueError("Prebuilt solute requires declared coordinates and topology")


def validate_mixture(spec, sources):
    """Validate explicit native prebuilt assets through the neutral scenario binding."""
    validate_prebuilt_sources(native_view(spec), sources)


def validate_packed(spec, sources):
    """Validate the declared packing recipe without changing the common workflow."""
    validate_packing(native_view(spec), sources)


SCENARIOS = {
    "prebuilt_solute_water": Scenario("prebuilt_solute_water", ("gromacs",), ("gromacs",), validate_solute),
    "prebuilt_mixture_water": Scenario("prebuilt_mixture_water", ("gromacs",), ("gromacs",), validate_mixture),
    "packed_liquid": Scenario("packed_liquid", ("gromacs",), ("gromacs", "packmol>=21.1.0"), validate_packed,
                              (("packing", "seed"),)),
}


def get_scenario(name):
    """Return a real assembly recipe or a structured unsupported-scenario error."""
    if name not in SCENARIOS:
        raise MateriaSimError("UNSUPPORTED_COMBINATION", f"Scenario not implemented: {name}", field="scenario.kind")
    return SCENARIOS[name]
