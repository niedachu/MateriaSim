"""Native GROMACS command execution with explicit logs and bounded attempts."""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from materiasim.storage import sha256
from materiasim.runtime.process import run_command
from materiasim.errors import MissingDependency
from materiasim.engines.gromacs.device import build_capabilities


def engine_info(candidate="gmx"):
    """Resolve the executable and query version/data prefix without running MD."""
    if sys.platform not in ("darwin", "linux"):
        raise ValueError("Only native macOS/Linux are supported")
    executable = shutil.which(str(candidate))
    if executable is None:
        raise MissingDependency(f"GROMACS executable not found: {candidate}")
    executable = str(Path(executable).resolve())
    result = subprocess.run([executable, "--version"], capture_output=True, text=True, check=True, timeout=15)
    output = result.stdout + result.stderr
    version = re.search(r"^GROMACS version:\s*(.+)$", output, re.M)
    prefix = re.search(r"^Data prefix:\s*(.+)$", output, re.M)
    if not version or not prefix:
        raise ValueError("Unrecognized GROMACS version output")
    return {"executable": executable, "sha256": sha256(executable), "version": version.group(1).strip(),
            "data_prefix": str(Path(prefix.group(1).strip()).resolve()), "platform": sys.platform,
            "build_capabilities": build_capabilities(output)}


def environment(inputs):
    """Isolate GROMACS lookup to the frozen library; preserve execution environment."""
    return dict(os.environ, GMXLIB=str(Path(inputs).resolve()), GMX_MAXBACKUP="-1")


def command(engine, arguments, cwd, record, inputs, seconds=120, stdin=None, overrides=None):
    """Run GROMACS with frozen input lookup; return the shared process execution record."""
    return run_command(engine, arguments, cwd, record, seconds=seconds, stdin=stdin,
                       env=dict(environment(inputs), **(overrides or {})))


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
