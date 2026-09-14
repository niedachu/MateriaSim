"""Compare the existing case analyzer and new streaming analyzer on identical frames."""

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path

from materials_sim.files import read_json, sha256, write_json
from materials_sim.records import stage_artifact
from materials_sim.state import verify_run


def main():
    """Compare a report-selected stage on private copies, preserving source Run cache bytes."""
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("legacy", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    spec, manifest = verify_run(args.run)
    report = read_json(args.analysis / "report.json")
    if report["run_id"] != manifest["run_id"] or report["spec_hash"] != manifest["spec_hash"]:
        raise ValueError("Analysis belongs to a different Run")
    config = report["selection"]
    # Old reports did not record a stage; their schema was explicitly fixed to prod.
    stage = "prod" if spec["schema_version"] == 1 else report["stage_id"]
    for role, name in (("coordinates", "coordinates.gro"), ("trajectory", "trajectory.xtc")):
        source = stage_artifact(args.run, spec, stage, role)
        shutil.copyfile(source, args.output / name)
        if sha256(args.output / name) != sha256(source):
            raise ValueError("Analysis comparison snapshot changed")
    config_path = args.output / "site_config.json"
    write_json(config_path, config)
    subprocess.run([sys.executable, "-B", str(args.legacy), "--topology", str(args.output / "coordinates.gro"),
                    "--trajectory", str(args.output / "trajectory.xtc"), "--site-config", str(config_path),
                    "--output", str(args.output / "legacy.json")], check=True)
    with (args.analysis / "hydration_counts.csv").open() as handle:
        new = list(csv.DictReader(handle))
    with (args.output / "legacy.csv").open() as handle:
        old = list(csv.DictReader(handle))
    if len(new) != len(old) or not new:
        raise AssertionError("Frame count mismatch")
    for current, previous in zip(new, old):
        if float(current["time_ps"]) != float(previous["time_ps"]):
            raise AssertionError("Frame time mismatch")
        for name in config["sites"]:
            if int(current[name]) != int(previous[name + "_count"]):
                raise AssertionError(f"Site count mismatch: {name}")
        if int(current["union"]) != int(previous["total_unique_count"]):
            raise AssertionError("Unique water count mismatch")
    result = dict(frames=len(new), equal=True, sites=list(config["sites"]),
                  legacy_script=str(args.legacy), legacy_sha256=sha256(args.legacy),
                  new_csv_sha256=sha256(args.analysis / "hydration_counts.csv"),
                  legacy_csv_sha256=sha256(args.output / "legacy.csv"))
    write_json(args.output / "comparison.json", result)
    print(result)


if __name__ == "__main__":
    main()
