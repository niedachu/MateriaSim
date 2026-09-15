"""Small functional engine boundary used by the real shared workflows."""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class BuildResult:
    """Return actual atom mapping and typed frozen assets from an implemented builder."""

    mapping: dict
    system: dict


@dataclass(frozen=True)
class PreparedStage:
    """Carry a compiled stage, typed assets, effective parameters and its frozen input closure.

    ``stage`` is the resolved protocol descriptor, not permission to override native inputs.
    Asset paths are relative to the owning Run; engine identity excludes executable location.
    """

    engine: str
    stage: dict
    inputs: dict
    artifacts: dict
    effective_parameters: dict
    dependency_hashes: dict
    engine_identity: dict
    contract_version: int = 1


@dataclass(frozen=True)
class StageEvidence:
    """Report native completion and an observed interruption, not scientific convergence."""

    complete: bool
    interrupted: bool


@dataclass(frozen=True)
class EngineAdapter:
    """Bind actual native validation, inspection, construction and stage operations."""

    id: str
    validate: Callable
    inspect: Callable
    build: Callable
    prepare_stage: Callable
    run_stage: Callable
    purposes: tuple
