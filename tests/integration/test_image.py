import struct

import numpy as np
import pytest
from PIL import Image, ImageCms

from uniconv.config import AppConfig, PathsConfig
from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job, JobRunner


def test_png_alpha_to_jpg_is_flattened_on_configured_background(registry, runner, tmp_path,
                                                                out_dir):
    src = tmp_path / "logo.png"
    Image.new("RGBA", (16, 16), (255, 0, 0, 0)).save(src)  # fully transparent red

    conv = registry.find("image", "png", "jpg")
    assert any("transparantie" in w.lower() for w in conv.expected_losses("png", "jpg"))

    [result] = runner.run(Job("image", "jpg", [src], out_dir), CancelToken())

    assert result.status == "done"
    with Image.open(result.output) as out:
        assert out.format == "JPEG"
        assert out.mode == "RGB"
        assert min(out.getpixel((0, 0))) > 245  # white (#FFFFFF), allowing for JPEG noise


def test_flatten_background_comes_from_config(registry, workspace, tmp_path, out_dir):
    src = tmp_path / "logo.png"
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(src)
    cfg = AppConfig(paths=PathsConfig(work_dir=tmp_path / "work"),
                    defaults={"image": {"flatten_background": "#000000"}})
    [result] = JobRunner(registry, workspace, cfg).run(
        Job("image", "bmp", [src], out_dir), CancelToken())
    with Image.open(result.output) as out:
        assert out.getpixel((0, 0)) == (0, 0, 0)


