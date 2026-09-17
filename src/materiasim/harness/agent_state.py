"""Pure state transitions for one-core-operation local agent approvals."""

from datetime import datetime, timedelta, timezone

from materiasim.harness.contracts import timestamp


def deadline(manifest):
    """Bound the next decision wait by both user policy and authorization expiration."""
    end = datetime.now(timezone.utc) + timedelta(seconds=manifest["agent_policy"]["decision_timeout_seconds"])
    return min(end, timestamp(manifest["authorization"]["expires_utc"])).isoformat()


def project(state, kind, data):
    """Project a validated agent event; never clear active uncertainty or reopen terminal work."""
    value = dict(state)
    if kind == "agent_configured":
        if state["status"] != "ready" or state["operations"] or state.get("agent_enabled"):
            raise ValueError("Agent configuration is only valid at creation")
        value.update(agent_enabled=True, status="waiting_for_agent", deadline=data["deadline"],
                     decisions=0, views=0, human_required=False, agent_credit=False)
        return value
    if not state.get("agent_enabled"):
        raise ValueError("Campaign has no frozen agent policy")
    if kind == "agent_view":
        if state["active"]:
            raise ValueError("Evidence disclosure requires settled work")
        value["views"] += 1
        return value
    if state["active"]:
        raise ValueError("Cannot decide over an unsettled operation")
    if kind == "agent_decision":
        if state["status"] != "waiting_for_agent" or state["human_required"]:
            raise ValueError("Agent cannot override human control or terminal work")
        action = data["request"]["action"]
        statuses = dict(continue_="ready", pause="paused", request_review="needs_human_review", stop="cancelled")
        value.update(status=statuses["continue_" if action == "continue" else action],
                     decisions=state["decisions"] + 1, agent_credit=action == "continue",
                     human_required=action in ("pause", "request_review"),
                     reason="agent_" + action, permit_expires_utc=data["request"]["expires_utc"])
    elif kind == "agent_wait":
        if state["status"] != "paused" or state["request"] is not None:
            raise ValueError("Only settled automatic yield can wait for another decision")
        value.update(status="paused" if state["human_required"] else "waiting_for_agent",
                     deadline=data["deadline"], agent_credit=False)
    elif kind == "agent_timeout":
        if state["status"] not in ("waiting_for_agent", "ready"):
            raise ValueError("Campaign is not waiting for an agent")
        value.update(status="needs_human_review", human_required=True, reason=data["reason"], agent_credit=False)
    elif kind == "human_decision":
        if state["status"] not in ("waiting_for_agent", "paused", "ready", "needs_human_review"):
            raise ValueError("No safe human decision boundary")
        if state["status"] == "needs_human_review" and state.get("reason") not in (
                "agent_request_review", "decision_timeout", "agent_decision_limit"):
            raise ValueError("Core uncertainty requires evidence reconciliation, not manual approval")
        action = data["action"]
        if action == "return_to_agent":
            value.update(status="waiting_for_agent", human_required=False, agent_credit=False,
                         request=None, deadline=data["deadline"])
        elif action == "continue":
            value.update(status="ready", human_required=True, agent_credit=True, request=None,
                         permit_expires_utc=data["deadline"])
        else:
            raise ValueError("Unknown human decision")
    else:
        raise ValueError("Unknown agent event")
    if value["status"] not in ("ready", "waiting_for_agent"):
        value["pending_launch"] = None
    return value
