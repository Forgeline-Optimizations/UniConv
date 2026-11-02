"""Image family: Pillow + pillow-heif. HEIC is source-only, PDF target-only."""

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener
from pydantic import BaseModel, ConfigDict, Field

from uniconv.core.converter import ConversionContext, Converter, Format
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


# Modes each writer accepts without surprises; anything else is converted first.
_TARGET_MODES = {
    "jpg": ("RGB", "L"), "bmp": ("RGB", "L", "1"), "pdf": ("RGB", "L"),
    "png": ("RGBA", "RGB", "LA", "L", "P", "1"), "webp": ("RGBA", "RGB"),
    "tiff": ("RGBA", "RGB", "L", "CMYK", "1"), "gif": ("P",),
}
_PIL_FORMAT = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "gif": "GIF",
               "bmp": "BMP", "tiff": "TIFF", "pdf": "PDF"}


class ImageConverter(Converter):
    family = "image"
    family_label = "Afbeelding"
    Options = ImageOptions
    formats = (
        Format("jpg", "JPEG", (".jpg", ".jpeg"), ("image/jpeg",)),
        Format("png", "PNG", (".png",), ("image/png",)),
        Format("webp", "WebP", (".webp",), ("image/webp",)),
        Format("gif", "GIF", (".gif",), ("image/gif",)),
        Format("bmp", "BMP", (".bmp",), ("image/bmp",)),
        Format("tiff", "TIFF", (".tif", ".tiff"), ("image/tiff",)),
        Format("heic", "HEIC", (".heic", ".heif"), ("image/heic", "image/heif"), target=False),
        Format("pdf", "PDF", (".pdf",), ("application/pdf",), source=False),
    )

    def expected_losses(self, source: str, target: str) -> list[str]:
        out = []
        if target in {"jpg", "bmp", "pdf"} and source in {"png", "webp", "gif", "tiff", "heic"}:
            out.append("Eventuele transparantie wordt een effen achtergrond.")
        if target == "gif":
            out.append("GIF heeft maximaal 256 kleuren.")
        if target == "jpg":
            out.append("JPEG is lossy: elke conversie kost wat kwaliteit.")
        return out

    def convert(self, ctx: ConversionContext) -> None:
        opts: ImageOptions = ctx.options  # type: ignore[assignment]
        key = ctx.target.key
        try:
            with Image.open(ctx.input_path) as im:  # lazy: size is known before pixels load
                if im.width * im.height > opts.max_megapixels * 1_000_000:
                    raise ConversionError(
                        f"Afbeelding is groter dan {opts.max_megapixels} megapixel "
                        "(aan te passen in config.json)"
                    )
                if getattr(im, "n_frames", 1) > 1:
                    ctx.warn("Alleen het eerste frame of de eerste pagina is geconverteerd.")
                img = ImageOps.exif_transpose(im)  # returns a copy: safe after the with-block
                icc = im.info.get("icc_profile")
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
            raise ConversionError(f"Afbeelding kan niet worden gelezen: {exc}") from exc
        ctx.cancel.raise_if_cancelled()

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
            case "pdf":
                params |= {"resolution": float(opts.pdf_dpi)}
        try:
            img.save(ctx.output_path, format=_PIL_FORMAT[key], **params)
        except (OSError, ValueError) as exc:
            raise ConversionError(f"Kan {ctx.target.label} niet schrijven: {exc}") from exc


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
