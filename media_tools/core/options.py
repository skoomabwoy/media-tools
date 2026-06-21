from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


CATEGORY_FULL = "Full stem separation"
CATEGORY_VOCALS = "Vocals isolation"
CATEGORY_UTILITY = "Utility (post-processing)"


@dataclass(frozen=True)
class ModelSpec:
    # Shown to the user: task + tier only, no engine name (see `tooltip` for that).
    label: str
    category: str
    kind: str  # "vocals" | "4stem" | "6stem" | "dereverb" | "denoise"
    engine: str = "msst"  # "msst" (roformer) | "demucs"
    tooltip: str = ""  # engine / quality detail for the hover tooltip
    # MSST engine:
    model_type: str = ""
    config_url: str = ""
    ckpt_url: str = ""
    # demucs engine:
    demucs_model: str = ""

    @property
    def config_filename(self) -> str:
        return self.config_url.rsplit("/", 1)[-1]

    @property
    def ckpt_filename(self) -> str:
        return self.ckpt_url.rsplit("/", 1)[-1]


# Curated: one option per task, plus a lighter tier where the speed gap is real.
# The engine (demucs vs roformer) is an implementation detail kept out of labels.
MODELS: list[ModelSpec] = [
    # --- Full stem separation (demucs) ---
    ModelSpec(
        label="Best quality · slow",
        category=CATEGORY_FULL,
        kind="4stem",
        engine="demucs",
        demucs_model="htdemucs_ft",
        tooltip="Demucs htdemucs_ft — fine-tuned 4-stem (vocals/drums/bass/other). "
                "Averages four models, so ~4× slower.",
    ),
    ModelSpec(
        label="Good quality · fast",
        category=CATEGORY_FULL,
        kind="4stem",
        engine="demucs",
        demucs_model="htdemucs",
        tooltip="Demucs htdemucs — 4-stem (vocals/drums/bass/other), single model. Much faster.",
    ),
    ModelSpec(
        label="6 stems (+ guitar & piano) · fast",
        category=CATEGORY_FULL,
        kind="6stem",
        engine="demucs",
        demucs_model="htdemucs_6s",
        tooltip="Demucs htdemucs_6s — adds guitar and piano to the usual four stems.",
    ),

    # --- Vocals isolation (Mel-Band RoFormer via MSST) ---
    ModelSpec(
        label="Best quality · slow",
        category=CATEGORY_VOCALS,
        kind="vocals",
        engine="msst",
        model_type="mel_band_roformer",
        config_url="https://raw.githubusercontent.com/ZFTurbo/Music-Source-Separation-Training/main/configs/KimberleyJensen/config_vocals_mel_band_roformer_kj.yaml",
        ckpt_url="https://huggingface.co/KimberleyJSN/melbandroformer/resolve/main/MelBandRoformer.ckpt",
        tooltip="Mel-Band RoFormer (KimberleyJensen), SDR 10.98. Outputs vocals + instrumental.",
    ),
    ModelSpec(
        label="Good quality · fast",
        category=CATEGORY_VOCALS,
        kind="vocals",
        engine="msst",
        model_type="mel_band_roformer",
        config_url="https://raw.githubusercontent.com/ZFTurbo/Music-Source-Separation-Training/main/configs/viperx/model_mel_band_roformer_ep_3005_sdr_11.4360.yaml",
        ckpt_url="https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/model_mel_band_roformer_ep_3005_sdr_11.4360.ckpt",
        tooltip="Mel-Band RoFormer (viperx). Lighter; outputs vocals + instrumental.",
    ),

    # --- Utility ---
    ModelSpec(
        label="Remove reverb",
        category=CATEGORY_UTILITY,
        kind="dereverb",
        engine="msst",
        model_type="mel_band_roformer",
        config_url="https://huggingface.co/anvuew/dereverb_mel_band_roformer/resolve/main/dereverb_mel_band_roformer_anvuew.yaml",
        ckpt_url="https://huggingface.co/anvuew/dereverb_mel_band_roformer/resolve/main/dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt",
        tooltip="Mel-Band RoFormer dereverb (anvuew).",
    ),
    ModelSpec(
        label="Remove noise",
        category=CATEGORY_UTILITY,
        kind="denoise",
        engine="msst",
        model_type="mel_band_roformer",
        config_url="https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v.1.0.7/model_mel_band_roformer_denoise.yaml",
        ckpt_url="https://github.com/ZFTurbo/Music-Source-Separation-Training/releases/download/v.1.0.7/denoise_mel_band_roformer_aufr33_sdr_27.9959.ckpt",
        tooltip="Mel-Band RoFormer denoise (aufr33).",
    ),
]


def models_by_category() -> dict[str, list[ModelSpec]]:
    """Group MODELS by category, preserving order within each group."""
    out: dict[str, list[ModelSpec]] = {}
    for m in MODELS:
        out.setdefault(m.category, []).append(m)
    return out


OUTPUT_FORMATS = [
    ("wav16", "WAV 16-bit"),
    ("wav24", "WAV 24-bit"),
    ("wav32", "WAV 32-bit float"),
    ("flac16", "FLAC 16-bit"),
    ("flac24", "FLAC 24-bit"),
]


CONVERT_FORMATS = [
    ("mp3", "MP3"),
    ("flac", "FLAC (lossless)"),
    ("wav", "WAV (uncompressed)"),
    ("ogg", "OGG Vorbis"),
    ("opus", "Opus"),
    ("aac", "AAC (.m4a)"),
    ("aiff", "AIFF"),
]

