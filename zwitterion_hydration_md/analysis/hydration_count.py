#!/usr/bin/env python3
"""Count site-specific and union-unique hydration waters with MDAnalysis."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import MDAnalysis as mda
import numpy as np
from MDAnalysis.lib.distances import distance_array

from hydration_core import summarize_counts, union_unique_water_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--trajectory", type=Path, required=True)
    parser.add_argument("--site-config", type=Path, required=True)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_site_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    water_selection = config.get("water_oxygen_selection")
    sites = config.get("sites")
    if not isinstance(water_selection, str) or not water_selection.strip():
        raise ValueError("site config requires water_oxygen_selection")
    if not isinstance(sites, dict) or not sites:
        raise ValueError("site config requires a non-empty sites object")
    for name, site in sites.items():
        if not isinstance(site.get("selection"), str) or not site["selection"].strip():
            raise ValueError(f"site {name} requires a selection")
        if site.get("mode") not in {"atoms", "cog"}:
            raise ValueError(f"site {name} mode must be atoms or cog")
        cutoff = site.get("cutoff_nm")
        if not isinstance(cutoff, (int, float)) or cutoff <= 0:
            raise ValueError(f"site {name} requires a positive cutoff_nm")
    return config


def main() -> None:
    args = parse_args()
    if args.stride < 1:
        raise ValueError("--stride must be at least 1")
    config = load_site_config(args.site_config)
    universe = mda.Universe(str(args.topology), str(args.trajectory))
    waters = universe.select_atoms(config["water_oxygen_selection"])
    if len(waters) == 0:
        raise ValueError("water oxygen selection matched no atoms")
    if len(np.unique(waters.resindices)) != len(waters):
        raise ValueError("water selection must contain exactly one oxygen per water residue")

    site_groups = {}
    for name, site in config["sites"].items():
        group = universe.select_atoms(site["selection"])
        if len(group) == 0:
            raise ValueError(f"site {name} selection matched no atoms")
        site_groups[name] = group

    rows: list[dict[str, float | int]] = []
    for ts in universe.trajectory[:: args.stride]:
        site_hits: dict[str, set[int]] = {}
        row: dict[str, float | int] = {"frame": int(ts.frame), "time_ps": float(ts.time)}
        for name, site in config["sites"].items():
            group = site_groups[name]
            reference = group.positions if site["mode"] == "atoms" else group.center_of_geometry()[None, :]
            distances = distance_array(reference, waters.positions, box=ts.dimensions)
            mask = np.any(distances <= float(site["cutoff_nm"]) * 10.0, axis=0)
            selected_ids = set((waters.indices[mask] + 1).astype(int).tolist())
            site_hits[name] = selected_ids
            row[f"{name}_count"] = len(selected_ids)
        row["total_unique_count"] = len(union_unique_water_ids(site_hits))
        rows.append(row)

    if not rows:
        raise RuntimeError("no trajectory frames were analyzed")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "topology": str(args.topology.resolve()),
        "trajectory": str(args.trajectory.resolve()),
        "site_config": str(args.site_config.resolve()),
        "trajectory_stride": args.stride,
        "frames_analyzed": len(rows),
        "total_unique_count": summarize_counts([int(row["total_unique_count"]) for row in rows]),
        "site_counts": {
            name: summarize_counts([int(row[f"{name}_count"]) for row in rows])
            for name in config["sites"]
        },
        "frame_counts_csv": str(csv_path.resolve()),
    }
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()

