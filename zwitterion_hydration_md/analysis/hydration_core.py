"""Dependency-free hydration counting primitives used by analysis and tests."""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping, Sequence


Vector3 = tuple[float, float, float]


def union_unique_water_ids(site_hits: Mapping[str, Iterable[int]]) -> set[int]:
    """Return unique water IDs selected by any hydration site."""
    combined: set[int] = set()
    for water_ids in site_hits.values():
        combined.update(int(water_id) for water_id in water_ids)
    return combined


def minimum_image_delta(delta: float, box_length: float) -> float:
    """Return an orthorhombic minimum-image displacement."""
    if box_length <= 0:
        raise ValueError("box lengths must be positive")
    return delta - box_length * math.floor(delta / box_length + 0.5)


def squared_minimum_image_distance(a: Vector3, b: Vector3, box: Vector3) -> float:
    """Squared distance under orthorhombic periodic boundary conditions."""
    deltas = (
        minimum_image_delta(a[0] - b[0], box[0]),
        minimum_image_delta(a[1] - b[1], box[1]),
        minimum_image_delta(a[2] - b[2], box[2]),
    )
    return sum(component * component for component in deltas)


def select_water_ids_reference(
    site_positions: Mapping[str, Sequence[Vector3]],
    site_cutoffs: Mapping[str, float],
    water_positions: Mapping[int, Vector3],
    box: Vector3,
) -> dict[str, set[int]]:
    """Small reference implementation for synthetic tests, coordinates in nm.

    Production trajectories use GROMACS and MDAnalysis distance engines. This
    implementation is deliberately simple and serves as an independent oracle.
    """
    if set(site_positions) != set(site_cutoffs):
        raise ValueError("site positions and cutoffs must contain identical site names")
    selected: dict[str, set[int]] = {}
    for site_name, positions in site_positions.items():
        cutoff = float(site_cutoffs[site_name])
        if cutoff <= 0:
            raise ValueError(f"cutoff for {site_name} must be positive")
        if not positions:
            raise ValueError(f"site {site_name} contains no positions")
        cutoff_sq = cutoff * cutoff
        selected[site_name] = {
            int(water_id)
            for water_id, water_position in water_positions.items()
            if any(
                squared_minimum_image_distance(site_position, water_position, box) <= cutoff_sq
                for site_position in positions
            )
        }
    return selected


def quantile(values: Sequence[float], probability: float) -> float:
    """Linear-interpolated quantile compatible with NumPy's default method."""
    if not values:
        raise ValueError("cannot calculate a quantile of an empty sequence")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between 0 and 1")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def summarize_counts(counts: Sequence[int]) -> dict[str, float | int]:
    """Summarize a non-empty hydration-count time series."""
    if not counts:
        raise ValueError("counts must not be empty")
    integer_counts = [int(value) for value in counts]
    if any(value < 0 for value in integer_counts):
        raise ValueError("hydration counts cannot be negative")
    return {
        "mean": statistics.fmean(integer_counts),
        "sample_std": statistics.stdev(integer_counts) if len(integer_counts) > 1 else 0.0,
        "minimum": min(integer_counts),
        "maximum": max(integer_counts),
        "p05": quantile(integer_counts, 0.05),
        "p25": quantile(integer_counts, 0.25),
        "median": quantile(integer_counts, 0.50),
        "p75": quantile(integer_counts, 0.75),
        "p95": quantile(integer_counts, 0.95),
    }

