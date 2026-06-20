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

---

## Windows quick start

You do **not** need to install Python, ffmpeg, or yt-dlp yourself — the only
thing to install is **uv**, which sets up everything else.

### 1. Install uv

Open **PowerShell** (press `Win`, type `powershell`, hit Enter) and paste:

```powershell
winget install astral-sh.uv
```

If `winget` isn't available, use this instead:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then **close and reopen** PowerShell so it picks up `uv`.

### 2. Download the app

- Go to **https://github.com/skoomabwoy/media-tools**
- Click the green **Code** button → **Download ZIP**
- **Extract** the ZIP (right-click → Extract All) to a folder you'll remember,
  e.g. `Documents\media-tools`

(If you have Git installed you can instead run
`git clone https://github.com/skoomabwoy/media-tools.git`.)

### 3. Install dependencies (one time)

Open the extracted folder in File Explorer, click the address bar, type `cmd`,
and press Enter — a terminal opens in that folder. Then run:

```sh
uv sync
```

This downloads Python, PyTorch (the right build for your GPU), and everything
else. It's a few GB and can take several minutes the first time.

### 4. Run it

Double-click **`run-win.bat`** in the folder.

The first time you use Separate (or a download/convert that needs ffmpeg), it
downloads the model weights / ffmpeg once, so that run is slower than usual.

> **GPU note:** NVIDIA cards get full acceleration. AMD GPUs on Windows run on
> CPU (PyTorch has no Windows ROCm build) — everything still works, just slower.

---

## Requirements

- **Python 3.11** (uv installs this for you automatically)
- [uv](https://docs.astral.sh/uv/)

`ffmpeg`/`ffprobe` and `yt-dlp` are bundled into the virtualenv, so there's
nothing else to install by hand.

### GPU acceleration

`uv sync` automatically picks the right PyTorch build for your machine:

| | NVIDIA | AMD | No GPU |
|-------------|--------|---------------|--------|
| **Linux**   | CUDA   | ROCm          | CPU    |
| **Windows** | CUDA   | CPU (no ROCm) | CPU    |

Separation runs on the GPU when one is available and falls back to CPU
otherwise (slower, but works everywhere).

## Linux / macOS

```sh
uv sync          # one-time setup
./run-linux.sh   # or: uv run python main.py
```

Separation model weights download automatically on first use and are cached
under `~/.cache/media-tools/`.

## Using the app

On first launch the app detects your GPU(s) and asks which device to use as the
default for separation; you can re-scan anytime with the **↻** button next to
the device dropdown on the Separate tab. The light/dark toggle is in the
bottom-left of the status bar.

## Configuration

Your device and theme choices are stored in `~/.config/media-tools/config.json`
(on Windows: `C:\Users\<you>\.config\media-tools\config.json`). Delete it to
re-run first-time setup.

## Credits

Stem separation is powered by [Music-Source-Separation-Training](https://github.com/ZFTurbo/Music-Source-Separation-Training)
by Roman Solovyev (ZFTurbo), vendored under `vendor/msst/` (MIT, commit
`c0197a0`).
