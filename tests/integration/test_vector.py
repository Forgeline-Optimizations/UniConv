"""SVG <-> raster and SVG -> PDF (plan 0.2 step 16)."""

import gzip
import threading
import time

import pikepdf
import pytest
from PIL import Image

from uniconv.config import AppConfig, PathsConfig
from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job, JobRunner
from uniconv.core.workspace import Workspace

pytestmark = pytest.mark.needs_resvg

_PNG_1PX_RED = Image.new("RGB", (8, 8), "red")


def _run(runner, src, target, out_dir):
    [result] = runner.run(Job("image", target, [src], out_dir), CancelToken())
    return result


def _runner_with(tmp_path, registry, **image_opts):
    cfg = AppConfig(paths=PathsConfig(work_dir=tmp_path / "work2"),
                    defaults={"image": image_opts})
    return JobRunner(registry, Workspace(cfg.paths.work_dir), cfg)


def test_small_svg_is_scaled_up_to_svg_min_px(runner, make_sample, out_dir):
    result = _run(runner, make_sample("svg"), "png", out_dir)
    assert result.status == "done", result.error
    with Image.open(result.output) as img:
        assert img.size == (512, 256)
        assert img.getpixel((5, 128))[0] > 200  # the gradient starts red


def test_huge_svg_is_refused_without_crashing(runner, tmp_path, out_dir):
    """Review #2: resvg aborts on a 200000x200000 canvas; we must refuse it first."""
    src = tmp_path / "bom.svg"
    src.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200000" height="200000">'
                   '<rect width="10" height="10"/></svg>', encoding="utf-8")

    [result] = runner.run(Job("image", "png", [src], out_dir), CancelToken())

    assert result.status == "failed"
    assert "te groot" in result.error
    assert list(out_dir.iterdir()) == []          # nothing half-written reaches the user
    assert list(runner.workspace.root.iterdir()) == []  # job directory cleaned up


def test_text_with_unknown_font_is_never_lost_silently(runner, tmp_path, out_dir):
    """Review #9: resvg either falls back to an installed font (Windows/macOS) or drops the
    text and says so on stderr; then the user must get a warning naming the font."""
    src = tmp_path / "font.svg"
    src.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60">'
                   '<text x="5" y="45" font-size="40" font-family="NoSuchFont123">Hoi</text>'
                   "</svg>", encoding="utf-8")
    result = _run(runner, src, "png", out_dir)
    assert result.status == "done", result.error
    with Image.open(result.output) as img:
        drawn = img.convert("RGBA").getbbox() is not None
    assert drawn or any("NoSuchFont123" in w for w in result.warnings)


def test_broken_svg_fails_readably(runner, tmp_path, out_dir):
    src = tmp_path / "kapot.svg"
    src.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect',
                   encoding="utf-8")
    result = _run(runner, src, "png", out_dir)
    assert result.status == "failed"
    assert result.error and not result.error.startswith("Onverwachte fout")


def test_svgz_to_png(runner, make_sample, tmp_path, out_dir):
    src = tmp_path / "logo.svgz"
    src.write_bytes(gzip.compress(make_sample("svg").read_bytes()))
    result = _run(runner, src, "png", out_dir)
    assert result.status == "done", result.error


@pytest.mark.needs_typst
def test_svg_to_pdf_is_vector(runner, make_sample, out_dir):
    result = _run(runner, make_sample("svg"), "pdf", out_dir)
    assert result.status == "done", result.error
    with pikepdf.open(result.output) as pdf:
        page = pdf.pages[0]
        assert len(page.get_images()) == 0  # drawn as paths, not as a picture
        box = [float(v) for v in page.mediabox]
    assert box[2] - box[0] == pytest.approx(180, abs=1)  # 240 px = 180 pt


@pytest.mark.needs_typst
def test_svgz_to_pdf(runner, make_sample, tmp_path, out_dir):
    """Review #26: Typst does not read .svgz itself."""
    src = tmp_path / "logo.svgz"
    src.write_bytes(gzip.compress(make_sample("svg").read_bytes()))
    result = _run(runner, src, "pdf", out_dir)
    assert result.status == "done", result.error


@pytest.mark.needs_typst
def test_svg_with_linked_image_to_pdf(runner, tmp_path, out_dir):
    """Review #26: Typst fails on linked images; fall back to a raster PDF with a warning."""
    _PNG_1PX_RED.save(tmp_path / "foto.png")
    src = tmp_path / "met-foto.svg"
    src.write_text('<svg xmlns="http://www.w3.org/2000/svg" '
                   'xmlns:xlink="http://www.w3.org/1999/xlink" width="100" height="50">'
                   '<image href="foto.png" xlink:href="foto.png" width="100" height="50"/></svg>',
                   encoding="utf-8")
    result = _run(runner, src, "pdf", out_dir)
    assert result.status == "done", result.error
    with pikepdf.open(result.output) as pdf:
        images = len(pdf.pages[0].get_images())
    fell_back = any("losse afbeeldingsbestanden" in w for w in result.warnings)
    assert images >= 1  # the photo is in the PDF either way
    assert fell_back or images == 1


@pytest.mark.needs_typst
def test_generic_font_warns_for_pdf(runner, tmp_path, out_dir):
    """Review #10."""
    src = tmp_path / "generiek.svg"
    src.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40">'
                   '<text x="2" y="30" font-family="sans-serif">Hoi</text></svg>',
                   encoding="utf-8")
    result = _run(runner, src, "pdf", out_dir)
    assert result.status == "done", result.error
    assert any("schreefletter" in w for w in result.warnings)


def test_logo_png_to_svg(runner, tmp_path, out_dir):
    src = tmp_path / "logo.png"
    img = Image.new("RGB", (120, 80), "white")
    img.paste((20, 90, 200), (20, 20, 100, 60))
    img.save(src)
    result = _run(runner, src, "svg", out_dir)
    assert result.status == "done", result.error
    text = result.output.read_text(encoding="utf-8")
    assert "<svg" in text and "<path" in text


def test_big_photo_is_downscaled_before_tracing(registry, tmp_path, out_dir):
    """Review #3: tracing time grows much faster than image size."""
    src = tmp_path / "foto.jpg"
    Image.linear_gradient("L").resize((2000, 2000)).convert("RGB").save(src)  # 4 MP
    runner = _runner_with(tmp_path, registry, trace_max_megapixels=0.05)
    result = _run(runner, src, "svg", out_dir)
    assert result.status == "done", result.error
    assert any("verkleind" in w for w in result.warnings)


def test_cancelling_a_slow_trace_stops_within_a_second(registry, tmp_path, out_dir):
    src = tmp_path / "ruis.png"
    Image.effect_noise((1000, 1000), 120).convert("RGB").save(src)  # worst case for tracing
    runner = _runner_with(tmp_path, registry, trace_max_megapixels=1.0,
                          trace_filter_speckle=0)
    cancel = CancelToken()
    threading.Timer(1.5, cancel.cancel).start()
    start = time.monotonic()
    [result] = runner.run(Job("image", "svg", [src], out_dir), cancel)
    assert result.status == "cancelled"
    assert time.monotonic() - start < 1.5 + 1.0
    assert list(out_dir.iterdir()) == []
