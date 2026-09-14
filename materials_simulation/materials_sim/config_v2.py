"""Executable v2 contracts for fixed molecular structures and explicit water-box experiments."""

from pathlib import Path

from .files import content_hash, read_json, sha256
from .schema import fields, identifier, integer, number, validate_analysis
from .protocol import validate_stages


def reference(parent, value, label):
    """Resolve an explicit local configuration path relative to its owning document."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: nonempty local path required")
    return (parent / value).resolve()


def assets(document, parent, sources):
    """Verify and flatten declared assets into sources, returning location-free records."""
    if not isinstance(document, list) or not document:
        raise ValueError("Nonempty asset list required")
    result = []
    for item in document:
        fields(item, ("name", "source", "sha256"), "asset")
        name = item["name"]
        identifier(name, "asset name")
        if name in sources:
            raise ValueError(f"Duplicate asset: {name}")
        source = reference(parent, item["source"], "asset source")
        if sha256(source) != item["sha256"]:
            raise ValueError(f"Source hash mismatch: {source}")
        sources[name] = source
        result.append(dict(name=name, sha256=item["sha256"]))
    return result


def model_card(path, sources):
    """Resolve a prebuilt molecular model; it contains no simulation protocol or counts."""
    model = read_json(path)
    fields(model, ("id", "component_id", "coordinates", "topology", "files"), "model")
    for key in ("id", "component_id", "coordinates", "topology"):
        identifier(model[key], "model." + key)
    frozen = assets(model["files"], path.parent, sources)
    own_names = {item["name"] for item in frozen}
    if any(name.endswith(".mdp") for name in own_names):
        raise ValueError("MDP belongs to the protocol, not the model")
    if any(model[key] not in own_names for key in ("coordinates", "topology")):
        raise ValueError("Model coordinates/topology must be declared assets")
    return dict(model, files=frozen)


def interaction_bundle(path, components, sources):
    """Require exact coverage of all component models and frozen global parameter assets."""
    bundle = read_json(path)
    common = ("id", "engine", "force_field", "library_hash", "water_model", "validation_scope")
    if "model_hash" in bundle:
        # M1 example files are real retained callers, not a second execution engine.
        fields(bundle, (*common, "model_hash"), "interaction_bundle")
        if len(components) != 1 or bundle["model_hash"] != content_hash(components[0]["model"]):
            raise ValueError("InteractionBundle does not cover this exact model")
    else:
        fields(bundle, (*common, "model_hashes", "files"), "interaction_bundle")
        expected = {item["id"]: content_hash(item["model"]) for item in components}
        if bundle["model_hashes"] != expected:
            raise ValueError("InteractionBundle must cover exactly all component model hashes")
        bundle = dict(bundle, files=assets(bundle["files"], path.parent, sources))
    identifier(bundle["id"], "bundle.id")
    identifier(bundle["force_field"], "force_field")
    if bundle["engine"] != "gromacs" or not bundle["force_field"].endswith(".ff"):
        raise ValueError("Only a native GROMACS .ff bundle is implemented")
    if bundle["water_model"] != "tip3p" or bundle["validation_scope"] != "engineering_only":
        raise ValueError("Only the existing engineering TIP3P bundle is implemented")
    for key in ("library_hash",):
        value = bundle[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"Invalid bundle {key}")
    return bundle


def resolve_components(document, parent, sources):
    """Load independent model cards and exact counts without creating molecular copies."""
    if not isinstance(document, list) or not 1 <= len(document) <= 8:
        raise ValueError("Expected 1–8 explicitly modeled components")
    resolved, seen = [], set()
    for component in document:
        fields(component, ("id", "model", "count"), "component")
        identifier(component["id"], "component.id")
        integer(component["count"], 1, 100, "component count")
        if component["id"] in seen or component["id"] == "SOL":
            raise ValueError("Duplicate component or reserved solvent identity")
        seen.add(component["id"])
        model = model_card(reference(parent, component["model"], "model"), sources)
        if component["id"] != model["component_id"]:
            raise ValueError("Component identity differs from model")
        resolved.append(dict(component, model=model))
    return resolved


def resolve_scenario(scenario, parent, sources):
    """Validate a water-box scenario and freeze explicitly supplied mixture coordinates/topology."""
    if not isinstance(scenario, dict) or "kind" not in scenario:
        raise ValueError("Explicit scenario kind required")
    if scenario["kind"] == "prebuilt_solute_water":
        fields(scenario, ("kind", "box_nm"), "scenario")
    elif scenario["kind"] == "prebuilt_mixture_water":
        fields(scenario, ("kind", "box_nm", "solvent_count", "structure"), "scenario")
        integer(scenario["solvent_count"], 1, 6000, "solvent_count")
        structure = scenario["structure"]
        fields(structure, ("coordinates", "topology", "files"), "prebuilt structure")
        frozen = assets(structure["files"], parent, sources)
        for key in ("coordinates", "topology"):
            identifier(structure[key], key)
            if structure[key] not in {item["name"] for item in frozen}:
                raise ValueError("Structure coordinate/topology must be its own declared asset")
        scenario = dict(scenario, structure=dict(structure, files=frozen))
    elif scenario["kind"] == "packed_liquid":
        fields(scenario, ("kind", "box_nm", "seed", "tolerance_nm", "max_iterations", "solvent", "groups"), "packing")
    else:
        raise ValueError("Scenario not implemented")
    if not isinstance(scenario["box_nm"], list) or len(scenario["box_nm"]) != 3:
        raise ValueError("box_nm requires three orthorhombic lengths")
    for length in scenario["box_nm"]:
        number(length, 3, 6, "box_nm")
    return scenario


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
            from .component_contacts import validate_contacts
            validate_contacts(request["config"])
        else:
            raise ValueError("Unsupported analysis kind")
    return requests


def resolve_spec(path, spec):
    """Resolve the current v2 subset and return content identity plus all source paths."""
    fields(spec, ("schema_version", "id", "purpose", "components", "interaction_bundle",
                  "scenario", "protocol", "analysis_requests"), "v2 experiment")
    identifier(spec["id"], "experiment.id")
    if spec["purpose"] != "engineering_smoke":
        raise ValueError("Only bounded engineering_smoke is implemented")
    if (isinstance(spec["scenario"], dict) and spec["scenario"].get("kind") == "prebuilt_solute_water"
            and (not isinstance(spec["components"], list) or len(spec["components"]) != 1)):
        raise ValueError("prebuilt_solute_water requires one component; multi-component assembly is not implemented")
    sources = {}
    components = resolve_components(spec["components"], path.parent, sources)
    bundle = interaction_bundle(reference(path.parent, spec["interaction_bundle"], "bundle"), components, sources)
    scenario = resolve_scenario(spec["scenario"], path.parent, sources)
    protocol_path = reference(path.parent, spec["protocol"], "protocol")
    protocol = read_json(protocol_path)
    fields(protocol, ("id", "files", "stages"), "protocol")
    identifier(protocol["id"], "protocol.id")
    protocol = dict(protocol, files=assets(protocol["files"], protocol_path.parent, sources))
    validate_stages(protocol["stages"], {item["name"]: sources[item["name"]] for item in protocol["files"]})
    requests = analysis_requests(spec["analysis_requests"], protocol["stages"])
    resolved = dict(spec, components=components, interaction_bundle=bundle, scenario=scenario,
                    protocol=protocol, analysis_requests=requests)
    if scenario["kind"] == "prebuilt_mixture_water":
        from .prebuilt import validate_prebuilt_sources
        validate_prebuilt_sources(resolved, sources)
    elif scenario["kind"] == "packed_liquid":
        from .assembly import validate_packing
        validate_packing(resolved, sources)
    return resolved, sources, content_hash(resolved)
