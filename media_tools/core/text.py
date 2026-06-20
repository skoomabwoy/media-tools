"""Small text/stream helpers shared across the backend and GUI."""

from __future__ import annotations

from typing import Callable


# Callback used to forward a single log line from a task to the UI.
LogFn = Callable[[str], None]


def format_duration(seconds: float | None) -> str:
    """Format a duration as ``H:MM:SS`` (``M:SS`` under an hour). ``—`` if unknown."""
    if seconds is None:
        return "—"
    m, sec = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


class LineSplitter:
    """Forward complete lines from a text stream to ``log``.

    Both ``\\n`` and ``\\r`` are treated as terminators, since tqdm and ffmpeg
    overwrite the current line with ``\\r`` rather than starting a new one.
    """

    def __init__(self, log: LogFn) -> None:
        self._log = log
        self._buf = ""

    def feed(self, text: str) -> None:
        if not text:
            return
        self._buf += text
        while True:
            idx_n = self._buf.find("\n")
            idx_r = self._buf.find("\r")
            cuts = [i for i in (idx_n, idx_r) if i != -1]
            if not cuts:
                break
            cut = min(cuts)
            line = self._buf[:cut].rstrip()
            self._buf = self._buf[cut + 1 :]
            if line:
                self._log(line)

    def flush(self) -> None:
        if self._buf.strip():
            self._log(self._buf.rstrip())
        self._buf = ""
