"""Strict automation and local user-authorization inputs; neither grants scientific approval."""

from datetime import datetime, timezone
from pathlib import Path

from materiasim.specs.schema import fields, identifier, integer
from materiasim.storage import read_json

TERMINAL = {"completed", "failed", "cancelled", "budget_exhausted"}
MAX_JSON_BYTES = 2 * 1024 * 1024


def bounded_json(path):
    """Read a regular small JSON request without following a final symlink."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Expected a regular JSON file no larger than 2 MiB")
    return read_json(path)


def timestamp(value):
    """Parse an explicit timezone-qualified timestamp; return a UTC-aware datetime."""
    if not isinstance(value, str):
        raise ValueError("Expected timezone-qualified timestamp")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Timestamp requires an explicit timezone")
    return result.astimezone(timezone.utc)


def automation(path):
    """Load one versioned sidecar and resolve its experiment or research source path."""
    path = Path(path).absolute()
    value = bounded_json(path)
    fields(value, ("contract_version", "id", "target", "capabilities", "allow_resume"), "automation")
    integer(value["contract_version"], 1, 1, "automation version")
    identifier(value["id"], "automation id")
    fields(value["target"], ("kind", "path"), "target")
    if value["target"]["kind"] not in ("experiment", "research"):
        raise ValueError("Only experiment/research targets are supported")
    if type(value["allow_resume"]) is not bool:
        raise ValueError("allow_resume must be explicit boolean")
    target = value["target"]["path"]
    if not isinstance(target, str) or not target:
        raise ValueError("target.path must name an existing definition")
    source = path.parent / target
    if not source.is_file():
        raise ValueError("Target is not executable; preparation-only studies require a real definition")
    return value, source.resolve()


def authorization(value, automation_id, output):
    """Validate a user-supplied local grant bound to one new Campaign directory.

    The grant is an auditable single-user declaration, not authenticated identity.
    No agent decision can modify this grant or authorize additional output roots.
    """
    fields(value, ("contract_version", "subject", "actor", "output_root", "expires_utc",
                   "allowed_actions", "total_seconds", "storage_bytes"), "authorization")
    integer(value["contract_version"], 1, 1, "authorization version")
    if value["subject"] != automation_id or not isinstance(value["actor"], str) or not value["actor"].strip():
        raise ValueError("Authorization subject/actor is missing or mismatched")
    if not isinstance(value["output_root"], str) or not Path(value["output_root"]).is_absolute():
        raise ValueError("Authorization requires an absolute output_root")
    if Path(value["output_root"]).absolute() != Path(output).absolute():
        raise ValueError("Authorization belongs to another output root")
    actions = value["allowed_actions"]
    if (not isinstance(actions, list) or any(not isinstance(a, str) for a in actions)
            or len(actions) != len(set(actions)) or "execute" not in actions
            or not set(actions) <= {"execute", "resume"}):
        raise ValueError("Explicit execute and optional resume authority required")
    integer(value["total_seconds"], 30, 3600, "campaign total_seconds")
    integer(value["storage_bytes"], 1048576, 2147483648, "campaign storage_bytes")
    if timestamp(value["expires_utc"]) <= datetime.now(timezone.utc):
        raise ValueError("Authorization expired")
    return value
