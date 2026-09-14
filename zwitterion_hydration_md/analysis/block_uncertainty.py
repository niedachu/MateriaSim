#!/usr/bin/env python3
"""Estimate a time-block standard error from a hydration-count CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--count-column", default="total_unique_count")
    parser.add_argument("--blocks", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.blocks < 2:
        raise ValueError("--blocks must be at least 2")

    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or args.count_column not in rows[0]:
        raise ValueError(f"missing count column: {args.count_column}")
    if len(rows) < args.blocks:
        raise ValueError("fewer frames than requested blocks")

    block_rows = []
    block_means = []
    for index in range(args.blocks):
        start = index * len(rows) // args.blocks
        stop = (index + 1) * len(rows) // args.blocks
        subset = rows[start:stop]
        values = [float(row[args.count_column]) for row in subset]
        mean = statistics.fmean(values)
        block_means.append(mean)
        block_rows.append(
            {
                "block": index + 1,
                "start_time_ps": float(subset[0]["time_ps"]),
                "end_time_ps": float(subset[-1]["time_ps"]),
                "frames": len(subset),
                "mean": mean,
            }
        )

    block_std = statistics.stdev(block_means)
    report = {
        "input": str(args.input.resolve()),
        "count_column": args.count_column,
        "block_count": args.blocks,
        "block_means": block_rows,
        "overall_frame_mean": statistics.fmean(float(row[args.count_column]) for row in rows),
        "block_mean_sample_std": block_std,
        "block_mean_sem": block_std / math.sqrt(args.blocks),
        "interpretation": "Time-block SEM; it does not represent uncertainty across independent trajectories.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
