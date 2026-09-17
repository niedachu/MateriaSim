"""Transactional, hash-chained local Campaign events with deterministic state projection."""

import json
import math
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from materiasim.harness.contracts import TERMINAL, MAX_JSON_BYTES
from materiasim.storage import content_hash, utc_now, unique_pairs, reject_constant
from materiasim.specs.schema import fields, identifier


def connect(root, writable=False):
    """Open an existing journal only; read queries never create a database or lock file."""
    path = Path(root) / "events.sqlite3"
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing regular Campaign journal")
    connection = sqlite3.connect(path.as_uri() + ("?mode=rw" if writable else "?mode=ro"),
                                 uri=True, timeout=5)
    if writable:
        connection.execute("PRAGMA synchronous=FULL")
    return connection


def initialize(root, manifest_hash):
    """Create a new local SQLite event journal; never migrate or overwrite an existing one."""
    path = Path(root) / "events.sqlite3"
    with path.open("xb"):
        pass
    with connect(root, True) as db:
        db.execute("CREATE TABLE events (seq INTEGER PRIMARY KEY, body TEXT NOT NULL, hash TEXT NOT NULL)")
        append(db, "created", dict(manifest_hash=manifest_hash))
    db.close()


def project(state, kind, data):
    """Apply one validated event to operational state; grants and physics remain immutable."""
    value = dict(state)
    if kind == "created":
        if state:
            raise ValueError("Duplicate created event")
        return dict(status="ready", active=None, charged_seconds=0.0, revoked=False,
                    request=None, operations=0, manifest_hash=data["manifest_hash"])
    if not state or (state["status"] in TERMINAL and kind != "agent_view"):
        raise ValueError("Terminal or uninitialized Campaign cannot advance")
    if kind.startswith("agent_") or kind == "human_decision":
        from materiasim.harness.agent_state import project as agent_project
        return agent_project(state, kind, data)
    if kind == "control":
        action = data["action"]
        if action not in ("pause", "cancel", "revoke", "resume"):
            raise ValueError("Unknown control action")
        if action == "resume":
            if state.get("agent_enabled"):
                raise ValueError("Agent Campaign requires explicit human-decision, not resume")
            if state["status"] != "paused" or state["revoked"] or state["active"]:
                raise ValueError("Only a verified paused Campaign can resume")
            value.update(status="ready", request=None)
        else:
            if state["request"] in ("cancel", "revoke") and action == "pause":
                raise ValueError("Cannot replace a terminal stop request with pause")
            request = "revoke" if state["revoked"] or action == "revoke" else action
            value.update(request=request, revoked=state["revoked"] or action == "revoke")
            if state["active"]:
                value["status"] = "pause_requested" if request == "pause" else "cancelling"
            else:
                value["status"] = "paused" if request == "pause" else "cancelled"
                value["pending_launch"] = None
            if state.get("agent_enabled"):
                value.update(human_required=True, agent_credit=False)
    elif kind == "launch":
        fields(data, ("launch_id", "host", "instance"), "launch")
        identifier(data["launch_id"], "launch id")
        identifier(data["instance"], "launch instance")
        if state["status"] not in ("ready", "waiting_for_agent") or state["active"] or state.get("pending_launch"):
            raise ValueError("Supervisor launch already pending or Campaign not ready")
        value["pending_launch"] = data["launch_id"]
    elif kind == "launch_reconciled":
        fields(data, ("launch_id",), "launch reconciliation")
        if state["active"] or state.get("pending_launch") != data["launch_id"]:
            raise ValueError("No idle launch to reconcile")
        value["pending_launch"] = None
    elif kind == "intent":
        if state["status"] != "ready" or state["active"] or state["revoked"]:
            raise ValueError("Campaign cannot accept a new operation")
        if state.get("agent_enabled") and not state["agent_credit"]:
            raise ValueError("No one-operation decision permit")
        fields(data, ("operation_id", "resume", "reserved_seconds", "owner_token"), "intent")
        identifier(data["operation_id"], "operation id")
        identifier(data["owner_token"], "owner token")
        if (type(data["resume"]) is not bool or type(data["reserved_seconds"]) not in (int, float)
                or not math.isfinite(data["reserved_seconds"]) or not 0 < data["reserved_seconds"] <= 3600):
            raise ValueError("Invalid operation reservation")
        value.update(status="executing", active=data, operations=state["operations"] + 1,
                     pending_launch=None, last_boundary={})
        if state.get("agent_enabled"):
            value["agent_credit"] = False
    elif kind == "uncertain":
        if not state["active"] or data["operation_id"] != state["active"]["operation_id"]:
            raise ValueError("Uncertainty has no matching intent")
        value.update(status="needs_human_review", reason="unsettled_operation_no_receipt")
    elif kind == "boundary":
        fields(data, ("operation_id", "task_id", "action"), "boundary")
        if not state["active"] or data["operation_id"] != state["active"]["operation_id"]:
            raise ValueError("Boundary has no matching operation")
        if state["status"] != "executing" or data["action"] not in ("build", "run", "resume", "analyze"):
            raise ValueError("Boundary cannot admit work after a stop request")
        if state.get("agent_enabled") and state.get("last_boundary"):
            raise ValueError("One decision cannot admit two core operations")
        identifier(data["task_id"], "boundary task")
        value["last_boundary"] = data
    elif kind == "outcome":
        if not state["active"] or data["operation_id"] != state["active"]["operation_id"]:
            raise ValueError("Outcome has no matching active reservation")
        seconds = data["charged_seconds"]
        if type(seconds) not in (float, int) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Invalid operation charge")
        status = data["status"]
        if status not in TERMINAL | {"paused", "needs_human_review", "ready"}:
            raise ValueError("Invalid outcome state")
        if state["request"] in ("cancel", "revoke"):
            status = "cancelled"
        elif state["request"] == "pause" and status in ("ready", "completed"):
            status = "paused"
        value.update(status=status, active=None, charged_seconds=state["charged_seconds"] + seconds,
                     reason=data["reason"])
    elif kind == "stop":
        if state["active"] or data["status"] not in TERMINAL | {"needs_human_review"}:
            raise ValueError("Cannot close an unaccounted operation")
        value.update(status=data["status"], reason=data["reason"])
    else:
        raise ValueError("Unknown Campaign event")
    return value


