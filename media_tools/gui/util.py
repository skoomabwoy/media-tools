from __future__ import annotations

from PySide6.QtWidgets import QLayout, QWidget


def wrap(layout: QLayout) -> QWidget:
    """Wrap a layout in a margin-free QWidget, e.g. to embed an HBox in a form row."""
    w = QWidget()
    w.setLayout(layout)
    layout.setContentsMargins(0, 0, 0, 0)
    return w
