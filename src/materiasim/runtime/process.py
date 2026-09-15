"""Bounded POSIX process execution with durable per-command evidence."""

import os
import signal
import subprocess
import time
from pathlib import Path

from materiasim.storage import utc_now, write_json
from materiasim.runtime.family import managed, kill, cleanup


class CommandFailed(RuntimeError):
    """Expose a failed command's recorded result for engine-specific, strictly validated handling."""

    def __init__(self, message, result):
        """Retain failure text and the exact persisted exit metadata; do not imply recoverability."""
        super().__init__(message)
        self.result = result


def run_command(engine, arguments, cwd, record, seconds=120, stdin=None, env=None):
    """Run tool arguments in cwd with explicit env; return timing/exit evidence and preserve failures.

    ``engine`` is the existing serialized tool identity field, including for Packmol.
    No engine-specific environment is injected here; env=None inherits the caller environment.
    """
    record = Path(record)
    record.mkdir(parents=True, exist_ok=False)
    argv = [engine["executable"], *map(str, arguments)]
    metadata = {"argv": argv, "cwd": str(Path(cwd).resolve()), "started_utc": utc_now(),
                "engine": engine, "timeout_seconds": seconds, "status": "running"}
    write_json(record / "command.json", metadata)
    interrupted = []
    stop_deadline = []
    with (record / "stdout.log").open("w") as out, (record / "stderr.log").open("w") as err:
        owner = not managed()
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=out, stderr=err,
                                   stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                   text=True, start_new_session=owner)

        def forward(signum, frame):
            """Forward cancellation only to this command's process group."""
            interrupted.append(signum)
            if not stop_deadline:
                stop_deadline.append(time.monotonic() + 10)
            if process.poll() is None:
                if owner:
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.send_signal(signal.SIGTERM)

        previous = {sig: signal.signal(sig, forward) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            deadline = time.monotonic() + seconds
            pending_input = stdin
            while True:
                try:
                    process.communicate(input=pending_input, timeout=.2)
                    break
                except subprocess.TimeoutExpired:
                    pending_input = None
                    if time.monotonic() >= deadline and not stop_deadline:
                        forward(signal.SIGTERM, None)
                    if stop_deadline and time.monotonic() >= stop_deadline[0]:
                        kill(process, owner)
                        process.wait()
                        break
        finally:
            if process.poll() is None:
                kill(process, owner)
                process.wait()
            cleanup(process, owner)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        metadata.update(returncode=process.returncode, interrupted=bool(interrupted),
                        ended_utc=utc_now(), status="finished")
        write_json(record / "command.json", metadata)
    if process.returncode != 0:
        raise CommandFailed(f"{Path(engine['executable']).name} failed ({process.returncode}); inspect {record / 'stderr.log'}", metadata)
    return metadata
