"""Streaming periodic hydration contacts; input files are owned by a separate AnalysisRun."""

import csv
import platform

from materiasim.storage import sha256, utc_now

def contact_sets(water_positions, reference_positions, dimensions, cutoff_nm):
    """Return unique water indices within cutoff_nm of any site atom under PBC."""
    import numpy as np
    from MDAnalysis.lib.distances import distance_array

    distances = distance_array(reference_positions, water_positions, box=dimensions)
    return set(np.flatnonzero((distances <= cutoff_nm * 10).any(axis=0)).tolist())


def prepare_selections(universe, config, mapping):
    """Validate topology order, nonempty site groups and one oxygen per SOL molecule."""
    if universe.atoms.n_atoms != mapping["atom_count"]:
        raise ValueError("Trajectory topology atom count differs from frozen mapping")
    for atom, expected in zip(universe.atoms, mapping["atoms"]):
        if atom.name != expected["name"][:5] or atom.resname != expected["resname"][:5]:
            raise ValueError("Analysis topology order differs from frozen mapping")
    water = universe.select_atoms(config["water_oxygen_selection"])
    if not len(water) or len(water.residues) != len(water):
        raise ValueError("Water selection must contain one oxygen per molecule")
    if len(water) != mapping["counts"]["SOL"] or any(atom.resname != "SOL" or not atom.name.startswith("O") for atom in water):
        raise ValueError("Water selection does not cover all SOL oxygen atoms exactly once")
    groups = {}
    for name, site in config["sites"].items():
        group = universe.select_atoms(site["selection"])
        if not len(group) or any(atom.resname == "SOL" for atom in group):
            raise ValueError(f"Site must select non-solvent atoms: {name}")
        groups[name] = group
    return water, groups


def hydration_contacts(topology, trajectory, mapping, config, output, identity):
    """Count one frozen trajectory using explicit selections; return engineering-only summary."""
    import MDAnalysis as mda
    import numpy as np

    universe = mda.Universe(str(topology), str(trajectory))
    try:
        water, groups = prepare_selections(universe, config, mapping)
        columns = [*groups, "union"]
        sums, squares = dict.fromkeys(columns, 0), dict.fromkeys(columns, 0)
        previous_time, frames, first_time = None, 0, None
        with (output / "hydration_counts.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["time_ps", *columns])
            writer.writeheader()
            for frame in universe.trajectory:
                if (not np.isfinite(frame.time) or not np.isfinite(frame.positions).all()
                        or frame.dimensions is None or not np.isfinite(frame.dimensions).all()
                        or np.any(frame.dimensions[:3] <= 0)):
                    raise ValueError("Invalid frame coordinates, time or box")
                if previous_time is not None and frame.time <= previous_time:
                    raise ValueError("Trajectory contains duplicate/nonmonotonic times")
                sets = {name: contact_sets(water.positions, group.positions, frame.dimensions,
                                          config["sites"][name]["cutoff_nm"]) for name, group in groups.items()}
                counts = {name: len(indices) for name, indices in sets.items()}
                counts["union"] = len(set().union(*sets.values()))
                writer.writerow(dict(time_ps=float(frame.time), **counts))
                for name, count in counts.items():
                    sums[name] += count
                    squares[name] += count * count
                frames += 1
                first_time = float(frame.time) if first_time is None else first_time
                previous_time = float(frame.time)
    finally:
        universe.trajectory.close()
    if frames < 2:
        raise ValueError("At least two frames are required for engineering comparison")
    summary = {name: dict(mean=sums[name] / frames,
                         population_std=(max(0, squares[name] / frames - (sums[name] / frames) ** 2)) ** .5)
               for name in columns}
    report = dict(purpose="engineering_smoke", scientific_quality="not_assessed", run_id=identity["run_id"],
                  created_utc=utc_now(), spec_hash=identity["spec_hash"], selection=config, frames=frames,
                  time_range_ps=[first_time, previous_time], equilibration_discard_ps=0,
                  summary=summary, independent_samples=None, confidence_interval=None,
                  warning="Provisional contact cutoffs; short trajectory, no scientific hydration conclusion.",
                  versions=dict(python=platform.python_version(), MDAnalysis=mda.__version__, numpy=np.__version__),
                  topology_sha256=sha256(topology), trajectory_sha256=sha256(trajectory),
                  csv_sha256=sha256(output / "hydration_counts.csv"))
    return report
