from __future__ import annotations

import time
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal

from media_tools.core.cancel import Cancelled, CancelToken


# Every started TaskHandle registers here and deregisters when its thread exits.
# Lets the app drain in-flight workers on shutdown so a QThread is never left
# running when QApplication is destroyed (which would qFatal/abort the process).
_live_handles: set[TaskHandle] = set()


def stop_all_workers(timeout_ms: int = 4000) -> bool:
    """Cancel every live worker and wait for its thread to exit.

    Returns True if all threads stopped within the budget. A still-running task
    that can't be interrupted (e.g. an in-progress torch inference) returns
    False, signalling the caller to exit hard rather than let Qt abort.
    """
    handles = list(_live_handles)
    if not handles:
        return True
    for handle in handles:
        handle.cancel()
        handle._thread.quit()
    deadline = time.monotonic() + timeout_ms / 1000
    all_stopped = True
    for handle in handles:
        remaining_ms = int(max(0.0, deadline - time.monotonic()) * 1000)
        if handle._thread.wait(remaining_ms):
            # The normal finished-slot cleanup won't run without an event loop.
            _live_handles.discard(handle)
        else:
            all_stopped = False
    return all_stopped


class _Worker(QObject):
    """Runs `target(opts, log_fn, cancel)` on a background thread."""

    log = Signal(str)
    finished_ok = Signal(object)
    finished_err = Signal(str)
    finished_cancelled = Signal()

    def __init__(
        self,
        target: Callable[[Any, Callable[[str], None], CancelToken], Any],
        opts: Any,
        cancel: CancelToken,
    ) -> None:
        super().__init__()
        self._target = target
        self._opts = opts
        self._cancel = cancel

    def run(self) -> None:
        def emit_log(line: str) -> None:
            self.log.emit(line)

        try:
            result = self._target(self._opts, emit_log, self._cancel)
            self.finished_ok.emit(result)
        except Cancelled:
            self.finished_cancelled.emit()
        except Exception as e:
            self.finished_err.emit(f"{type(e).__name__}: {e}")


class TaskHandle(QObject):
    """
    Owns a (_Worker, QThread) pair and forwards their signals safely.

    The crucial detail: `done_ok` / `done_err` / `done_cancelled` are only
    emitted from `QThread.finished`, never directly from the worker. That
    guarantees the underlying OS thread has fully exited by the time the caller
    runs its completion callback — so it is safe for the caller to drop the
    handle reference. (If the caller dropped a QThread reference while it was
    still running, Qt would call qFatal and abort the process.)
    """

    log = Signal(str)
    done_ok = Signal(object)
    done_err = Signal(str)
    done_cancelled = Signal()

    def __init__(self, target: Callable[[Any, Callable[[str], None], CancelToken], Any], opts: Any) -> None:
        super().__init__()
        self._cancel = CancelToken()
        self._thread = QThread()
        self._worker = _Worker(target, opts, self._cancel)
        self._worker.moveToThread(self._thread)

        # Forward log lines through queued connections.
        self._worker.log.connect(self.log, Qt.ConnectionType.QueuedConnection)

        # Capture the result locally; emit only after the thread actually exits.
        self._result: tuple[str, Any] | None = None
        self._worker.finished_ok.connect(self._on_worker_ok, Qt.ConnectionType.QueuedConnection)
        self._worker.finished_err.connect(self._on_worker_err, Qt.ConnectionType.QueuedConnection)
        self._worker.finished_cancelled.connect(self._on_worker_cancelled, Qt.ConnectionType.QueuedConnection)

        # Quit the thread once the worker is done (any outcome).
        self._worker.finished_ok.connect(self._thread.quit)
        self._worker.finished_err.connect(self._thread.quit)
        self._worker.finished_cancelled.connect(self._thread.quit)

        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._on_thread_finished)

    def start(self) -> None:
        _live_handles.add(self)
        self._thread.start()

    def cancel(self) -> None:
        """Request cancellation of the running task. Safe to call from the UI thread."""
        self._cancel.cancel()

    def _on_worker_ok(self, result: Any) -> None:
        self._result = ("ok", result)

    def _on_worker_err(self, msg: str) -> None:
        self._result = ("err", msg)

    def _on_worker_cancelled(self) -> None:
        self._result = ("cancelled", None)

    def _on_thread_finished(self) -> None:
        _live_handles.discard(self)
        # Block briefly to make sure the OS thread is fully torn down before
        # we touch anything that might rely on it. Should be near-instant since
        # we're already inside the `finished` signal.
        self._thread.wait(2000)
        if self._result is None:
            self.done_err.emit("Worker exited without emitting a result.")
        elif self._result[0] == "ok":
            self.done_ok.emit(self._result[1])
        elif self._result[0] == "cancelled":
            self.done_cancelled.emit()
        else:
            self.done_err.emit(self._result[1])
        # Schedule both worker and thread for deletion via the main thread's event loop.
        self._worker.deleteLater()
        self._thread.deleteLater()


def start_worker(
    target: Callable[[Any, Callable[[str], None], CancelToken], Any],
    opts: Any,
    on_log: Callable[[str], None],
    on_done_ok: Callable[[Any], None],
    on_done_err: Callable[[str], None],
    on_done_cancelled: Callable[[], None] | None = None,
) -> TaskHandle:
    handle = TaskHandle(target, opts)
    handle.log.connect(on_log)
    handle.done_ok.connect(on_done_ok)
    handle.done_err.connect(on_done_err)
    if on_done_cancelled is not None:
        handle.done_cancelled.connect(on_done_cancelled)
    handle.start()
    return handle
