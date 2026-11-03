"""Image family: Pillow + pillow-heif, img2pdf for PDF. HEIC is source-only, PDF target-only."""

import io
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import img2pdf
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError
from pillow_heif import register_heif_opener
from pydantic import BaseModel, ConfigDict, Field

from uniconv.converters.formats import BMP, GIF, HEIC, JPG, PDF, PNG, TIFF, WEBP
from uniconv.core.converter import ConversionContext, Converter
from uniconv.core.errors import ConversionError

register_heif_opener()


class ImageOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jpeg_quality: int = Field(90, ge=1, le=95)     # >95 only grows files in Pillow
    png_compress_level: int = Field(6, ge=0, le=9)
    webp_quality: int = Field(85, ge=1, le=100)
    pdf_dpi: int = Field(150, ge=72, le=600)
    flatten_background: str = Field("#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    max_megapixels: int = Field(150, ge=1)          # below Pillow's own ~178 MP hard limit
    svg_min_px: int = Field(512, ge=16, le=16384)        # small icons are scaled up to this
    trace_colormode: Literal["color", "binary"] = "color"
    trace_max_megapixels: float = Field(1.0, gt=0, le=16)  # 4 MP took 111 s in tests
    trace_filter_speckle: int = Field(4, ge=0, le=128)     # ignore blobs smaller than this (px)


# Modes each writer accepts without surprises; anything else is converted first.
_TARGET_MODES = {
    "jpg": ("RGB", "L"), "bmp": ("RGB", "L", "1"),
    "png": ("RGBA", "RGB", "LA", "L", "P", "1"), "webp": ("RGBA", "RGB"),
    "tiff": ("RGBA", "RGB", "L", "CMYK", "1"), "gif": ("P",),
}
_PIL_FORMAT = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "gif": "GIF",
               "bmp": "BMP", "tiff": "TIFF"}


class ImageConverter(Converter):
    family = "image"
    family_label = "Afbeelding"
    Options = ImageOptions
    formats = (JPG, PNG, WEBP, GIF, BMP, TIFF, HEIC, PDF)

    def expected_losses(self, source: str, target: str) -> list[str]:
        out = []
        # PDF keeps alpha (img2pdf adds a soft mask), so only JPG and BMP flatten it
        if target in {"jpg", "bmp"} and source in {"png", "webp", "gif", "tiff", "heic"}:
            out.append("Eventuele transparantie wordt een effen achtergrond.")
        if target == "gif":
            out.append("GIF heeft maximaal 256 kleuren.")
        if target == "jpg":
            out.append("JPEG is lossy: elke conversie kost wat kwaliteit.")
        return out

    def convert(self, ctx: ConversionContext) -> None:
        if ctx.target.key == "pdf":
            self._to_pdf(ctx)  # lossless, multi-page (review #1)
            return
        opts: ImageOptions = ctx.options  # type: ignore[assignment]
        key = ctx.target.key
        try:
            with Image.open(ctx.input_path) as im:  # lazy: size is known before pixels load
                _check_size(im, opts)
                if getattr(im, "n_frames", 1) > 1:
                    ctx.warn("Alleen het eerste frame of de eerste pagina is geconverteerd.")
                img = ImageOps.exif_transpose(im)  # returns a copy: safe after the with-block
                icc = im.info.get("icc_profile")
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
            raise ConversionError(f"Afbeelding kan niet worden gelezen: {exc}") from exc
        ctx.cancel.raise_if_cancelled()
        encode_raster(img, key, opts, ctx.output_path, icc)

    def _to_pdf(self, ctx: ConversionContext) -> None:
        """Pillow would re-encode every page as JPEG q75; img2pdf embeds losslessly (review #1)."""
        opts: ImageOptions = ctx.options  # type: ignore[assignment]
        if ctx.source.key == "jpg":
            _check_size_of(ctx.input_path, opts)
            pages = [ctx.input_path.read_bytes()]  # embedded as-is: no second JPEG generation
        else:
            # PNG keeps alpha (img2pdf adds a soft mask); img2pdf itself refuses WebP with
            # alpha, so everything goes through PNG first (review #18)
            pages = list(_frames_as_png(ctx, opts))
        ctx.cancel.raise_if_cancelled()
        layout = img2pdf.get_fixed_dpi_layout_fun((opts.pdf_dpi, opts.pdf_dpi))
        try:
            data = img2pdf.convert(pages, layout_fun=layout,
                                   rotation=img2pdf.Rotation.ifvalid)  # honours EXIF rotation
        except Exception as exc:  # img2pdf raises plain ValueError and its own types
            raise ConversionError(f"Kan geen PDF maken: {exc}") from exc
        ctx.output_path.write_bytes(data)


