from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from media_tools.backend.download import run_download
from media_tools.backend.url_probe import URLInfo, probe_url
from media_tools.backend.url_suggest import (
    suggest_audio_format,
    suggest_audio_quality,
    suggest_video_resolution,
)
from media_tools.core.options import (
    DOWNLOAD_AUDIO_FORMATS,
    DOWNLOAD_BROWSERS,
    DOWNLOAD_MODES,
    DOWNLOAD_QUALITY_BY_FORMAT,
    DOWNLOAD_SPONSORBLOCK,
    DOWNLOAD_VIDEO_CONTAINERS,
    DOWNLOAD_VIDEO_RESOLUTIONS,
    DownloadOpts,
)
from media_tools.gui.log_panel import LogPanel
from media_tools.gui.util import wrap
from media_tools.gui.widgets.info_panel import MediaInfoPanel
from media_tools.gui.worker import start_worker


_RECOMMENDED_SUFFIX = "  (recommended)"


class DownloadTab(QWidget):
    def __init__(self, log_panel: LogPanel, parent=None) -> None:
        super().__init__(parent)
        self._log = log_panel
        self._dl_thread = None
        # Live probe TaskHandles, kept alive until each finishes. A probe handle
        # must not be dropped while its QThread is still running, or Qt aborts
        # the process. We discard each handle from its own done callbacks.
        self._probe_threads: set = set()
        # Increment on each probe request. Stale results (older probes finishing
        # after a newer URL was entered) are silently discarded.
        self._probe_seq = 0
        self._last_probed_url = ""
        # Stashed info from the most recent successful probe; used so we can
        # re-mark the quality recommendation when the user changes audio format.
        self._last_info: URLInfo | None = None
        self._build_ui()
        self._on_mode_changed(0)
        self._on_audio_format_changed(0)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # URL row
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://www.youtube.com/watch?v=…")
        self.url_edit.editingFinished.connect(self._maybe_probe_url)
        btn_paste = QPushButton("Paste")
        btn_paste.clicked.connect(self._paste_url)
        url_row.addWidget(self.url_edit, 1)
        url_row.addWidget(btn_paste)
        root.addLayout(url_row)

        # URL info panel (reusing the shared widget)
        self.url_info = MediaInfoPanel(title="Source info")
        root.addWidget(self.url_info)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Output dir
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("/path/to/output/dir")
        out_row = QHBoxLayout()
        out_row.addWidget(self.output_edit, 1)
        btn_pick_out = QPushButton("Browse…")
        btn_pick_out.clicked.connect(self._pick_output)
        out_row.addWidget(btn_pick_out)
        form.addRow("Output dir:", wrap(out_row))

        # Mode picker
        self.mode_combo = QComboBox()
        for key, label in DOWNLOAD_MODES:
            self.mode_combo.addItem(label, key)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        form.addRow("Mode:", self.mode_combo)

        # Conditional Audio / Video panels in a QStackedWidget
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_audio_panel())
        self.stack.addWidget(self._build_video_panel())
        form.addRow("", self.stack)

        # Extras
        self.thumbnail_cb = QCheckBox("Embed thumbnail (when supported)")
        self.metadata_cb = QCheckBox("Embed metadata & chapters")
        form.addRow("", self.thumbnail_cb)
        form.addRow("", self.metadata_cb)

        # SponsorBlock
        self.sb_combo = QComboBox()
        for key, label in DOWNLOAD_SPONSORBLOCK:
            self.sb_combo.addItem(label, key)
        form.addRow("SponsorBlock:", self.sb_combo)

        # Cookies
        self.cookies_combo = QComboBox()
        for key, label in DOWNLOAD_BROWSERS:
            self.cookies_combo.addItem(label, key)
        form.addRow("Cookies from:", self.cookies_combo)

        root.addLayout(form)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Download")
        self.run_btn.clicked.connect(self._run)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.setEnabled(False)
        btn_row.addWidget(self.run_btn, 1)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

    def _build_audio_panel(self) -> QWidget:
        w = QWidget()
        layout = QFormLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        self.audio_fmt_combo = QComboBox()
        for key, label in DOWNLOAD_AUDIO_FORMATS:
            self.audio_fmt_combo.addItem(label, key)
        self.audio_fmt_combo.currentIndexChanged.connect(self._on_audio_format_changed)
        layout.addRow("Format:", self.audio_fmt_combo)

        self.audio_q_combo = QComboBox()
        self.audio_q_label = QLabel("Quality:")
        layout.addRow(self.audio_q_label, self.audio_q_combo)

        return w

    def _build_video_panel(self) -> QWidget:
        w = QWidget()
        layout = QFormLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        self.video_container_combo = QComboBox()
        for key, label in DOWNLOAD_VIDEO_CONTAINERS:
            self.video_container_combo.addItem(label, key)
        layout.addRow("Container:", self.video_container_combo)

        self.video_res_combo = QComboBox()
        for key, label in DOWNLOAD_VIDEO_RESOLUTIONS:
            self.video_res_combo.addItem(label, key)
        layout.addRow("Max resolution:", self.video_res_combo)

        return w

    def _on_mode_changed(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)

    def _on_audio_format_changed(self, *args) -> None:
        fmt = self.audio_fmt_combo.currentData()
        opts = DOWNLOAD_QUALITY_BY_FORMAT.get(fmt, [])
        self.audio_q_combo.clear()
        for key, label in opts:
            self.audio_q_combo.addItem(label, key)
        has_quality = bool(opts)
        self.audio_q_combo.setEnabled(has_quality)
        self.audio_q_label.setEnabled(has_quality)
        if not has_quality:
            self.audio_q_combo.addItem("(no quality picker for this format)", "")
        # If we have probe info, re-mark the recommended quality for this format.
        if self._last_info is not None and has_quality:
            recommended_q = suggest_audio_quality(self._last_info, fmt)
            self._mark_recommended(self.audio_q_combo, recommended_q, also_select=True)

    def _paste_url(self) -> None:
        from PySide6.QtGui import QGuiApplication
        cb = QGuiApplication.clipboard()
        if cb is None:
            return
        text = cb.text().strip()
        if text:
            self.url_edit.setText(text)
            self._maybe_probe_url()

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Pick output directory")
        if path:
            self.output_edit.setText(path)

    def _maybe_probe_url(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            self.url_info.set_rows([])
            self._last_probed_url = ""
            return
        if url == self._last_probed_url:
            return
        self._probe_seq += 1
        my_seq = self._probe_seq
        self._last_probed_url = url
        self.url_info.set_status("Fetching info…")

        def on_done_ok(info: URLInfo) -> None:
            self._probe_threads.discard(handle)
            if my_seq != self._probe_seq:
                return  # stale
            self.url_info.set_rows(info.as_rows())
            self._apply_suggestions(info)

        def on_done_err(msg: str) -> None:
            self._probe_threads.discard(handle)
            if my_seq != self._probe_seq:
                return
            self.url_info.set_rows([("Probe failed", msg)])
            self._last_info = None
            self._clear_recommendations()

        handle = start_worker(
            lambda url, log, cancel: probe_url(url, log),
            url,
            on_log=self._log.log,
            on_done_ok=on_done_ok,
            on_done_err=on_done_err,
        )
        self._probe_threads.add(handle)

    def _apply_suggestions(self, info: URLInfo) -> None:
        """Pick recommended audio format / quality / video resolution and label them."""
        self._last_info = info
        self._clear_recommendations()

        if info.has_audio:
            rec_fmt = suggest_audio_format(info)
            self._mark_recommended(self.audio_fmt_combo, rec_fmt, also_select=True)
            # Switching the format combo re-runs _on_audio_format_changed,
            # which will mark the recommended quality for the new format.

        if info.has_video:
            rec_res = suggest_video_resolution(info)
            self._mark_recommended(self.video_res_combo, rec_res, also_select=True)

    def _mark_recommended(self, combo: QComboBox, recommended_key: str, also_select: bool) -> None:
        """Strip any existing (recommended) suffix, then append it to the matching item."""
        for i in range(combo.count()):
            text = combo.itemText(i)
            if text.endswith(_RECOMMENDED_SUFFIX):
                combo.setItemText(i, text[: -len(_RECOMMENDED_SUFFIX)])
            if combo.itemData(i) == recommended_key:
                combo.setItemText(i, combo.itemText(i) + _RECOMMENDED_SUFFIX)
                if also_select:
                    combo.setCurrentIndex(i)

    def _clear_recommendations(self) -> None:
        for combo in (self.audio_fmt_combo, self.audio_q_combo, self.video_res_combo):
            for i in range(combo.count()):
                text = combo.itemText(i)
                if text.endswith(_RECOMMENDED_SUFFIX):
                    combo.setItemText(i, text[: -len(_RECOMMENDED_SUFFIX)])

    def _collect_opts(self) -> DownloadOpts | None:
        url = self.url_edit.text().strip()
        out = self.output_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please paste a URL to download.")
            return None
        if not out:
            QMessageBox.warning(self, "Missing output", "Please pick an output directory.")
            return None
        return DownloadOpts(
            url=url,
            output_dir=Path(out).expanduser(),
            mode=self.mode_combo.currentData(),
            audio_format=self.audio_fmt_combo.currentData(),
            audio_quality=self.audio_q_combo.currentData() or "",
            video_container=self.video_container_combo.currentData(),
            video_max_height=self.video_res_combo.currentData() or "",
            embed_thumbnail=self.thumbnail_cb.isChecked(),
            embed_metadata=self.metadata_cb.isChecked(),
            sponsorblock_mode=self.sb_combo.currentData() or "",
            cookies_browser=self.cookies_combo.currentData() or "",
        )

    def _run(self) -> None:
        if self._dl_thread is not None:
            QMessageBox.information(self, "Busy", "A download is already running.")
            return
        opts = self._collect_opts()
        if opts is None:
            return
        self._log.log(f"--- Downloading {opts.url} ---")
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Downloading…")
        self.cancel_btn.setEnabled(True)
        self._dl_thread = start_worker(
            run_download,
            opts,
            on_log=self._log.log,
            on_done_ok=self._on_done_ok,
            on_done_err=self._on_done_err,
            on_done_cancelled=self._on_done_cancelled,
        )

    def is_running(self) -> bool:
        return self._dl_thread is not None

    def _cancel(self) -> None:
        if self._dl_thread is None:
            return
        self._log.log("--- Cancelling… ---")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling…")
        self._dl_thread.cancel()

    def _on_done_ok(self, out_dir: Path) -> None:
        self._log.log(f"--- Done. Files in {out_dir} ---")
        self._reset()

    def _on_done_err(self, msg: str) -> None:
        self._log.log(f"--- Failed: {msg} ---")
        self._reset()

    def _on_done_cancelled(self) -> None:
        self._log.log("--- Cancelled ---")
        self._reset()

    def _reset(self) -> None:
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Download")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancel")
        self._dl_thread = None
