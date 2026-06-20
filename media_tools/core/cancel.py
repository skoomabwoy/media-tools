"""Cooperative cancellation for background tasks.

A CancelToken is handed to each backend task. The task should:
- call `bind_process(proc)` after spawning a subprocess, so the token can
  terminate it when cancelled, and
- call `raise_if_cancelled()` (or check `cancelled`) at safe points in any
  in-process loop it controls.

Cancellation is cooperative: work the task cannot interrupt (e.g. a single
torch inference call) keeps running until it returns on its own.
"""

from __future__ import annotations

import subprocess


class Cancelled(Exception):
    """Raised by a task when it stops early because its CancelToken was tripped."""


class CancelToken:
    def __init__(self) -> None:
        self._cancelled = False
        self._proc: subprocess.Popen | None = None

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def cancel(self) -> None:
        """Request cancellation. Safe to call from another thread."""
        self._cancelled = True
        proc = self._proc
        if proc is not None:
            self._terminate(proc)

    def bind_process(self, proc: subprocess.Popen) -> None:
        """Register the task's active subprocess so cancel() can terminate it.

        Handles the race where cancel() arrives before the process is bound.
        """
        self._proc = proc
        if self._cancelled:
            self._terminate(proc)

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise Cancelled()

    @staticmethod
    def _terminate(proc: subprocess.Popen) -> None:
        try:
            proc.terminate()
        except (ProcessLookupError, OSError):
            pass
