"""Bounded research definitions and declared-variable comparability checks."""

from copy import deepcopy
from pathlib import Path

from materiasim.storage import content_hash, read_json, sha256
from materiasim.specs.schema import fields, identifier, integer
from materiasim.workflows.validation import validate_resolved
from materiasim.workflows.migration import load_executable
from materiasim.research.semantics import (apply_repeat, seed_values, observables_check,
                                         match_observables, rules_check)


def nonempty(value, label):
    """Require a nonempty explanatory string at a research input boundary."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: nonempty text required")


def limits_check(limits, version=1):
    """Validate serial CPU smoke ceilings; times include separately reserved exit grace."""
    bounds = dict(max_tasks=(1, 16), concurrency=(1, 1), threads=(1, 8),
                  max_attempts=(1, 2), execution_seconds=(1, 180),
                  build_seconds=(1, 600), analysis_seconds=(1, 120),
                  total_seconds=(30, 1800), storage_bytes=(1048576, 1073741824))
    if version == 2:
        bounds = {key: bounds[key] for key in ("max_tasks", "concurrency", "total_seconds", "storage_bytes")}
    fields(limits, bounds, "limits")
    for name, (low, high) in bounds.items():
        integer(limits[name], low, high, "limits." + name)


def definition_check(value):
    """Validate research metadata and finite explicit cases, returning no runtime state."""
    fields(value, ("schema_version", "id", "revision", "question", "hypothesis", "purpose",
                   "baseline_case", "varied_factors", "controlled_factors", "observables",
                   "decision_rules", "cases", "limits", "sources"), "research")
    integer(value["schema_version"], 1, 2, "research schema_version")
    version = value["schema_version"]
    integer(value["revision"], 1, 100000, "research revision")
    identifier(value["id"], "research id")
    allowed = ("engineering_smoke",) if version == 1 else ("engineering_smoke", "model_validation", "production")
    if value["purpose"] not in allowed:
        raise ValueError("Unsupported research purpose")
    for name in ("question", "hypothesis"):
        nonempty(value[name], name)
    for name in ("controlled_factors", "sources"):
        if not isinstance(value[name], list) or not value[name]:
            raise ValueError(f"{name}: nonempty list required")
        for item in value[name]:
            nonempty(item, name)
    varied = value["varied_factors"]
    if (not isinstance(varied, list) or not varied or any(
            item not in (("component_counts", "scenario", "protocol") if version == 2 else
                         ("component_counts", "scenario")) for item in varied) or len(set(varied)) != len(varied)):
        raise ValueError("Unknown or duplicate varied_factors")
    if version == 1:
        nonempty(value["decision_rules"], "decision_rules")
        if value["observables"] != [dict(metric="mean_unique_molecule_pairs", unit="molecule_pairs")]:
            raise ValueError("Research v1 comparison supports explicit raw component-contact means only")
    else:
        observables_check(value["observables"])
        rules_check(value["decision_rules"], value["observables"])
    limits_check(value["limits"], version)
    if not isinstance(value["cases"], list) or not 2 <= len(value["cases"]) <= value["limits"]["max_tasks"]:
        raise ValueError("Expected 2 or more explicitly bounded cases")


def projection(spec, varied, version=1):
    """Remove only declared variables and repeat seeds; all other content must match."""
    result = deepcopy(spec)
    result.pop("id")
    config = scenario_config(result)
    config.pop("seed", None)
    for stage in result["protocol"]["stages"]:
        if stage["velocities"] == "generate":
            stage["seed"] = "repeat_seed"
    if "component_counts" in varied:
        for component in result["components"]:
            component.pop("count")
        for group in config.get("groups", []):
            group.pop("count")
    if "scenario" in varied:
        result.pop("scenario")
    if version == 2:
        result.pop("execution_profile")
        result.pop("purpose_policy", None)
        if "protocol" in varied:
            result.pop("protocol")
    return result


def scenario_config(spec):
    """Read v3 builder configuration or the persisted v2 representation for historical plans."""
    return spec["scenario"]["builder"]["config"] if spec["schema_version"] == 3 else spec["scenario"]


def expand_case(case, owner, seen, seeds, version=1):
    """Resolve one condition and explicit repeat seeds into fully validated task records."""
    fields(case, ("id", "experiment", "repeats"), "case")
    identifier(case["id"], "case id")
    if case["id"] in seen:
        raise ValueError("Duplicate case id")
    seen.add(case["id"])
    nonempty(case["experiment"], "case experiment")
    path = (owner / case["experiment"]).resolve()
    original, sources, _, source_report = load_executable(path)
    if version == 1 and original["scenario"]["kind"] != "packed_liquid":
        raise ValueError("Research v1 seed expansion currently requires packed_liquid")
    if not isinstance(case["repeats"], list) or not 1 <= len(case["repeats"]) <= 16:
        raise ValueError("Explicit bounded repeats required")
    generating = [s for s in original["protocol"]["stages"] if s["velocities"] == "generate"]
    if version == 1 and len(generating) != 1:
        raise ValueError("Research repeats require exactly one velocity-generation stage")
    if version == 1 and (not original["analysis_requests"] or any(
            r["kind"] != "component_contacts" for r in original["analysis_requests"])):
        raise ValueError("Research comparison requires component_contacts requests")
    documents = [Path(item["path"]) for item in source_report["documents"].values()]
    tasks, repeat_ids = [], set()
    for repeat in case["repeats"]:
        spec = deepcopy(original)
        if version == 1:
            fields(repeat, ("id", "packing_seed", "velocity_seed"), "repeat")
            identifier(repeat["id"], "repeat id")
            pair = (repeat["packing_seed"], repeat["velocity_seed"])
            for seed in pair:
                integer(seed, 1, 2147483646, "repeat seed")
            scenario_config(spec)["seed"] = pair[0]
            generating_id = generating[0]["id"]
            next(s for s in spec["protocol"]["stages"] if s["id"] == generating_id)["seed"] = pair[1]
        else:
            apply_repeat(spec, repeat)
            pair = tuple(sorted(seed_values(spec).items()))
        if repeat["id"] in repeat_ids or pair in seeds:
            raise ValueError("Duplicate repeat id or seed pair")
        repeat_ids.add(repeat["id"])
        seeds.add(pair)
        validate_resolved(spec, sources)
        tasks.append(dict(case_id=case["id"], repeat=repeat, spec=spec, spec_hash=content_hash(spec),
                          sources={name: str(p) for name, p in sources.items()},
                          source_report=source_report,
                          source_documents={str(p): sha256(p) for p in documents}))
    return tasks


def expand(path):
    """Read and expand every task without calling an engine or writing a Run."""
    path = Path(path).resolve()
    value = read_json(path)
    definition_check(value)
    version = value["schema_version"]
    tasks, seen, seeds = [], set(), set()
    for case in value["cases"]:
        tasks.extend(expand_case(case, path.parent, seen, seeds, version))
    if value["baseline_case"] not in seen:
        raise ValueError("baseline_case must name a declared condition")
    if len(tasks) > value["limits"]["max_tasks"]:
        raise ValueError("Expanded task count exceeds budget")
    for task in tasks:
        if task["spec"]["purpose"] != value["purpose"]:
            raise ValueError("Research purpose differs from task purpose")
        profile = task["spec"]["execution_profile"]
        if version == 2:
            if profile["contract_version"] not in (2, 3):
                raise ValueError("Research v2 requires an explicit whole-workflow execution profile")
            match_observables(task["spec"], value["observables"])
        if version == 1 and (value["limits"]["threads"] != profile["threads"] or
                value["limits"]["execution_seconds"] > profile["max_wall_seconds"] or
                value["limits"]["max_attempts"] > profile["max_attempts"]):
            raise ValueError("Research limits conflict with a task's frozen execution profile")
    baseline = projection(tasks[0]["spec"], value["varied_factors"], version)
    if any(projection(t["spec"], value["varied_factors"], version) != baseline for t in tasks):
        raise ValueError("Undeclared condition or observable difference")
    # A conservative admission reservation, not a physical trajectory-size prediction.
    storage_reservation = len(tasks) * 64 * 1024 * 1024
    if storage_reservation > value["limits"]["storage_bytes"]:
        raise ValueError("Storage budget below 64 MiB/task admission reservation")
    return dict(schema_version=3, research=value, research_hash=content_hash(value),
                source_document=dict(path=str(path), sha256=sha256(path)), tasks=tasks,
                storage_reservation_bytes=storage_reservation, scientific_quality="not_assessed")
