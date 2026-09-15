"""Explicit engine registration; unavailable backends never receive dummy implementations."""

from materiasim.engines.gromacs.adapter import ADAPTER
from materiasim.errors import MateriaSimError

ENGINES = {ADAPTER.id: ADAPTER}


def get_engine(name):
    """Return the registered adapter or reject an unsupported engine identifier."""
    if name not in ENGINES:
        raise MateriaSimError("UNSUPPORTED_COMBINATION", f"Engine not implemented: {name}", field="engine")
    return ENGINES[name]
