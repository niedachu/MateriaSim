"""Explicit bindings for the two real native construction pipelines."""

from materiasim.errors import MateriaSimError


def prebuilt(root, spec, sources, engine, attempt, packmol):
    """Build an explicitly prebuilt native solute/mixture through the existing validated pipeline."""
    from materiasim.engines.gromacs.build import prepare_system
    return prepare_system(root, spec, sources, engine, attempt)


def packed(root, spec, sources, engine, attempt, packmol):
    """Assemble frozen molecular templates using the existing bounded Packmol pipeline."""
    from materiasim.engines.gromacs.packed import prepare_packed
    return prepare_packed(root, spec, sources, engine, attempt, packmol)


BUILDERS = {"gromacs_prebuilt": prebuilt, "gromacs_packmol": packed}


def get_builder(name):
    """Return an actual builder; unknown implementations never receive placeholder behavior."""
    if name not in BUILDERS:
        raise MateriaSimError("UNSUPPORTED_COMBINATION", f"Builder not implemented: {name}", field="scenario.builder")
    return BUILDERS[name]
