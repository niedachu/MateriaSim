"""Access-logged, allowlisted summaries; raw scientific files and logs are never returned."""

from pathlib import Path

from materiasim.harness import journal
from materiasim.harness.agent_contracts import policy
from materiasim.harness.service import check_authority
from materiasim.harness.snapshots import load
from materiasim.research.resources import storage_bytes
from materiasim.specs.schema import identifier
from materiasim.storage import content_hash, inventory


def agent_manifest(root, source=None):
    """Verify a v3 campaign and optional local actor label, not an authenticated identity."""
    manifest = load(root)
    if manifest["contract_version"] != 3:
        raise ValueError("Agent execution requires a new v3 Campaign")
    rule = policy(manifest["agent_policy"])
    if source is not None and source != rule["agent_id"]:
        raise ValueError("Agent source differs from frozen policy")
    return manifest


def capacity(root, manifest):
    """Reserve bounded event-write headroom inside the existing Campaign storage grant."""
    if storage_bytes(root) + 262144 >= manifest["authorization"]["storage_bytes"]:
        raise ValueError("Insufficient Campaign storage for an agent event")


def summary(root, manifest, state):
    """Return only fixed metadata and work digests; never copy user/model prose or raw paths."""
    reserved = state["active"]["reserved_seconds"] if state["active"] else 0
    return dict(contract_version=1, campaign_hash=manifest["manifest_hash"], status=state["status"],
                scientific_quality="not_assessed", declared_tasks=len(manifest["composition"]["selections"]),
                operations=state["operations"], charged_seconds=state["charged_seconds"],
                remaining_seconds=max(0, manifest["authorization"]["total_seconds"] - state["charged_seconds"] - reserved),
                decisions_used=state["decisions"], decision_limit=manifest["agent_policy"]["max_decisions"],
                deadline=state["deadline"], human_required=state["human_required"],
                allowed_actions=manifest["agent_policy"]["allowed_actions"],
                last_operation=state.get("last_boundary", {}).get("action"),
                snapshot_digest=content_hash(manifest["snapshot_hashes"]),
                work_digest=content_hash(inventory(root, ["work"])))


def envelope(event):
    """Return the exact disclosed view and its optimistic-concurrency identity."""
    data = event["data"]
    return dict(view_id=event["sequence"], sha256=data["summary_hash"], summary=data["summary"],
                expected_sequence=event["sequence"], event_head=event["sha256"])


def read_view(root, source, request_id):
    """Disclose one bounded progress view and atomically record what the local agent saw."""
    root = Path(root).resolve()
    identifier(source, "agent source")
    identifier(request_id, "view request")
    manifest = agent_manifest(root, source)
    with journal.transaction(root) as db:
        state, events = journal.read(db)
        # A cancelled/revoked grant cannot disclose new or cached evidence.
        check_authority(manifest, state)
        for event in events:
            if event["kind"] == "agent_view" and event["data"]["request_id"] == request_id:
                if event["data"]["source"] != source:
                    raise ValueError("View idempotency conflict")
                return envelope(event)
        if state["active"] or state["status"] == "ready":
            raise ValueError("Agent evidence requires a quiescent decision boundary")
        if state["views"] >= 4 * manifest["agent_policy"]["max_decisions"] + 4:
            raise ValueError("Agent view allowance exhausted")
        capacity(root, manifest)
        value = summary(root, manifest, state)
        journal.append(db, "agent_view", dict(request_id=request_id, source=source,
                                               summary=value, summary_hash=content_hash(value)))
        return envelope(journal.read(db)[1][-1])
