from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from media_tools.core.cancel import Cancelled, CancelToken
from media_tools.core.options import DownloadOpts
from media_tools.core.text import LogFn
from media_tools.core.tools import require_tool


# Containers that can carry embedded thumbnails (yt-dlp/ffmpeg constraint).
_THUMBNAIL_AUDIO_FORMATS = {"mp3", "flac", "opus", "m4a"}
_THUMBNAIL_VIDEO_CONTAINERS = {"mp4", "mkv"}


def _build_yt_dlp_args(opts: DownloadOpts) -> list[str]:
    args: list[str] = [
        # Invoke yt-dlp as a module via the current interpreter, so the bundled
        # dependency is used regardless of whether the venv is on PATH.
        sys.executable, "-m", "yt_dlp",
        "--no-playlist",
        "--newline",  # one line per progress update, easier to stream
        "-P", str(opts.output_dir),
    ]

    if opts.mode == "audio":
        args += ["--extract-audio", "--audio-format", opts.audio_format]
        # For lossless or pass-through formats yt-dlp ignores --audio-quality,
        # so we only emit it when there's something to set.
        if opts.audio_quality:
            args += ["--audio-quality", opts.audio_quality]
    else:
        if opts.video_max_height:
            h = opts.video_max_height
            args += ["-f", f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"]
        args += ["--merge-output-format", opts.video_container]

    if opts.embed_thumbnail:
        if opts.mode == "audio" and opts.audio_format in _THUMBNAIL_AUDIO_FORMATS:
            args.append("--embed-thumbnail")
        elif opts.mode == "video" and opts.video_container in _THUMBNAIL_VIDEO_CONTAINERS:
            args.append("--embed-thumbnail")
    if opts.embed_metadata:
        args += ["--embed-metadata", "--embed-chapters"]

    if opts.sponsorblock_mode == "mark":
        args += ["--sponsorblock-mark", "default"]
    elif opts.sponsorblock_mode == "remove":
        args += ["--sponsorblock-remove", "default"]

    if opts.cookies_browser:
        args += ["--cookies-from-browser", opts.cookies_browser]

    args.append(opts.url)
    return args


def run_download(opts: DownloadOpts, log: LogFn, cancel: CancelToken) -> Path:
    if not opts.url.strip():
        raise ValueError("URL is empty.")
    # yt-dlp needs ffmpeg for extraction/merge/embedding; resolving it here also
    # primes PATH (via the bundled fallback) so the yt-dlp child process finds it.
    require_tool("ffmpeg")
    opts.output_dir.mkdir(parents=True, exist_ok=True)

    argv = _build_yt_dlp_args(opts)
    log("Invoking yt-dlp: " + " ".join(argv))

    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    cancel.bind_process(proc)
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    rc = proc.wait()
    if cancel.cancelled:
        raise Cancelled()
    if rc != 0:
        raise RuntimeError(f"yt-dlp exited with code {rc}")
    log(f"Saved to: {opts.output_dir}")
    return opts.output_dir
