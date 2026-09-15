"""Engine-neutral v3 document shapes; backend applicability is checked by workflows."""

from copy import deepcopy

from materiasim.specs.schema import fields, identifier, integer, number
from materiasim.specs.analysis import analysis_requests
from materiasim.storage import content_hash, sha256


def digest(value, label):
    """Require a lowercase SHA-256 identity, without interpreting scientific suitability."""
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label}: SHA-256 required")


def profile_check(value):
    """Validate the currently consumed local CPU execution contract and finite ceilings."""
    if isinstance(value, dict) and type(value.get("contract_version")) is int and value["contract_version"] in (2, 3):
        from materiasim.specs.execution import validate_profile
        return validate_profile(value)
    fields(value, ("contract_version", "device", "threads", "max_wall_seconds", "total_wall_seconds",
                   "max_attempts", "checkpoint_interval_minutes"), "execution_profile")
    integer(value["contract_version"], 1, 1, "profile contract_version")
    if value["device"] != "cpu":
        raise ValueError("Only explicit CPU execution is implemented; GPU cannot fall back silently")
    integer(value["threads"], 1, 8, "threads")
    number(value["max_wall_seconds"], 1, 600, "max_wall_seconds")
    number(value["total_wall_seconds"], 1, 1800, "total_wall_seconds")
    integer(value["max_attempts"], 1, 8, "max_attempts")
    number(value["checkpoint_interval_minutes"], .001, 10, "checkpoint_interval_minutes")
    if value["total_wall_seconds"] < value["max_wall_seconds"]:
        raise ValueError("Total execution budget cannot be smaller than one attempt")
    if value["total_wall_seconds"] < 26:
        raise ValueError("Total execution budget must reserve checkpoint/exit grace plus useful work")


def default_profile():
    """Return the explicit migration policy for the existing two-thread engineering examples."""
    return dict(contract_version=1, device="cpu", threads=2, max_wall_seconds=180,
                total_wall_seconds=360, max_attempts=2, checkpoint_interval_minutes=.01)


def file_records(items, names):
    """Validate typed logical assets and collect globally unique names across the experiment."""
    if not isinstance(items, list):
        raise ValueError("Asset files must be a list")
    for item in items:
        fields(item, ("name", "format", "sha256"), "asset")
        identifier(item["name"], "asset.name")
        identifier(item["format"], "asset.format")
        digest(item["sha256"], "asset.sha256")
        if item["name"] in names:
            raise ValueError("Duplicate asset name")
        names.add(item["name"])


def models_check(components, names):
    """Validate component counts/roles and model metadata independently of native syntax."""
    if not isinstance(components, list) or not components:
        raise ValueError("At least one explicit component is required")
    seen = set()
    for item in components:
        fields(item, ("id", "model", "count", "role"), "component")
        identifier(item["id"], "component.id")
        integer(item["count"], 1, 2147483646, "component.count")
        if item["id"] in seen:
            raise ValueError("Duplicate component identity")
        seen.add(item["id"])
        if item["role"] not in ("unspecified", "solute", "solvent", "material"):
            raise ValueError("Unknown component role")
        model = item["model"]
        fields(model, ("id", "component_id", "resolution", "provenance", "coordinates", "topology", "files"), "model")
        for key in ("id", "component_id", "coordinates", "topology"):
            identifier(model[key], "model." + key)
        if model["component_id"] != item["id"]:
            raise ValueError("Model/component identity mismatch")
        if model["resolution"] not in ("unspecified", "atomistic", "coarse_grained"):
            raise ValueError("Unknown model resolution")
        provenance = model["provenance"]
        fields(provenance, ("status", "references"), "model provenance")
        if provenance["status"] not in ("not_provided", "declared") or not isinstance(provenance["references"], list):
            raise ValueError("Invalid model provenance")
        if (provenance["status"] == "declared") != bool(provenance["references"]):
            raise ValueError("Declared provenance requires references; missing provenance cannot invent references")
        if any(not isinstance(ref, str) or not ref.strip() for ref in provenance["references"]):
            raise ValueError("Empty model provenance reference")
        file_records(model["files"], names)
        own = {asset["name"] for asset in model["files"]}
        if not {model["coordinates"], model["topology"]} <= own:
            raise ValueError("Model coordinate/topology references must name its own assets")


