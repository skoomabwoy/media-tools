"""Cheap, non-blocking CPU/GPU/VRAM sampling for the status bar.

GPU support is picked once at import, in order:
- AMD (Linux): read sysfs directly — gpu_busy_percent / mem_info_vram_{used,total}
  under /sys/class/drm/cardN/device. The dGPU is the card with the most VRAM.
- NVIDIA (Linux/Windows): poll `nvidia-smi` on a background thread so the UI
  timer never blocks on the subprocess.
- Otherwise: no GPU meter (CPU only). The UI shows "GPU —".
"""

from __future__ import annotations

import glob
import subprocess
import threading
import time
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


# --- AMD sysfs backend (Linux) ---

def _detect_amd() -> tuple[Path | None, str | None]:
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
    name: str | None = None
    try:
        for line in (dev / "uevent").read_text().splitlines():
            if line.startswith("PCI_ID="):
                name = "AMD GPU " + line.split("=", 1)[1]
                break
    except OSError:
        pass
    return dev, name


def _sample_amd(dev: Path) -> tuple[float | None, float | None, float | None]:
    busy = _read_int(dev / "gpu_busy_percent")
    used = _read_int(dev / "mem_info_vram_used")
    total = _read_int(dev / "mem_info_vram_total")
    return (
        float(busy) if busy is not None else None,
        used / (1024**3) if used is not None else None,
        total / (1024**3) if total is not None else None,
    )


# --- NVIDIA nvidia-smi backend (Linux/Windows) ---

_NVIDIA_QUERY = "utilization.gpu,memory.used,memory.total,name"


def _query_nvidia() -> tuple[float, float, float, str] | None:
    """One nvidia-smi sample: (gpu%, used_gb, total_gb, name) for the first GPU."""
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={_NVIDIA_QUERY}", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    parts = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")]
    try:
        # nvidia-smi reports memory in MiB; convert to GiB to match the AMD path.
        return float(parts[0]), float(parts[1]) / 1024, float(parts[2]) / 1024, parts[3]
    except (ValueError, IndexError):
        return None


class _NvidiaMonitor:
    """Polls nvidia-smi on a daemon thread, exposing the latest cached sample."""

    def __init__(self, name: str) -> None:
        self.name = "NVIDIA " + name if not name.startswith("NVIDIA") else name
        self._latest: tuple[float | None, float | None, float | None] = (None, None, None)
        self._lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self) -> None:
        while True:
            sample = _query_nvidia()
            if sample is not None:
                with self._lock:
                    self._latest = sample[:3]
            time.sleep(1.5)

    def sample(self) -> tuple[float | None, float | None, float | None]:
        with self._lock:
            return self._latest


def _detect_backend() -> tuple[str | None, object, str | None]:
    dev, name = _detect_amd()
    if dev is not None:
        return "amd", dev, name
    probe = _query_nvidia()
    if probe is not None:
        monitor = _NvidiaMonitor(probe[3])
        return "nvidia", monitor, monitor.name
    return None, None, None


_KIND, _GPU, _GPU_NAME = _detect_backend()


def sample() -> SysSample:
    cpu = psutil.cpu_percent(interval=None)

    gpu_pct: float | None = None
    vram_used: float | None = None
    vram_total: float | None = None
    if _KIND == "amd":
        gpu_pct, vram_used, vram_total = _sample_amd(_GPU)  # type: ignore[arg-type]
    elif _KIND == "nvidia":
        gpu_pct, vram_used, vram_total = _GPU.sample()  # type: ignore[union-attr]

    return SysSample(
        cpu_percent=cpu,
        gpu_percent=gpu_pct,
        vram_used_gb=vram_used,
        vram_total_gb=vram_total,
        gpu_name=_GPU_NAME,
    )
