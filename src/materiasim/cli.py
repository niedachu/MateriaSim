"""Explicit read-only queries and separate bounded build/run/analysis commands."""

import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

from materiasim.storage import read_json
from materiasim.engines.gromacs.command import engine_info
from materiasim.engines.gromacs.mdp import mdp_values
from materiasim.specs.schema import STAGES, load_spec


def parser():
    """Return the supported CLI, keeping queries separate from state-changing actions."""
    result = argparse.ArgumentParser(prog="materiasim")
    commands = result.add_subparsers(dest="action", required=True)
    from materiasim.research.cli import add_commands
    add_commands(commands)
    doctor = commands.add_parser("doctor", help="Read-only native environment check")
    doctor.add_argument("--gmx", default="gmx")
    doctor.add_argument("--packmol", help="Explicitly check the optional native packing tool")
    commands.add_parser("capabilities", help="Read-only implemented subsets, not scientific validation")
    validate = commands.add_parser("validate", help="Read-only specification and source-hash check")
    validate.add_argument("spec", type=Path)
    builder = commands.add_parser("build", help="Snapshot and prepare, without integrating dynamics")
    builder.add_argument("spec", type=Path)
    builder.add_argument("--run-root", type=Path, required=True)
    builder.add_argument("--gmx", default="gmx")
    builder.add_argument("--packmol", default="packmol")
    for name in ("run", "resume"):
        executor = commands.add_parser(name, help="Bounded CPU smoke execution")
        executor.add_argument("run_dir", type=Path)
        executor.add_argument("--gmx", default="gmx")
        executor.add_argument("--threads", type=int, default=2)
        executor.add_argument("--max-wall-seconds", type=float, default=180)
        executor.add_argument("--through", help="Stop after this resolved stage ID")
    for name in ("status", "analyze", "report"):
        query = commands.add_parser(name)
        query.add_argument("run_dir", type=Path)
        if name == "analyze":
            query.add_argument("--output-root", type=Path, required=True)
            query.add_argument("--request", type=Path, help="Independent single analysis request JSON")
        elif name == "report":
            query.add_argument("--analysis-root", type=Path, help="Read external AnalysisRuns for this Run")
    return result


def dispatch(args):
    """Execute the selected action, returning JSON-serializable evidence or a path."""
    if args.action == "research":
        from materiasim.research.cli import dispatch as research_dispatch
        return research_dispatch(args)
    if args.action == "doctor":
        versions = {}
        for name in ("MDAnalysis", "numpy"):
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = "not installed (analysis unavailable)"
        result = dict(python=platform.python_version(), engine=engine_info(args.gmx), analysis=versions)
        if args.packmol is not None:
            from materiasim.builders.packmol import packmol_info
            result["packing"] = packmol_info(args.packmol)
        return result
    if args.action == "capabilities":
        import shutil
        return dict(engine="gromacs", purposes=["engineering_smoke"],
                    scenarios=["prebuilt_solute_water", "prebuilt_mixture_water", "packed_liquid"],
                    packed_solvent_policies=["tip3p_fill", "none"],
                    packing="Packmol >=21.1.0; <=2000 solute atoms; <=20000 total atoms",
                    packmol_on_path=shutil.which("packmol") is not None,
                    regions="explicit orthorhombic boxes; repeated groups may share one model",
                    analysis=["hydration_contacts", "component_contacts"],
                    not_implemented=["mixed_solvents", "concentration_recipes", "polymers", "solids", "interfaces", "lammps"],
                    scientific_quality="not_assessed", runtime_validation="See platform-specific acceptance records")
    if args.action == "validate":
        spec, sources, identity = load_spec(args.spec)
        if spec["schema_version"] == 1:
            for stage in STAGES:
                mdp_values(sources[f"{stage}.mdp"])
        from materiasim.runtime.records import stage_ids
        return dict(valid=True, executable=spec["schema_version"] == 2, spec_hash=identity,
                    purpose=spec["purpose"], stages=stage_ids(spec))
    if args.action == "build":
        from materiasim.workflows.build import build
        return dict(run_dir=build(args.spec, args.run_root, args.gmx, args.packmol))
    if args.action in ("run", "resume"):
        from materiasim.workflows.execute import execute
        return execute(args.run_dir, args.action == "resume", args.gmx, args.threads,
                       args.max_wall_seconds, args.through)
    if args.action == "analyze":
        from materiasim.workflows.analysis import analyze
        request = read_json(args.request) if args.request else None
        return dict(analysis_dirs=analyze(args.run_dir, args.output_root, request))
    if args.action == "status":
        from materiasim.runtime.state import verify_run
        state = read_json(args.run_dir / "status.json")
        if state["status"] in ("building", "running", "failed"):
            return dict(state, integrity="not_checked_while_active_or_failed")
        verify_run(args.run_dir)
        return dict(state, integrity="verified")
    from materiasim.runtime.state import verify_run
    _, manifest = verify_run(args.run_dir)
    folder = args.analysis_root if args.analysis_root else args.run_dir / "analysis"
    reports = [read_json(path) for path in sorted(folder.glob("*/report.json"))]
    return [report for report in reports if report["run_id"] == manifest["run_id"]
            and report["spec_hash"] == manifest["spec_hash"]]


def main(argv=None):
    """Run the CLI and return zero on success, nonzero with an explicit error otherwise."""
    args = parser().parse_args(argv)
    try:
        print(json.dumps(dispatch(args), indent=2, ensure_ascii=False, allow_nan=False))
    except (ValueError, OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0
