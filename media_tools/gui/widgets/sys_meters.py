from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from media_tools.backend import sysmon


class SysMeters(QWidget):
    """Compact CPU + GPU + VRAM meters intended for a status bar."""

    def __init__(self, interval_ms: int = 1500, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)

        self.cpu_label = QLabel("CPU 0%")
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setFixedWidth(80)
        self.cpu_bar.setTextVisible(False)

        self.gpu_label = QLabel("GPU 0%")
        self.gpu_bar = QProgressBar()
        self.gpu_bar.setRange(0, 100)
        self.gpu_bar.setFixedWidth(80)
        self.gpu_bar.setTextVisible(False)

        self.vram_label = QLabel("VRAM —")

        layout.addWidget(self.cpu_label)
        layout.addWidget(self.cpu_bar)
        layout.addSpacing(12)
        layout.addWidget(self.gpu_label)
        layout.addWidget(self.gpu_bar)
        layout.addSpacing(12)
        layout.addWidget(self.vram_label)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(interval_ms)
        self._tick()

    def _tick(self) -> None:
        s = sysmon.sample()
        self.cpu_label.setText(f"CPU {s.cpu_percent:.0f}%")
        self.cpu_bar.setValue(int(s.cpu_percent))

        if s.gpu_percent is None:
            self.gpu_label.setText("GPU —")
            self.gpu_bar.setValue(0)
        else:
            self.gpu_label.setText(f"GPU {s.gpu_percent:.0f}%")
            self.gpu_bar.setValue(int(s.gpu_percent))

        if s.vram_used_gb is None or s.vram_total_gb is None:
            self.vram_label.setText("VRAM —")
        else:
            self.vram_label.setText(
                f"VRAM {s.vram_used_gb:.1f} / {s.vram_total_gb:.1f} GB"
            )
