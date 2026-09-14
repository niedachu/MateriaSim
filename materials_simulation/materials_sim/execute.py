"""Bounded linear protocol orchestration, separate from native engine operations."""

import time
from pathlib import Path

from .files import read_json, run_lock, write_json
from .gromacs import engine_info
from .gromacs_stage import execute_stage
from .records import stage_ids
from .schema import integer, number
from .state import new_attempt, set_status, verify_execution


def execute(run, resume=False, candidate="gmx", threads=2, max_wall_seconds=180, through=None):
    """Execute frozen ordered stages within a CPU/wall budget, optionally stopping at an ID."""
    integer(threads, 1, 8, "threads")
    number(max_wall_seconds, 1, 600, "max_wall_seconds")
    root = Path(run).resolve()
    # Reject old/different-code Runs before even creating a writer-lock file.
    verify_execution(root)
    with run_lock(root):
        spec, manifest = verify_execution(root)
        ids = stage_ids(spec)
        through = ids[-1] if through is None else through
        if through not in ids:
            raise ValueError("Unknown final stage ID")
        status = read_json(root / "status.json")
        required = "interrupted" if resume else "ready"
        if status["status"] != required:
            raise ValueError(f"Expected Run state {required}, got {status['status']}")
        target_seal = root / "stages" / through / "stage.json"
        if target_seal.exists() and read_json(target_seal)["status"] == "completed":
            raise ValueError("Requested --through stage is already complete")
        engine = engine_info(candidate)
        if any(engine[key] != manifest["engine"][key] for key in ("sha256", "version", "platform")):
            raise ValueError("Engine identity changed; create a new Run")
        attempt = new_attempt(root, "resume" if resume else "run")
        started = time.monotonic()
        set_status(root, "running", attempt=attempt.name)
        try:
            for stage in spec["protocol"]["stages"]:
                name = stage["id"]
                seal = root / "stages" / name / "stage.json"
                if seal.exists() and read_json(seal)["status"] == "completed":
                    continue
                remaining = max_wall_seconds - (time.monotonic() - started)
                if remaining < 1:
                    return set_status(root, "interrupted", attempt=attempt.name, next_stage=name, reason="wall_budget")
                complete, cancelled = execute_stage(root, stage, engine, attempt, threads, remaining)
                if not complete or (name != ids[-1] and (cancelled or name == through)):
                    return set_status(root, "interrupted", attempt=attempt.name, stage=name,
                                      reason="checkpoint_or_requested_boundary")
            return set_status(root, "completed", attempt=attempt.name, scientific_quality="not_assessed")
        except Exception as error:
            set_status(root, "failed", attempt=attempt.name, error=str(error))
            write_json(attempt / "failure.json", dict(error=str(error)))
            raise
