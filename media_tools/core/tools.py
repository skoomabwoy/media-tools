"""Locating external command-line tools (ffmpeg/ffprobe/yt-dlp) with friendly,
platform-aware errors when they're missing."""

from __future__ import annotations

import shutil
import sys


def _install_hint(tool: str) -> str:
    # ffmpeg and ffprobe ship together as "FFmpeg".
    is_ffmpeg = tool in ("ffmpeg", "ffprobe")
    if sys.platform.startswith("win"):
        if is_ffmpeg:
            return ("Install FFmpeg (e.g. `winget install Gyan.FFmpeg`) and make sure "
                    "ffmpeg.exe is on your PATH.")
        return "Install yt-dlp (e.g. `winget install yt-dlp.yt-dlp`)."
    if sys.platform == "darwin":
        return f"Install it with `brew install {'ffmpeg' if is_ffmpeg else tool}`."
    # Linux / other
    pkg = "ffmpeg" if is_ffmpeg else tool
    return f"Install it with your package manager, e.g. `sudo pacman -S {pkg}` or `sudo apt install {pkg}`."


def require_tool(tool: str) -> str:
    """Return the resolved path to `tool`, or raise a friendly error if missing.

    A system install is preferred; for ffmpeg/ffprobe we fall back to the bundled
    `static-ffmpeg` binaries (fetched on first use and added to PATH, which child
    processes such as yt-dlp then inherit).
    """
    path = shutil.which(tool)
    if path:
        return path
    if tool in ("ffmpeg", "ffprobe"):
        try:
            import static_ffmpeg
            static_ffmpeg.add_paths()  # downloads on first run, prepends to PATH
        except Exception:
            pass
        path = shutil.which(tool)
        if path:
            return path
    raise RuntimeError(f"{tool} was not found on PATH. {_install_hint(tool)}")
