#!/usr/bin/env python3
"""List water oxygens whose minimum distance is close to a hydration cutoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import MDAnalysis as mda
from MDAnalysis.lib.distances import distance_array


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--site-config", type=Path, required=True)
    parser.add_argument("--time-ps", type=float, required=True)
    parser.add_argument("--tolerance-nm", type=float, default=0.003)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.site_config.read_text(encoding="utf-8"))
    universe = mda.Universe(str(args.topology), str(args.trajectory))
    waters = universe.select_atoms(config["water_oxygen_selection"])
    found = False
    for ts in universe.trajectory:
        if abs(float(ts.time) - args.time_ps) < 1e-6:
            found = True
            break
    if not found:
        raise ValueError(f"no frame found at {args.time_ps} ps")
    report: dict[str, object] = {"time_ps": float(ts.time), "sites": {}}
    for name, site in config["sites"].items():
        atoms = universe.select_atoms(site["selection"])
        distances_nm = distance_array(atoms.positions, waters.positions, box=ts.dimensions).min(axis=0) / 10.0
        cutoff = float(site["cutoff_nm"])
        near = [
            {
                "water_atom_id": int(water_id),
                "minimum_distance_nm": float(distance),
                "delta_from_cutoff_nm": float(distance - cutoff),
            }
            for water_id, distance in zip(waters.indices + 1, distances_nm, strict=True)
            if abs(float(distance) - cutoff) <= args.tolerance_nm
        ]
        report["sites"][name] = {"cutoff_nm": cutoff, "near_cutoff_waters": near}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
