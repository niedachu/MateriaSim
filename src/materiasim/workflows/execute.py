"""Bounded linear protocol orchestration, separate from native engine operations."""

import time
from pathlib import Path

from materiasim.storage import read_json, run_lock, write_json
from materiasim.engines.registry import get_engine
from materiasim.engines.prepared import validate_prepared
from materiasim.runtime.records import stage_ids
from materiasim.specs.schema import integer, number
from materiasim.runtime.state import set_status, verify_execution
from materiasim.runtime.budget import execution_grant
from materiasim.specs.v3 import profile_check


def execute(run, resume=False, candidate=None, threads=None, max_wall_seconds=None, through=None):
    """Execute with the same frozen whole-operation supervisor used by builds, analyses and research."""
    spec, _ = verify_execution(Path(run).resolve())
    from materiasim.specs.purpose import select_tool
    candidate = select_tool(spec["execution_profile"], "gmx", candidate)
    if spec["execution_profile"]["contract_version"] in (2, 3):
        from materiasim.runtime.control import supervise
        profile = spec["execution_profile"]
        profile_check(profile)
        if threads is not None and threads != profile["threads"]:
            raise ValueError("Requested threads differ from the frozen execution profile")
        if max_wall_seconds is not None:
            number(max_wall_seconds, 1, profile["max_wall_seconds"], "max_wall_seconds")
        if through is not None and through not in stage_ids(spec):
            raise ValueError("Unknown final stage ID")
        expected = "interrupted" if resume else "ready"
        if read_json(Path(run) / "status.json")["status"] != expected:
            raise ValueError("Run is not in the required execution state")
        return supervise(run, spec, "materiasim.workflows.execute", "resume" if resume else "run",
                         dict(run=str(Path(run).resolve()), resume=resume, candidate=candidate,
                              threads=threads, max_wall_seconds=max_wall_seconds, through=through))
    return _execute(run, resume, candidate, threads, max_wall_seconds, through)


def _execute(run, resume=False, candidate="gmx", threads=None, max_wall_seconds=None, through=None, _control=None):
    """Execute v3 stages using the frozen CPU profile; a caller may only shorten its wall allowance."""
    root = Path(run).resolve()
    # Reject old/different-code Runs before even creating a writer-lock file.
    verify_execution(root)
    with run_lock(root):
        spec, manifest = verify_execution(root)
        profile = spec["execution_profile"]
        profile_check(profile)
        threads = profile["threads"] if threads is None else threads
        max_wall_seconds = profile["max_wall_seconds"] if max_wall_seconds is None else max_wall_seconds
        integer(threads, 1, 8, "threads")
        number(max_wall_seconds, 1, profile["max_wall_seconds"], "max_wall_seconds")
        if threads != profile["threads"]:
            raise ValueError("Requested threads differ from the frozen execution profile; create a new Run")
        if _control is not None:
            if manifest["spec_hash"] != _control["expected_spec_hash"]:
                raise ValueError("Run changed before supervised execution")
            max_wall_seconds = min(max_wall_seconds, _control["seconds"])
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
        adapter = get_engine(spec["interaction_bundle"]["engine"])
        engine = adapter.inspect(candidate)
        from materiasim.specs.purpose import validate_environment
        validate_environment(spec, engine)
        if any(engine[key] != manifest["engine"][key] for key in ("sha256", "version", "platform")):
            raise ValueError("Engine identity changed; create a new Run")
        if profile["contract_version"] in (2, 3):
            from materiasim.engines.gromacs.device import resolve_device
            engine["execution_device"] = resolve_device(profile, engine)
            for previous in (root / "attempts").glob("*/device.json"):
                if read_json(previous) != engine["execution_device"]:
                    raise ValueError("Execution device identity changed; create a new Run")
        with execution_grant(root, profile, max_wall_seconds, "resume" if resume else "run") as (attempt, seconds):
            if profile["contract_version"] in (2, 3):
                write_json(attempt / "device.json", engine["execution_device"])
            return execute_protocol(root, spec, adapter, engine, profile, attempt, seconds, through)


def execute_protocol(root, spec, adapter, engine, profile, attempt, seconds, through):
    """Consume one reserved grant and retain failure/status evidence for its ordered stage work."""
    started = time.monotonic()
    ids = stage_ids(spec)
    set_status(root, "running", attempt=attempt.name)
    try:
        for stage in spec["protocol"]["stages"]:
            name = stage["id"]
            seal = root / "stages" / name / "stage.json"
            if seal.exists() and read_json(seal)["status"] == "completed":
                continue
            remaining = seconds - (time.monotonic() - started)
            if remaining < 1:
                return set_status(root, "interrupted", attempt=attempt.name, next_stage=name, reason="wall_budget")
            prepared = adapter.prepare_stage(root, stage, engine, attempt)
            validate_prepared(root, stage, adapter.id, prepared)
            remaining = seconds - (time.monotonic() - started)
            if remaining < 1:
                return set_status(root, "interrupted", attempt=attempt.name, next_stage=name, reason="wall_budget")
            evidence = adapter.run_stage(root, prepared, engine, attempt, profile, remaining)
            if not evidence.complete or (name != ids[-1] and (evidence.interrupted or name == through)):
                return set_status(root, "interrupted", attempt=attempt.name, stage=name,
                                  reason="checkpoint_or_requested_boundary")
        return set_status(root, "completed", attempt=attempt.name, scientific_quality="not_assessed")
    except Exception as error:
        set_status(root, "failed", attempt=attempt.name, error=str(error))
        write_json(attempt / "failure.json", dict(error=str(error)))
        raise


if __name__ == "__main__":
    from materiasim.runtime.control import worker_main
    worker_main(_execute)
