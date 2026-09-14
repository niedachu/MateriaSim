#!/usr/bin/env python3
"""Render a centered GROMACS box snapshot with formal tight-bound waters."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import MDAnalysis as mda
import matplotlib.pyplot as plt
import numpy as np
from MDAnalysis.lib.distances import distance_array
from mpl_toolkits.mplot3d.art3d import Line3DCollection


def element_color(atom_name: str) -> str:
    first = atom_name[0].upper()
    return {"O": "#d73027", "S": "#f4c542", "N": "#4575b4", "C": "#4d4d4d", "H": "#f2f2f2"}.get(first, "#777777")


def cube_edges(length: float) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    corners = [(x, y, z) for x in (0.0, length) for y in (0.0, length) for z in (0.0, length)]
    return [
        (a, b)
        for index, a in enumerate(corners)
        for b in corners[index + 1 :]
        if sum(abs(left - right) > 0 for left, right in zip(a, b)) == 1
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gro", type=Path, required=True)
    parser.add_argument("--site-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.site_config.read_text(encoding="utf-8"))
    universe = mda.Universe(str(args.gro))
    ts = universe.trajectory.ts
    zil = universe.select_atoms("resname ZIL")
    waters = universe.select_atoms(config["water_oxygen_selection"])
    if not len(zil) or not len(waters):
        raise ValueError("snapshot must contain ZIL and water oxygen atoms")

    tight = np.zeros(len(waters), dtype=bool)
    for site in config["sites"].values():
        reference = universe.select_atoms(site["selection"])
        distances = distance_array(reference.positions, waters.positions, box=ts.dimensions)
        tight |= np.any(distances <= float(site["cutoff_nm"]) * 10.0, axis=0)

    figure = plt.figure(figsize=(8, 8), dpi=220)
    axis = figure.add_subplot(111, projection="3d")
    axis.scatter(*waters.positions[~tight].T / 10.0, s=2.0, c="#74add1", alpha=0.14, linewidths=0, label="other water O")
    axis.scatter(*waters.positions[tight].T / 10.0, s=20.0, c="#fdae61", alpha=0.95, edgecolors="#7f3b08", linewidths=0.25, label="tight-bound water O")

    positions_nm = zil.positions / 10.0
    segments = []
    for i in range(len(zil)):
        for j in range(i + 1, len(zil)):
            first, second = zil[i].name[0].upper(), zil[j].name[0].upper()
            cutoff = 0.125 if "H" in {first, second} else 0.190
            if first != "H" or second != "H":
                if np.linalg.norm(positions_nm[i] - positions_nm[j]) <= cutoff:
                    segments.append([positions_nm[i], positions_nm[j]])
    if segments:
        axis.add_collection3d(Line3DCollection(segments, colors="#202020", linewidths=1.2, alpha=0.9))
    for atom in zil:
        axis.scatter(*(atom.position / 10.0), s=42 if atom.name[0].upper() != "H" else 13, c=element_color(atom.name), edgecolors="#222222", linewidths=0.25)

    box_nm = float(ts.dimensions[0]) / 10.0
    axis.add_collection3d(Line3DCollection(cube_edges(box_nm), colors="#333333", linewidths=0.7, alpha=0.65))
    axis.set(xlim=(0, box_nm), ylim=(0, box_nm), zlim=(0, box_nm), xlabel="x / nm", ylabel="y / nm", zlabel="z / nm")
    axis.set_box_aspect((1, 1, 1))
    axis.view_init(elev=20, azim=42)
    axis.set_proj_type("ortho")
    axis.set_title("ZIL in AMBER TIP3P water, 10.000 ns\n4.5 nm cubic box; ZIL-centered periodic image")
    axis.legend(loc="upper left", frameon=True, fontsize=8)
    figure.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, bbox_inches="tight")


if __name__ == "__main__":
    main()
