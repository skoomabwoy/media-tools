"""Recommend yt-dlp output defaults that fit a probed source URL.

Given a URLInfo (codec + bitrate of the best available streams), suggest the
audio format, audio bitrate, and video resolution that match the source.
"""

from __future__ import annotations

from media_tools.backend.url_probe import URLInfo
from media_tools.core.options import (
    DOWNLOAD_AUDIO_FORMATS,
    DOWNLOAD_QUALITY_BY_FORMAT,
    DOWNLOAD_VIDEO_RESOLUTIONS,
)


# yt-dlp codec strings → our DOWNLOAD_AUDIO_FORMATS keys.
_AUDIO_CODEC_MAP = {
    "mp4a": "m4a",
    "aac":  "m4a",
    "opus": "opus",
    "vorbis": "vorbis",
    "mp3":  "mp3",
    "flac": "flac",
    "alac": "flac",
}


def suggest_audio_format(info: URLInfo) -> str:
    """Pick the format that re-encodes the least vs. source codec.

    Falls back to 'best' (no re-encode) when source codec is unknown.
    """
    codec = (info.best_audio_codec or "").lower()
    for key, target in _AUDIO_CODEC_MAP.items():
        if codec.startswith(key):
            return target
    return "best"


def suggest_audio_quality(info: URLInfo, fmt: str) -> str:
    """Pick the bitrate/quality that wastes the least space vs. source.

    Rule: smallest option whose numeric value is >= source bitrate.
    If all options are below the source, return the highest available.
    For lossless / pass-through formats (no quality options), returns "".
    """
    options = DOWNLOAD_QUALITY_BY_FORMAT.get(fmt, [])
    if not options:
        return ""
    src = info.best_audio_abr_kbps or 0
    if src <= 0:
        return options[0][0]  # default to highest

    def parse_kbps(key: str) -> float:
        # Examples: "320k" → 320, "192k" → 192, "10" → 10 (Vorbis quality, not kbps).
        k = key.rstrip("kK")
        try:
            return float(k)
        except ValueError:
            return 0.0

    is_kbps = options[0][0].endswith(("k", "K"))
    if is_kbps:
        candidates = sorted(options, key=lambda o: parse_kbps(o[0]))
        for key, _label in candidates:
            if parse_kbps(key) >= src:
                return key
        return candidates[-1][0]
    # Vorbis quality: 10=best, 3=low. Not directly comparable to kbps; keep default best.
    return options[0][0]


def suggest_video_resolution(info: URLInfo) -> str:
    """Pick the smallest preset >= source height; fall back to 'best available'."""
    src = info.best_video_height or 0
    if src <= 0:
        return ""  # best available
    # DOWNLOAD_VIDEO_RESOLUTIONS items: ("", "Best available"), ("2160", "..."), ...
    numeric = [(int(k), k) for k, _ in DOWNLOAD_VIDEO_RESOLUTIONS if k]
    numeric.sort()
    for value, key in numeric:
        if value >= src:
            return key
    return ""  # source is larger than any preset → use best available