def encode_raster(img: Image.Image, key: str, opts: ImageOptions, path: Path,
                  icc: bytes | None = None) -> None:
    """Save `img` as raster format `key`; shared with VectorConverter (SVG -> JPG, ...)."""
    before = _colour_space(img.mode)
    img = _normalize_mode(img, key, opts.flatten_background)
    # Writers fall back to img.info["icc_profile"], so the profile must leave the image too.
    img.info.pop("icc_profile", None)
    if _colour_space(img.mode) != before:
        icc = None  # a CMYK profile attached to RGB pixels renders wrong colours (review #4)

    params: dict = {}
    if icc and key in {"jpg", "png", "webp", "tiff"}:
        params["icc_profile"] = icc  # keeps Display P3 iPhone photos looking right
    match key:
        case "jpg":
            params |= {"quality": opts.jpeg_quality, "optimize": True}
        case "png":
            params |= {"compress_level": opts.png_compress_level}
        case "webp":
            params |= {"quality": opts.webp_quality}
        case "tiff":
            params |= {"compression": "tiff_lzw"}
    try:
        img.save(path, format=_PIL_FORMAT[key], **params)
    except (OSError, ValueError) as exc:
        raise ConversionError(f"Kan {key.upper()} niet schrijven: {exc}") from exc


def _check_size(im: Image.Image, opts: ImageOptions) -> None:
    """Checked from the header, before pixels load (review #9)."""
    if im.width * im.height > opts.max_megapixels * 1_000_000:
        raise ConversionError(
            f"Afbeelding is groter dan {opts.max_megapixels} megapixel "
            "(aan te passen in config.json)"
        )


def _check_size_of(path: Path, opts: ImageOptions) -> None:
    try:
        with Image.open(path) as im:
            _check_size(im, opts)
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise ConversionError(f"Afbeelding kan niet worden gelezen: {exc}") from exc


def _frames_as_png(ctx: ConversionContext, opts: ImageOptions) -> Iterator[bytes]:
    """Every frame/page as a lossless PNG; CMYK and 16-bit are normalised as for PNG output."""
    try:
        with Image.open(ctx.input_path) as im:
            _check_size(im, opts)
            for frame in ImageSequence.Iterator(im):
                ctx.cancel.raise_if_cancelled()
                img = ImageOps.exif_transpose(frame)
                icc = img.info.get("icc_profile")
                before = _colour_space(img.mode)
                if img.mode == "P":  # img2pdf is strict about palette transparency
                    img = img.convert("RGBA" if "transparency" in img.info else "RGB")
                img = _normalize_mode(img, "png", opts.flatten_background)
                img.info.pop("icc_profile", None)
                params: dict = {"compress_level": opts.png_compress_level}
                if icc and _colour_space(img.mode) == before:
                    params["icc_profile"] = icc
                buf = io.BytesIO()
                img.save(buf, format="PNG", **params)
                yield buf.getvalue()
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise ConversionError(f"Afbeelding kan niet worden gelezen: {exc}") from exc


def _is_high_bit_grey(mode: str) -> bool:
    return mode in ("I", "F") or mode.startswith("I;16")


def _colour_space(mode: str) -> str:
    if mode == "CMYK":
        return "CMYK"
    if mode in ("1", "L", "LA") or _is_high_bit_grey(mode):
        return "GREY"
    return "RGB"


def _normalize_mode(img: Image.Image, key: str, background: str) -> Image.Image:
    allowed = _TARGET_MODES[key]
    if img.mode in allowed:
        return img
    if _is_high_bit_grey(img.mode):  # 16-bit grey: scale to 8 bit instead of clipping to white
        img = img.convert("I").point(lambda v: v * (1 / 256)).convert("L")
        if img.mode in allowed:
            return img
    if key == "gif":
        return img.convert("RGBA").quantize(colors=256)
    has_alpha = img.mode in ("RGBA", "LA", "PA", "RGBa", "La") or "transparency" in img.info
    if has_alpha and "RGBA" in allowed:
        return img.convert("RGBA")
    if has_alpha:  # target cannot store alpha: composite onto the configured colour
        rgba = img.convert("RGBA")
        base = Image.new("RGBA", rgba.size, background)
        return Image.alpha_composite(base, rgba).convert("RGB")
    return img.convert("RGB")  # CMYK, YCbCr, P without alpha, L for WebP, ...
