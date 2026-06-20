# Media Tools

A unified PySide6 GUI for a music workflow: download, inspect, convert, and
separate audio into stems.

- **Download** — fetch audio or video from a URL via `yt-dlp`, with format,
  quality, SponsorBlock, and cookie options. Probes the source and recommends
  settings that match it.
- **Separate** — split a track into stems (vocals / instrumental / 4-stem,
  plus dereverb & denoise) using RoFormer models, GPU-accelerated.
- **Convert** — transcode between MP3 / FLAC / WAV / OGG / Opus / AAC / AIFF,
  preserving album art where the target format supports it.
- File info + live CPU / GPU / VRAM meters throughout.

## Requirements

This release targets **Linux with an AMD GPU (ROCm)**.

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- An AMD GPU with a working ROCm stack (torch is pinned to the ROCm 6.3 wheels)
- `ffmpeg` / `ffprobe` and `yt-dlp` available on `PATH`
  (e.g. `sudo pacman -S ffmpeg yt-dlp`)

## Setup

```sh
uv sync
```

This creates `.venv/` with PyTorch (ROCm) and all dependencies. The separation
model weights download automatically on first use and are cached under
`~/.cache/media-tools/`.

## Run

```sh
./run.sh
```

or `uv run python main.py`.

To add it to your application menu, edit the paths in `media-tools.desktop` if
the repo isn't at the default location, then:

```sh
cp media-tools.desktop ~/.local/share/applications/
```

On first launch the app detects your GPU(s) and asks which device to use as the
default for separation; you can change it anytime via the **Compute device**
button in the bottom-left.

## Configuration

Your device choice is stored in `$XDG_CONFIG_HOME/media-tools/config.json`
(usually `~/.config/media-tools/config.json`).

## Credits

Stem separation is powered by [Music-Source-Separation-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training)
by Roman Solovyev (ZFTurbo), vendored under `vendor/msst/` (MIT, commit
`c0197a0`).
