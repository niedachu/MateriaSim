"""Portable closed input snapshots; plan preview never creates Run evidence."""

from materiasim.runtime.capacity import copy_file, preflight, copy_budget
from pathlib import Path

from materiasim.storage import (contained, content_hash, inventory, read_json, sha256,
                               source_root, verify_hashes, write_json)
from materiasim.specs.schema import fields
from materiasim.workflows.validation import load_spec
from materiasim.research.schema import definition_check, expand, projection, scenario_config
from materiasim.workflows.migration import portable_document
from materiasim.research.semantics import apply_repeat, seed_values, match_observables
from copy import deepcopy


def external_output(path, protected=()):
    """Resolve an output path outside source/input trees; reject symlink components."""
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Output paths must not contain symlinks")
    path = path.resolve()
    for root in (source_root(), *map(lambda p: Path(p).resolve(), protected)):
        if path == root or root in path.parents:
            raise ValueError("Research output must be outside source, inputs and frozen plans")
    return path


def snapshot_task(task, folder):
    """Freeze portable v3 task bytes and retain original source documents plus the declared repeat derivation."""
    folder.mkdir(parents=True, exist_ok=False)
    assets = folder / "assets"
    assets.mkdir()
    spec = portable_document(task["spec"], {name: "assets/" + name for name in task["sources"]})
    for name, source in task["sources"].items():
        copy_file(source, assets / name)

    origin = folder / "origin"
    origin.mkdir()
    for name, record in task["source_report"]["documents"].items():
        copy_file(record["path"], origin / name)
        if sha256(origin / name) != record["sha256"]:
            raise ValueError("Source document changed while freezing task")
    write_json(origin / "derivation.json", dict(source=task["source_report"], repeat=task["repeat"],
                                               derived_spec_hash=task["spec_hash"]))
    write_json(folder / "experiment.json", spec)
    resolved, _, identity = load_spec(folder / "experiment.json")
    if identity != task["spec_hash"] or resolved != task["spec"]:
        raise ValueError("Frozen task differs from expanded scientific content")


def plan(path, output=None):
    """Return a read-only expansion, or explicitly create a new portable frozen plan."""
    expanded = expand(path)
    if output is None:
        return expanded
    protected = [Path(path).resolve().parent]
    protected.extend(Path(p).parent for t in expanded["tasks"] for p in t["sources"].values())
    root = external_output(output, protected)
    inputs = [p for task in expanded["tasks"] for p in task["sources"].values()]
    inputs += [r["path"] for task in expanded["tasks"] for r in task["source_report"]["documents"].values()]
    with copy_budget([root], expanded["research"]["limits"]["storage_bytes"], 64 * 1024 * 1024):
        preflight(inputs, root)
    root.mkdir(parents=True, exist_ok=False)
    frozen_tasks = []
    for index, task in enumerate(expanded["tasks"]):
        for document, digest in task["source_documents"].items():
            if sha256(document) != digest:
                raise ValueError("Source document changed while freezing plan")
        task_id = f"task-{index:03d}"
        snapshot_task(task, root / "tasks" / task_id)
        frozen_tasks.append(dict(id=task_id, case_id=task["case_id"], repeat=task["repeat"],
                                 spec_hash=task["spec_hash"], source_documents=task["source_documents"]))
    payload = dict(expanded, tasks=frozen_tasks, hashes=inventory(root, ["tasks"]))
    payload["plan_hash"] = content_hash(payload)
    write_json(root / "plan.json", payload)
    load_plan(root)
    return dict(plan_dir=str(root), plan_hash=payload["plan_hash"], task_count=len(frozen_tasks))


def load_plan(root):
    """Verify the closed snapshot and re-resolve every task; never trust unchecked hashes alone."""
    root = Path(root).resolve()
    value = read_json(root / "plan.json")
    fields(value, ("schema_version", "research", "research_hash", "source_document", "tasks",
                   "storage_reservation_bytes", "scientific_quality", "hashes", "plan_hash"), "plan")
    if type(value["schema_version"]) is not int or value["schema_version"] not in (1, 2, 3):
        raise ValueError("Unsupported frozen plan version")
    payload = dict(value)
    identity = payload.pop("plan_hash")
    if content_hash(payload) != identity:
        raise ValueError("Frozen plan identity changed")
    definition_check(value["research"])
    if value["research_hash"] != content_hash(value["research"]):
        raise ValueError("Frozen research identity changed")
    verify_hashes(root, value["hashes"])
    if inventory(root, ["tasks"]) != value["hashes"]:
        raise ValueError("Frozen plan inventory changed")
    expected = [(case["id"], repeat) for case in value["research"]["cases"] for repeat in case["repeats"]]
    if [(t["case_id"], t["repeat"]) for t in value["tasks"]] != expected:
        raise ValueError("Frozen tasks differ from declared conditions/repeats")
    if len(expected) > value["research"]["limits"]["max_tasks"]:
        raise ValueError("Frozen tasks exceed budget")
    common = None
    research_version = value["research"]["schema_version"]
    seen_seeds, seen_cases = set(), set()
    for case in value["research"]["cases"]:
        if case["id"] in seen_cases or len({r["id"] for r in case["repeats"]}) != len(case["repeats"]):
            raise ValueError("Duplicate frozen case/repeat")
        seen_cases.add(case["id"])
    if value["research"]["baseline_case"] not in seen_cases:
        raise ValueError("Frozen baseline is missing")
    for index, task in enumerate(value["tasks"]):
        if task["id"] != f"task-{index:03d}":
            raise ValueError("Unexpected frozen task id")
        spec, _, identity = load_spec(contained(root, f"tasks/{task['id']}/experiment.json"))
        if spec["purpose"] != value["research"]["purpose"]:
            raise ValueError("Frozen research purpose differs from task purpose")
        if identity != task["spec_hash"]:
            raise ValueError("Frozen task specification changed")
        if value["schema_version"] >= 2 and spec["schema_version"] != 3:
            raise ValueError("New frozen plans require v3 task contracts")
        if research_version == 1:
            stages = [s for s in spec["protocol"]["stages"] if s["velocities"] == "generate"]
            if (scenario_config(spec).get("seed") != task["repeat"]["packing_seed"] or len(stages) != 1
                    or stages[0]["seed"] != task["repeat"]["velocity_seed"]):
                raise ValueError("Frozen repeat seeds differ from task definition")
            seeds = (task["repeat"]["packing_seed"], task["repeat"]["velocity_seed"])
        else:
            repeated = deepcopy(spec)
            apply_repeat(repeated, task["repeat"])
            if repeated != spec:
                raise ValueError("Frozen repeat differs from declared seeds")
            match_observables(spec, value["research"]["observables"])
            seeds = tuple(sorted(seed_values(spec).items()))
        if seeds in seen_seeds:
            raise ValueError("Duplicate frozen repeat seed assignment")
        seen_seeds.add(seeds)
        projected = projection(spec, value["research"]["varied_factors"], research_version)
        if common is not None and projected != common:
            raise ValueError("Undeclared frozen task difference")
        common = projected
    return value
