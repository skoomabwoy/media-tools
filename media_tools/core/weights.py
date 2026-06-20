from __future__ import annotations

from pathlib import Path

import requests

from .cancel import Cancelled, CancelToken
from .options import ModelSpec
from .text import LogFn


CACHE_DIR = Path.home() / ".cache" / "media-tools" / "weights"


def _download(url: str, dest: Path, log: LogFn, cancel: CancelToken | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"Downloading {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        last_pct = -1
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if cancel is not None and cancel.cancelled:
                    # Leave the .part file behind; a later run resumes from scratch.
                    raise Cancelled()
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 // total
                    if pct != last_pct and pct % 5 == 0:
                        log(f"  {pct}% ({done / 1e6:.1f} / {total / 1e6:.1f} MB)")
                        last_pct = pct
    tmp.rename(dest)
    log(f"Saved to {dest}")


def ensure_model(model: ModelSpec, log: LogFn, cancel: CancelToken | None = None) -> tuple[Path, Path]:
    """Download config + checkpoint if not already cached. Returns (config_path, ckpt_path)."""
    model_dir = CACHE_DIR / model.model_type
    config_path = model_dir / model.config_filename
    ckpt_path = model_dir / model.ckpt_filename

    if not config_path.exists():
        _download(model.config_url, config_path, log, cancel)
    else:
        log(f"Using cached config: {config_path.name}")

    if not ckpt_path.exists():
        _download(model.ckpt_url, ckpt_path, log, cancel)
    else:
        log(f"Using cached weights: {ckpt_path.name}")

    return config_path, ckpt_path
