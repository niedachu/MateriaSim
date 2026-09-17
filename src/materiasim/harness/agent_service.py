"""Transactional local decision admission, human takeover and bounded wait expiry."""

from datetime import datetime, timezone
from pathlib import Path

from materiasim.harness import journal
from materiasim.harness.agent_contracts import decision
from materiasim.harness.agent_state import deadline
from materiasim.harness.agent_views import agent_manifest, capacity, summary
from materiasim.harness.contracts import TERMINAL, timestamp
from materiasim.harness.service import check_authority
from materiasim.specs.schema import identifier, integer
from materiasim.storage import content_hash


def receipt(event):
    """Acknowledge durable permission, never claim that a worker was launched or finished."""
    return dict(submitted=True, executed=False, decision_hash=content_hash(event["data"]["request"]),
                accepted_sequence=event["sequence"], request_id=event["data"]["request"]["request_id"])


def submit(root, path):
    """Accept one fresh v2 decision against an access receipt; replay never creates another permit."""
    root = Path(root).resolve()
    value = decision(path)
    manifest = agent_manifest(root, value["source"])
    with journal.transaction(root) as db:
        state, events = journal.read(db)
        for event in events:
            if event["kind"] == "agent_decision" and event["data"]["request"]["request_id"] == value["request_id"]:
                if event["data"]["request"] != value:
                    raise ValueError("Decision idempotency conflict")
                return receipt(event)
        check_authority(manifest, state, value["action"] == "continue" and state["operations"] > 0)
        now = datetime.now(timezone.utc)
        if now >= timestamp(value["expires_utc"]) or now >= timestamp(state["deadline"]):
            raise ValueError("Decision or wait deadline expired; human review required")
        if timestamp(value["expires_utc"]) > timestamp(state["deadline"]):
            raise ValueError("Decision expiry exceeds the frozen wait boundary")
        if value["action"] not in manifest["agent_policy"]["allowed_actions"]:
            raise ValueError("Action is not allowed by agent policy")
        if state["decisions"] >= manifest["agent_policy"]["max_decisions"]:
            raise ValueError("Agent decision allowance exhausted")
        if (value["campaign_hash"] != manifest["manifest_hash"] or value["expected_sequence"] != state["sequence"]
                or value["event_head"] != events[-1]["sha256"]):
            raise ValueError("Stale decision identity or event head")
        index = value["evidence"]["view_id"]
        view = events[index] if index < len(events) else None
        if (not view or view["kind"] != "agent_view" or view["data"]["source"] != value["source"]
                or value["evidence"]["sha256"] != view["data"]["summary_hash"]
                or summary(root, manifest, state) != view["data"]["summary"]):
            raise ValueError("Forged or changed evidence view")
        capacity(root, manifest)
        journal.append(db, "agent_decision", dict(request=value))
        return receipt(journal.read(db)[1][-1])


def human(root, action, request_id, expected_sequence):
    """Issue a management-only one-step permit or explicitly return control to the agent."""
    identifier(request_id, "human request")
    integer(expected_sequence, 0, 4095, "expected sequence")
    manifest = agent_manifest(root)
    request = dict(action=action, request_id=request_id, expected_sequence=expected_sequence)
    with journal.transaction(root) as db:
        state, events = journal.read(db)
        for event in events:
            if event["kind"] == "human_decision" and event["data"]["request_id"] == request_id:
                if {key: event["data"][key] for key in request} != request:
                    raise ValueError("Human decision idempotency conflict")
                return state
        if expected_sequence != state["sequence"]:
            raise ValueError("Stale human decision")
        check_authority(manifest, state, state["operations"] > 0)
        if action == "return_to_agent" and state["decisions"] >= manifest["agent_policy"]["max_decisions"]:
            raise ValueError("Cannot renew an exhausted agent decision allowance")
        capacity(root, manifest)
        return journal.append(db, "human_decision", dict(request, deadline=deadline(manifest)))


def tick(root):
    """Expire an unattended wait without starting MD, resetting budgets or renewing authority."""
    manifest = agent_manifest(root)
    with journal.transaction(root) as db:
        state, _ = journal.read(db)
        if state["status"] in TERMINAL or state["active"]:
            return state
        now = datetime.now(timezone.utc)
        if now >= timestamp(manifest["authorization"]["expires_utc"]):
            return journal.append(db, "stop", dict(status="budget_exhausted", reason="authorization_expired"))
        if state["status"] != "waiting_for_agent":
            return state
        reason = None
        if state["decisions"] >= manifest["agent_policy"]["max_decisions"]:
            reason = "agent_decision_limit"
        elif now >= timestamp(state["deadline"]):
            reason = "decision_timeout"
        if reason:
            return journal.append(db, "agent_timeout", dict(reason=reason))
        return state
