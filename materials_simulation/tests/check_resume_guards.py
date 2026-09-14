"""Acceptance-only mutation tests on new disposable copies, never on the source Run."""

import argparse
import shutil
from pathlib import Path

from materials_sim.execute import execute
from materials_sim.files import read_json, write_json
from materials_sim.state import verify_run


def main():
    """Clone an interrupted Run and record rejected mutation/residual-output attempts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--gmx", default="gmx")
    args = parser.parse_args()
    spec, _ = verify_run(args.run)
    state = read_json(args.run / "status.json")
    if state["status"] != "interrupted" or "stage" not in state:
        raise ValueError("Acceptance fixture must be an interrupted Run")
    seal = read_json(args.run / "stages" / state["stage"] / "stage.json")
    if seal["status"] != "interrupted":
        raise ValueError("Acceptance requires an actual interrupted dynamics checkpoint, not a stage boundary")
    targets = (("input_mutation", "inputs/" + spec["components"][0]["model"]["topology"]),
               ("checkpoint_mutation", seal["artifacts"]["checkpoint"]["path"]),
               ("output_mutation", seal["artifacts"]["trajectory"]["path"]))
    args.output.mkdir(parents=True, exist_ok=False)
    results = {}
    for name, relative in targets:
        clone = args.output / name
        shutil.copytree(args.run, clone)
        before = len(list((clone / "attempts").iterdir()))
        with (clone / relative).open("ab") as handle:
            handle.write(b"acceptance mutation")
        try:
            execute(clone, resume=True, candidate=args.gmx)
        except ValueError as error:
            if "Frozen artifact changed" not in str(error):
                raise
            results[name] = str(error)
        else:
            raise AssertionError("Changed artifact unexpectedly resumed")
        if len(list((clone / "attempts").iterdir())) != before:
            raise AssertionError("Rejected mutation created an execution attempt")
    clone = args.output / "restart_refused"
    shutil.copytree(args.run, clone)
    try:
        execute(clone, resume=False)
    except ValueError as error:
        if "Expected Run state ready" not in str(error):
            raise
        results["restart_refused"] = str(error)
    else:
        raise AssertionError("Interrupted Run unexpectedly restarted")
    write_json(args.output / "guard_results.json", results)
    print(results)


if __name__ == "__main__":
    main()
