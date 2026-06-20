from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass

from media_tools.core.text import LogFn, format_duration


@dataclass
class URLInfo:
    url: str
    title: str | None
    uploader: str | None
    duration_sec: float | None
    best_video_height: int | None
    best_video_fps: float | None
    best_video_codec: str | None
    best_audio_abr_kbps: float | None
    best_audio_codec: str | None
    best_audio_sample_rate: int | None
    has_video: bool
    has_audio: bool

    def as_rows(self) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        rows.append(("Title", self.title or "—"))
        rows.append(("Uploader", self.uploader or "—"))
        rows.append(("Duration", format_duration(self.duration_sec)))

        if self.has_video and self.best_video_height:
            fps = f"@{self.best_video_fps:.0f}fps" if self.best_video_fps else ""
            codec = self.best_video_codec or "?"
            rows.append(("Best video", f"{self.best_video_height}p {fps} {codec}".strip()))
        else:
            rows.append(("Best video", "— (audio only)"))

        if self.has_audio and self.best_audio_abr_kbps:
            codec = self.best_audio_codec or "?"
            sr = f", {self.best_audio_sample_rate} Hz" if self.best_audio_sample_rate else ""
            rows.append(("Best audio", f"{self.best_audio_abr_kbps:.0f} kbps {codec}{sr}"))
        else:
            rows.append(("Best audio", "—"))
        return rows


def _pick_best_video(formats: list[dict]) -> dict | None:
    vids = [
        f for f in formats
        if f.get("vcodec") and f["vcodec"] != "none" and f.get("height")
    ]
    if not vids:
        return None
    return max(vids, key=lambda f: (f.get("height") or 0, f.get("fps") or 0, f.get("tbr") or 0))


def _pick_best_audio(formats: list[dict]) -> dict | None:
    auds = [
        f for f in formats
        if f.get("acodec") and f["acodec"] != "none" and (not f.get("vcodec") or f["vcodec"] == "none")
    ]
    if not auds:
        # No audio-only stream; fall back to whichever has the highest abr.
        auds = [f for f in formats if f.get("abr")]
    if not auds:
        return None
    return max(auds, key=lambda f: f.get("abr") or 0)


def probe_url(url: str, log: LogFn) -> URLInfo:
    if not url.strip():
        raise ValueError("URL is empty.")
    if shutil.which("yt-dlp") is None:
        raise RuntimeError("yt-dlp not found on PATH. Install it with `pacman -S yt-dlp`.")

    log(f"Probing {url} …")
    result = subprocess.run(
        ["yt-dlp", "-J", "--no-playlist", "--skip-download", url],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Surface only the first stderr line, the rest is noise.
        msg = (result.stderr or "").strip().splitlines()
        raise RuntimeError(msg[0] if msg else f"yt-dlp exited with code {result.returncode}")

    data = json.loads(result.stdout)
    formats = data.get("formats") or []

    bv = _pick_best_video(formats)
    ba = _pick_best_audio(formats)

    return URLInfo(
        url=url,
        title=data.get("title"),
        uploader=data.get("uploader") or data.get("channel"),
        duration_sec=data.get("duration"),
        best_video_height=(bv or {}).get("height"),
        best_video_fps=(bv or {}).get("fps"),
        best_video_codec=(bv or {}).get("vcodec"),
        best_audio_abr_kbps=(ba or {}).get("abr"),
        best_audio_codec=(ba or {}).get("acodec"),
        best_audio_sample_rate=(ba or {}).get("asr"),
        has_video=bv is not None,
        has_audio=ba is not None,
    )
