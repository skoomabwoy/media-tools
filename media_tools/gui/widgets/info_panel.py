from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from media_tools.backend.info import MediaInfo, probe
from media_tools.gui.worker import start_worker


class MediaInfoPanel(QGroupBox):
    """Read-only info table for a media file. Updates when refresh() is called.

    ffprobe runs on a background thread so a large or slow file never freezes the
    UI. Optional callback `on_info_changed` fires whenever a successful probe
    completes, so other widgets can react (e.g. auto-pick an output format).
    """

    def __init__(
        self,
        title: str = "File info",
        on_info_changed: Callable[[MediaInfo], None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(title, parent)
        self._on_info_changed = on_info_changed
        # Bump per refresh so a slow probe finishing after a newer one is ignored.
        self._seq = 0
        # Live probe handles, kept alive until each finishes (see DownloadTab).
        self._probe_handles: set = set()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self._table = QTableWidget(0, 2)
        self._table.horizontalHeader().setVisible(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._table.setShowGrid(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        layout.addWidget(self._table)

    def refresh(self, path_str: str) -> None:
        self._seq += 1
        my_seq = self._seq
        if not path_str:
            self.set_rows([])
            return
        path = Path(path_str).expanduser()
        if not path.exists():
            self.set_rows([("Error", f"File not found: {path}")])
            return
        self.set_status("Reading…")

        def on_ok(info: MediaInfo) -> None:
            self._probe_handles.discard(handle)
            if my_seq != self._seq:
                return  # stale
            self.set_rows(info.as_rows())
            if self._on_info_changed is not None:
                self._on_info_changed(info)

        def on_err(msg: str) -> None:
            self._probe_handles.discard(handle)
            if my_seq != self._seq:
                return
            self.set_rows([("Error", f"ffprobe failed: {msg}")])

        handle = start_worker(
            lambda p, log, cancel: probe(p),
            path,
            on_log=lambda _s: None,
            on_done_ok=on_ok,
            on_done_err=on_err,
        )
        self._probe_handles.add(handle)

    def set_status(self, text: str) -> None:
        """Show a single-line status message (e.g. 'Fetching…')."""
        self.set_rows([("", text)])

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        self._table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            key_item = QTableWidgetItem(k)
            key_item.setFlags(key_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            val_item = QTableWidgetItem(v)
            val_item.setFlags(val_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(i, 0, key_item)
            self._table.setItem(i, 1, val_item)
        self._table.resizeRowsToContents()
        rows_h = sum(self._table.rowHeight(i) for i in range(self._table.rowCount()))
        self._table.setFixedHeight(max(rows_h + 4, 30))
