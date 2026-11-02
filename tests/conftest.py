"""Shared fixtures. Samples are generated per test; the repo holds no binary test files."""

from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from uniconv.config import AppConfig, PathsConfig
from uniconv.core.jobs import JobRunner
from uniconv.core.registry import Registry, build_default_registry
from uniconv.core.workspace import Workspace

_PIL_FORMAT = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "gif": "GIF", "bmp": "BMP",
               "tiff": "TIFF", "heic": "HEIF"}


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


@pytest.fixture
def make_sample(tmp_path: Path) -> Callable[..., Path]:
    samples = tmp_path / "samples"
    samples.mkdir()

    def _make(key: str, name: str = "sample", **kw) -> Path:
        ext = ".tif" if key == "tiff" else f".{key}"
        path = samples / f"{name}{ext}"
        if key in _PIL_FORMAT:
            return make_image(path, key, **kw)
        raise KeyError(f"no sample generator for {key!r}")

    return _make
