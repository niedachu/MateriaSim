"""Versioned operation evidence validation; legacy journals remain read-only evidence."""

from pathlib import Path
import re

from materiasim.specs.schema import fields, integer, number
from materiasim.storage import contained, content_hash, read_json, sha256

LIMITS = {"build": "build_seconds", "run": "max_wall_seconds",
          "resume": "max_wall_seconds", "analyze": "analysis_seconds"}
REASONS = (None, "cancelled", "wall_budget", "storage_budget", "disk_reserve", "worker_did_not_stop")


def regular_json(root, relative):
    """Read a regular contained JSON artifact, rejecting links and missing evidence first."""
    path = contained(root, relative)
    sha256(path)
    return read_json(path)


def storage_path(value):
    """Require an absolute canonical output path without symlinked roots or ancestors."""
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise ValueError("Workflow output must be an absolute path")
    path = Path(value)
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Symlink in supervised storage")
    if str(path.resolve()) != value:
        raise ValueError("Workflow output path is not canonical")
    if path.exists() and not path.is_dir():
        raise ValueError("Workflow output root must be a directory")
    return path


def event_shape(event, version):
    """Validate one closed settlement or open reservation before its fields are consumed."""
    if not isinstance(event, dict) or type(event.get("closed")) is not bool:
        raise ValueError("Workflow event closed flag must be boolean")
    keys = ["id", "action", "closed", "charged_seconds"]
    if version == 2:
        keys.append("request_sha256")
    if event["closed"]:
        keys += ["successful", "stop_reason", "outcome_sha256"]
        if version == 2:
            keys.append("result_sha256")
    fields(event, keys, "workflow event")
    if not isinstance(event["id"], str) or not re.fullmatch(r"operation-[0-9a-f]{32}", event["id"]):
        raise ValueError("Invalid workflow event identity")
    if not isinstance(event["action"], str) or event["action"] not in LIMITS:
        raise ValueError("Unknown workflow action")
    number(event["charged_seconds"], 0, 1e12, "workflow charged_seconds")
    if event["closed"] and (type(event["successful"]) is not bool or event["stop_reason"] not in REASONS):
        raise ValueError("Invalid workflow settlement status")


def request_check(root, ledger, event, profile, index, spent, previous_hash, recorded_root=None):
    """Bind the request to its event, identity, exact grant and chronological predecessor."""
    folder = contained(root, "events/" + event["id"])
    request = regular_json(folder, "request.json")
    keys = ["arguments", "control", "profile", "seconds", "control_id", "expected_spec_hash", "action"]
    if ledger["contract_version"] == 2:
        keys += ["control_version", "sequence", "previous_outcome_sha256"]
        if sha256(folder / "request.json") != event["request_sha256"]:
            raise ValueError("Workflow request changed")
    fields(request, keys, "workflow request")
    if (request["control"] != str(recorded_root or root) or request["control_id"] != ledger["id"] or
            request["expected_spec_hash"] != ledger["spec_hash"] or request["profile"] != profile or
            request["action"] != event["action"] or not isinstance(request["arguments"], dict)):
        raise ValueError("Workflow request binding changed")
    grant = min(profile[LIMITS[event["action"]]],
                profile["workflow_seconds"] - spent - profile["termination_grace_seconds"])
    number(request["seconds"], 1, profile[LIMITS[event["action"]]], "workflow seconds")
    if request["seconds"] != grant:
        raise ValueError("Workflow grant/accounting history changed")
    if ledger["contract_version"] == 2:
        integer(request["control_version"], 2, 2, "control_version")
        integer(request["sequence"], index, index, "workflow sequence")
        if request["previous_outcome_sha256"] != previous_hash:
            raise ValueError("Workflow predecessor changed")
    if not event["closed"] and event["charged_seconds"] != grant + profile["termination_grace_seconds"]:
        raise ValueError("Workflow reservation changed")
    output = request["arguments"].get("output_root") if event["action"] == "analyze" else None
    if output is not None and recorded_root is None:
        storage_path(output)
    return output