def stages_check(protocol, engine, names, purpose="engineering_smoke"):
    """Validate linear handoff, explicit physical declarations and role requirements without MDP parsing."""
    fields(protocol, ("id", "files", "stages"), "protocol")
    identifier(protocol["id"], "protocol.id")
    file_records(protocol["files"], names)
    own = {item["name"] for item in protocol["files"]}
    stages = protocol["stages"]
    if not isinstance(stages, list) or not stages:
        raise ValueError("Explicit protocol stages required")
    previous, seen = None, set()
    for stage in stages:
        keys = ("id", "type", "engine_parameters", "steps", "input", "velocities", "seed",
                "time_origin_ps", "step_origin", "physics", "outputs")
        fields(stage, keys + (("sampling",) if purpose != "engineering_smoke" else ()), "stage")
        if purpose != "engineering_smoke":
            fields(stage["sampling"], ("contract_version", "log_steps", "energy_steps", "trajectory_steps"), "sampling")
            integer(stage["sampling"]["contract_version"], 1, 1, "sampling version")
            for key in ("log_steps", "energy_steps", "trajectory_steps"):
                integer(stage["sampling"][key], 1, stage["steps"], key)
        identifier(stage["id"], "stage.id")
        if stage["id"] in seen:
            raise ValueError("Duplicate stage ID")
        seen.add(stage["id"])
        if stage["type"] not in ("minimization", "dynamics"):
            raise ValueError("Unsupported stage type")
        integer(stage["steps"], 1, 2147483646, "steps")
        integer(stage["step_origin"], 0, 2147483646, "step_origin")
        number(stage["time_origin_ps"], 0, 1e12, "time_origin_ps")
        fields(stage["input"], ("stage_id", "kind"), "stage.input")
        if stage["input"]["stage_id"] != previous or stage["input"]["kind"] not in ("coordinates", "checkpoint"):
            raise ValueError("Stage must explicitly consume the immediately preceding state")
        if stage["velocities"] not in ("none", "generate", "inherit"):
            raise ValueError("Unknown velocity policy")
        if stage["velocities"] == "generate":
            integer(stage["seed"], 1, 2147483646, "seed")
        elif stage["seed"] is not None:
            raise ValueError("Only velocity generation accepts a seed")
        fields(stage["engine_parameters"], ("engine", "asset"), "engine_parameters")
        if stage["engine_parameters"]["engine"] != engine or stage["engine_parameters"]["asset"] not in own:
            raise ValueError("Stage engine parameters must reference a declared protocol asset for this engine")
        fields(stage["physics"], ("timestep_ps", "temperature_k", "pressure_bar", "force_tolerance_kj_mol_nm"), "physics")
        for key in ("timestep_ps", "force_tolerance_kj_mol_nm"):
            if stage["physics"][key] is not None:
                number(stage["physics"][key], 1e-15, 1e12, key)
        for key in ("temperature_k", "pressure_bar"):
            if not isinstance(stage["physics"][key], list):
                raise ValueError("Temperature/pressure must use explicit component lists")
            for value in stage["physics"][key]:
                number(value, 0 if key == "temperature_k" else -1e12, 1e12, key)
        if (not isinstance(stage["outputs"], list) or not stage["outputs"] or
                len(stage["outputs"]) != len(set(stage["outputs"]))):
            raise ValueError("Unique output roles required")
        for role in stage["outputs"]:
            identifier(role, "output role")
        previous = stage["id"]


def document_fields(spec):
    """Check unchanged smoke shape or the explicitly versioned non-smoke review extension."""
    keys = ("schema_version", "id", "purpose", "components", "interaction_bundle", "scenario",
            "protocol", "analysis_requests", "execution_profile")
    fields(spec, keys + (("purpose_policy",) if isinstance(spec, dict) and
                        spec.get("purpose") in ("model_validation", "production") else ()), "v3 experiment")


