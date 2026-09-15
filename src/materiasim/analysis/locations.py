"""Discover explicit operation-owned analysis generations and the existing flat layout."""

from pathlib import Path


def generations(parent):
    """Return all direct legacy or operation-owned analysis directories, retaining failed generations."""
    parent = Path(parent)
    if not parent.exists():
        return []
    result = []
    for child in sorted(parent.iterdir()):
        if child.is_symlink() or not child.is_dir():
            raise ValueError("Unexpected artifact in analysis output root")
        if child.name.startswith("operation-"):
            items = list(child.iterdir())
            if not items or any(p.is_symlink() or not p.is_dir() for p in items):
                raise ValueError("Empty or invalid analysis operation namespace")
            result.extend(sorted(items))
        else:
            result.append(child)
    return result
