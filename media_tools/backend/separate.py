from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add vendored MSST to sys.path so its internal `from utils.*` imports work.
_MSST_ROOT = Path(__file__).resolve().parents[2] / "vendor" / "msst"
if str(_MSST_ROOT) not in sys.path:
    sys.path.insert(0, str(_MSST_ROOT))

from media_tools.core.cancel import CancelToken
from media_tools.core.options import SeparateOpts
from media_tools.core.text import LineSplitter, LogFn
from media_tools.core.weights import ensure_model


_FORMAT_TO_FLAGS: dict[str, dict] = {
    "wav16": {"pcm_type": "PCM_16"},
    "wav24": {"pcm_type": "PCM_24"},
    "wav32": {"pcm_type": "FLOAT"},
    "flac16": {"flac_file": True, "pcm_type": "PCM_16"},
    "flac24": {"flac_file": True, "pcm_type": "PCM_24"},
}


class _LineWriter(io.TextIOBase):
    """Adapt LineSplitter to the file-like interface that redirect_stdout expects."""

    def __init__(self, log: LogFn) -> None:
        super().__init__()
        self._splitter = LineSplitter(log)

    def write(self, s: str) -> int:
        self._splitter.feed(s)
        return len(s)

    def flush(self) -> None:
        self._splitter.flush()


def _build_msst_args(
    opts: SeparateOpts,
    config_path: Path,
    ckpt_path: Path,
    input_folder: Path,
    output_folder: Path,
) -> dict:
    args: dict = {
        "model_type": opts.model.model_type,
        "config_path": str(config_path),
        "start_check_point": str(ckpt_path),
        "input_folder": str(input_folder),
        "store_dir": str(output_folder),
    }
    args.update(_FORMAT_TO_FLAGS[opts.output_format])

    if opts.model.supports_instrumental and opts.extract_instrumental:
        args["extract_instrumental"] = True
    if opts.use_tta:
        args["use_tta"] = True
    if opts.bigshifts > 1:
        args["bigshifts"] = opts.bigshifts
    if opts.device == "cpu":
        args["force_cpu"] = True
    elif opts.device.startswith("cuda:"):
        args["device_ids"] = [int(opts.device.split(":", 1)[1])]
    return args


def run_separation(opts: SeparateOpts, log: LogFn, cancel: CancelToken) -> Path:
    """Run a separation end-to-end. Returns the output directory the stems were written into.

    Cancellation takes effect during the weight-download phase and just before
    inference starts; a torch inference run already in progress cannot be
    interrupted in-thread and will finish on its own.
    """
    if not opts.input_file.exists():
        raise FileNotFoundError(opts.input_file)
    opts.output_dir.mkdir(parents=True, exist_ok=True)

    log(f"Model: {opts.model.label}")
    config_path, ckpt_path = ensure_model(opts.model, log, cancel)

    # MSST expects an input folder, not a file. Stage the file in a tempdir.
    with tempfile.TemporaryDirectory(prefix="media-tools-") as tmp:
        tmpdir = Path(tmp)
        staged_input = tmpdir / "input"
        staged_output = tmpdir / "output"
        staged_input.mkdir()
        staged_output.mkdir()

        staged_file = staged_input / opts.input_file.name
        os.symlink(opts.input_file.resolve(), staged_file)

        msst_args = _build_msst_args(opts, config_path, ckpt_path, staged_input, staged_output)
        log("Invoking MSST inference with args: " + ", ".join(f"{k}={v}" for k, v in msst_args.items()))

        # Last chance to bail before the uninterruptible inference call.
        cancel.raise_if_cancelled()

        # Import lazily so module import isn't slowed down by torch boot.
        from inference import proc_folder  # type: ignore

        writer = _LineWriter(log)
        with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
            proc_folder(msst_args)
        writer.flush()

        # Move staged outputs into the user's chosen output dir.
        final_dir = opts.output_dir / opts.input_file.stem
        final_dir.mkdir(parents=True, exist_ok=True)
        moved: list[Path] = []
        for src in staged_output.rglob("*"):
            if src.is_file():
                dst = final_dir / src.name
                shutil.move(str(src), str(dst))
                moved.append(dst)

        log(f"Wrote {len(moved)} files to {final_dir}")
        for p in moved:
            log(f"  {p.name}")
        return final_dir
