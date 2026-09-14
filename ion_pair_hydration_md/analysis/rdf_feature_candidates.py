#!/usr/bin/env python3
"""Report smoothed RDF first-shell peak and post-peak local-minimum candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def load_xvg(path: Path) -> tuple[np.ndarray, np.ndarray]:
    rows: list[tuple[float, float]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "@")):
            continue
        radius, value = line.split()[:2]
        rows.append((float(radius), float(value)))
    if len(rows) < 7:
        raise ValueError(f"RDF has too few data rows: {path}")
    data = np.asarray(rows, dtype=float)
    return data[:, 0], data[:, 1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rdf", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoothing-points", type=int, default=5)
    parser.add_argument("--peak-min-nm", type=float, default=0.15)
    parser.add_argument("--peak-max-nm", type=float, default=0.45)
    parser.add_argument("--minimum-max-nm", type=float, default=0.60)
    parser.add_argument("--minimum-after-peak-nm", type=float, default=0.04)
    args = parser.parse_args()
    if args.smoothing_points < 3 or args.smoothing_points % 2 == 0:
        raise ValueError("--smoothing-points must be an odd integer of at least 3")

    report: dict[str, object] = {"smoothing_points": args.smoothing_points, "rdfs": {}}
    for path in args.rdf:
        radius, rdf = load_xvg(path)
        padded = np.pad(rdf, args.smoothing_points // 2, mode="edge")
        smoothed = np.convolve(padded, np.ones(args.smoothing_points) / args.smoothing_points, mode="valid")
        peak_indices = np.flatnonzero((radius >= args.peak_min_nm) & (radius <= args.peak_max_nm))
        if not len(peak_indices):
            raise ValueError(f"no peak-search data in {path}")
        peak_index = int(peak_indices[np.argmax(smoothed[peak_indices])])
        candidates = []
        for index in range(peak_index + 1, len(radius) - 1):
            if radius[index] < radius[peak_index] + args.minimum_after_peak_nm:
                continue
            if radius[index] > args.minimum_max_nm:
                break
            if smoothed[index] <= smoothed[index - 1] and smoothed[index] < smoothed[index + 1]:
                candidates.append(
                    {
                        "radius_nm": float(radius[index]),
                        "smoothed_rdf": float(smoothed[index]),
                        "raw_rdf": float(rdf[index]),
                    }
                )
        report["rdfs"][path.name] = {
            "first_shell_peak_nm": float(radius[peak_index]),
            "first_shell_peak_smoothed_rdf": float(smoothed[peak_index]),
            "post_peak_local_minimum_candidates": candidates,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
