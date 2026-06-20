from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from media_tools.core import config
from media_tools.core.theme import DEFAULT_THEME, apply_theme
from media_tools.gui.app import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    apply_theme(app, config.load().get("theme", DEFAULT_THEME))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
