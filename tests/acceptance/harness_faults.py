"""Acceptance-only process-handle interruption and disposable checkpoint guards; no new Run designs."""

import signal
import threading
import time
from pathlib import Path
from unittest.mock import patch

from materiasim.harness import service, supervisor
from materiasim.runtime.capacity import copy_tree
from materiasim.runtime.family import launch
from materiasim.storage import read_json, write_json


def interrupt(campaign, output):
    """Interrupt the owned live worker during its first real NVT; never signal a PID read from disk."""
    launched = threading.Event()
    children, observations = [], []

    def capture(arguments, **options):
        """Retain the actual child handle issued by this acceptance process's launch call."""
        process, owner = launch(arguments, **options)
        children.append(process)
        launched.set()
        return process, owner

    def stop():
        """Observe the new campaign's first NVT and cooperatively stop its known worker handle."""
        if not launched.wait(10):
            observations.append("worker_not_launched")
            return
        process = children[0]
        deadline = time.monotonic() + 60
        while process.poll() is None and time.monotonic() < deadline:
            logs = list((campaign / "work").glob("batches/*/runs/*/stages/nvt/md.log"))
            if logs:
                time.sleep(.2)
                if process.poll() is None:
                    process.send_signal(signal.SIGTERM)
                    observations.append(str(logs[0]))
                return
            time.sleep(.02)
        observations.append("nvt_not_observed")
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)

    thread = threading.Thread(target=stop)
    thread.start()
    try:
        with patch("materiasim.harness.supervisor.launch", side_effect=capture):
            state = supervisor.run(campaign)
    finally:
        thread.join(timeout=75)
    if state["status"] != "paused" or len(observations) != 1 or not observations[0].endswith("md.log"):
        raise AssertionError(f"Real checkpoint interruption was not established: {state}, {observations}")
    run = Path(observations[0]).parents[2]
    seal = read_json(run / "stages/nvt/stage.json")
    if seal["status"] != "interrupted" or not 0 < seal["evidence"]["step"] < seal["evidence"]["target_step"]:
        raise AssertionError("No actual in-stage checkpoint was sealed")
    # Deletion touches only a fresh acceptance-owned copy, never the live Run.
    clone = output / "missing-checkpoint" / run.name
    clone.parent.mkdir(parents=True, exist_ok=False)
    copy_tree(run, clone)
    checkpoint = clone / seal["artifacts"]["checkpoint"]["path"]
    checkpoint.unlink()
    from materiasim.workflows.execute import execute
    with patch("subprocess.Popen", side_effect=AssertionError("missing checkpoint launched a tool")):
        try:
            execute(clone, resume=True)
        except ValueError as error:
            rejection = str(error)
        else:
            raise AssertionError("Missing checkpoint was allowed to restart")
    report = dict(run_id=run.name, checkpoint=seal["evidence"], missing_checkpoint_rejection=rejection,
                  status="paused", actual_worker_handle_used=True)
    write_json(output / "interruption.json", report)
    service.control(campaign, "resume", "checkpoint-resume", state["sequence"])
    return report
