"""Native GROMACS command execution with explicit logs and bounded attempts."""

import os
import re
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from .files import sha256, utc_now, write_json


def engine_info(candidate="gmx"):
    """Resolve the executable and query version/data prefix without running MD."""
    if sys.platform not in ("darwin", "linux"):
        raise ValueError("Only native macOS/Linux are supported")
    executable = shutil.which(str(candidate))
    if executable is None:
        raise FileNotFoundError(f"GROMACS executable not found: {candidate}")
    executable = str(Path(executable).resolve())
    result = subprocess.run([executable, "--version"], capture_output=True, text=True, check=True, timeout=15)
    output = result.stdout + result.stderr
    version = re.search(r"^GROMACS version:\s*(.+)$", output, re.M)
    prefix = re.search(r"^Data prefix:\s*(.+)$", output, re.M)
    if not version or not prefix:
        raise ValueError("Unrecognized GROMACS version output")
    return {"executable": executable, "sha256": sha256(executable), "version": version.group(1).strip(),
            "data_prefix": str(Path(prefix.group(1).strip()).resolve()), "platform": sys.platform}


def environment(inputs):
    """Isolate GROMACS lookup to the frozen library; preserve execution environment."""
    return dict(os.environ, GMXLIB=str(Path(inputs).resolve()), GMX_MAXBACKUP="-1")


def command(engine, arguments, cwd, record, inputs, seconds=120, stdin=None):
    """Execute one bounded command, forwarding termination and preserving logs."""
    record = Path(record)
    record.mkdir(parents=True, exist_ok=False)
    argv = [engine["executable"], *map(str, arguments)]
    metadata = {"argv": argv, "cwd": str(Path(cwd).resolve()), "started_utc": utc_now(),
                "engine": engine, "timeout_seconds": seconds, "status": "running"}
    write_json(record / "command.json", metadata)
    interrupted = []
    with (record / "stdout.log").open("w") as out, (record / "stderr.log").open("w") as err:
        process = subprocess.Popen(argv, cwd=cwd, env=environment(inputs), stdout=out, stderr=err,
                                   stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                   text=True, start_new_session=True)

        def forward(signum, frame):
            """Forward cancellation only to this command's process group."""
            interrupted.append(signum)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)

        previous = {sig: signal.signal(sig, forward) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            process.communicate(input=stdin, timeout=seconds)
        except subprocess.TimeoutExpired:
            forward(signal.SIGTERM, None)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
        metadata.update(returncode=process.returncode, interrupted=bool(interrupted),
                        ended_utc=utc_now(), status="finished")
        write_json(record / "command.json", metadata)
    if process.returncode != 0:
        raise RuntimeError(f"{Path(engine['executable']).name} failed ({process.returncode}); inspect {record / 'stderr.log'}")
    return metadata


def checkpoint(engine, path):
    """Read step, time and atom count from a checkpoint using the engine parser."""
    result = subprocess.run([engine["executable"], "dump", "-cp", str(path)],
                            capture_output=True, text=True, check=True, timeout=30)
    values = {}
    for key, pattern, converter in (("step", r"^step\s*=\s*(\d+)$", int),
                                    ("time_ps", r"^t\s*=\s*([^\s]+)$", float),
                                    ("atom_count", r"^#atoms\s*=\s*(\d+)$", int)):
        match = re.search(pattern, result.stdout, re.M)
        if not match:
            raise ValueError(f"Missing {key} in checkpoint dump")
        values[key] = converter(match.group(1))
    return values
