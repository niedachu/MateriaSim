"""Read-only local proposal validation; this contract never submits or authorizes computation."""

from datetime import datetime, timezone
from pathlib import Path

from materiasim.errors import MateriaSimError
from materiasim.harness import journal
from materiasim.harness.contracts import bounded_json, timestamp
from materiasim.harness.service import check_authority
from materiasim.harness.snapshots import load
from materiasim.specs.schema import fields, identifier, integer
from materiasim.storage import contained, content_hash, sha256


def validate(root, path):
    """Validate an inert proposal against current identity, event head and bounded evidence references."""
    root = Path(root).resolve()
    value = bounded_json(path)
    fields(value, ("contract_version", "request_id", "source", "action", "campaign_hash", "expected_sequence",
                   "event_head", "expires_utc", "reason", "evidence"), "decision")
    integer(value["contract_version"], 1, 1, "decision version")
    identifier(value["request_id"], "decision request")
    identifier(value["source"], "decision source")
    integer(value["expected_sequence"], 0, 4095, "decision sequence")
    if value["action"] not in ("continue", "pause", "request_review", "stop"):
        raise MateriaSimError("UNSUPPORTED_DECISION", "Decision may not change inputs or authority", category="permission")
    if not isinstance(value["reason"], str) or not 1 <= len(value["reason"]) <= 2000:
        raise ValueError("Decision reason must contain 1..2000 characters")
    if timestamp(value["expires_utc"]) <= datetime.now(timezone.utc):
        raise MateriaSimError("DECISION_EXPIRED", "Decision expired", category="control")
    manifest = load(root)
    db = journal.connect(root)
    try:
        state, events = journal.read(db)
    finally:
        db.close()
    check_authority(manifest, state, value["action"] == "continue" and state["operations"] > 0)
    if (value["campaign_hash"] != manifest["manifest_hash"] or value["expected_sequence"] != state["sequence"]
            or value["event_head"] != events[-1]["sha256"]):
        raise MateriaSimError("STALE_DECISION", "Decision identity or event view differs", category="integrity")
    if state["active"] or state["status"] not in ("ready", "paused", "needs_human_review"):
        raise MateriaSimError("DECISION_STATE_REJECTED", "No quiescent decision boundary", category="control")
    refs = value["evidence"]
    if not isinstance(refs, list) or not 1 <= len(refs) <= 16:
        raise ValueError("Decision requires 1..16 evidence references")
    seen = set()
    for ref in refs:
        fields(ref, ("path", "sha256"), "evidence reference")
        if not isinstance(ref["path"], str) or ref["path"] in seen:
            raise ValueError("Duplicate or invalid evidence path")
        seen.add(ref["path"])
        item = contained(root, ref["path"])
        if Path(ref["path"]).parts[0] not in ("snapshot", "work", "operations"):
            raise ValueError("Decision evidence must refer to frozen or operation-owned data")
        if sha256(item) != ref["sha256"]:
            raise MateriaSimError("EVIDENCE_CHANGED", "Decision evidence digest mismatch", category="integrity")
    if journal.status(root)["sequence"] != state["sequence"]:
        raise MateriaSimError("STALE_DECISION", "Campaign advanced during validation", category="control")
    return dict(contract_version=1, decision_hash=content_hash(value), valid=True, executed=False,
                warning="v1 proposal validation is not authorization or submission; execution requires the separate v2 contract")
