"""Management-only controls and read-only evidence views for local Campaigns."""

from datetime import datetime, timezone
from pathlib import Path

from materiasim.harness import journal
from materiasim.harness.contracts import timestamp
from materiasim.harness.snapshots import load
from materiasim.errors import MateriaSimError


def check_authority(manifest, state, resume=False):
    """Check time, revocation and recovery authority at each launch boundary."""
    if state["revoked"] or state["request"] in ("cancel", "revoke"):
        raise MateriaSimError("AUTHORIZATION_REVOKED", "Campaign authorization revoked or cancelled", category="permission")
    if timestamp(manifest["authorization"]["expires_utc"]) <= datetime.now(timezone.utc):
        raise MateriaSimError("AUTHORIZATION_EXPIRED", "Campaign authorization expired", category="permission")
    if resume and (not manifest["automation"]["allow_resume"] or
                   "resume" not in manifest["authorization"]["allowed_actions"]):
        raise MateriaSimError("RESUME_NOT_AUTHORIZED", "Recovery was not authorized", category="permission")


def control(root, action, request_id, expected_sequence):
    """Apply a user control with optimistic concurrency and idempotency; never expand authority."""
    from materiasim.specs.schema import identifier, integer
    identifier(request_id, "request id")
    integer(expected_sequence, 0, 4095, "expected sequence")
    manifest = load(root)
    if manifest["contract_version"] not in (2, 3):
        raise ValueError("Campaign v1 is read-only")
    request = dict(action=action, request_id=request_id, expected_sequence=expected_sequence)
    with journal.transaction(root) as db:
        state, events = journal.read(db)
        previous = [e for e in events if e["kind"] == "control" and e["data"]["request_id"] == request_id]
        if previous:
            if previous[0]["data"] != request:
                raise MateriaSimError("IDEMPOTENCY_CONFLICT", "Idempotency key reused for different control", category="control")
            return state
        if state["sequence"] != expected_sequence:
            raise MateriaSimError("STALE_CONTROL", "Stale control; inspect current Campaign sequence", category="control")
        if action == "resume":
            check_authority(manifest, state, True)
        return journal.append(db, "control", request)


def status(root):
    """Return verified manifest/journal state; do not guess whether a stale worker is alive."""
    manifest = load(root)
    state = journal.status(root)
    return dict(campaign_dir=str(Path(root).resolve()), **state,
                automation_id=manifest["automation"]["id"], scientific_quality="not_assessed",
                ownership="requires_supervisor_reconciliation" if state["active"] else "no_outstanding_intent")


def evidence(root):
    """Expose the shared read-only evidence audit used by CLI and local management clients."""
    from materiasim.harness.audit import evidence as audit
    return audit(root)
