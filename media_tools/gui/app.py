from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from media_tools.core import config
from media_tools.core.devices import detect_cuda_devices, device_options
from media_tools.gui.log_panel import LogPanel
from media_tools.gui.tabs.convert import ConvertTab
from media_tools.gui.tabs.download import DownloadTab
from media_tools.gui.tabs.separate import SeparateTab
from media_tools.gui.widgets.sys_meters import SysMeters
from media_tools.gui.worker import start_worker, stop_all_workers


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Media Tools")
        self.resize(950, 800)

        log_panel = LogPanel()

        tabs = QTabWidget()
        self._download_tab = DownloadTab(log_panel)
        self._separate_tab = SeparateTab(log_panel)
        self._convert_tab = ConvertTab(log_panel)
        tabs.addTab(self._download_tab, "Download")
        tabs.addTab(self._separate_tab, "Separate")
        tabs.addTab(self._convert_tab, "Convert")

        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(QLabel("Log:"))
        log_layout.addWidget(log_panel)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(tabs)
        splitter.addWidget(log_container)
        # Both halves get to grow, but the log grows preferentially so users
        # don't end up staring at empty space above the log when forms are short.
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 380])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

        status = QStatusBar()
        self._device_btn = QPushButton("Compute device")
        self._device_btn.setToolTip("Choose the default device for stem separation")
        self._device_btn.clicked.connect(self._choose_device)
        status.addWidget(self._device_btn)          # bottom-left
        status.addPermanentWidget(SysMeters())      # bottom-right
        self.setStatusBar(status)

        self._detect_handle = None
        self._closing = False
        self._maybe_detect_devices()

    def _maybe_detect_devices(self) -> None:
        """On first run, discover GPUs in the background, then prompt for a default."""
        if "cuda_devices" in config.load():
            return  # already detected on a previous run
        self._start_detection(prompt=True)

    def _start_detection(self, prompt: bool) -> None:
        if self._detect_handle is not None:
            return  # detection already running
        self._device_btn.setEnabled(False)
        self._detect_handle = start_worker(
            lambda _opts, _log, cancel: detect_cuda_devices(cancel=cancel),
            None,
            on_log=lambda _s: None,
            on_done_ok=lambda result: self._on_devices_detected(result, prompt),
            on_done_err=lambda _msg: self._on_devices_detected(None, prompt),
        )

    def _active_task(self) -> str | None:
        """Name of a running user task (download/separation/conversion), if any.

        Background work (device detection, info probes) doesn't count — it's quick
        and cancelled cleanly on close without bothering the user.
        """
        for name, tab in (
            ("A download", self._download_tab),
            ("A separation", self._separate_tab),
            ("A conversion", self._convert_tab),
        ):
            if tab.is_running():
                return name
        return None

    def closeEvent(self, event) -> None:
        task = self._active_task()
        if task is not None:
            resp = QMessageBox.question(
                self,
                "Quit while a task is running?",
                f"{task} is still running. Quitting now will stop it — an "
                "in-progress separation can't be resumed. Quit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                event.ignore()
                return

        # Drain in-flight workers so no QThread is left running when Qt tears down
        # QApplication (which would qFatal/abort). If something can't be stopped in
        # time (e.g. an in-progress inference), exit hard to avoid that abort.
        self._closing = True
        if not stop_all_workers():
            os._exit(0)
        super().closeEvent(event)

    def _on_devices_detected(self, result, prompt: bool) -> None:
        self._detect_handle = None
        self._device_btn.setEnabled(True)
        if self._closing:
            return  # window is going away; don't pop a dialog during shutdown
        cuda_names = result if isinstance(result, list) else []
        # Cache only a definitive result; on detection failure we retry next launch.
        if result is not None:
            config.update(cuda_devices=cuda_names)
        if prompt:
            self._apply_device_choice(cuda_names)

    def _choose_device(self) -> None:
        """Status-bar button: let the user (re)pick the default device."""
        if self._detect_handle is not None:
            return  # detection in progress; button is disabled anyway
        cached = config.load().get("cuda_devices")
        if isinstance(cached, list):
            self._apply_device_choice(cached)
        else:
            # First-run detection failed earlier; try again, then prompt.
            self._start_detection(prompt=True)

    def _apply_device_choice(self, cuda_names: list[str]) -> None:
        selected = self._prompt_device_choice(cuda_names, config.load().get("device", "auto"))
        config.update(device=selected)
        self._separate_tab.set_device_options(cuda_names, selected)

    def _prompt_device_choice(self, cuda_names: list[str], current: str | None = None) -> str:
        options = device_options(cuda_names)
        labels = [label for _, label in options]
        keys = [key for key, _ in options]
        if current in keys:
            default = keys.index(current)
        else:
            default = 1 if cuda_names else 0  # first GPU if present, else Auto
        label, ok = QInputDialog.getItem(
            self,
            "Select compute device",
            "Choose the default device for stem separation.\n"
            "You can also change this anytime from this button.",
            labels,
            default,
            False,  # not editable
        )
        if not ok:
            return keys[default]
        return keys[labels.index(label)]