def validate_document(spec):
    """Validate an already resolved v3 document; backend restrictions are intentionally separate."""
    document_fields(spec)
    integer(spec["schema_version"], 3, 3, "schema_version")
    identifier(spec["id"], "experiment.id")
    if spec["purpose"] not in ("engineering_smoke", "model_validation", "production"):
        raise ValueError("Unknown experiment purpose")
    names = set()
    models_check(spec["components"], names)
    bundle = spec["interaction_bundle"]
    fields(bundle, ("id", "engine", "model_hashes", "engine_parameters", "validation_scope", "files"), "bundle")
    identifier(bundle["id"], "bundle.id")
    identifier(bundle["engine"], "bundle.engine")
    if bundle["model_hashes"] != {c["id"]: content_hash(c["model"]) for c in spec["components"]}:
        raise ValueError("Interaction bundle must cover exact model identities")
    if not isinstance(bundle["engine_parameters"], dict) or not isinstance(bundle["validation_scope"], str):
        raise ValueError("Explicit bundle parameters/scope required")
    file_records(bundle["files"], names)
    scenario = spec["scenario"]
    fields(scenario, ("kind", "boundary", "builder"), "scenario")
    identifier(scenario["kind"], "scenario.kind")
    fields(scenario["boundary"], ("vectors_nm", "periodic"), "boundary")
    vectors, periodic = scenario["boundary"]["vectors_nm"], scenario["boundary"]["periodic"]
    if not isinstance(vectors, list) or len(vectors) != 3:
        raise ValueError("Three box vectors in nm required")
    for vector in vectors:
        if not isinstance(vector, list) or len(vector) != 3:
            raise ValueError("Each box vector requires three coordinates")
        for value in vector:
            number(value, -1e9, 1e9, "box vector nm")
    if not isinstance(periodic, list) or len(periodic) != 3 or any(type(v) is not bool for v in periodic):
        raise ValueError("Three explicit periodic-axis booleans required")
    fields(scenario["builder"], ("id", "config"), "builder")
    identifier(scenario["builder"]["id"], "builder.id")
    if not isinstance(scenario["builder"]["config"], dict):
        raise ValueError("Builder config must be an object")
    if "structure" in scenario["builder"]["config"]:
        file_records(scenario["builder"]["config"]["structure"]["files"], names)
    stages_check(spec["protocol"], bundle["engine"], names, spec["purpose"])
    if "purpose_policy" in spec:
        file_records(spec["purpose_policy"]["files"], names)
    analysis_requests(spec["analysis_requests"], spec["protocol"]["stages"])
    profile_check(spec["execution_profile"])


def asset_documents(spec):
    """Return the actual typed-asset owners, including an explicitly supplied prebuilt structure."""
    owners = [c["model"] for c in spec["components"]] + [spec["interaction_bundle"], spec["protocol"]]
    config = spec["scenario"]["builder"]["config"]
    if "structure" in config:
        owners.append(config["structure"])
    if "purpose_policy" in spec:
        owners.append(spec["purpose_policy"])
    return owners


def resolve_spec(path, document):
    """Resolve self-contained v3 asset paths, hash bytes and return location-free content and sources."""
    spec, sources = deepcopy(document), {}
    # Reject top-level shape before walking asset owners to avoid guessing a document dialect.
    document_fields(spec)
    try:
        owners = asset_documents(spec)
    except (KeyError, TypeError) as error:
        raise ValueError("Malformed v3 component/scenario asset owners") from error
    for owner in owners:
        if not isinstance(owner, dict) or not isinstance(owner.get("files"), list):
            raise ValueError("Each model/bundle/protocol/structure must declare an asset list")
        for item in owner["files"]:
            fields(item, ("name", "format", "sha256", "source"), "source asset")
            value = item.pop("source")
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Asset source path is required")
            source = (path.parent / value).resolve()
            if sha256(source) != item["sha256"]:
                raise ValueError("Source asset hash mismatch")
            sources[item["name"]] = source
    validate_document(spec)
    return spec, sources, content_hash(spec)
