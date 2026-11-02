import json
import subprocess
import threading
import time

import pytest

from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job
from uniconv.core.tools import find_tool

from ..conftest import make_media

pytestmark = pytest.mark.needs_ffmpeg


def _streams(path) -> list[dict]:
    out = subprocess.run(
        [str(find_tool("ffprobe")), "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout
    return json.loads(out)["streams"]


def test_required_encoders_present():
    """Step 26 audit: every encoder in the codec table exists in the pinned build."""
    out = subprocess.run([str(find_tool("ffmpeg")), "-hide_banner", "-encoders"],
                         check=True, capture_output=True, text=True, timeout=30).stdout
    for enc in ("libx264", "libvpx-vp9", "libopus", "libmp3lame", "libvorbis", "aac",
                "flac", "pcm_s16le"):
        assert f" {enc} " in out, f"encoder {enc} missing"


def test_odd_sized_video_to_mp4(runner, tmp_path, out_dir):
    """Review #2: x264 + yuv420p refuses odd dimensions without the scale filter."""
    src = make_media(tmp_path / "odd.mkv", "mkv", size="63x47",
                     extra=("-c:v", "ffv1", "-pix_fmt", "yuv444p"))
    [result] = runner.run(Job("media", "mp4", [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    [video] = [s for s in _streams(result.output) if s["codec_type"] == "video"]
    assert (video["width"], video["height"]) == (62, 46)
    assert video["codec_name"] == "h264"


def test_mkv_with_subtitles_to_mp4(runner, tmp_path, out_dir):
    """Review #6: subtitle streams are dropped instead of breaking the MP4 mux."""
    srt = tmp_path / "subs.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:00,900\nHallo\n", encoding="utf-8")
    src = make_media(tmp_path / "subs.mkv", "mkv",
                     inputs=("-i", str(srt)),
                     extra=("-map", "0", "-map", "1", "-map", "2", "-c:s", "srt"))
    assert any(s["codec_type"] == "subtitle" for s in _streams(src))
    [result] = runner.run(Job("media", "mp4", [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    assert {s["codec_type"] for s in _streams(result.output)} == {"video", "audio"}


def test_mp4_to_mp3_has_no_video_stream(runner, make_sample, out_dir, registry):
    conv = registry.find("media", "mp4", "mp3")
    assert "Alleen het geluid wordt bewaard." in conv.expected_losses("mp4", "mp3")
    [result] = runner.run(Job("media", "mp3", [make_sample("mp4")], out_dir), CancelToken())
    assert result.status == "done", result.error
    assert [s["codec_type"] for s in _streams(result.output)] == ["audio"]


def test_audio_sources_offer_only_audio_targets(registry):
    assert set(registry.targets("media", "mp3")) == {"wav", "flac", "ogg", "m4a", "opus"}


def test_video_without_audio_to_mp3_fails_readably(runner, tmp_path, out_dir):
    src = make_media(tmp_path / "silent.mp4", "mp4", audio=False)
    [result] = runner.run(Job("media", "mp3", [src], out_dir), CancelToken())
    assert result.status == "failed"
    assert "geen geluid" in result.error


def test_progress_rises(runner, tmp_path, out_dir):
    src = make_media(tmp_path / "long.mp4", "mp4", seconds=8, size="320x240")
    seen: list[float] = []
    [result] = runner.run(Job("media", "webm", [src], out_dir), CancelToken(),
                          on_progress=lambda _i, p: seen.append(p))
    assert result.status == "done", result.error
    partial = [p for p in seen if 0 < p < 1]
    assert partial, f"no intermediate progress reported: {seen}"
    assert partial == sorted(partial)
    assert seen[-1] == 1.0


def test_cancel_stops_within_a_second(runner, workspace, tmp_path, out_dir):
    src = make_media(tmp_path / "long.mp4", "mp4", seconds=20, size="640x480",
                     extra=("-preset", "ultrafast"))
    cancel = CancelToken()
    timer = threading.Timer(0.8, cancel.cancel)
    timer.start()
    start = time.monotonic()
    [result] = runner.run(Job("media", "webm", [src], out_dir), cancel)
    elapsed = time.monotonic() - start
    assert result.status == "cancelled"
    assert elapsed < 0.8 + 1.0
    assert list(out_dir.iterdir()) == []
    assert list(workspace.root.iterdir()) == []


def test_corrupt_media_fails_readably(runner, tmp_path, out_dir):
    src = tmp_path / "kapot.mp3"
    src.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 128)
    [result] = runner.run(Job("media", "wav", [src], out_dir), CancelToken())
    assert result.status == "failed"
    assert not result.error.startswith("Onverwachte fout")
