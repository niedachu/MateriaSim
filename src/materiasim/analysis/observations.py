"""Method-owned observation semantics, independent of research scheduling."""

from materiasim.specs.schema import number


def component_observations(report):
    """Expose the existing raw molecular-pair mean with its explicit normalization."""
    value = report["mean_unique_molecule_pairs"]
    number(value, 0, 1e15, "component mean")
    return dict(normalization=report["normalization"], metrics=[
        dict(metric="mean_unique_molecule_pairs", unit="molecule_pairs", value=value)])


def hydration_observations(report):
    """Expose the existing union water-contact mean, not a thermodynamic hydration number."""
    value = report["summary"]["union"]["mean"]
    number(value, 0, 1e15, "water-contact mean")
    return dict(normalization="unique water oxygen union per frame; no site-count normalization", metrics=[
        dict(metric="mean_union_water_contacts", unit="water_molecules", value=value)])
