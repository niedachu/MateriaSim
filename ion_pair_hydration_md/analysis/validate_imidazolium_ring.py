#!/usr/bin/env python3
"""Check that the CAT imidazolium heavy-atom ring remains planar in a GRO frame."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


RING_NAMES = {"N1", "C3", "N2", "C9", "C10"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gro", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold-nm", type=float, default=0.03)
    args = parser.parse_args()

    lines = args.gro.read_text(encoding="utf-8").splitlines()
    atom_count = int(lines[1].strip())
    ring = []
    for line in lines[2 : 2 + atom_count]:
        residue = line[5:10].strip()
        atom = line[10:15].strip()
        if residue == "CAT" and atom in RING_NAMES:
            ring.append((atom, [float(line[20:28]), float(line[28:36]), float(line[36:44])]))
    if {name for name, _ in ring} != RING_NAMES:
        raise ValueError(f"expected CAT ring atoms {sorted(RING_NAMES)}, found {[name for name, _ in ring]}")
    coordinates = np.asarray([xyz for _, xyz in ring])
    centroid = coordinates.mean(axis=0)
    _, _, vh = np.linalg.svd(coordinates - centroid, full_matrices=False)
    normal = vh[-1]
    deviations = np.abs((coordinates - centroid) @ normal)
    maximum = float(deviations.max())
    payload = {
        "frame": str(args.gro),
        "ring_atoms": [name for name, _ in ring],
        "max_distance_from_best_fit_plane_nm": maximum,
        "threshold_nm": args.threshold_nm,
        "passes_planarity_screen": maximum <= args.threshold_nm,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if not payload["passes_planarity_screen"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
