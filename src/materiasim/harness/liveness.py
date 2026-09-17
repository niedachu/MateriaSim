"""Worker-side parent-loss detection using an inherited pipe, never a persisted PID."""

import os
import select
import signal
import stat
import threading

from materiasim.errors import MateriaSimError


class SupervisorConnection:
    """Own a read-only liveness descriptor; EOF requests cooperative stop of this worker.

    Only the live supervisor retains the write end. Descendants must not inherit
    either end, so PID reuse or a surviving native child cannot mask parent loss.
    This is a cooperative guard, not an operating-system orphan-reaper service.
    """

    def __init__(self, descriptor):
        """Validate and own the inherited pipe descriptor without trusting any PID from disk."""
        if descriptor < 3 or not stat.S_ISFIFO(os.fstat(descriptor).st_mode):
            raise ValueError("Worker requires an inherited supervisor pipe")
        self.descriptor = descriptor
        os.set_inheritable(descriptor, False)
        self.stopped = threading.Event()
        self.lost = threading.Event()
        self.thread = threading.Thread(target=self._watch, name="supervisor-connection", daemon=True)

    def disconnected(self, timeout=0):
        """Return whether the liveness channel closed or violated its no-payload protocol."""
        readable, _, _ = select.select([self.descriptor], [], [], timeout)
        # The supervisor never writes data. Any readability means EOF or an invalid channel.
        if readable:
            self.lost.set()
        return self.lost.is_set()

    def check(self):
        """Reject a new operation once the actual supervisory connection has disappeared."""
        if self.disconnected():
            raise MateriaSimError("SUPERVISOR_LOST", "Supervisor connection closed; no new operation admitted",
                                  category="control")

    def _watch(self):
        """Signal this process once on EOF; nested runtime handlers forward the cooperative stop."""
        while not self.stopped.is_set():
            if self.disconnected(.1):
                if not self.stopped.is_set():
                    os.kill(os.getpid(), signal.SIGTERM)
                return

    def __enter__(self):
        """Start monitoring only after synchronous startup admission, returning the guard."""
        try:
            self.check()
            self.thread.start()
        except BaseException:
            self.stopped.set()
            if self.thread.ident is not None:
                self.thread.join()
            os.close(self.descriptor)
            raise
        return self

    def __exit__(self, exc_type, exc, traceback):
        """Stop the monitor before sealing the receipt; never signal after normal teardown."""
        self.stopped.set()
        self.thread.join()
        os.close(self.descriptor)
