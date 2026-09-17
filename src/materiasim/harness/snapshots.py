"""Freeze existing source definitions without changing scientific fields or inventing research cases."""

import shutil
from pathlib import Path

from materiasim.harness.contracts import automation, authorization, bounded_json
from materiasim.harness import journal
from materiasim.plugins.builtin import environment, resolve, verify
from materiasim.research.plan import external_output, load_plan, plan, snapshot_task
from materiasim.runtime.capacity import copy_budget
from materiasim.storage import content_hash, inventory, read_json, verify_hashes, write_json, utc_now
from materiasim.workflows.migration import load_executable


def preview(path):
    """Resolve source and capability requirements without probing native tools or writing files."""
    recipe, source = automation(path)
    if recipe["target"]["kind"] == "research":
        expanded = plan(source)
        specs = [item["spec"] for item in expanded["tasks"]]
        identity = expanded["research_hash"]
    else:
        spec, _, identity, _ = load_executable(source)
        specs = [spec]
    for spec in specs:
        if spec["purpose"] != "engineering_smoke" or spec["execution_profile"]["device"] != "cpu":
            raise ValueError("Rule Campaign v1 supports engineering_smoke CPU tasks only")
    composition = resolve(specs, recipe["capabilities"])
    return dict(contract_version=1, automation=recipe, source=str(source), target_hash=identity,
                task_count=len(specs), composition=composition, environment="not_checked",
                scientific_quality="not_assessed")


def specs_at(root, manifest):
    """Load the frozen target through existing validators and return its executable specs."""
    root = Path(root)
    if manifest["automation"]["target"]["kind"] == "research":
        value = load_plan(root / "snapshot")
        return [load_executable(root / "snapshot/tasks" / t["id"] / "experiment.json")[0] for t in value["tasks"]]
    return [load_executable(root / "snapshot/experiment.json")[0]]


def load(root, current=False, check_snapshot=True):
    """Verify identity; audit may defer snapshot checking to enumerate missing files explicitly."""
    root = external_output(root)
    value = bounded_json(root / "manifest.json")
    payload = dict(value)
    digest = payload.pop("manifest_hash")
    if type(value["contract_version"]) is not int or value["contract_version"] not in (1, 2, 3) or content_hash(payload) != digest:
        raise ValueError("Campaign manifest identity mismatch")
    if str(root) != value["authorization"]["output_root"]:
        raise ValueError("Active Campaign relocation is unsupported")
    state = journal.status(root)
    if state["manifest_hash"] != digest:
        raise ValueError("Campaign journal refers to a different manifest")
    if value["contract_version"] == 3:
        from materiasim.harness.agent_contracts import policy
        policy(value["agent_policy"])
        if not state.get("agent_enabled"):
            raise ValueError("Incomplete agent Campaign initialization")
    if current or check_snapshot:
        verify_hashes(root, value["snapshot_hashes"])
        if inventory(root, ["snapshot"]) != value["snapshot_hashes"]:
            raise ValueError("Frozen Campaign inventory changed")
    if current:
        if value["contract_version"] not in (2, 3):
            raise ValueError("Campaign v1 is read-only; create a new Campaign from source")
        verify(specs_at(root, value), value["composition"])
    return value


def create(path, grant_path, output, gmx="gmx", packmol="packmol", agent_policy=None):
    """Freeze a new campaign and optional user agent policy; creation never starts MD."""
    from materiasim.harness.agent_contracts import policy
    from materiasim.harness.agent_state import deadline
    rule = policy(bounded_json(agent_policy)) if agent_policy is not None else None
    checked = preview(path)
    recipe, source = checked["automation"], Path(checked["source"])
    root = external_output(output, [source.parent, Path(path).resolve().parent, Path(grant_path).resolve()])
    grant = authorization(bounded_json(grant_path), recipe["id"], root)
    if recipe["allow_resume"] and "resume" not in grant["allowed_actions"]:
        raise ValueError("Recipe requests recovery without user resume authority")
    if rule and (not recipe["allow_resume"] or "resume" not in grant["allowed_actions"]):
        raise ValueError("Stepwise agent execution requires explicitly granted resume")
    if root.exists():
        raise FileExistsError(root)
    if shutil.disk_usage(root.parent).free < grant["storage_bytes"]:
        raise ValueError("Insufficient disk for Campaign reservation")
    from materiasim.engines.gromacs.command import engine_info
    from materiasim.builders.packmol import packmol_info
    engine = engine_info(gmx)
    packing = packmol_info(packmol) if "builder:gromacs_packmol" in recipe["capabilities"] else None
    dependencies = environment(checked["composition"])
    root.mkdir()
    with copy_budget([root], grant["storage_bytes"], 64 * 1024 * 1024):
        if recipe["target"]["kind"] == "research":
            frozen = plan(source, root / "snapshot")
            target_hash = load_plan(root / "snapshot")["research_hash"]
        else:
            spec, sources, target_hash, report = load_executable(source)
            snapshot_task(dict(spec=spec, sources=sources, spec_hash=target_hash,
                               source_report=report, repeat=None), root / "snapshot")
            frozen = dict(spec_hash=target_hash)
        if target_hash != checked["target_hash"] or preview(path) != checked:
            raise ValueError("Source changed while freezing Campaign")
        from materiasim.specs.purpose import select_tool
        manifest = dict(contract_version=2, created_utc=utc_now(), automation=recipe,
                        max_invocations=2 + 3 * checked["task_count"],
                        dependencies=dependencies,
                        authorization=grant, target=frozen, composition=checked["composition"],
                        tools=dict(gmx=gmx, packmol=packmol), engine=engine, packing=packing,
                        snapshot_hashes=inventory(root, ["snapshot"]))
        if rule:
            manifest.update(contract_version=3, agent_policy=rule)
        for spec in specs_at(root, manifest):
            select_tool(spec["execution_profile"], "gmx", gmx)
            select_tool(spec["execution_profile"], "packmol", packmol)
        manifest["manifest_hash"] = content_hash(manifest)
        write_json(root / "manifest.json", manifest)
        for name in ("supervisor", "worker_guard", "operations", "work", "launches"):
            (root / name).mkdir()
        journal.initialize(root, manifest["manifest_hash"])
        if rule:
            with journal.transaction(root) as db:
                journal.append(db, "agent_configured", dict(deadline=deadline(manifest)))
    return dict(campaign_dir=str(root), **journal.status(root))


def verify_tools(manifest):
    """Reject replacement native executables before every operation, including a resumed batch."""
    from materiasim.engines.gromacs.command import engine_info
    from materiasim.builders.packmol import packmol_info
    actual = engine_info(manifest["tools"]["gmx"])
    if actual != manifest["engine"]:
        raise ValueError("GROMACS identity or location changed")
    if manifest["packing"] is not None and packmol_info(manifest["tools"]["packmol"]) != manifest["packing"]:
        raise ValueError("Packmol identity changed")
    if environment(manifest["composition"]) != manifest["dependencies"]:
        raise ValueError("Analysis dependency versions changed")
