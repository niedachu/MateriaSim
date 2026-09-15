"""Stable machine-readable errors; messages never determine recovery permission."""


class MateriaSimError(ValueError):
    """Carry an explicit code, field and evidence references for a rejected operation."""

    def __init__(self, code, message, *, category="validation", field=None, evidence_refs=()):
        """Store the supplied diagnostic; recoverability remains unassessed until Run checks."""
        super().__init__(message)
        self.code = code
        self.category = category
        self.field = field
        self.evidence_refs = list(evidence_refs)


class MissingDependency(FileNotFoundError):
    """Identify an absent native tool while preserving existing FileNotFoundError callers."""


def error_record(error):
    """Serialize a boundary error without inferring retry permission from its text."""
    if isinstance(error, MateriaSimError):
        code, category = error.code, error.category
        field, evidence = error.field, error.evidence_refs
    else:
        if isinstance(error, MissingDependency):
            code = "MISSING_DEPENDENCY"
        elif isinstance(error, FileNotFoundError):
            code = "MISSING_RESOURCE"
        else:
            code = "INVALID_SPEC" if isinstance(error, ValueError) else "OPERATION_FAILED"
        category = "validation" if isinstance(error, ValueError) else "execution"
        field, evidence = None, []
    return dict(contract_version=1, ok=False, error=dict(
        code=code, category=category, message=str(error), field=field,
        evidence_refs=evidence, recoverability="not_assessed"))
