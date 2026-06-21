from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from media_tools.backend.format_match import suggest_separation_format
from media_tools.backend.info import MediaInfo
from media_tools.backend.separate import run_separation
from media_tools.core import config
from media_tools.core.devices import detect_cuda_devices, device_options
from media_tools.core.options import (
    OUTPUT_FORMATS,
    REFINEMENT_LEVELS,
    SeparateOpts,
    models_by_category,
)
from media_tools.gui.log_panel import LogPanel
from media_tools.gui.util import wrap
from media_tools.gui.widgets.info_panel import MediaInfoPanel
from media_tools.gui.worker import start_worker


class SeparateTab(QWidget):
    def __init__(self, log_panel: LogPanel, parent=None) -> None:
        super().__init__(parent)
        self._log = log_panel
        self._thread = None
        self._detect_handle = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --- Input file row ---
        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("/path/to/song.flac")
        self.input_edit.editingFinished.connect(self._refresh_info)
        btn_pick_input = QPushButton("Browse…")
        btn_pick_input.clicked.connect(self._pick_input)
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(btn_pick_input)
        root.addLayout(input_row)

        # --- Info panel (shared widget) ---
        self.info_panel = MediaInfoPanel(on_info_changed=self._on_info)
        root.addWidget(self.info_panel)

        # --- Form ---
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Output directory
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("/path/to/output/dir")
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_edit, 1)
        btn_pick_output = QPushButton("Browse…")
        btn_pick_output.clicked.connect(self._pick_output)
        output_row.addWidget(btn_pick_output)
        form.addRow("Output dir:", wrap(output_row))

        # Model dropdown grouped by category
        self.model_combo = QComboBox()
        self._build_model_combo(self.model_combo)
        form.addRow("Model:", self.model_combo)

        # Output format
        self.format_combo = QComboBox()
        for key, label in OUTPUT_FORMATS:
            self.format_combo.addItem(label, key)
        self.format_combo.setCurrentIndex(self._format_index("flac24"))
        form.addRow("Output format:", self.format_combo)

        # Optional extra passes (off by default; diminishing returns).
        self.refinement_combo = QComboBox()
        for key, label in REFINEMENT_LEVELS:
            self.refinement_combo.addItem(label, key)
        self.refinement_combo.setToolTip(
            "Averages additional passes for a small quality gain. Much slower with "
            "diminishing returns — the default single pass already gives an "
            "excellent result."
        )
        form.addRow("Refinement:", self.refinement_combo)

        self.device_combo = QComboBox()
        # Populate from cached detection (if any); MainWindow refreshes this once
        # GPU detection finishes on first run. Default selection comes from config.
        cfg = config.load()
        cached = cfg.get("cuda_devices")
        self._populate_devices(
            cached if isinstance(cached, list) else [],
            cfg.get("device", "auto"),
        )
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)

        self.redetect_btn = QPushButton()
        self.redetect_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.redetect_btn.setToolTip("Re-scan for compute devices")
        self.redetect_btn.setFixedWidth(32)
        self.redetect_btn.clicked.connect(self._redetect_devices)

        device_row = QHBoxLayout()
        device_row.addWidget(self.device_combo, 1)
        device_row.addWidget(self.redetect_btn)
        form.addRow("Device:", wrap(device_row))

        root.addLayout(form)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Run separation")
        self.run_btn.clicked.connect(self._run)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.run_btn, 1)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

    def _build_model_combo(self, combo: QComboBox) -> None:
        """Populate the combo with categorized headers (disabled) and selectable models."""
        model = QStandardItemModel(combo)
        first_selectable: int | None = None

        for category, items in models_by_category().items():
            header = QStandardItem(f"── {category} ──")
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            model.appendRow(header)

            for spec in items:
                row = QStandardItem("  " + spec.label)
                row.setData(spec, Qt.ItemDataRole.UserRole)
                if spec.tooltip:
                    row.setToolTip(spec.tooltip)
                model.appendRow(row)
                if first_selectable is None:
                    first_selectable = model.rowCount() - 1

        combo.setModel(model)
        if first_selectable is not None:
            combo.setCurrentIndex(first_selectable)

    def _current_model(self):
        idx = self.model_combo.currentIndex()
        return self.model_combo.model().item(idx).data(Qt.ItemDataRole.UserRole)

    def _format_index(self, key: str) -> int:
        for i in range(self.format_combo.count()):
            if self.format_combo.itemData(i) == key:
                return i
        return 0

    def _populate_devices(self, cuda_names: list[str], selected: str) -> None:
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for key, label in device_options(cuda_names):
            self.device_combo.addItem(label, key)
        idx = self.device_combo.findData(selected)
        self.device_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.device_combo.blockSignals(False)

    def set_device_options(self, cuda_names: list[str], selected: str) -> None:
        """Rebuild the device list after detection (called by MainWindow)."""
        self._populate_devices(cuda_names, selected)

    def _on_device_changed(self, *args) -> None:
        # Persist the user's device choice so it sticks across launches.
        config.update(device=self.device_combo.currentData())

    def _redetect_devices(self) -> None:
        """Re-scan for compute devices in the background and refresh the list."""
        if self._detect_handle is not None:
            return  # a scan is already running
        self.redetect_btn.setEnabled(False)
        self.device_combo.setEnabled(False)
        self._log.log("Scanning for compute devices…")
        self._detect_handle = start_worker(
            lambda _opts, _log, cancel: detect_cuda_devices(cancel=cancel),
            None,
            on_log=lambda _s: None,
            on_done_ok=self._on_redetect_done,
            on_done_err=lambda _msg: self._on_redetect_done(None),
        )

    def _on_redetect_done(self, result) -> None:
        self._detect_handle = None
        self.redetect_btn.setEnabled(True)
        self.device_combo.setEnabled(True)
        if not isinstance(result, list):
            self._log.log("Device scan failed; keeping the current list.")
            return
        config.update(cuda_devices=result)
        # Keep the current selection if it survived the rescan, else fall back to
        # Auto. Persist whatever ended up selected so config matches the UI.
        current = self.device_combo.currentData()
        self._populate_devices(result, current)
        config.update(device=self.device_combo.currentData())
        self._log.log(f"Found {len(result)} GPU(s).")

    def _pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pick audio file",
            "",
            "Audio files (*.wav *.flac *.mp3 *.m4a *.opus *.ogg);;All files (*.*)",
        )
        if path:
            self.input_edit.setText(path)
            self._refresh_info()
            if not self.output_edit.text():
                self.output_edit.setText(str(Path(path).parent))

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Pick output directory")
        if path:
            self.output_edit.setText(path)

    def _refresh_info(self) -> None:
        self.info_panel.refresh(self.input_edit.text().strip())

    def _on_info(self, info: MediaInfo) -> None:
        # Auto-pick an output format that matches the input.
        suggested = suggest_separation_format(info)
        self.format_combo.setCurrentIndex(self._format_index(suggested))

    def _collect_opts(self) -> SeparateOpts | None:
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        if not input_path:
            QMessageBox.warning(self, "Missing input", "Please pick an input file.")
            return None
        if not output_path:
            QMessageBox.warning(self, "Missing output", "Please pick an output directory.")
            return None
        spec = self._current_model()
        if spec is None:
            QMessageBox.warning(self, "Missing model", "Please pick a model.")
            return None
        return SeparateOpts(
            input_file=Path(input_path).expanduser(),
            output_dir=Path(output_path).expanduser(),
            model=spec,
            output_format=self.format_combo.currentData(),
            refinement=self.refinement_combo.currentData(),
            device=self.device_combo.currentData(),
        )

    def _run(self) -> None:
        if self._thread is not None:
            QMessageBox.information(self, "Busy", "A separation is already running.")
            return
        opts = self._collect_opts()
        if opts is None:
            return
        self._log.log(f"--- Starting separation of {opts.input_file.name} ---")
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running…")
        self.cancel_btn.setEnabled(True)
        self._thread = start_worker(
            run_separation,
            opts,
            on_log=self._log.log,
            on_done_ok=self._on_done_ok,
            on_done_err=self._on_done_err,
            on_done_cancelled=self._on_done_cancelled,
        )

    def is_running(self) -> bool:
        return self._thread is not None

    def _cancel(self) -> None:
        if self._thread is None:
            return
        # Cancel applies to the weight-download phase and the wait before
        # inference; a torch run already in progress finishes on its own.
        self._log.log("--- Cancelling… (a model run already in progress will finish first) ---")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling…")
        self._thread.cancel()

    def _on_done_ok(self, out_dir: Path) -> None:
        self._log.log(f"--- Done. Output in {out_dir} ---")
        self._reset()

    def _on_done_err(self, msg: str) -> None:
        self._log.log(f"--- Failed: {msg} ---")
        self._reset()

    def _on_done_cancelled(self) -> None:
        self._log.log("--- Cancelled ---")
        self._reset()

    def _reset(self) -> None:
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run separation")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel")
        self._thread = None