def read(db):
    """Verify the full event chain and replay state, rejecting gaps and malformed events."""
    state, previous, events = {}, None, []
    for index, (seq, body, digest) in enumerate(db.execute("SELECT seq, body, hash FROM events ORDER BY seq")):
        if len(body.encode()) > MAX_JSON_BYTES:
            raise ValueError("Oversized Campaign event")
        event = json.loads(body, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
        fields(event, ("sequence", "previous", "utc", "kind", "data"), "event")
        if seq != index or event["sequence"] != index or event["previous"] != previous:
            raise ValueError("Campaign event sequence is corrupt")
        if content_hash(event) != digest:
            raise ValueError("Campaign event hash mismatch")
        state = project(state, event["kind"], event["data"])
        events.append(dict(event, sha256=digest))
        previous = digest
    if not events:
        raise ValueError("Empty Campaign journal")
    return dict(state, sequence=len(events) - 1), events


def append(db, kind, data):
    """Append and validate one event inside the caller's write transaction."""
    count = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    state, events = read(db) if count else ({}, [])
    project(state, kind, data)
    event = dict(sequence=count, previous=events[-1]["sha256"] if events else None,
                 utc=utc_now(), kind=kind, data=data)
    body = json.dumps(event, ensure_ascii=False, allow_nan=False)
    if len(body.encode()) > MAX_JSON_BYTES or count >= 4096:
        raise ValueError("Campaign event storage limit")
    db.execute("INSERT INTO events VALUES (?, ?, ?)", (count, body, content_hash(event)))
    return read(db)[0]


@contextmanager
def transaction(root):
    """Serialize local state transitions with SQLite's immediate transaction and FULL sync."""
    db = connect(root, True)
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def status(root):
    """Read a consistent committed snapshot without writing projection files."""
    db = connect(root)
    try:
        return read(db)[0]
    finally:
        db.close()
