from __future__ import annotations

import subprocess
from pathlib import Path

from media_tools.core.cancel import Cancelled, CancelToken
from media_tools.core.options import ConvertOpts
from media_tools.core.text import LineSplitter, LogFn


def _codec_and_quality_flags(opts: ConvertOpts) -> list[str]:
    fmt = opts.format
    q = opts.quality
    if fmt == "mp3":
        return ["-c:a", "libmp3lame", "-b:a", q or "320k"]
    if fmt == "flac":
        # ffmpeg's flac encoder only accepts s16 or s32 sample formats; there is
        # no valid "s24" token. 24-bit FLAC is produced with the s32 format plus
        # an explicit bits_per_raw_sample so the stream is tagged 24-bit rather
        # than 32-bit.
        depth = q or "16"
        if depth == "16":
            return ["-c:a", "flac", "-sample_fmt", "s16"]
        return ["-c:a", "flac", "-sample_fmt", "s32", "-bits_per_raw_sample", "24"]
    if fmt == "wav":
        return ["-c:a", q or "pcm_s16le"]
    if fmt == "ogg":
        return ["-c:a", "libvorbis", "-q:a", q or "5"]
    if fmt == "opus":
        return ["-c:a", "libopus", "-b:a", q or "192k"]
    if fmt == "aac":
        return ["-c:a", "aac", "-b:a", q or "192k"]
    if fmt == "aiff":
        return ["-c:a", "pcm_s16be"]
    raise ValueError(f"Unsupported format: {fmt}")


# Containers whose encoders can carry an embedded cover image. For these we keep
# attached album art; everything else drops all non-audio streams.
_COVER_ART_FORMATS = {"mp3", "flac", "aac"}


def _video_mapping_flags(fmt: str) -> list[str]:
    if fmt not in _COVER_ART_FORMATS:
        return ["-vn"]  # audio only — drop video and cover art
    # Keep audio plus any attached cover picture, but drop real video streams so
    # converting an actual video to audio doesn't copy its video track. ffmpeg's
    # lowercase "v" includes attached pics; uppercase "V" is real video only, so
    # mapping 0:v minus 0:V leaves just the cover. The "?" keeps each map optional.
    return ["-map", "0:a", "-map", "0:v?", "-map", "-0:V?", "-c:v", "copy"]


def _build_ffmpeg_args(opts: ConvertOpts) -> list[str]:
    args: list[str] = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-i", str(opts.input_file),
    ]
    args += _video_mapping_flags(opts.format)
    args += _codec_and_quality_flags(opts)
    if opts.sample_rate:
        args += ["-ar", opts.sample_rate]
    args.append(str(opts.output_file))
    return args


def run_conversion(opts: ConvertOpts, log: LogFn, cancel: CancelToken) -> Path:
    if not opts.input_file.exists():
        raise FileNotFoundError(opts.input_file)
    if opts.output_file.resolve() == opts.input_file.resolve():
        # ffmpeg -y would truncate the source before reading it.
        raise ValueError("Output file is the same as the input file; choose a different name or folder.")
    opts.output_file.parent.mkdir(parents=True, exist_ok=True)

    argv = _build_ffmpeg_args(opts)
    log("Invoking ffmpeg: " + " ".join(argv))

    proc = subprocess.Popen(
        argv,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    cancel.bind_process(proc)
    assert proc.stderr is not None
    splitter = LineSplitter(log)
    while True:
        chunk = proc.stderr.read(256)
        if not chunk:
            break
        splitter.feed(chunk)
    splitter.flush()
    rc = proc.wait()
    if cancel.cancelled:
        raise Cancelled()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exited with code {rc}")
    log(f"Wrote {opts.output_file}")
    return opts.output_file
