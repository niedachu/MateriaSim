"""Explicit experiment composition, independent of engine coordinate formats."""


def declared_counts(spec):
    """Return the exact non-solvent molecule counts specified by the experiment."""
    return {item["id"]: item["count"] for item in spec["components"]}
