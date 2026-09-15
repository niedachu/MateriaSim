"""Measured copy admission and independent immutable copies, not a filesystem quota."""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import shutil

from materiasim.errors import MateriaSimError
from materiasim.storage import sha256

_budget = ContextVar("materiasim_copy_budget", default=None)


@contextmanager
def copy_budget(paths, maximum, reserve):
    """Apply an operation's registered output quota and free-byte reserve to its copies."""
    token = _budget.set((list(map(Path, paths)), maximum, reserve))
    try:
        yield
    finally:
        _budget.reset(token)


def files_under(source):
    """Enumerate regular source files without following symlinks or special device files."""
    source = Path(source)
    if source.is_symlink():
        raise ValueError("Copy source cannot be a symlink")
    if source.is_file():
        return [source]
    if not source.is_dir():
        raise ValueError("Copy source must be a regular file or directory")
    files = []
    for path in source.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("Copy tree contains a link or special file")
        if path.is_file():
            files.append(path)
    return files


def preflight(sources, destination):
    """Measure every planned source byte, rejecting insufficient space before creating a copy."""
    files = [file for source in sources for file in files_under(source)]
    size = sum(path.stat().st_size for path in files)
    parent = Path(destination).absolute()
    if any(p.is_symlink() for p in (parent, *parent.parents)):
        raise ValueError("Copy destination cannot contain symlinks")
    while not parent.exists():
        parent = parent.parent
    profile = _budget.get()
    reserve = profile[2] if profile is not None else 0
    if shutil.disk_usage(parent).free < size + reserve:
        raise MateriaSimError("BUDGET_EXHAUSTED", "Insufficient free bytes for copy and disk reserve", category="budget")
    if profile is not None:
        # Count logical files, including existing independent append/analysis generations.
        existing = {p for root in profile[0] if root.exists() for p in files_under(root)}
        used = sum(path.stat().st_size for path in existing)
        if used + size > profile[1]:
            raise MateriaSimError("BUDGET_EXHAUSTED", "Copy exceeds registered output storage allowance", category="budget")
    return dict(copy_bytes=size, files=len(files), reserve_bytes=reserve)


def copy_file(source, destination):
    """Create a non-overwriting independent file and verify source/destination byte identities."""
    source, destination = Path(source), Path(destination)
    preflight([source], destination)
    digest = sha256(source)
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
    if sha256(source) != digest or sha256(destination) != digest:
        raise ValueError("Source changed during checked copy")
    return str(destination)


def copy_tree(source, destination):
    """Copy a complete checked tree without hardlinks, preserving partial failures for diagnosis."""
    source, destination = Path(source), Path(destination)
    preflight([source], destination)
    before = {str(p.relative_to(source)): sha256(p) for p in files_under(source)}
    shutil.copytree(source, destination, copy_function=copy_file)
    after = {str(p.relative_to(source)): sha256(p) for p in files_under(source)}
    copied = {str(p.relative_to(destination)): sha256(p) for p in files_under(destination)}
    if before != after or before != copied:
        raise ValueError("Copy tree inventory changed")
    return str(destination)
