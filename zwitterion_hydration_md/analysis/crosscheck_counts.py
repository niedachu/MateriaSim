#!/usr/bin/env python3
"""Compare GROMACS gmx-select counts with MDAnalysis frame counts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_gromacs_xvg(path: Path) -> dict[float, int]:
    values: dict[float, int] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith(("#", "@")):
            continue
        fields = line.split()
        if len(fields) < 2:
            raise ValueError(f"invalid XVG line {line_number}: {raw_line}")
        time_ps = float(fields[0])
        count = float(fields[1])
        if not count.is_integer():
            raise ValueError(f"non-integer GROMACS count at {time_ps} ps: {count}")
        values[time_ps] = int(count)
    if not values:
        raise ValueError("GROMACS count file contains no data")
    return values


def read_mdanalysis_csv(path: Path) -> dict[float, int]:
    values: dict[float, int] = {}
    with path.open("r", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            values[float(row["time_ps"])] = int(row["total_unique_count"])
    if not values:
        raise ValueError("MDAnalysis count file contains no data")
    return values


def compare_counts(gromacs: dict[float, int], mdanalysis: dict[float, int], time_tolerance_ps: float) -> dict:
    unmatched_mda = set(mdanalysis)
    mismatches = []
    matched = 0
    for gmx_time, gmx_count in sorted(gromacs.items()):
        candidates = [time for time in unmatched_mda if abs(time - gmx_time) <= time_tolerance_ps]
        if len(candidates) != 1:
            mismatches.append({"gromacs_time_ps": gmx_time, "reason": "no unique matching MDAnalysis frame"})
            continue
        mda_time = candidates[0]
        unmatched_mda.remove(mda_time)
        matched += 1
        if gmx_count != mdanalysis[mda_time]:
            mismatches.append(
                {
                    "gromacs_time_ps": gmx_time,
                    "mdanalysis_time_ps": mda_time,
                    "gromacs_count": gmx_count,
                    "mdanalysis_count": mdanalysis[mda_time],
                }
            )
    for time in sorted(unmatched_mda):
        mismatches.append({"mdanalysis_time_ps": time, "reason": "no matching GROMACS frame"})
    return {"matched_frames": matched, "mismatch_count": len(mismatches), "mismatches": mismatches}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gromacs-xvg", type=Path, required=True)
    parser.add_argument("--mdanalysis-csv", type=Path, required=True)
    parser.add_argument("--time-tolerance-ps", type=float, default=1e-3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.time_tolerance_ps < 0:
        raise ValueError("time tolerance cannot be negative")
    report = compare_counts(
        read_gromacs_xvg(args.gromacs_xvg),
        read_mdanalysis_csv(args.mdanalysis_csv),
        args.time_tolerance_ps,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if report["mismatch_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

