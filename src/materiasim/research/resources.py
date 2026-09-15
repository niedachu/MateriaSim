"""Whole-operation watchdog, covering build/compile/analysis as well as integration."""

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

GRACE_SECONDS = 20


def storage_bytes(root):
    """Count batch file bytes and reject symlinks; sampled usage is not a filesystem quota."""
    total = 0
    for path in Path(root).rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink in batch storage")
        try:
            if path.is_file():
                total += path.stat().st_size
        except FileNotFoundError:
            # Atomic JSON writes may retire a temporary file during a sample.
            continue
    return total


def supervise(batch, index, action, seconds, storage_limit, event_dir):
    """Bound a complete worker operation; return wall/exit evidence including exit grace."""
    event_dir.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    reason = None
    cancelled = []

    def stop(signum, frame):
        """Record external cancellation for the watchdog's controlled termination path."""
        cancelled.append(signum)

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    process = None
    try:
        with (event_dir / "stdout.log").open("w") as out, (event_dir / "stderr.log").open("w") as err:
            process = subprocess.Popen([sys.executable, "-B", "-m", "materiasim.research.worker",
                                        str(batch), str(index), action], stdout=out, stderr=err,
                                       stdin=subprocess.DEVNULL, start_new_session=True)
            while process.poll() is None:
                if cancelled:
                    reason = "cancelled"
                elif time.monotonic() - started >= seconds:
                    reason = "wall_budget"
                elif storage_bytes(batch) >= storage_limit:
                    reason = "storage_budget"
                elif shutil.disk_usage(batch).free < 64 * 1024 * 1024:
                    reason = "disk_reserve"
                if reason:
                    process.send_signal(signal.SIGTERM)
                    break
                time.sleep(.1)
            try:
                process.wait(timeout=GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                reason = "worker_did_not_stop"
    finally:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return dict(action=action, returncode=process.returncode, stop_reason=reason,
                elapsed_seconds=time.monotonic() - started, storage_bytes=storage_bytes(batch))
