"""Fusion-based light/dark theming.

Forcing the Fusion style gives a predictable look that's identical across
platforms and fully driven by the QPalette, so a palette swap restyles every
stock widget with no per-widget work.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


THEMES = ("light", "dark")
DEFAULT_THEME = "light"


def _dark_palette() -> QPalette:
    window = QColor(53, 53, 53)
    base = QColor(35, 35, 35)
    text = QColor(220, 220, 220)
    disabled = QColor(127, 127, 127)
    highlight = QColor(42, 130, 218)

    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, window)
    p.setColor(QPalette.ColorRole.ToolTipBase, window)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, window)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 80, 80))
    p.setColor(QPalette.ColorRole.Link, highlight)
    p.setColor(QPalette.ColorRole.Highlight, highlight)
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    p.setColor(QPalette.ColorRole.PlaceholderText, disabled)

    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(80, 80, 80))
    return p


def apply_theme(app: QApplication, name: str) -> None:
    """Apply the named theme ('light' or 'dark') to the running application."""
    if name not in THEMES:
        name = DEFAULT_THEME
    app.setStyle("Fusion")
    if name == "dark":
        app.setPalette(_dark_palette())
    else:
        # Fusion's own standard palette is a clean light theme.
        app.setPalette(app.style().standardPalette())
