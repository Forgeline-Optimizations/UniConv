"""Shared fixtures. Samples are generated per test; the repo holds no binary test files."""

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from uniconv.config import AppConfig, PathsConfig
from uniconv.core.jobs import JobRunner
from uniconv.core.registry import Registry, build_default_registry
from uniconv.core.tools import find_tool
from uniconv.core.workspace import Workspace

RECORDS = [
    {"id": 1, "naam": "Zoë", "adres": {"stad": "Delft", "postcode": "2611"}},
    {"id": 2, "naam": "Jürgen", "adres": {"stad": "Gent", "postcode": "9000"}},
]
_TEXT_SAMPLES = {
    "json": json.dumps(RECORDS, ensure_ascii=False, indent=2),
    "yaml": (
        "- id: 1\n  naam: Zoë\n  adres: {stad: Delft}\n"
        "- id: 2\n  naam: Jürgen\n  adres: {stad: Gent}\n"
    ),
    "toml": '[[rows]]\nid = 1\nnaam = "Zoë"\n\n[[rows]]\nid = 2\nnaam = "Jürgen"\n',
    "xml": (
        "<?xml version='1.0' encoding='utf-8'?>\n"
        "<root><row><id>1</id><naam>Zoë</naam></row>"
        "<row><id>2</id><naam>Jürgen</naam></row></root>\n"
    ),
    "csv": "id,naam,stad\n1,Zoë,Delft\n2,Jürgen,Gent\n",
    "md": "# Titel\n\nTekst met *nadruk* en een [link](https://example.org).\n",
    "html": (
        "<!DOCTYPE html><html><head><title>T</title></head><body><h1>Titel</h1>"
        "<p>Tekst met <em>nadruk</em>.</p></body></html>\n"
    ),
    "tex": (
        r"\documentclass{article}" "\n" r"\begin{document}" "\n"
        r"\section{Titel}" "\nTekst.\n" r"\end{document}" "\n"
    ),
    "rtf": r"{\rtf1\ansi{\b Titel}\par Tekst met nadruk.\par}" "\n",
}
_PANDOC_SAMPLES = {"docx", "odt", "epub"}
_PIL_FORMAT = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "gif": "GIF", "bmp": "BMP",
               "tiff": "TIFF", "heic": "HEIF"}


def pytest_collection_modifyitems(config, items):
    missing = {name: find_tool(name) is None for name in ("pandoc", "ffmpeg")}
    for item in items:
        for name, absent in missing.items():
            if absent and item.get_closest_marker(f"needs_{name}"):
                item.add_marker(pytest.mark.skip(reason=f"{name} not found (fetch_binaries.py)"))


@pytest.fixture
def cfg(tmp_path: Path) -> AppConfig:
    return AppConfig(paths=PathsConfig(work_dir=tmp_path / "work"))


@pytest.fixture
def registry() -> Registry:
    return build_default_registry()


@pytest.fixture
def workspace(cfg: AppConfig) -> Workspace:
    return Workspace(cfg.paths.work_dir)


@pytest.fixture
def runner(registry: Registry, workspace: Workspace, cfg: AppConfig) -> JobRunner:
    return JobRunner(registry, workspace, cfg)


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    d = tmp_path / "out"
    d.mkdir()
    return d


def make_image(path: Path, key: str, size: tuple[int, int] = (32, 24),
               mode: str = "RGBA") -> Path:
    img = Image.new("RGBA", size)
    for x in range(size[0]):  # a gradient, so lossy encoders have something to chew on
        for y in range(size[1]):
            img.putpixel((x, y), (x * 8 % 256, y * 10 % 256, 128, 255 if x % 4 else 128))
    if key in ("jpg", "bmp") or mode == "RGB":
        img = img.convert("RGB")
    elif key == "gif":
        img = img.convert("RGB").quantize(colors=64)
    elif mode != "RGBA":
        img = img.convert(mode)
    img.save(path, format=_PIL_FORMAT[key])
    return path


def run_pandoc(*args: str) -> None:
    subprocess.run([str(find_tool("pandoc")), *args], check=True, timeout=60,
                   capture_output=True)


_MEDIA_AUDIO = {"mp3", "wav", "flac", "ogg", "m4a", "opus"}
_MEDIA_VIDEO = {"mp4", "mkv", "webm", "mov"}


def make_media(path: Path, key: str, seconds: float = 1, size: str = "64x64",
               extra: tuple[str, ...] = (), inputs: tuple[str, ...] = (),
               audio: bool = True, video: bool = True) -> Path:
    """lavfi test sources; ffmpeg picks its default codecs for the container."""
    cmd = [str(find_tool("ffmpeg")), "-hide_banner", "-nostdin", "-y", "-v", "error"]
    if key in _MEDIA_VIDEO and video:
        cmd += ["-f", "lavfi", "-i", f"testsrc=duration={seconds}:size={size}:rate=10"]
    if audio or key in _MEDIA_AUDIO:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += inputs  # extra inputs (e.g. subtitles) must precede all output options
    if key in _MEDIA_VIDEO and video and "-c:v" not in extra:
        cmd += ["-pix_fmt", "yuv420p"]
    if key == "webm":
        cmd += ["-deadline", "realtime", "-cpu-used", "8"]
    cmd += [*extra, str(path)]
    subprocess.run(cmd, check=True, timeout=120, capture_output=True)
    return path


@pytest.fixture
def make_sample(tmp_path: Path) -> Callable[..., Path]:
    samples = tmp_path / "samples"
    samples.mkdir()

    def _make(key: str, name: str = "sample", **kw) -> Path:
        ext = ".tif" if key == "tiff" else f".{key}"
        path = samples / f"{name}{ext}"
        if key in _PIL_FORMAT:
            return make_image(path, key, **kw)
        if key in _TEXT_SAMPLES:
            text = kw.get("text", _TEXT_SAMPLES[key])
            path.write_text(text, encoding=kw.get("encoding", "utf-8"), newline="")
            return path
        if key == "xlsx":
            pd.DataFrame(RECORDS).drop(columns="adres").to_excel(path, index=False)
            return path
        if key in _PANDOC_SAMPLES:
            md = samples / f"{name}-src.md"
            md.write_text(_TEXT_SAMPLES["md"], encoding="utf-8")
            run_pandoc(str(md), "-o", str(path), "--metadata", "title=Voorbeeld")
            return path
        if key in _MEDIA_AUDIO | _MEDIA_VIDEO:
            return make_media(path, key, **kw)
        raise KeyError(f"no sample generator for {key!r}")

    return _make
