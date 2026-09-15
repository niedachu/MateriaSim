"""Identity checks for explicitly supplied multi-molecule structures, not automatic packing."""

import re

from materiasim.specs.composition import declared_counts
from materiasim.engines.gromacs.topology import gro_atoms, molecule_counts, section_rows


def structure_assets(spec):
    """Return the current scenario's declared coordinate/topology assets without inventing them."""
    if spec["scenario"]["kind"] == "prebuilt_solute_water":
        return spec["components"][0]["model"]
    return spec["scenario"]["structure"]


def molecular_definitions(path):
    """Read complete ordered molecule blocks for identity comparison after preprocessing."""
    definitions, current = {}, None
    for section, row in section_rows(path):
        if section in ("system", "molecules"):
            current = None
        elif section == "moleculetype":
            current = row[0]
            if current in definitions:
                raise ValueError("Duplicate molecule definition")
            definitions[current] = []
        if current is not None:
            definitions[current].append((section, row))
    return definitions


def validate_prebuilt_sources(spec, sources):
    """Require dry coordinates/counts/model order and direct unmodified model includes."""
    structure = structure_assets(spec)
    topology = sources[structure["topology"]]
    expected_counts = declared_counts(spec)
    if molecule_counts(topology) != expected_counts:
        raise ValueError("Prebuilt topology composition differs from experiment; no automatic assembly")
    if any(section not in ("system", "molecules") for section, _ in section_rows(topology)):
        raise ValueError("Prebuilt system topology must only include models and declare system/molecules")
    includes = re.findall(r'^\s*#include\s+"([^"]+)"', topology.read_text(), re.M)
    expected_atoms = []
    for component in spec["components"]:
        model = component["model"]
        if includes.count(model["topology"]) != 1:
            raise ValueError("Prebuilt topology must include each declared model exactly once")
        definitions = molecular_definitions(sources[model["topology"]])
        if set(definitions) != {component["id"]}:
            raise ValueError("Model must define exactly its declared molecule type")
        atoms = [row for section, row in definitions[component["id"]] if section == "atoms"]
        model_atoms, _ = gro_atoms(sources[model["coordinates"]])
        order = [(row[3], row[4]) for row in atoms]
        if [(atom["resname"], atom["name"]) for atom in model_atoms] != order:
            raise ValueError("Individual model coordinate/topology order mismatch")
        expected_atoms.extend(order * component["count"])
    # [molecules] order is physical atom order, not an unordered composition alone.
    if list(molecule_counts(topology)) != list(expected_counts):
        raise ValueError("Prebuilt molecule order differs from component list")
    actual, box = gro_atoms(sources[structure["coordinates"]])
    if [(atom["resname"], atom["name"]) for atom in actual] != expected_atoms:
        raise ValueError("Prebuilt coordinate atom order/count differs from declared models")
    if box != spec["scenario"]["box_nm"]:
        raise ValueError("Frozen prebuilt box differs from the experiment")


def verify_processed_models(spec, sources, processed):
    """Require native-preprocessed non-solvent molecule blocks to match model-card definitions."""
    actual = molecular_definitions(processed)
    for component in spec["components"]:
        expected = molecular_definitions(sources[component["model"]["topology"]])
        if actual.get(component["id"]) != expected[component["id"]]:
            raise ValueError("Preprocessed model differs from the frozen component definition")
