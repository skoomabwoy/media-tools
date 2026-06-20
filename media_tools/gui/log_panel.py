from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit


class LogPanel(QPlainTextEdit):
    appended = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)
        font = QFont("monospace")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.appended.connect(self._append_on_ui_thread, Qt.ConnectionType.QueuedConnection)

    def log(self, line: str) -> None:
        """Thread-safe entry point. Forwards to the UI thread via signal."""
        self.appended.emit(line)

    def _append_on_ui_thread(self, line: str) -> None:
        self.appendPlainText(line)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
