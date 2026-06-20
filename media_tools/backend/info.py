from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from media_tools.core.text import format_duration
from media_tools.core.tools import require_tool


@dataclass
class MediaInfo:
    path: Path
    container: str
    codec: str
    sample_rate: int | None
    bit_depth: int | None
    channels: int | None
    channel_layout: str | None
    duration_sec: float | None
    bitrate_kbps: int | None
    size_bytes: int

    def as_rows(self) -> list[tuple[str, str]]:
        def fmt_size(b: int) -> str:
            for unit in ("B", "KB", "MB", "GB"):
                if b < 1024:
                    return f"{b:.1f} {unit}" if unit != "B" else f"{b} B"
                b /= 1024.0
            return f"{b:.1f} TB"

        return [
            ("File", str(self.path)),
            ("Container", self.container or "—"),
            ("Codec", self.codec or "—"),
            ("Sample rate", f"{self.sample_rate} Hz" if self.sample_rate else "—"),
            ("Bit depth", f"{self.bit_depth}-bit" if self.bit_depth else "—"),
            ("Channels", f"{self.channels} ({self.channel_layout})" if self.channels else "—"),
            ("Duration", format_duration(self.duration_sec)),
            ("Bitrate", f"{self.bitrate_kbps} kbps" if self.bitrate_kbps else "—"),
            ("Size", fmt_size(self.size_bytes)),
        ]


# Lossy codecs decode to float/int PCM, but that decode width is not a
# meaningful "bit depth" of the source, so we don't report one for them.
_LOSSY_CODECS = {
    "mp3", "aac", "vorbis", "opus", "ac3", "eac3", "wmav1", "wmav2", "wmapro",
}


def _bit_depth_from_codec(sample_fmt: str | None, codec: str) -> int | None:
    if not sample_fmt or codec in _LOSSY_CODECS:
        return None
    mapping = {
        "u8": 8, "u8p": 8,
        "s16": 16, "s16p": 16,
        "s24": 24, "s24p": 24,
        "s32": 32, "s32p": 32,
        "flt": 32, "fltp": 32,
        "dbl": 64, "dblp": 64,
    }
    return mapping.get(sample_fmt)


def probe(path: Path) -> MediaInfo:
    """Run ffprobe on `path` and return a parsed MediaInfo."""
    require_tool("ffprobe")
    if not path.exists():
        raise FileNotFoundError(path)

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    fmt = data.get("format", {})
    streams = data.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})

    codec = audio.get("codec_name", "")
    sample_rate = int(audio["sample_rate"]) if audio.get("sample_rate") else None
    channels = audio.get("channels")
    bit_depth = _bit_depth_from_codec(audio.get("sample_fmt"), codec)
    if codec in ("pcm_s24le", "pcm_s24be"):
        bit_depth = 24
    if codec in ("pcm_s32le", "pcm_s32be"):
        bit_depth = 32
    if audio.get("bits_per_raw_sample"):
        try:
            bit_depth = int(audio["bits_per_raw_sample"])
        except (TypeError, ValueError):
            pass

    duration = None
    if fmt.get("duration"):
        try:
            duration = float(fmt["duration"])
        except (TypeError, ValueError):
            pass

    bitrate = None
    if fmt.get("bit_rate"):
        try:
            bitrate = int(int(fmt["bit_rate"]) / 1000)
        except (TypeError, ValueError):
            pass

    return MediaInfo(
        path=path,
        container=fmt.get("format_name", ""),
        codec=codec,
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        channels=channels,
        channel_layout=audio.get("channel_layout"),
        duration_sec=duration,
        bitrate_kbps=bitrate,
        size_bytes=int(fmt.get("size", path.stat().st_size)),
    )
