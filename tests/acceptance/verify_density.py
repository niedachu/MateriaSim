"""Exercise native energy analysis on an existing completed Run, without launching MD."""

import argparse
import time
from pathlib import Path

from materiasim.research.compare import verified_report
from materiasim.research.plan import external_output
from materiasim.runtime.state import verify_run
from materiasim.storage import sha256, write_json
from materiasim.workflows.analysis import analyze


def verify_density(run, output, stage, begin, end, gromacs):
    """Analyze explicit ps endpoints into a new external directory and audit the source bytes."""
    run = Path(run).resolve()
    spec, manifest = verify_run(run)
    output = external_output(output, [run])
    output.mkdir(parents=True, exist_ok=False)
    before = {p.relative_to(run).as_posix(): sha256(p) for p in run.rglob("*") if p.is_file()}
    request = dict(id="density_acceptance", kind="mass_density", stage_id=stage,
                   config=dict(gromacs_command=gromacs, begin_ps=begin, end_ps=end))
    start = time.monotonic()
    folders = analyze(run, output / "analyses", request)
    report = verified_report(Path(folders[0]), run, spec, manifest, request)
    after = {p.relative_to(run).as_posix(): sha256(p) for p in run.rglob("*") if p.is_file()}
    if after != before:
        raise ValueError("Source Run was modified by analysis")
    result = dict(status="engineering_pass", scientific_quality="not_assessed", source_run=str(run),
                  source_run_id=manifest["run_id"], source_files_checked=len(before), source_unchanged=True,
                  analysis_dir=folders[0], report_sha256=report["report_sha256"],
                  frames=report["frames"], time_range_ps=report["time_range_ps"],
                  mean_density_kg_m3=report["mean_density_kg_m3"], mean_volume_nm3=report["mean_volume_nm3"],
                  versions=report["versions"], elapsed_seconds=time.monotonic() - start,
                  md_launched=False, limitation="Existing engineering trajectory, not an ethanol validation.")
    write_json(output / "acceptance.json", result)
    return result


def main():
    """Require an existing source and explicit new output/window; never choose a simulation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--begin-ps", type=float, required=True)
    parser.add_argument("--end-ps", type=float, required=True)
    parser.add_argument("--gmx", required=True)
    args = parser.parse_args()
    print(verify_density(args.run, args.output, args.stage, args.begin_ps, args.end_ps, args.gmx))


if __name__ == "__main__":
    main()
