# Media Tools

A unified PySide6 GUI for a music workflow: download, inspect, convert, and
separate audio into stems.

- **Download** — fetch audio or video from a URL via `yt-dlp`, with format,
  quality, SponsorBlock, and cookie options. Probes the source and recommends
  settings that match it.
- **Separate** — split a track into stems (vocals / instrumental / 4-stem,
  plus dereverb & denoise) using RoFormer models, GPU-accelerated where possible.
- **Convert** — transcode between MP3 / FLAC / WAV / OGG / Opus / AAC / AIFF,
  preserving album art where the target format supports it.
- File info, live CPU / GPU / VRAM meters, and a light/dark theme toggle.

## Requirements

- **Python 3.11**
- [uv](https://docs.astral.sh/uv/)

That's it — `ffmpeg`/`ffprobe` and `yt-dlp` are bundled (installed into the
virtualenv), so you don't need to install them separately.

### GPU acceleration

`uv sync` automatically picks the right PyTorch build for your machine:

| | NVIDIA | AMD | No GPU |
|-----------|--------|------------------|--------|
| **Linux** | CUDA   | ROCm             | CPU    |
| **Windows** | CUDA | CPU (no ROCm)    | CPU    |

Separation runs on the GPU when one is available and falls back to CPU
otherwise (slower, but works everywhere). Note: PyTorch has no ROCm build for
Windows, so an AMD GPU on Windows runs on CPU.

## Setup

```sh
uv sync
```

This creates `.venv/` with PyTorch and all dependencies (a few GB). Separation
model weights download automatically on first use and are cached under
`~/.cache/media-tools/` (Linux/macOS) or `%USERPROFILE%\.cache\media-tools\`
(Windows).

## Run

- **Linux/macOS:** `./run-linux.sh` (or `uv run python main.py`)
- **Windows:** double-click `run-win.bat` (or `uv run python main.py`)

On first launch the app detects your GPU(s) and asks which device to use as the
default for separation; you can re-scan anytime with the **↻** button next to
the device dropdown on the Separate tab. The light/dark toggle is in the
bottom-left of the status bar.

## Configuration

Your device and theme choices are stored in `~/.config/media-tools/config.json`
(`$XDG_CONFIG_HOME` is honored if set). Delete it to re-run first-time setup.

## Credits

Stem separation is powered by [Music-Source-Separation-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training)
by Roman Solovyev (ZFTurbo), vendored under `vendor/msst/` (MIT, commit
`c0197a0`).
