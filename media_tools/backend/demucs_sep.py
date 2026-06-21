"""Stem separation via Demucs (htdemucs family).

Used for the full-stem (4- and 6-stem) options. Roformer models go through the
MSST path in `separate.py`; both share the same SeparateOpts contract and output
layout (`<output_dir>/<input stem>/<stem>.<ext>`).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import numpy as np
import soundfile as sf

from media_tools.core.cancel import CancelToken
from media_tools.core.options import SeparateOpts
from media_tools.core.text import LineWriter, LogFn
from media_tools.core.tools import require_tool
from media_tools.core.weights import CACHE_DIR


# output_format key -> (soundfile container extension, subtype)
_FORMAT_TO_SF: dict[str, tuple[str, str]] = {
    "wav16": ("wav", "PCM_16"),
    "wav24": ("wav", "PCM_24"),
    "wav32": ("wav", "FLOAT"),
    "flac16": ("flac", "PCM_16"),
    "flac24": ("flac", "PCM_24"),
}

# Optional extra passes -> demucs `shifts` (random shift-and-average count).
_REFINEMENT_SHIFTS = {"none": 1, "extra": 2, "max": 5}


def _torch_device(device: str) -> str:
    import torch

    if device == "cpu":
        return "cpu"
    if torch.cuda.is_available():
        return device if device.startswith("cuda:") else "cuda"
    return "cpu"


def run_demucs(opts: SeparateOpts, log: LogFn, cancel: CancelToken) -> Path:
    """Separate `opts.input_file` with a demucs model. Returns the output dir.

    Like the roformer path, an in-progress inference can't be interrupted; cancel
    takes effect at the boundaries (before model load / before inference).
    """
    require_tool("ffmpeg")  # demucs decodes audio via ffmpeg; primes PATH too

    import torch
    from demucs.apply import apply_model
    from demucs.audio import AudioFile
    from demucs.pretrained import get_model

    # Keep all weights under our single cache dir (demucs downloads via torch.hub).
    demucs_cache = CACHE_DIR / "demucs"
    demucs_cache.mkdir(parents=True, exist_ok=True)
    torch.hub.set_dir(str(demucs_cache))

    name = opts.model.demucs_model
    device = _torch_device(opts.device)
    shifts = _REFINEMENT_SHIFTS.get(opts.refinement, 1)

    log(f"Loading demucs model '{name}' on {device} (weights download on first use)…")
    writer = LineWriter(log)
    with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
        model = get_model(name)
        model.to(device)
        model.eval()
    writer.flush()

    cancel.raise_if_cancelled()

    # Decode at the model's native rate/channels, then normalize as demucs does.
    wav = AudioFile(opts.input_file).read(
        streams=0, samplerate=model.samplerate, channels=model.audio_channels
    )
    ref = wav.mean(0)
    std = ref.std() + 1e-8
    wav = (wav - ref.mean()) / std

    cancel.raise_if_cancelled()
    log(f"Separating into {len(model.sources)} stems (shifts={shifts})…")
    writer = LineWriter(log)
    with torch.no_grad(), contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
        sources = apply_model(
            model, wav[None], device=device, shifts=shifts,
            split=True, overlap=0.25, progress=True,
        )[0]
    writer.flush()
    sources = sources * std + ref.mean()

    final_dir = opts.output_dir / opts.input_file.stem
    final_dir.mkdir(parents=True, exist_ok=True)
    container, subtype = _FORMAT_TO_SF[opts.output_format]

    written: list[Path] = []
    for stem_name, source in zip(model.sources, sources):
        data = source.cpu().numpy().T  # -> [samples, channels]
        # Rescale (don't hard-clip) if a stem peaks above full scale for PCM output.
        if subtype != "FLOAT":
            peak = float(np.abs(data).max())
            if peak > 1.0:
                data = data / peak
        out = final_dir / f"{stem_name}.{container}"
        sf.write(str(out), data, model.samplerate, subtype=subtype)
        written.append(out)

    log(f"Wrote {len(written)} files to {final_dir}")
    for p in written:
        log(f"  {p.name}")
    return final_dir
