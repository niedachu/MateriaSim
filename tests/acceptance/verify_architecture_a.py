"""Bounded real-tool acceptance of the component extraction, not a research batch scheduler."""

import argparse
import time
from pathlib import Path

from tests.acceptance.audit_asset_dependencies import audit_experiment
from materiasim.workflows.build import build
from materiasim.workflows.execute import execute
from materiasim.storage import read_json, write_json
from materiasim.engines.gromacs.command import engine_info
from materiasim.runtime.state import source_identity
from tests.acceptance.verify_m3_evidence import audit_run

CASES = ("packed_zil_water", "packed_ions_water", "packed_mixture_water", "packed_zil_dry")


def check_budget(output, started):
    """Refuse more acceptance work after 30 minutes or 1 GiB of generated evidence."""
    size = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    if time.monotonic() - started >= 1800 or size >= 1024 ** 3:
        raise RuntimeError("Architecture acceptance budget exhausted; keep partial evidence")


def exercise_run(example, output, started, engine):
    """Build and complete one existing short case, exercising mixture checkpoint continuation explicitly."""
    check_budget(output, started)
    root = Path(build(example, output / "runs", candidate=engine["executable"]))
    print(f"built {root.name}", flush=True)
    interruption = None
    if example.stem == "packed_mixture_water":
        execute(root, candidate=engine["executable"], threads=2, max_wall_seconds=180, through="em")
        check_budget(output, started)
        # The public executor needs at least one second remaining before entering a stage;
        # a total budget of exactly one second tests only its pre-stage budget guard.
        execute(root, resume=True, candidate=engine["executable"], threads=2, max_wall_seconds=2)
        state = read_json(root / "status.json")
        seals = [read_json(path) for path in sorted((root / "stages").glob("*/stage.json"))]
        interrupted = [seal for seal in seals if seal["status"] == "interrupted"]
        interruption = dict(state=state, actual_checkpoint_interruption=bool(interrupted),
                            evidence=[seal["evidence"] for seal in interrupted])
        write_json(output / "mixture_interruption.json", interruption)
        if not interrupted:
            raise AssertionError("No in-stage checkpoint interruption; do not report this coverage as passed")
    state = read_json(root / "status.json")["status"]
    for _ in range(2):
        if state == "completed":
            break
        check_budget(output, started)
        result = execute(root, resume=state == "interrupted", candidate=engine["executable"],
                         threads=2, max_wall_seconds=180)
        state = result["status"]
    if state != "completed":
        raise RuntimeError("Run did not finish within acceptance attempts")
    check_budget(output, started)
    result = audit_run(root, output / "checks" / example.stem)
    if interruption is not None:
        result["interruption"] = interruption
    print(f"verified {root.name}: {result['counts']}", flush=True)
    return result


def main():
    """Write real short-run evidence to a new explicit external output directory, preserving failures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gmx", default="gmx")
    args = parser.parse_args()
    output = args.output.resolve()
    repository = Path(__file__).resolve().parents[2]
    if output == repository or repository in output.parents:
        raise ValueError("Acceptance output must be outside the repository")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    engine = engine_info(args.gmx)
    examples = Path(__file__).resolve().parents[2] / "examples"
    references = ("zil_smoke", "zil_smoke_v2", "cat_ani_smoke", *CASES)
    before = [audit_experiment(examples / f"{name}.json", engine) for name in references]
    write_json(output / "dependencies_before.json", before)
    report = dict(status="running", implementation=source_identity(), engine=engine,
                  scientific_quality="not_assessed", runs=[], pending=list(CASES),
                  limits=dict(threads=2, total_wall_seconds=1800, storage_bytes=1024 ** 3),
                  not_tested=["Linux", "GPU", "research packages", "equilibrium", "material properties"])
    try:
        for name in CASES:
            result = exercise_run(examples / f"{name}.json", output, started, engine)
            report["runs"].append(result)
            report["pending"].remove(name)
            write_json(output / "acceptance.json", report)
        after = [audit_experiment(examples / f"{name}.json", engine) for name in references]
        write_json(output / "dependencies_after.json", after)
        if before != after:
            raise AssertionError("Scientific dependencies changed during acceptance")
        check_budget(output, started)
        report.update(status="passed", dependency_identity_unchanged=True)
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        report["elapsed_seconds"] = time.monotonic() - started
        write_json(output / "acceptance.json", report)
    print(output / "acceptance.json", flush=True)


if __name__ == "__main__":
    main()
