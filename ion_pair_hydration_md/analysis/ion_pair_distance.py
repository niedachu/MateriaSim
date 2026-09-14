#!/usr/bin/env python3
"""Write the CAT/ANI center-of-mass distance for each trajectory frame."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import MDAnalysis as mda
import numpy as np


def minimum_image(delta: np.ndarray, dimensions_angstrom: np.ndarray) -> np.ndarray:
    box = dimensions_angstrom[:3]
    return delta - box * np.floor(delta / box + 0.5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    universe = mda.Universe(str(args.topology), str(args.trajectory))
    cat = universe.select_atoms("resname CAT")
    ani = universe.select_atoms("resname ANI")
    if not len(cat) or not len(ani):
        raise ValueError("trajectory must contain CAT and ANI")
    rows = []
    for ts in universe.trajectory:
        delta = minimum_image(ani.center_of_mass() - cat.center_of_mass(), ts.dimensions)
        rows.append({"frame": ts.frame, "time_ps": float(ts.time), "cat_ani_com_distance_nm": float(np.linalg.norm(delta) / 10.0)})
    values = [row["cat_ani_com_distance_nm"] for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    args.output.write_text(json.dumps({"frames": len(rows), "minimum_nm": min(values), "maximum_nm": max(values), "mean_nm": float(np.mean(values)), "final_nm": values[-1]}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
