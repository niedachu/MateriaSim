"""One bounded batch operation delegates to the normal core, never a second MD runner."""

import json
import sys
from pathlib import Path

from materiasim.storage import contained, read_json, run_lock
from materiasim.research.plan import load_plan
from materiasim.research.resources import task_limits


def operation(batch, index, action):
    """Execute the registered task action using the frozen plan and reserved destinations."""
    batch = Path(batch).resolve()
    plan = load_plan(batch / "plan")
    ledger = read_json(batch / "ledger.json")
    task = plan["tasks"][index]
    record = ledger["tasks"][index]
    limits = task_limits(plan["research"], read_json(batch / "plan/tasks" / task["id"] / "experiment.json"))
    root = contained(batch, "runs/" + record["run_id"])
    with run_lock(batch / "operation_guard"):
        if action == "build":
            from materiasim.workflows.build import build
            return build(batch / "plan/tasks" / task["id"] / "experiment.json", batch / "runs",
                         ledger["gmx"], ledger["packmol"], run_id=record["run_id"])
        if action in ("run", "resume"):
            from materiasim.workflows.execute import execute
            return execute(root, action == "resume", ledger["gmx"], limits["threads"],
                           limits["execution_seconds"])
        if action == "analyze":
            from materiasim.workflows.analysis import analyze
            return analyze(root, batch / "analyses" / task["id"])
        raise ValueError("Unknown research operation")


def main():
    """Run one parent-selected operation and expose failure without replacing core evidence."""
    try:
        result = operation(sys.argv[1], int(sys.argv[2]), sys.argv[3])
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
