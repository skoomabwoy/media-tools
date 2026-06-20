"""Cheap, non-blocking CPU/GPU/VRAM sampling for the status bar.

For the AMD GPU side we read sysfs files directly:
- /sys/class/drm/cardN/device/gpu_busy_percent
- /sys/class/drm/cardN/device/mem_info_vram_used
- /sys/class/drm/cardN/device/mem_info_vram_total

The dGPU is auto-detected as the card with the most VRAM (the iGPU on a 9800X3D
exposes only ~2 GB while the 9070 XT has ~16 GB).
"""

from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass
class SysSample:
    cpu_percent: float
    gpu_percent: float | None
    vram_used_gb: float | None
    vram_total_gb: float | None
    gpu_name: str | None


def _read_int(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _detect_dgpu_path() -> tuple[Path | None, str | None]:
    candidates: list[tuple[int, Path]] = []
    for card in sorted(glob.glob("/sys/class/drm/card*")):
        dev = Path(card) / "device"
        total = _read_int(dev / "mem_info_vram_total")
        if total is None:
            continue
        candidates.append((total, dev))
    if not candidates:
        return None, None
    candidates.sort(reverse=True)
    dev = candidates[0][1]
    # Best-effort label from uevent.
    name: str | None = None
    try:
        for line in (dev / "uevent").read_text().splitlines():
            if line.startswith("PCI_ID="):
                name = "AMD GPU " + line.split("=", 1)[1]
                break
    except OSError:
        pass
    return dev, name


_DGPU_PATH, _DGPU_NAME = _detect_dgpu_path()


def sample() -> SysSample:
    cpu = psutil.cpu_percent(interval=None)

    gpu_pct: float | None = None
    vram_used: float | None = None
    vram_total: float | None = None
    if _DGPU_PATH is not None:
        busy = _read_int(_DGPU_PATH / "gpu_busy_percent")
        used = _read_int(_DGPU_PATH / "mem_info_vram_used")
        total = _read_int(_DGPU_PATH / "mem_info_vram_total")
        if busy is not None:
            gpu_pct = float(busy)
        if used is not None:
            vram_used = used / (1024**3)
        if total is not None:
            vram_total = total / (1024**3)

    return SysSample(
        cpu_percent=cpu,
        gpu_percent=gpu_pct,
        vram_used_gb=vram_used,
        vram_total_gb=vram_total,
        gpu_name=_DGPU_NAME,
    )
