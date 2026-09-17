"""Explicit local management commands; no external-model or arbitrary-code endpoint."""

from pathlib import Path


def add_commands(commands):
    """Register implemented Campaign commands on the shared CLI parser."""
    parser = commands.add_parser("campaign", help="Local bounded rule campaigns")
    actions = parser.add_subparsers(dest="campaign_action", required=True)
    actions.add_parser("plugins", help="List actual built-in capability descriptors")
    preview = actions.add_parser("preflight", help="Read-only source and composition validation")
    preview.add_argument("automation", type=Path)
    create = actions.add_parser("create", help="Freeze a NEW campaign; does not run MD")
    create.add_argument("automation", type=Path)
    create.add_argument("--authorization", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--gmx", default="gmx")
    create.add_argument("--packmol", default="packmol")
    create.add_argument("--agent-policy", type=Path, help="Explicit local agent policy for a NEW v3 Campaign")
    decision = actions.add_parser("validate-decision", help="Read-only local proposal check; never execute")
    decision.add_argument("campaign_dir", type=Path)
    decision.add_argument("decision", type=Path)
    read = actions.add_parser("agent-read", help="Disclose allowlisted progress and WRITE its access receipt")
    read.add_argument("campaign_dir", type=Path)
    read.add_argument("--source", required=True)
    read.add_argument("--request-id", required=True)
    submit = actions.add_parser("submit-decision", help="Admit a v2 decision; does not itself launch a worker")
    submit.add_argument("campaign_dir", type=Path)
    submit.add_argument("decision", type=Path)
    human = actions.add_parser("human-decision", help="Management-only takeover or return to agent")
    human.add_argument("campaign_dir", type=Path)
    human.add_argument("--action", choices=("continue", "return_to_agent"), required=True)
    human.add_argument("--request-id", required=True)
    human.add_argument("--expected-sequence", type=int, required=True)
    tick = actions.add_parser("agent-tick", help="Persist wait expiry without submitting MD")
    tick.add_argument("campaign_dir", type=Path)
    for name in ("run", "start", "reconcile", "status", "evidence", "pause", "cancel", "revoke", "resume"):
        action = actions.add_parser(name)
        action.add_argument("campaign_dir", type=Path)
        if name in ("pause", "cancel", "revoke", "resume"):
            action.add_argument("--request-id", required=True)
            action.add_argument("--expected-sequence", type=int, required=True)


def dispatch(args):
    """Dispatch only enumerated management operations; unknown commands never execute scripts."""
    from materiasim.harness import snapshots, service, supervisor
    action = args.campaign_action
    if action == "plugins":
        from materiasim.plugins.builtin import catalog
        return catalog()
    if action == "preflight":
        return snapshots.preview(args.automation)
    if action == "create":
        return snapshots.create(args.automation, args.authorization, args.output, args.gmx, args.packmol, args.agent_policy)
    if action in ("agent-read", "submit-decision"):
        return agent_dispatch(args)
    if action in ("human-decision", "agent-tick"):
        from materiasim.harness import agent_service
        if action == "human-decision":
            return agent_service.human(args.campaign_dir, args.action, args.request_id, args.expected_sequence)
        return agent_service.tick(args.campaign_dir)
    if action == "validate-decision":
        from materiasim.harness.decisions import validate
        return validate(args.campaign_dir, args.decision)
    if action == "status":
        return service.status(args.campaign_dir)
    if action == "evidence":
        return service.evidence(args.campaign_dir)
    if action in ("run", "start", "reconcile"):
        return getattr(supervisor, action)(args.campaign_dir)
    return service.control(args.campaign_dir, action, args.request_id, args.expected_sequence)


def agent_dispatch(args):
    """Expose only allowlisted output/errors to an agent; management retains detailed diagnostics."""
    import sqlite3
    from materiasim.errors import MateriaSimError
    from materiasim.harness.agent_service import submit
    from materiasim.harness.agent_views import read_view
    try:
        if args.campaign_action == "agent-read":
            return read_view(args.campaign_dir, args.source, args.request_id)
        return submit(args.campaign_dir, args.decision)
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as error:
        # Untrusted filesystem errors and input diagnostics may contain private paths/prose.
        # The agent must not receive them, nor infer retry permission from their wording.
        raise MateriaSimError("AGENT_REQUEST_REJECTED", "Request rejected; inspect through the human management interface",
                              category="control") from error