MP3_BITRATES = [
    ("320k", "320 kbps — highest quality"),
    ("256k", "256 kbps"),
    ("192k", "192 kbps"),
    ("128k", "128 kbps"),
    ("64k", "64 kbps"),
]

OPUS_BITRATES = [
    ("256k", "256 kbps — highest quality"),
    ("192k", "192 kbps"),
    ("128k", "128 kbps"),
    ("64k", "64 kbps — speech"),
]

AAC_BITRATES = [
    ("256k", "256 kbps — highest quality"),
    ("192k", "192 kbps"),
    ("128k", "128 kbps"),
    ("96k", "96 kbps"),
]

OGG_QUALITIES = [
    ("10", "Quality 10 — highest"),
    ("7", "Quality 7 — high"),
    ("5", "Quality 5 — medium"),
    ("3", "Quality 3 — low"),
]

WAV_DEPTHS = [
    ("pcm_s16le", "16-bit"),
    ("pcm_s24le", "24-bit"),
    ("pcm_f32le", "32-bit float"),
]

FLAC_DEPTHS = [
    ("16", "16-bit"),
    ("24", "24-bit"),
]

SAMPLE_RATES = [
    ("", "Keep original"),
    ("44100", "44100 Hz (CD)"),
    ("48000", "48000 Hz (DVD / pro)"),
    ("96000", "96000 Hz (high-res)"),
    ("22050", "22050 Hz (low)"),
]


DOWNLOAD_MODES = [
    ("audio", "Audio only"),
    ("video", "Video"),
]

DOWNLOAD_AUDIO_FORMATS = [
    ("mp3", "MP3"),
    ("flac", "FLAC (lossless)"),
    ("opus", "Opus"),
    ("m4a", "M4A / AAC"),
    ("wav", "WAV"),
    ("vorbis", "OGG Vorbis"),
    ("best", "Best available (no re-encode)"),
]

# Quality options per audio format — kbps for lossy codecs, ignored for lossless / best.
DOWNLOAD_QUALITY_BY_FORMAT: dict[str, list[tuple[str, str]]] = {
    "mp3":    [("320k", "320 kbps"), ("256k", "256 kbps"), ("192k", "192 kbps"), ("128k", "128 kbps"), ("96k", "96 kbps")],
    "opus":   [("256k", "256 kbps"), ("192k", "192 kbps"), ("128k", "128 kbps"), ("96k", "96 kbps"),  ("64k", "64 kbps (speech)")],
    "m4a":    [("256k", "256 kbps"), ("192k", "192 kbps"), ("128k", "128 kbps"), ("96k", "96 kbps")],
    "vorbis": [("10", "Quality 10 — highest"), ("7", "Quality 7"), ("5", "Quality 5"), ("3", "Quality 3 — low")],
    # Lossless or pass-through — no quality picker needed.
    "flac": [],
    "wav":  [],
    "best": [],
}

DOWNLOAD_VIDEO_CONTAINERS = [
    ("mp4", "MP4 (most compatible)"),
    ("mkv", "MKV (supports more codecs/subs)"),
    ("webm", "WebM"),
]

DOWNLOAD_VIDEO_RESOLUTIONS = [
    ("", "Best available"),
    ("2160", "4K / 2160p"),
    ("1440", "1440p"),
    ("1080", "1080p"),
    ("720", "720p"),
    ("480", "480p"),
    ("360", "360p"),
]

DOWNLOAD_SPONSORBLOCK = [
    ("", "Off"),
    ("mark", "Mark segments as chapters"),
    ("remove", "Remove segments"),
]

DOWNLOAD_BROWSERS = [
    ("", "No cookies"),
    ("firefox", "Firefox"),
    ("chrome", "Chrome"),
    ("chromium", "Chromium"),
    ("brave", "Brave"),
    ("edge", "Edge"),
    ("vivaldi", "Vivaldi"),
    ("opera", "Opera"),
]


@dataclass
class DownloadOpts:
    url: str
    output_dir: Path
    mode: str = "audio"               # one of DOWNLOAD_MODES keys
    audio_format: str = "mp3"         # DOWNLOAD_AUDIO_FORMATS
    audio_quality: str = ""            # DOWNLOAD_QUALITY_BY_FORMAT[audio_format] entry, or "" if N/A
    video_container: str = "mp4"      # DOWNLOAD_VIDEO_CONTAINERS
    video_max_height: str = ""        # DOWNLOAD_VIDEO_RESOLUTIONS, "" = best
    embed_thumbnail: bool = False
    embed_metadata: bool = False
    sponsorblock_mode: str = ""       # DOWNLOAD_SPONSORBLOCK
    cookies_browser: str = ""         # DOWNLOAD_BROWSERS


@dataclass
class ConvertOpts:
    input_file: Path
    output_file: Path
    format: str                # one of CONVERT_FORMATS keys
    quality: str = ""          # bitrate / depth / vorbis-quality, depending on format
    sample_rate: str = ""      # "" = keep original


# Optional extra-passes setting. Off by default — a single pass of the chosen
# model already gives an excellent result; higher levels average more passes for
# a small gain at a large time cost (diminishing returns).
REFINEMENT_LEVELS = [
    ("none", "None (recommended)"),
    ("extra", "Extra"),
    ("max", "Maximum"),
]


@dataclass
class SeparateOpts:
    input_file: Path
    output_dir: Path
    model: ModelSpec
    output_format: str = "flac24"
    refinement: str = "none"  # one of REFINEMENT_LEVELS keys
    device: str = "auto"
