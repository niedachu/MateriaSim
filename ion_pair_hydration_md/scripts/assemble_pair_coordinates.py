#!/usr/bin/env python3
"""Place separate CAT and ANI GRO coordinates in a cubic box without covalent joining."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def read_gro(path: Path) -> list[tuple[int, str, str, int, np.ndarray]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    count = int(lines[1].strip())
    records = []
    for line in lines[2 : 2 + count]:
        records.append((int(line[:5]), line[5:10].strip(), line[10:15].strip(), int(line[15:20]), np.array([float(line[20:28]), float(line[28:36]), float(line[36:44])], dtype=float)))
    if len(records) != count:
        raise ValueError(f"truncated GRO file: {path}")
    return records


def moved(records: list[tuple[int, str, str, int, np.ndarray]], residue_number: int, center: np.ndarray) -> list[tuple[int, str, str, int, np.ndarray]]:
    centroid = np.mean([record[4] for record in records], axis=0)
    return [(residue_number, resname, atomname, atomid, position - centroid + center) for _, resname, atomname, atomid, position in records]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cat", type=Path, required=True)
    parser.add_argument("--ani", type=Path, required=True)
    parser.add_argument("--box-nm", type=float, default=4.5)
    parser.add_argument("--separation-nm", type=float, default=2.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 0 < args.separation_nm < args.box_nm - 1.0:
        raise ValueError("separation must fit inside the box with a 0.5 nm margin")
    midpoint = np.full(3, args.box_nm / 2.0)
    cat_center = midpoint.copy()
    ani_center = midpoint.copy()
    cat_center[0] -= args.separation_nm / 2.0
    ani_center[0] += args.separation_nm / 2.0
    records = moved(read_gro(args.cat), 1, cat_center) + moved(read_gro(args.ani), 2, ani_center)
    for _, _, _, _, position in records:
        if np.any(position <= 0.0) or np.any(position >= args.box_nm):
            raise ValueError("placed ion extends outside the initial box")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        handle.write("Noncovalent CAT/ANI pair, initial separation 2.0 nm\n")
        handle.write(f"{len(records):5d}\n")
        for index, (residue, resname, atomname, _, position) in enumerate(records, start=1):
            handle.write(f"{residue:5d}{resname:<5}{atomname:>5}{index:5d}{position[0]:8.3f}{position[1]:8.3f}{position[2]:8.3f}\n")
        handle.write(f"{args.box_nm:10.5f}{args.box_nm:10.5f}{args.box_nm:10.5f}\n")


if __name__ == "__main__":
    main()
