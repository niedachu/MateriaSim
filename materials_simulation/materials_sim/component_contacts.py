"""Periodic unique-molecule contacts between explicit component identities, including dry boxes."""

import csv
from collections import Counter

from .files import sha256, utc_now
from .schema import fields, identifier, number


def validate_contacts(config):
    """Require two component IDs and a finite contact cutoff in nm; same-component contacts are allowed."""
    fields(config, ("component_a", "component_b", "cutoff_nm"), "component contacts")
    for key in ("component_a", "component_b"):
        identifier(config[key], key)
    number(config["cutoff_nm"], .01, 1.0, "cutoff_nm")


def molecule_pairs(positions_a, positions_b, ids_a, ids_b, dimensions, cutoff_nm):
    """Return unordered unique molecular contact pairs; exclude all intramolecular atom contacts."""
    from MDAnalysis.lib.distances import capped_distance

    pairs = capped_distance(positions_a, positions_b, max_cutoff=cutoff_nm * 10,
                            box=dimensions, return_distances=False)
    return {tuple(sorted((ids_a[i], ids_b[j]))) for i, j in pairs if ids_a[i] != ids_b[j]}


def component_contacts(topology, trajectory, mapping, config, output, identity):
    """Stream a frozen trajectory and return contact-count distribution, not equilibrium probabilities."""
    import MDAnalysis as mda
    import numpy as np

    validate_contacts(config)
    universe = mda.Universe(str(topology), str(trajectory))
    histogram, frames, previous, first = Counter(), 0, None, None
    try:
        if len(universe.atoms) != mapping["atom_count"]:
            raise ValueError("Contact topology atom count differs from mapping")
        for atom, frozen in zip(universe.atoms, mapping["atoms"]):
            if (atom.name, atom.resname) != (frozen["name"][:5], frozen["resname"][:5]):
                raise ValueError("Contact topology order differs from mapping")
        indices = [[i for i, atom in enumerate(mapping["atoms"]) if atom["component_id"] == config[key]]
                   for key in ("component_a", "component_b")]
        if any(not group for group in indices):
            raise ValueError("Contact component not present in the actual system")
        ids = [[mapping["atoms"][i]["molecule_id"] for i in group] for group in indices]
        with (output / "component_contacts.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["time_ps", "unique_molecule_pairs"])
            writer.writeheader()
            for frame in universe.trajectory:
                if (not np.isfinite(frame.time) or not np.isfinite(frame.positions).all()
                        or frame.dimensions is None or not np.isfinite(frame.dimensions).all()
                        or np.any(frame.dimensions[:3] <= 0)):
                    raise ValueError("Invalid contact frame geometry/time")
                if previous is not None and frame.time <= previous:
                    raise ValueError("Duplicate/nonmonotonic contact frame time")
                pairs = molecule_pairs(frame.positions[indices[0]], frame.positions[indices[1]],
                                       ids[0], ids[1], frame.dimensions, config["cutoff_nm"])
                count = len(pairs)
                histogram[count] += 1
                writer.writerow(dict(time_ps=float(frame.time), unique_molecule_pairs=count))
                frames += 1
                first = float(frame.time) if first is None else first
                previous = float(frame.time)
    finally:
        universe.trajectory.close()
    if frames < 2:
        raise ValueError("At least two contact frames are required")
    mean = sum(count * frequency for count, frequency in histogram.items()) / frames
    return dict(purpose="engineering_smoke", scientific_quality="not_assessed", kind="component_contacts",
                run_id=identity["run_id"], spec_hash=identity["spec_hash"], created_utc=utc_now(),
                selection=config, frames=frames, time_range_ps=[first, previous],
                contact_count_histogram=dict(sorted(histogram.items())), mean_unique_molecule_pairs=mean,
                normalization="unordered unique inter-molecular pairs per frame; no atom-count normalization",
                equilibration_discard_ps=0, independent_samples=None, confidence_interval=None,
                warning="Short correlated frames; contacts are not binding free energies or equilibrium populations.",
                versions=dict(MDAnalysis=mda.__version__, numpy=np.__version__),
                topology_sha256=sha256(topology), trajectory_sha256=sha256(trajectory),
                csv_sha256=sha256(output / "component_contacts.csv"))
