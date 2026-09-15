"""Single-Run execution grants with cumulative charging and conservative crash handling."""

import time
from contextlib import contextmanager

from materiasim.errors import MateriaSimError
from materiasim.specs.schema import fields, number
from materiasim.storage import read_json, write_json

GRACE_SECONDS = 25


def budget_record(root, profile):
    """Read a budget ledger and require one event per existing execution attempt."""
    path = root / "execution.json"
    value = read_json(path) if path.exists() else dict(contract_version=1, events=[], active=None)
    fields(value, ("contract_version", "events", "active"), "execution ledger")
    if type(value["contract_version"]) is not int or value["contract_version"] != 1:
        raise ValueError("Unsupported execution ledger version")
    attempts = {p.name for pattern in ("run-*", "resume-*") for p in (root / "attempts").glob(pattern)}
    if not isinstance(value["events"], list) or {event["attempt"] for event in value["events"]} != attempts:
        raise ValueError("Execution ledger differs from existing attempts")
    if len(value["events"]) != len(attempts):
        raise ValueError("Duplicate execution budget events")
    for event in value["events"]:
        fields(event, ("attempt", "charged_seconds", "reserved_seconds", "closed"), "execution event")
        number(event["charged_seconds"], 0, 1e12, "charged_seconds")
        number(event["reserved_seconds"], 1, profile["total_wall_seconds"], "reserved_seconds")
        if type(event["closed"]) is not bool:
            raise ValueError("Execution event closed flag must be boolean")
    if value["active"] is not None or any(not event["closed"] for event in value["events"]):
        raise ValueError("Uncertain execution budget handoff; do not retry or reset its reservation")
    return value


@contextmanager
def execution_grant(root, profile, requested, action):
    """Reserve before creating a Run attempt; yield attempt/grant and charge measured execution plus exit time."""
    from materiasim.runtime.state import new_attempt
    ledger = budget_record(root, profile)
    spent = sum(event["charged_seconds"] for event in ledger["events"])
    grant = min(requested, profile["total_wall_seconds"] - spent - GRACE_SECONDS)
    if grant < 1 or len(ledger["events"]) >= profile["max_attempts"]:
        raise MateriaSimError("BUDGET_EXHAUSTED", "Run execution time or attempt budget exhausted", category="budget")
    attempt = new_attempt(root, action)
    event = dict(attempt=attempt.name, charged_seconds=grant + GRACE_SECONDS,
                 reserved_seconds=grant + GRACE_SECONDS, closed=False)
    ledger["events"].append(event)
    ledger["active"] = attempt.name
    write_json(root / "execution.json", ledger)
    started = time.monotonic()
    try:
        yield attempt, grant
    finally:
        event.update(charged_seconds=time.monotonic() - started, closed=True)
        ledger["active"] = None
        write_json(root / "execution.json", ledger)
