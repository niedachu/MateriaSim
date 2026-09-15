"""Research CLI registration; query actions cannot launch workers."""

from pathlib import Path


def add_commands(commands):
    """Add bounded research actions to the single package CLI parser."""
    research = commands.add_parser("research", help="Explicit bounded research bundles")
    actions = research.add_subparsers(dest="research_action", required=True)
    for name in ("validate", "plan"):
        query = actions.add_parser(name)
        query.add_argument("research_file", type=Path)
        if name == "plan":
            query.add_argument("--output", type=Path, help="Explicit NEW frozen-plan directory; omitted means preview")
    executor = actions.add_parser("run")
    executor.add_argument("plan_dir", type=Path)
    executor.add_argument("--output-root", required=True, type=Path)
    executor.add_argument("--gmx", default="gmx")
    executor.add_argument("--packmol", default="packmol")
    executor.add_argument("--resume", action="store_true")
    for name in ("status", "compare"):
        query = actions.add_parser(name)
        query.add_argument("batch_dir", type=Path)
        if name == "compare":
            query.add_argument("--output-root", type=Path)


def dispatch(args):
    """Return preview/verification or explicitly requested execution/derived evidence."""
    if args.research_action in ("validate", "plan"):
        from materiasim.research.plan import plan
        result = plan(args.research_file, getattr(args, "output", None))
        return dict(valid=True, task_count=len(result["tasks"])) if args.research_action == "validate" else result
    if args.research_action == "run":
        from materiasim.research.batch import run
        return run(args.plan_dir, args.output_root, args.gmx, args.packmol, args.resume)
    if args.research_action == "status":
        from materiasim.research.batch import status
        return status(args.batch_dir)
    from materiasim.research.compare import compare
    return compare(args.batch_dir, args.output_root)
