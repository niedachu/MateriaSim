"""Versioned local agent messages; no shell, scientific-input or network authority."""

from pathlib import Path

from materiasim.harness.contracts import bounded_json, timestamp
from materiasim.specs.schema import fields, identifier, integer

ACTIONS = ("continue", "pause", "request_review", "stop")


def policy(value):
    """Validate the user's frozen local-agent policy and return it unchanged."""
    fields(value, ("contract_version", "agent_id", "allowed_actions", "decision_timeout_seconds",
                   "max_decisions", "transport", "readable_summaries"), "agent policy")
    integer(value["contract_version"], 1, 1, "policy version")
    identifier(value["agent_id"], "agent id")
    actions = value["allowed_actions"]
    if (not isinstance(actions, list) or not actions or any(a not in ACTIONS for a in actions)
            or len(set(actions)) != len(actions)):
        raise ValueError("Invalid agent action allowlist")
    integer(value["decision_timeout_seconds"], 1, 3600, "decision timeout seconds")
    integer(value["max_decisions"], 1, 128, "decision limit")
    if value["transport"] != "local" or value["readable_summaries"] != ["progress"]:
        raise ValueError("Only local progress-summary access is implemented")
    return value


def decision(path):
    """Read a bounded v2 executable decision; v1 remains a read-only proposal."""
    path = Path(path)
    if path.stat().st_size > 65536:
        raise ValueError("Decision exceeds 64 KiB")
    value = bounded_json(path)
    fields(value, ("contract_version", "request_id", "source", "action", "campaign_hash",
                   "expected_sequence", "event_head", "expires_utc", "reason", "evidence"), "decision")
    integer(value["contract_version"], 2, 2, "executable decision version")
    identifier(value["request_id"], "decision request")
    identifier(value["source"], "decision source")
    integer(value["expected_sequence"], 0, 4095, "decision sequence")
    if value["action"] not in ACTIONS:
        raise ValueError("Decision cannot change inputs, authority or tools")
    if not isinstance(value["reason"], str) or not 1 <= len(value["reason"]) <= 1000:
        raise ValueError("Decision reason requires 1..1000 characters")
    fields(value["evidence"], ("view_id", "sha256"), "view reference")
    integer(value["evidence"]["view_id"], 0, 4095, "view id")
    for digest in (value["campaign_hash"], value["event_head"], value["evidence"]["sha256"]):
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Expected SHA-256 digest")
    timestamp(value["expires_utc"])
    return value
