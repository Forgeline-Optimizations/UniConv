"""Shared fixtures. Samples are generated per test; the repo holds no binary test files."""

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from uniconv.config import AppConfig, PathsConfig
from uniconv.core.apps import find_app
from uniconv.core.jobs import JobRunner
from uniconv.core.registry import Registry, build_default_registry, default_providers
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
    "svg": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="120">'
        '<defs><linearGradient id="g"><stop offset="0" stop-color="#e33"/>'
        '<stop offset="1" stop-color="#33e"/></linearGradient></defs>'
        '<rect width="240" height="120" fill="url(#g)"/>'
        '<text x="20" y="75" font-size="40" font-family="Arial, sans-serif" fill="white">'
        "UniConv</text></svg>\n"
    ),
}
_PANDOC_SAMPLES = {"docx", "odt", "epub", "pptx"}
# made by LibreOffice from a generated modern file: (filter, made from)
_SOFFICE_SAMPLES = {"doc": ("doc", "docx"), "xls": ("xls", "xlsx"), "ppt": ("ppt", "pptx"),
                    "ods": ("ods", "xlsx"), "odp": ("odp", "pptx")}
_PIL_FORMAT = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "gif": "GIF", "bmp": "BMP",
               "tiff": "TIFF", "heic": "HEIF"}


def pytest_collection_modifyitems(config, items):
    missing = {name: find_tool(name) is None for name in ("pandoc", "ffmpeg", "typst", "resvg")}
    missing |= {name: find_app(name) is None for name in ("libreoffice", "browser")}
    for item in items:
        for name, absent in missing.items():
            if absent and item.get_closest_marker(f"needs_{name}"):
                item.add_marker(pytest.mark.skip(reason=f"{name} not found"))


@pytest.fixture
def cfg(tmp_path: Path) -> AppConfig:
    return AppConfig(paths=PathsConfig(work_dir=tmp_path / "work"))


@pytest.fixture
def registry() -> Registry:
    return build_default_registry()


@pytest.fixture
def registry_without() -> Callable[..., Registry]:
    """A default registry in which the given provider classes are registered as unavailable,
    so fallback routes are testable on machines that do have LibreOffice or Chrome."""

    def _make(*classes: type) -> Registry:
        reg = Registry()
        for conv in default_providers():
            if isinstance(conv, classes):
                conv.available = lambda: False  # type: ignore[method-assign]
            reg.register(conv)
        return reg

    return _make


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


def run_soffice(src: Path, fmt: str, outdir: Path) -> Path:
    """Convert with the user's LibreOffice, own profile, like converters/office.py."""
    profile = (outdir / "lo-profile").resolve().as_uri()
    subprocess.run([str(find_app("libreoffice")), f"-env:UserInstallation={profile}",
                    "--headless", "--norestore", "--convert-to", fmt, "--outdir", str(outdir),
                    str(src)], check=True, timeout=180, capture_output=True)
    out = outdir / f"{src.stem}.{fmt}"
    assert out.is_file(), f"LibreOffice made no {fmt}"
    return out


def make_protected_docx(path: Path, password: str = "geheim") -> Path:
    """A password-protected .docx is an OLE container, not a zip (review #13)."""
    import msoffcrypto.format.ooxml

    plain = path.with_name(f"{path.stem}-plain.docx")
    md = path.with_name(f"{path.stem}-src.md")
    md.write_text(_TEXT_SAMPLES["md"], encoding="utf-8")
    run_pandoc(str(md), "-o", str(plain))
    with plain.open("rb") as src, path.open("wb") as out:
        msoffcrypto.format.ooxml.OOXMLFile(src).encrypt(password, out)
    return path


def run_pandoc(*args: str) -> None:
    subprocess.run([str(find_tool("pandoc")), *args], check=True, timeout=60,
                   capture_output=True)


_MODEL3D = {"stl", "obj", "ply", "off", "glb", "gltf", "3mf"}


def make_model(path: Path, key: str) -> Path:
    """A scene of a box and a sphere, exported with trimesh in the test process."""
    import trimesh

    scene = trimesh.Scene([trimesh.creation.box(),
                           trimesh.creation.icosphere().apply_translation([3, 0, 0])])
    if key in {"stl", "ply", "off"}:  # single-mesh formats
        data = scene.to_mesh().export(file_type=key)
    elif key == "gltf":
        (data,) = trimesh.exchange.gltf.export_gltf(scene, embed_buffers=True).values()
    elif key == "obj":
        data = scene.export(file_type="obj", include_texture=False)
    else:
        data = scene.export(file_type=key)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return path


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
        if key in _SOFFICE_SAMPLES:
            fmt, base = _SOFFICE_SAMPLES[key]
            modern = _make(base, name=f"{name}-modern")
            made = run_soffice(modern, fmt, samples / f"lo-{key}")
            return made.replace(path)
        if key in _MEDIA_AUDIO | _MEDIA_VIDEO:
            return make_media(path, key, **kw)
        if key in _MODEL3D:
            return make_model(path, key)
        raise KeyError(f"no sample generator for {key!r}")

    return _make
