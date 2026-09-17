"""Explicit control exceptions and conservative operation-aware failure categories."""

from materiasim.errors import MateriaSimError, MissingDependency, error_record


class PauseRequested(Exception):
    """Stop at an admitted core-operation boundary without marking the scientific work failed."""


def failure(error, phase):
    """Return a stable diagnostic by exception type/operation, never by searching stderr prose.

    An execution failure is not automatically a numerical failure. Unclassified
    native or Python exceptions stay unknown and never obtain retry permission.
    """
    record = error_record(error)
    if isinstance(error, MateriaSimError):
        return record
    if isinstance(error, MissingDependency):
        code, category = "MISSING_DEPENDENCY", "capability"
    elif isinstance(error, OSError):
        code, category = "STORAGE_OR_SYSTEM_ERROR", "resource"
    elif phase == "analyze":
        code, category = "ANALYSIS_FAILED", "analysis"
    elif phase in ("admission", "identity"):
        code, category = "INPUT_OR_IDENTITY_REJECTED", "integrity"
    else:
        code, category = "UNKNOWN_OPERATION_FAILURE", "unknown"
    record["error"].update(code=code, category=category, recoverability="not_assessed")
    return record
