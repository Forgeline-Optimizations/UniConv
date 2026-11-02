"""Audio/video family: ffmpeg with one well-chosen codec per target container."""

import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from uniconv.core.converter import ConversionContext, Converter, Format
from uniconv.core.errors import ConversionError, ToolMissingError
from uniconv.core.tools import find_tool, run_tool


class MediaOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    audio_bitrate: str = Field("192k", pattern=r"^\d{2,3}k$")
    video_crf: int = Field(23, ge=0, le=51)
    video_preset: Literal["ultrafast", "veryfast", "fast", "medium", "slow"] = "veryfast"
    webm_crf: int = Field(32, ge=0, le=63)


_AUDIO = {"mp3", "wav", "flac", "ogg", "m4a", "opus"}
# yuv420p needs even width and height; phone videos are often rotated or cropped (review #2)
_EVEN = ["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2"]


@dataclass(frozen=True)
class _Probe:
    duration: float | None
    has_video: bool
    has_audio: bool


class MediaConverter(Converter):
    family = "media"
    family_label = "Audio/video"
    Options = MediaOptions
    formats = (
        Format("mp3", "MP3", (".mp3",), ("audio/mpeg",)),
        Format("wav", "WAV", (".wav",), ("audio/x-wav", "audio/wav")),
        Format("flac", "FLAC", (".flac",), ("audio/x-flac", "audio/flac")),
        Format("ogg", "Ogg Vorbis", (".ogg",), ("audio/ogg",)),
        Format("m4a", "M4A", (".m4a",), ("audio/mp4", "audio/x-m4a")),
        # Opus lives in an Ogg container: filetype says audio/ogg, the extension decides.
        Format("opus", "Opus", (".opus",), ("audio/opus", "audio/ogg")),
        Format("mp4", "MP4", (".mp4",), ("video/mp4",)),
        Format("mkv", "MKV", (".mkv",), ("video/x-matroska",)),
        Format("webm", "WebM", (".webm",), ("video/webm",)),
        Format("mov", "QuickTime", (".mov",), ("video/quicktime",)),
    )

    def available(self) -> bool:
        return find_tool("ffmpeg") is not None and find_tool("ffprobe") is not None

    def targets(self, source: str) -> list[str]:
        keys = super().targets(source)
        # an audio file has no picture to put in a video container
        return keys if source not in _AUDIO else [k for k in keys if k in _AUDIO]

    def expected_losses(self, source: str, target: str) -> list[str]:
        out = []
        if source not in _AUDIO and target in _AUDIO:
            out.append("Alleen het geluid wordt bewaard.")
        if source not in _AUDIO and target not in _AUDIO:
            out.append("Ondertitels en extra audiosporen worden niet meegenomen.")
        if source in {"wav", "flac"} and target in {"mp3", "m4a", "ogg", "opus"}:
            out.append("Lossless naar lossy: kleiner bestand, minder detail.")
        return out

    def convert(self, ctx: ConversionContext) -> None:
        ffmpeg = find_tool("ffmpeg")
        if ffmpeg is None:
            raise ToolMissingError("ffmpeg is niet gevonden; herinstalleer UniConv")
        probe = _probe(ctx)
        target = ctx.target.key
        if target in _AUDIO and not probe.has_audio:
            raise ConversionError("Dit bestand bevat geen geluid om te converteren")
        if target not in _AUDIO and not (probe.has_video or probe.has_audio):
            raise ConversionError("Dit bestand bevat geen beeld of geluid")
        if target not in _AUDIO and not probe.has_video:
            ctx.warn("Het bestand bevat geen beeld; alleen het geluid is geconverteerd.")

        cmd = [str(ffmpeg), "-hide_banner", "-nostdin", "-y",
               "-i", str(ctx.input_path),
               "-map_metadata", "0",
               "-sn", "-dn",  # drop subtitle/data streams: image subs break MP4 (review #6)
               *_codec_args(target, ctx.options, probe.has_video),  # type: ignore[arg-type]
               "-progress", "pipe:1", "-nostats",
               str(ctx.output_path)]
        duration = probe.duration  # None keeps the progress bar indeterminate

        def on_line(line: str) -> None:
            if duration and line.startswith("out_time_us="):  # position in microseconds
                us = line.split("=", 1)[1].strip()
                if us.isdigit():
                    ctx.on_progress(min(int(us) / 1e6 / duration, 0.99))

        run_tool(cmd, timeout_s=ctx.timeout_s, cancel=ctx.cancel, on_stdout_line=on_line)


def _probe(ctx: ConversionContext) -> _Probe:
    ffprobe = find_tool("ffprobe")
    if ffprobe is None:
        raise ToolMissingError("ffprobe is niet gevonden; herinstalleer UniConv")
    out: list[str] = []
    try:
        run_tool([str(ffprobe), "-v", "error", "-show_entries",
                  "format=duration:stream=codec_type:stream_disposition=attached_pic",
                  "-of", "json", "--", str(ctx.input_path)],
                 timeout_s=min(ctx.timeout_s, 60), cancel=ctx.cancel, on_stdout_line=out.append)
    except ConversionError as exc:
        raise ConversionError(f"Kan {ctx.input_path.name} niet lezen: {exc}") from exc
    try:
        info = json.loads("\n".join(out) or "{}")
    except json.JSONDecodeError:
        info = {}
    streams = info.get("streams", [])
    # album art in an MP3/M4A is a "video" stream with attached_pic=1: not real video
    video = any(s.get("codec_type") == "video"
                and not s.get("disposition", {}).get("attached_pic") for s in streams)
    audio = any(s.get("codec_type") == "audio" for s in streams)
    try:
        duration = float(info.get("format", {}).get("duration", ""))
    except ValueError:
        duration = None
    return _Probe(duration if duration and duration > 0 else None, video, audio)


def _codec_args(target: str, o: MediaOptions, has_video: bool) -> list[str]:
    # 8-bit 4:2:0 plays in QuickTime and browsers, also when the source is 10-bit HDR
    x264 = [*_EVEN, "-c:v", "libx264", "-preset", o.video_preset, "-crf", str(o.video_crf),
            "-pix_fmt", "yuv420p"] if has_video else ["-vn"]
    aac = ["-c:a", "aac", "-b:a", o.audio_bitrate]
    match target:
        case "mp4" | "mov":
            return [*x264, *aac, "-movflags", "+faststart"]
        case "mkv":
            return [*x264, *aac]
        case "webm":  # VP9 defaults are slower than realtime; these settings are (review #12)
            vp9 = [*_EVEN, "-c:v", "libvpx-vp9", "-crf", str(o.webm_crf), "-b:v", "0",
                   "-deadline", "good", "-cpu-used", "4", "-row-mt", "1",
                   "-pix_fmt", "yuv420p"] if has_video else ["-vn"]
            return [*vp9, "-c:a", "libopus", "-b:a", o.audio_bitrate]
        # -vn on audio targets also keeps MP3 album art from becoming a video stream
        case "mp3":
            return ["-vn", "-c:a", "libmp3lame", "-b:a", o.audio_bitrate]
        case "m4a":
            return ["-vn", *aac]
        case "ogg":
            return ["-vn", "-c:a", "libvorbis", "-b:a", o.audio_bitrate]
        case "opus":
            return ["-vn", "-c:a", "libopus", "-b:a", o.audio_bitrate]
        case "flac":
            return ["-vn", "-c:a", "flac"]
        case "wav":
            return ["-vn", "-c:a", "pcm_s16le"]
    raise ConversionError(f"Onbekend mediaformaat: {target}")