def settlement_check(root, event, version):
    """Verify measured charges, stop reason and result presence against durable outcome evidence."""
    folder = contained(root, "events/" + event["id"])
    outcome = regular_json(folder, "outcome.json")
    if sha256(folder / "outcome.json") != event["outcome_sha256"]:
        raise ValueError("Workflow outcome changed")
    fields(outcome, ("returncode", "stop_reason", "elapsed_seconds", "storage_bytes"), "workflow outcome")
    integer(outcome["returncode"], -255, 255, "worker returncode")
    number(outcome["elapsed_seconds"], 0, 1e12, "workflow elapsed_seconds")
    integer(outcome["storage_bytes"], 0, 2**63 - 1, "workflow storage_bytes")
    if outcome["stop_reason"] not in REASONS:
        raise ValueError("Unknown workflow stop reason")
    result = contained(folder, "result.json")
    present = result.exists()
    if present:
        regular_json(folder, "result.json")
    successful = outcome["returncode"] == 0 and outcome["stop_reason"] is None and present
    if (event["charged_seconds"] != outcome["elapsed_seconds"] or
            event["successful"] != successful or event["stop_reason"] != outcome["stop_reason"]):
        raise ValueError("Workflow accounting/status changed")
    if version == 2 and event["result_sha256"] != (sha256(result) if present else None):
        raise ValueError("Workflow result changed")


def validate_journal(root, run, profile, spec_hash, allow_active=False, recorded_root=None):
    """Audit events; recorded_root permits only a caller-verified archive's original path provenance."""
    ledger = regular_json(root, "ledger.json")
    fields(ledger, ("contract_version", "id", "run_id", "spec_hash", "profile_hash", "events", "active", "outputs"),
           "workflow ledger")
    integer(ledger["contract_version"], 1, 2, "workflow contract_version")
    if not isinstance(ledger["id"], str) or not re.fullmatch(r"[0-9a-f]{32}", ledger["id"]):
        raise ValueError("Invalid workflow control identity")
    if (ledger["profile_hash"] != content_hash(profile) or ledger["spec_hash"] != spec_hash or
            ledger["run_id"] != Path(run).name):
        raise ValueError("Workflow control identity differs from the Run")
    if (Path(run) / "manifest.json").exists():
        manifest = regular_json(run, "manifest.json")
        if manifest.get("operation_control") != dict(contract_version=ledger["contract_version"], id=ledger["id"]):
            raise ValueError("Run/control binding changed")
    if not isinstance(ledger["events"], list) or not isinstance(ledger["outputs"], list):
        raise ValueError("Workflow events/outputs must be lists")
    for output in ledger["outputs"]:
        if recorded_root is None:
            storage_path(output)
        elif not isinstance(output, str) or not Path(output).is_absolute():
            raise ValueError("Archived output provenance must be an absolute path")
    for event in ledger["events"]:
        event_shape(event, ledger["contract_version"])
    ids = [event["id"] for event in ledger["events"]]
    events_root = contained(root, "events")
    existing = list(events_root.iterdir()) if events_root.exists() else []
    if any(path.is_symlink() or not path.is_dir() for path in existing):
        raise ValueError("Unexpected artifact in workflow event inventory")
    if len(ids) != len(set(ids)) or set(ids) != {path.name for path in existing}:
        raise ValueError("Workflow ledger differs from operation events")
    opened = [event["id"] for event in ledger["events"] if not event["closed"]]
    if opened != ([] if ledger["active"] is None else [ledger["active"]]) or (opened and opened != ids[-1:]):
        raise ValueError("Invalid workflow active reservation")
    if opened and not allow_active:
        raise ValueError("Uncertain workflow handoff; do not reset or retry its reservation")
    spent, previous_hash, outputs = 0, None, []
    for index, event in enumerate(ledger["events"]):
        if (index == 0) != (event["action"] == "build"):
            raise ValueError("Workflow must begin with exactly one build")
        if index:
            previous = ledger["events"][index - 1]
            if not previous["successful"] and not (event["action"] == "resume" and
                    previous["action"] in ("run", "resume") and previous["stop_reason"] in ("cancelled", "wall_budget")):
                raise ValueError("Workflow history retries a terminal failure")
        output = request_check(root, ledger, event, profile, index, spent, previous_hash, recorded_root)
        if output is not None and output not in outputs:
            outputs.append(output)
        if event["closed"]:
            settlement_check(root, event, ledger["contract_version"])
            previous_hash = event["outcome_sha256"]
        spent += event["charged_seconds"]
    if ledger["outputs"] != outputs:
        raise ValueError("Workflow output inventory differs from analysis requests")
    return ledger
