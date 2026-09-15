"""Portable closed input snapshots; plan preview never creates Run evidence."""

import shutil
from copy import deepcopy
from pathlib import Path

from materiasim.storage import (contained, content_hash, inventory, read_json, sha256,
                               source_root, verify_hashes, write_json)
from materiasim.specs.schema import fields, load_spec
from materiasim.research.schema import definition_check, expand, projection


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
    """Copy exact asset bytes and reconstruct ordinary v2 files for the existing loader."""
    folder.mkdir(parents=True, exist_ok=False)
    assets = folder / "assets"
    assets.mkdir()
    spec = deepcopy(task["spec"])
    for name, source in task["sources"].items():
        shutil.copyfile(source, assets / name)

    def restore_sources(document):
        """Restore local paths stripped from scientific identity during resolution."""
        for item in document.get("files", []):
            item["source"] = "assets/" + item["name"]

    for index, component in enumerate(spec["components"]):
        model = component["model"]
        restore_sources(model)
        component["model"] = f"model-{index}.json"
        write_json(folder / component["model"], model)
    for key in ("interaction_bundle", "protocol"):
        document = spec[key]
        restore_sources(document)
        spec[key] = key + ".json"
        write_json(folder / spec[key], document)
    if "structure" in spec["scenario"]:
        restore_sources(spec["scenario"]["structure"])
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
    for index, task in enumerate(value["tasks"]):
        if task["id"] != f"task-{index:03d}":
            raise ValueError("Unexpected frozen task id")
        spec, _, identity = load_spec(contained(root, f"tasks/{task['id']}/experiment.json"))
        if identity != task["spec_hash"]:
            raise ValueError("Frozen task specification changed")
        stages = [s for s in spec["protocol"]["stages"] if s["velocities"] == "generate"]
        if (spec["scenario"].get("seed") != task["repeat"]["packing_seed"] or len(stages) != 1
                or stages[0]["seed"] != task["repeat"]["velocity_seed"]):
            raise ValueError("Frozen repeat seeds differ from task definition")
        projected = projection(spec, value["research"]["varied_factors"])
        if common is not None and projected != common:
            raise ValueError("Undeclared frozen task difference")
        common = projected
    return value
