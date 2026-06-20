"""Compute-device discovery and the option list shown in the UI.

Device names come from torch, but torch is heavy to import, so we query it in a
subprocess (once, then cache the result in the local config) rather than pulling
it into the GUI process at startup.
"""

from __future__ import annotations

import json
import subprocess
import sys

from media_tools.core.cancel import CancelToken


AUTO = ("auto", "Auto (best available)")
CPU = ("cpu", "CPU")

_DETECT_SCRIPT = (
    "import torch, json;"
    "print(json.dumps([torch.cuda.get_device_name(i)"
    " for i in range(torch.cuda.device_count())]))"
)


def detect_cuda_devices(
    timeout: float = 180.0, cancel: CancelToken | None = None
) -> list[str] | None:
    """Return CUDA/ROCm device names indexed by device id.

    ``[]`` means "torch ran and found no GPU"; ``None`` means detection itself
    failed (torch missing, crash, timeout) or was cancelled, and the caller
    should retry later rather than cache the empty result.
    """
    try:
        proc = subprocess.Popen(
            [sys.executable, "-c", _DETECT_SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return None
    if cancel is not None:
        cancel.bind_process(proc)
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return None
    if proc.returncode != 0:
        return None
    try:
        names = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None
    return names if isinstance(names, list) else None


def device_options(cuda_names: list[str]) -> list[tuple[str, str]]:
    """Build (key, label) options: Auto, one entry per detected GPU, then CPU."""
    options = [AUTO]
    for i, name in enumerate(cuda_names):
        options.append((f"cuda:{i}", f"GPU {i} — {name}"))
    options.append(CPU)
    return options
