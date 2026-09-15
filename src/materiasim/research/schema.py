"""Bounded research definitions and declared-variable comparability checks."""

from copy import deepcopy
from pathlib import Path

from materiasim.storage import content_hash, read_json, sha256
from materiasim.specs.schema import fields, identifier, integer, load_spec
from materiasim.engines.gromacs.mdp import validate_protocol
from materiasim.scenarios.packed import validate_packing


def nonempty(value, label):
    """Require a nonempty explanatory string at a research input boundary."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: nonempty text required")


def limits_check(limits):
    """Validate serial CPU smoke ceilings; times include separately reserved exit grace."""
    bounds = dict(max_tasks=(1, 16), concurrency=(1, 1), threads=(1, 8),
                  max_attempts=(1, 2), execution_seconds=(1, 180),
                  build_seconds=(1, 600), analysis_seconds=(1, 120),
                  total_seconds=(30, 1800), storage_bytes=(1048576, 1073741824))
    fields(limits, bounds, "limits")
    for name, (low, high) in bounds.items():
        integer(limits[name], low, high, "limits." + name)


def definition_check(value):
    """Validate research metadata and finite explicit cases, returning no runtime state."""
    fields(value, ("schema_version", "id", "revision", "question", "hypothesis", "purpose",
                   "baseline_case", "varied_factors", "controlled_factors", "observables",
                   "decision_rules", "cases", "limits", "sources"), "research")
    integer(value["schema_version"], 1, 1, "research schema_version")
    integer(value["revision"], 1, 100000, "research revision")
    identifier(value["id"], "research id")
    if value["purpose"] != "engineering_smoke":
        raise ValueError("Research v1 supports engineering_smoke only")
    for name in ("question", "hypothesis", "decision_rules"):
        nonempty(value[name], name)
    for name in ("controlled_factors", "sources"):
        if not isinstance(value[name], list) or not value[name]:
            raise ValueError(f"{name}: nonempty list required")
        for item in value[name]:
            nonempty(item, name)
    varied = value["varied_factors"]
    if (not isinstance(varied, list) or not varied or any(
            item not in ("component_counts", "scenario") for item in varied) or len(set(varied)) != len(varied)):
        raise ValueError("varied_factors supports unique component_counts/scenario entries")
    if value["observables"] != [dict(metric="mean_unique_molecule_pairs", unit="molecule_pairs")]:
        raise ValueError("Research v1 comparison supports explicit raw component-contact means only")
    limits_check(value["limits"])
    if not isinstance(value["cases"], list) or not 2 <= len(value["cases"]) <= value["limits"]["max_tasks"]:
        raise ValueError("Expected 2 or more explicitly bounded cases")


def projection(spec, varied):
    """Remove only declared variables and repeat seeds; all other content must match."""
    result = deepcopy(spec)
    result.pop("id")
    result["scenario"].pop("seed", None)
    for stage in result["protocol"]["stages"]:
        if stage["velocities"] == "generate":
            stage["seed"] = "repeat_seed"
    if "component_counts" in varied:
        for component in result["components"]:
            component.pop("count")
        for group in result["scenario"].get("groups", []):
            group.pop("count")
    if "scenario" in varied:
        result.pop("scenario")
    return result


def expand_case(case, owner, seen, seeds):
    """Resolve one condition and explicit repeat seeds into fully validated task records."""
    fields(case, ("id", "experiment", "repeats"), "case")
    identifier(case["id"], "case id")
    if case["id"] in seen:
        raise ValueError("Duplicate case id")
    seen.add(case["id"])
    nonempty(case["experiment"], "case experiment")
    path = (owner / case["experiment"]).resolve()
    original, sources, _ = load_spec(path)
    if original["schema_version"] != 2 or original["scenario"]["kind"] != "packed_liquid":
        raise ValueError("Research seed expansion currently requires v2 packed_liquid")
    if not isinstance(case["repeats"], list) or not 1 <= len(case["repeats"]) <= 16:
        raise ValueError("Explicit bounded repeats required")
    generating = [s for s in original["protocol"]["stages"] if s["velocities"] == "generate"]
    if len(generating) != 1:
        raise ValueError("Research repeats require exactly one velocity-generation stage")
    if not original["analysis_requests"] or any(
            r["kind"] != "component_contacts" for r in original["analysis_requests"]):
        raise ValueError("Research comparison requires component_contacts requests")
    raw = read_json(path)
    documents = [path, (path.parent / raw["protocol"]).resolve(),
                 (path.parent / raw["interaction_bundle"]).resolve()]
    documents.extend((path.parent / c["model"]).resolve() for c in raw["components"])
    tasks, repeat_ids = [], set()
    for repeat in case["repeats"]:
        fields(repeat, ("id", "packing_seed", "velocity_seed"), "repeat")
        identifier(repeat["id"], "repeat id")
        pair = (repeat["packing_seed"], repeat["velocity_seed"])
        for seed in pair:
            integer(seed, 1, 2147483646, "repeat seed")
        if repeat["id"] in repeat_ids or pair in seeds:
            raise ValueError("Duplicate repeat id or seed pair")
        repeat_ids.add(repeat["id"])
        seeds.add(pair)
        spec = deepcopy(original)
        spec["scenario"]["seed"] = pair[0]
        for stage in spec["protocol"]["stages"]:
            if stage["velocities"] == "generate":
                stage["seed"] = pair[1]
        validate_protocol(spec["protocol"]["stages"], sources)
        validate_packing(spec, sources)
        tasks.append(dict(case_id=case["id"], repeat=repeat, spec=spec, spec_hash=content_hash(spec),
                          sources={name: str(p) for name, p in sources.items()},
                          source_documents={str(p): sha256(p) for p in documents}))
    return tasks


def expand(path):
    """Read and expand every task without calling an engine or writing a Run."""
    path = Path(path).resolve()
    value = read_json(path)
    definition_check(value)
    tasks, seen, seeds = [], set(), set()
    for case in value["cases"]:
        tasks.extend(expand_case(case, path.parent, seen, seeds))
    if value["baseline_case"] not in seen:
        raise ValueError("baseline_case must name a declared condition")
    if len(tasks) > value["limits"]["max_tasks"]:
        raise ValueError("Expanded task count exceeds budget")
    baseline = projection(tasks[0]["spec"], value["varied_factors"])
    if any(projection(t["spec"], value["varied_factors"]) != baseline for t in tasks):
        raise ValueError("Undeclared condition or observable difference")
    # A conservative admission reservation, not a physical trajectory-size prediction.
    storage_reservation = len(tasks) * 64 * 1024 * 1024
    if storage_reservation > value["limits"]["storage_bytes"]:
        raise ValueError("Storage budget below 64 MiB/task admission reservation")
    return dict(schema_version=1, research=value, research_hash=content_hash(value),
                source_document=dict(path=str(path), sha256=sha256(path)), tasks=tasks,
                storage_reservation_bytes=storage_reservation, scientific_quality="not_assessed")
