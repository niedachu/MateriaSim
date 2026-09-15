"""Adapt the existing native implementation without duplicating its numerical path."""

from materiasim.engines.contracts import BuildResult, EngineAdapter, StageEvidence
from materiasim.engines.gromacs.command import engine_info
from materiasim.engines.gromacs.compile import prepare_stage
from materiasim.engines.gromacs.mdp import validate_protocol
from materiasim.storage import content_hash, read_json, write_json
from materiasim.engines.gromacs.specification import native_view, validate_native_protocol


def validate(spec, sources):
    """Bind the resolved protocol to declared GROMACS MDP assets without running tools."""
    if spec["schema_version"] == 3:
        native_view(spec)
        validate_native_protocol(spec, sources)
    protocol = spec["protocol"]
    validate_protocol(protocol["stages"],
                      {item["name"]: sources[item["name"]] for item in protocol["files"]})


def build(root, spec, sources, engine, attempt, packmol_candidate):
    """Run the established native builder and return its checked mapping and system record."""
    from materiasim.builders.registry import get_builder
    from materiasim.scenarios.planning import build_plan
    plan = build_plan(spec)
    operation = get_builder(plan["steps"][0]["builder"])
    mapping = operation(root, native_view(spec), sources, engine, attempt, packmol_candidate)
    system = read_json(root / "build/resolved_system.json")
    system.update(scenario=spec["scenario"], bundle_hash=content_hash(spec["interaction_bundle"]),
                  model_hashes={c["id"]: content_hash(c["model"]) for c in spec["components"]})
    write_json(root / "build/resolved_system.json", system)
    write_json(root / "build/plan.json", plan)
    return BuildResult(mapping, system)


def run_stage(root, prepared, engine, attempt, profile, remaining):
    """Execute a checked compiled contract and expose the observed native stage outcome."""
    from materiasim.engines.gromacs.stage import execute_stage
    complete, interrupted = execute_stage(root, prepared, engine, attempt, profile["threads"], remaining,
                                         checkpoint_interval_minutes=profile["checkpoint_interval_minutes"], profile=profile)
    return StageEvidence(complete, interrupted)


ADAPTER = EngineAdapter("gromacs", validate, engine_info, build, prepare_stage, run_stage,
                        ("engineering_smoke", "model_validation", "production"))
