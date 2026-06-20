"""Pick a sensible default output format for stem separation, given input info."""

from __future__ import annotations

from media_tools.backend.info import MediaInfo


_WAV_CONTAINERS = ("wav", "riff", "aiff")
_FLAC_CONTAINERS = ("flac",)


def suggest_separation_format(info: MediaInfo) -> str:
    """Return an OUTPUT_FORMATS key (wav16/wav24/wav32/flac16/flac24) that best
    matches the input. For lossy inputs, default to flac24 (sensible lossless
    container with no upscaling claim).
    """
    container = (info.container or "").lower()
    depth = info.bit_depth or 0
    is_wav = any(c in container for c in _WAV_CONTAINERS)
    is_flac = any(c in container for c in _FLAC_CONTAINERS)

    if is_flac:
        return "flac24" if depth >= 24 else "flac16"
    if is_wav:
        if depth >= 32:
            return "wav32"
        if depth >= 24:
            return "wav24"
        return "wav16"
    # Lossy input — no meaningful source bit depth. Use lossless 24-bit FLAC.
    return "flac24"
