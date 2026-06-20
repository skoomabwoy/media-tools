from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from media_tools.backend.convert import run_conversion
from media_tools.core.options import (
    AAC_BITRATES,
    CONVERT_FORMATS,
    ConvertOpts,
    FLAC_DEPTHS,
    MP3_BITRATES,
    OGG_QUALITIES,
    OPUS_BITRATES,
    SAMPLE_RATES,
    WAV_DEPTHS,
)
from media_tools.gui.log_panel import LogPanel
from media_tools.gui.util import wrap
from media_tools.gui.widgets.info_panel import MediaInfoPanel
from media_tools.gui.worker import start_worker


_QUALITY_OPTIONS: dict[str, list[tuple[str, str]]] = {
    "mp3": MP3_BITRATES,
    "flac": FLAC_DEPTHS,
    "wav": WAV_DEPTHS,
    "ogg": OGG_QUALITIES,
    "opus": OPUS_BITRATES,
    "aac": AAC_BITRATES,
    "aiff": [("pcm_s16be", "16-bit")],
}


class ConvertTab(QWidget):
    def __init__(self, log_panel: LogPanel, parent=None) -> None:
        super().__init__(parent)
        self._log = log_panel
        self._thread = None
        self._build_ui()
        self._on_format_changed(0)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # --- Input file row ---
        input_row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("/path/to/file.flac")
        self.input_edit.editingFinished.connect(self._refresh_info)
        btn_pick = QPushButton("Browse…")
        btn_pick.clicked.connect(self._pick_input)
        input_row.addWidget(self.input_edit, 1)
        input_row.addWidget(btn_pick)
        root.addLayout(input_row)

        # --- Info panel (shared widget) ---
        self.info_panel = MediaInfoPanel()
        root.addWidget(self.info_panel)

        # --- Conversion group ---
        conv_group = QGroupBox("Convert")
        conv_form = QFormLayout(conv_group)
        conv_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.format_combo = QComboBox()
        for key, label in CONVERT_FORMATS:
            self.format_combo.addItem(label, key)
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        conv_form.addRow("Target format:", self.format_combo)

        self.quality_combo = QComboBox()
        conv_form.addRow("Quality:", self.quality_combo)

        self.sr_combo = QComboBox()
        for key, label in SAMPLE_RATES:
            self.sr_combo.addItem(label, key)
        conv_form.addRow("Sample rate:", self.sr_combo)

        out_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("(auto from input + format)")
        btn_pick_out = QPushButton("Browse…")
        btn_pick_out.clicked.connect(self._pick_output)
        out_row.addWidget(self.output_edit, 1)
        out_row.addWidget(btn_pick_out)
        conv_form.addRow("Output file:", wrap(out_row))

        btn_row = QHBoxLayout()
        self.convert_btn = QPushButton("Convert")
        self.convert_btn.clicked.connect(self._run)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.convert_btn, 1)
        btn_row.addWidget(self.cancel_btn)
        conv_form.addRow("", wrap(btn_row))

        root.addWidget(conv_group)

    def _pick_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pick media file",
            "",
            "Media files (*.wav *.flac *.mp3 *.m4a *.aac *.opus *.ogg *.aiff *.wma);;All files (*.*)",
        )
        if path:
            self.input_edit.setText(path)
            self._refresh_info()

    def _pick_output(self) -> None:
        suggested = self.output_edit.text() or self._suggested_output_path()
        path, _ = QFileDialog.getSaveFileName(self, "Output file", suggested or "")
        if path:
            self.output_edit.setText(path)

    def _suggested_output_path(self) -> str:
        src = self.input_edit.text().strip()
        if not src:
            return ""
        ext = self.format_combo.currentData()
        if ext == "aac":
            ext = "m4a"
        return str(Path(src).with_suffix(f".{ext}"))

    def _refresh_info(self) -> None:
        self.info_panel.refresh(self.input_edit.text().strip())
        if not self.output_edit.text():
            self.output_edit.setPlaceholderText(self._suggested_output_path() or "")

    def _on_format_changed(self, idx: int) -> None:
        fmt = self.format_combo.currentData()
        self.quality_combo.clear()
        for key, label in _QUALITY_OPTIONS.get(fmt, []):
            self.quality_combo.addItem(label, key)
        self.output_edit.setPlaceholderText(self._suggested_output_path() or "")

    def _collect_opts(self) -> ConvertOpts | None:
        src = self.input_edit.text().strip()
        if not src:
            QMessageBox.warning(self, "Missing input", "Please pick an input file.")
            return None
        out = self.output_edit.text().strip() or self._suggested_output_path()
        if not out:
            QMessageBox.warning(self, "Missing output", "Please specify an output file.")
            return None
        return ConvertOpts(
            input_file=Path(src).expanduser(),
            output_file=Path(out).expanduser(),
            format=self.format_combo.currentData(),
            quality=self.quality_combo.currentData() or "",
            sample_rate=self.sr_combo.currentData() or "",
        )

    def _run(self) -> None:
        if self._thread is not None:
            QMessageBox.information(self, "Busy", "A conversion is already running.")
            return
        opts = self._collect_opts()
        if opts is None:
            return
        self._log.log(f"--- Converting {opts.input_file.name} → {opts.output_file.name} ---")
        self.convert_btn.setEnabled(False)
        self.convert_btn.setText("Converting…")
        self.cancel_btn.setEnabled(True)
        self._thread = start_worker(
            run_conversion,
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
        self._log.log("--- Cancelling… ---")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling…")
        self._thread.cancel()

    def _on_done_ok(self, out_path: Path) -> None:
        self._log.log(f"--- Done. Wrote {out_path} ---")
        self._reset()

    def _on_done_err(self, msg: str) -> None:
        self._log.log(f"--- Failed: {msg} ---")
        self._reset()

    def _on_done_cancelled(self) -> None:
        self._log.log("--- Cancelled ---")
        self._reset()

    def _reset(self) -> None:
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText("Convert")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel")
        self._thread = None