def test_cmyk_jpeg_to_png(runner, tmp_path, out_dir):
    """Review #4: PNG cannot store CMYK, and a CMYK profile must not travel along."""
    src = tmp_path / "print.jpg"
    Image.new("CMYK", (20, 20), (0, 255, 255, 0)).save(src, icc_profile=b"fake-cmyk-profile")
    [result] = runner.run(Job("image", "png", [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    with Image.open(result.output) as out:
        assert out.mode == "RGB"
        assert "icc_profile" not in out.info
        r, g, b = out.getpixel((10, 10))
        assert r > 200 and g < 60 and b < 60  # cyan-free, magenta+yellow = red


def test_16bit_tiff_to_jpg_keeps_tones(runner, tmp_path, out_dir):
    """Review #4: 16-bit grey must be scaled to 8 bit, not clipped to white."""
    src = tmp_path / "scan.tif"
    arr = np.full((10, 10), 32768, dtype=np.uint16)  # mid grey
    Image.fromarray(arr).save(src)  # uint16 -> mode I;16
    [result] = runner.run(Job("image", "jpg", [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    with Image.open(result.output) as out:
        assert out.mode == "L"
        assert 110 < out.getpixel((5, 5)) < 145


def test_icc_profile_is_kept_when_colour_space_is_unchanged(runner, tmp_path, out_dir):
    src = tmp_path / "p3.png"
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (8, 8), (10, 200, 30)).save(src, icc_profile=icc)
    [result] = runner.run(Job("image", "jpg", [src], out_dir), CancelToken())
    with Image.open(result.output) as out:
        assert out.info.get("icc_profile") == icc


def _jpeg_with_orientation(path, orientation):
    img = Image.new("RGB", (40, 20), (255, 0, 0))
    img.paste((0, 0, 255), (0, 0, 20, 20))  # left half blue
    exif = Image.Exif()
    exif[0x0112] = orientation
    img.save(path, exif=exif.tobytes())


def test_exif_orientation_is_baked_in(runner, tmp_path, out_dir):
    src = tmp_path / "phone.jpg"
    _jpeg_with_orientation(src, 6)  # rotate 90 deg clockwise on display
    [result] = runner.run(Job("image", "png", [src], out_dir), CancelToken())
    with Image.open(result.output) as out:
        assert out.size == (20, 40)
        assert out.getexif().get(0x0112) in (None, 1)


def test_animated_gif_warns_about_first_frame(runner, tmp_path, out_dir):
    src = tmp_path / "anim.gif"
    frames = [Image.new("RGB", (8, 8), c) for c in ("red", "green", "blue")]
    frames[0].save(src, save_all=True, append_images=frames[1:])
    [result] = runner.run(Job("image", "png", [src], out_dir), CancelToken())
    assert result.status == "done"
    assert any("eerste frame" in w for w in result.warnings)


def test_image_above_megapixel_limit_fails_cleanly(registry, workspace, tmp_path, out_dir):
    """Review #9: the limit is checked from the header, before pixels are loaded."""
    src = tmp_path / "huge.png"
    Image.new("L", (2000, 1000)).save(src)
    cfg = AppConfig(paths=PathsConfig(work_dir=tmp_path / "work"),
                    defaults={"image": {"max_megapixels": 1}})
    [result] = JobRunner(registry, workspace, cfg).run(
        Job("image", "jpg", [src], out_dir), CancelToken())
    assert result.status == "failed"
    assert "megapixel" in result.error
    assert list(out_dir.iterdir()) == []


def test_corrupt_image_fails_readably(runner, tmp_path, out_dir):
    src = tmp_path / "broken.gif"
    src.write_bytes(b"GIF89a" + struct.pack("<HH", 10, 10) + b"\x00" * 4)
    [result] = runner.run(Job("image", "png", [src], out_dir), CancelToken())
    assert result.status == "failed"
    assert result.error and not result.error.startswith("Onverwachte fout")


@pytest.mark.parametrize("mode", ["LA", "P", "L", "1", "RGB"])
def test_unusual_modes_reach_every_target(runner, tmp_path, out_dir, mode):
    src = tmp_path / f"m{mode}.png"
    Image.new("RGBA", (9, 7), (120, 30, 200, 100)).convert(mode).save(src)
    for target in ("jpg", "webp", "gif", "bmp", "tiff", "pdf"):
        [result] = runner.run(Job("image", target, [src], out_dir), CancelToken())
        assert result.status == "done", f"{mode}->{target}: {result.error}"


# ---- image -> PDF via img2pdf (0.2) -----------------------------------------------------

def _pdf_images(path):
    import pikepdf

    with pikepdf.open(path) as pdf:
        out = []
        for page in pdf.pages:
            for raw in page.get_images().values():
                out.append((raw.Filter, bytes(raw.read_raw_bytes()), page.mediabox))
        return out, len(pdf.pages)


def test_png_to_pdf_is_lossless(runner, make_sample, out_dir):
    """Review #1: Pillow wrote every page as JPEG q75; img2pdf uses a Flate stream."""
    [result] = runner.run(Job("image", "pdf", [make_sample("png")], out_dir), CancelToken())
    assert result.status == "done", result.error
    images, pages = _pdf_images(result.output)
    assert pages == 1
    assert images[0][0] == "/FlateDecode"


def test_jpg_to_pdf_embeds_the_original_bytes(runner, make_sample, out_dir):
    """Review #1: no second JPEG generation."""
    src = make_sample("jpg")
    [result] = runner.run(Job("image", "pdf", [src], out_dir), CancelToken())
    [(flt, data, _box)] = _pdf_images(result.output)[0]
    assert flt == "/DCTDecode"
    assert data == src.read_bytes()


def test_webp_with_alpha_to_pdf(runner, tmp_path, out_dir):
    """Review #18: img2pdf refuses WebP with alpha; we go through PNG."""
    src = tmp_path / "alpha.webp"
    Image.new("RGBA", (20, 20), (0, 128, 255, 100)).save(src, lossless=True)
    [result] = runner.run(Job("image", "pdf", [src], out_dir), CancelToken())
    assert result.status == "done", result.error


def test_animated_gif_to_pdf_has_a_page_per_frame(runner, tmp_path, out_dir):
    src = tmp_path / "anim.gif"
    frames = [Image.new("RGB", (8, 8), c) for c in ("red", "green", "blue")]
    frames[0].save(src, save_all=True, append_images=frames[1:])
    [result] = runner.run(Job("image", "pdf", [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    assert _pdf_images(result.output)[1] == 3
    assert not any("eerste frame" in w for w in result.warnings)


def test_exif_orientation_gives_portrait_pdf_page(runner, tmp_path, out_dir):
    src = tmp_path / "phone.jpg"
    _jpeg_with_orientation(src, 6)  # 40x20 stored, 20x40 on display
    [result] = runner.run(Job("image", "pdf", [src], out_dir), CancelToken())
    import pikepdf

    with pikepdf.open(result.output) as pdf:
        page = pdf.pages[0]
        box = [float(v) for v in page.mediabox]
        width, height = box[2] - box[0], box[3] - box[1]
        if int(page.obj.get("/Rotate", 0)) % 180:
            width, height = height, width
    assert height > width


def test_cmyk_jpeg_and_16bit_tiff_to_pdf(runner, tmp_path, out_dir):
    cmyk = tmp_path / "print.jpg"
    Image.new("CMYK", (20, 20), (0, 255, 255, 0)).save(cmyk)
    tif = tmp_path / "scan.tif"
    Image.fromarray(np.full((10, 10), 32768, dtype=np.uint16)).save(tif)
    for src in (cmyk, tif):
        [result] = runner.run(Job("image", "pdf", [src], out_dir), CancelToken())
        assert result.status == "done", result.error
