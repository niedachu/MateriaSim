"""Owned local process groups for cooperative and forced descendant cleanup."""

import os
import signal
import subprocess


def managed():
    """Return whether this worker inherited the framework's owned process-group scope."""
    return os.environ.get("MATERIASIM_MANAGED_GROUP") == "1"


def launch(arguments, **options):
    """Launch a nested worker in its owner's group, or create a new owned top-level group."""
    owner = not managed()
    process = subprocess.Popen(arguments, start_new_session=owner,
                               env=dict(os.environ, MATERIASIM_MANAGED_GROUP="1"), **options)
    return process, owner


def kill(process, owner):
    """Force-stop the exact owned group, or only a nested worker whose outer owner will reap descendants."""
    try:
        if owner:
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        # Normal exit may race the stop request; no unrelated PID/group is searched.
        return


def cleanup(process, owner):
    """Remove surviving descendants after the owned worker exits; never signal the caller's group."""
    if owner:
        kill(process, True)
