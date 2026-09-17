"""Explicit read-only queries and separate bounded build/run/analysis commands."""

import argparse
import importlib.metadata
import json
import platform
import sqlite3
import sys
import subprocess
from pathlib import Path

from materiasim.storage import read_json
from materiasim.engines.gromacs.command import engine_info
from materiasim.engines.gromacs.mdp import mdp_values
from materiasim.specs.schema import STAGES
from materiasim.workflows.validation import load_spec
from materiasim.capabilities import capabilities
from materiasim.errors import MateriaSimError, error_record


class ArgumentParser(argparse.ArgumentParser):
    """Keep CLI syntax failures in the same structured diagnostic channel as runtime errors."""

    def error(self, message):
        """Raise an explicit argument error; --help retains argparse's normal successful exit."""
        raise MateriaSimError("INVALID_ARGUMENT", message, category="arguments")


def parser():
    """Return the supported CLI, keeping queries separate from state-changing actions."""
    result = ArgumentParser(prog="materiasim")
    result.add_argument("--json-envelope", action="store_true", help="Versioned response envelope for agent callers")
    commands = result.add_subparsers(dest="action", required=True)
    from materiasim.research.cli import add_commands
    add_commands(commands)
    from materiasim.harness.cli import add_commands as add_campaign_commands
    add_campaign_commands(commands)
    doctor = commands.add_parser("doctor", help="Read-only native environment check")
    doctor.add_argument("--gmx", default="gmx")
    doctor.add_argument("--packmol", help="Explicitly check the optional native packing tool")
    doctor.add_argument("--devices", action="store_true", help="Read-only optional NVIDIA driver inventory")
    commands.add_parser("capabilities", help="Read-only implemented subsets, not scientific validation")
    commands.add_parser("tools", help="Read-only CLI action and mutation contract")
    archive = commands.add_parser("archive", help="Copy a completed Run to a NEW read-only evidence bundle")
    archive.add_argument("run_dir", type=Path)
    archive.add_argument("--output", type=Path, required=True)
    archive.add_argument("--max-bytes", type=int, required=True)
    check_archive = commands.add_parser("verify-archive", help="Read-only local archive integrity check")
    check_archive.add_argument("archive_dir", type=Path)
    validate = commands.add_parser("validate", help="Read-only specification and source-hash check")
    validate.add_argument("spec", type=Path)
    migration = commands.add_parser("migrate", help="Read-only v2/v3 normalization and source provenance preview")
    migration.add_argument("spec", type=Path)
    builder = commands.add_parser("build", help="Snapshot and prepare, without integrating dynamics")
    builder.add_argument("spec", type=Path)
    builder.add_argument("--run-root", type=Path, required=True)
    builder.add_argument("--gmx", help="Must match a v3 profile tool locator")
    builder.add_argument("--packmol", help="Must match a v3 profile tool locator")
    for name in ("run", "resume"):
        executor = commands.add_parser(name, help="Execute within the frozen purpose, device and resource policy")
        executor.add_argument("run_dir", type=Path)
        executor.add_argument("--gmx", help="Must match a v3 profile tool locator")
        executor.add_argument("--threads", type=int, help="Must match the frozen profile")
        executor.add_argument("--max-wall-seconds", type=float, help="May shorten the frozen per-attempt limit")
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
    if args.action == "tools":
        return dict(contract_version=1, envelope_flag="--json-envelope", actions=[
            dict(action=name, read_only=name in ("doctor", "capabilities", "tools", "validate", "migrate", "status", "report", "verify-archive"))
            for name in ("doctor", "capabilities", "tools", "validate", "migrate", "build", "run", "resume", "status", "analyze", "report", "archive", "verify-archive")],
            research=dict(read_only=["validate", "status", "compare without --output-root", "plan without --output"],
                          writes=["run", "plan --output", "compare --output-root"]),
            campaign=dict(read_only=["plugins", "preflight", "status", "evidence", "validate-decision"],
                          writes=["create", "run", "start", "reconcile", "pause", "resume", "cancel", "revoke",
                                  "agent-read", "submit-decision", "human-decision", "agent-tick"]))
    if args.action == "archive":
        from materiasim.workflows.archive import export_archive
        return export_archive(args.run_dir, args.output, args.max_bytes)
    if args.action == "verify-archive":
        from materiasim.workflows.archive import verify_archive
        return verify_archive(args.archive_dir)
    if args.action == "research":
        from materiasim.research.cli import dispatch as research_dispatch
        return research_dispatch(args)
    if args.action == "campaign":
        from materiasim.harness.cli import dispatch as campaign_dispatch
        return campaign_dispatch(args)
    if args.action == "doctor":
        versions = {}
        for name in ("MDAnalysis", "numpy"):
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                versions[name] = "not installed (analysis unavailable)"
        result = dict(python=platform.python_version(), engine=engine_info(args.gmx), analysis=versions)
        if args.devices:
            from materiasim.engines.gromacs.device import visible_devices
            result["devices"] = visible_devices()
        if args.packmol is not None:
            from materiasim.builders.packmol import packmol_info
            result["packing"] = packmol_info(args.packmol)
        return result
    if args.action == "capabilities":
        return capabilities()
    if args.action == "migrate":
        from materiasim.workflows.migration import load_executable, portable_document
        spec, sources, _, report = load_executable(args.spec)
        return dict(migration=report, experiment=portable_document(spec, sources))
    if args.action == "validate":
        spec, sources, identity = load_spec(args.spec)
        if spec["schema_version"] == 1:
            for stage in STAGES:
                mdp_values(sources[f"{stage}.mdp"])
        from materiasim.runtime.records import stage_ids
        return dict(valid=True, executable=spec["schema_version"] in (2, 3), spec_hash=identity,
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
    from materiasim.analysis.locations import generations
    reports = [read_json(path / "report.json") for path in generations(folder)]
    return [report for report in reports if report["run_id"] == manifest["run_id"]
            and report["spec_hash"] == manifest["spec_hash"]]


def main(argv=None):
    """Run the CLI and return zero on success, nonzero with an explicit error otherwise."""
    try:
        args = parser().parse_args(argv)
        result = dispatch(args)
        if args.json_envelope:
            result = dict(contract_version=1, ok=True, action=args.action, result=result)
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError, sqlite3.Error) as error:
        print(json.dumps(error_record(error), ensure_ascii=False, allow_nan=False), file=sys.stderr)
        return 1
    return 0
