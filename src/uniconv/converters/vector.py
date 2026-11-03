"""SVG in and out. resvg renders SVG to pixels, Typst makes vector PDFs, vtracer traces
pixels to SVG. All three run outside the app process."""

import gzip
import re
import xml.etree.ElementTree as ET  # noqa: S405 - only the root tag is read, see _svg_size
from pathlib import Path

import img2pdf
from PIL import Image, ImageOps, UnidentifiedImageError

from uniconv.converters import formats as F
from uniconv.converters.image import ImageConverter, ImageOptions, encode_raster
from uniconv.core.converter import ConversionContext, Converter
from uniconv.core.errors import ConversionError, ToolMissingError
from uniconv.core.isolate import run_isolated
from uniconv.core.tools import find_tool, run_tool

_RASTER_OUT = ["png", "jpg", "webp", "gif", "bmp", "tiff"]
_UNIT_PX = {"": 1, "px": 1, "pt": 96 / 72, "pc": 16, "mm": 96 / 25.4, "cm": 96 / 2.54,
            "in": 96, "em": 16, "ex": 8}
_GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}
_FONT_MISSING = re.compile(r"No match for '\"?([^'\"]+)\"?' font-family")
_FONT_FAMILY = re.compile(r"font-family\s*[:=]\s*(\"[^\"]*\"|'[^']*'|[^;\"'>]+)")
_RASTER_PDF_SCALE = 2  # linked-image fallback: render at 2x, then place at the SVG's size


class VectorConverter(Converter):
    family = "image"
    family_label = "Afbeelding"
    formats = (F.SVG, F.JPG, F.PNG, F.WEBP, F.GIF, F.BMP, F.TIFF, F.HEIC, F.PDF)
    Options = ImageOptions  # shares the "image" section with ImageConverter

    def available(self) -> bool:
        return find_tool("resvg") is not None

    def targets(self, source: str) -> list[str]:
        if source == "svg":
            return _RASTER_OUT + (["pdf"] if find_tool("typst") else [])
        return ["svg"]  # every raster source can be traced

    def expected_losses(self, source: str, target: str) -> list[str]:
        if target == "svg":
            return ["Tracing benadert de afbeelding met vlakken: kleurverlopen worden vlakke "
                    "kleuren. Werkt het best voor logo's en tekeningen, niet voor foto's."]
        if source == "svg" and target != "pdf":
            return ["Het resultaat heeft vaste afmetingen en wordt wazig bij inzoomen.",
                    *ImageConverter().expected_losses("png", target)]
        return []

    def convert(self, ctx: ConversionContext) -> None:
        if ctx.target.key == "svg":
            self._trace(ctx)
        elif ctx.target.key == "pdf":
            self._svg_to_pdf(ctx)
        else:
            self._svg_to_raster(ctx)

    def _render(self, ctx: ConversionContext, scale_to: int | None = None) -> Path:
        """Render the SVG with resvg to a PNG in the job dir; returns its path."""
        opts: ImageOptions = ctx.options  # type: ignore[assignment]
        resvg = find_tool("resvg")
        if resvg is None:
            raise ToolMissingError("resvg is niet gevonden; herinstalleer UniConv")
        w, h = _svg_size(ctx.input_path)
        scale = scale_to or max(1.0, opts.svg_min_px / max(w, h))
        if w * h * scale * scale > opts.max_megapixels * 1_000_000:  # resvg aborts (#2)
            raise ConversionError(f"SVG is te groot om te renderen ({w:.0f}×{h:.0f} px)")
        png = ctx.output_path.with_name("render.png")
        stderr = run_tool([str(resvg), "--width", str(round(w * scale)),
                           "--resources-dir", str(ctx.input_path.resolve().parent),
                           str(ctx.input_path), str(png)],
                          timeout_s=ctx.timeout_s, cancel=ctx.cancel)
        for name in sorted(set(_FONT_MISSING.findall(stderr))):  # review #9
            ctx.warn(f"Lettertype '{name}' ontbreekt op deze computer; die tekst is weggelaten.")
        return png

    def _svg_to_raster(self, ctx: ConversionContext) -> None:
        opts: ImageOptions = ctx.options  # type: ignore[assignment]
        png = self._render(ctx)
        if ctx.target.key == "png":
            png.replace(ctx.output_path)
        else:
            with Image.open(png) as img:
                encode_raster(img.copy(), ctx.target.key, opts, ctx.output_path)

    def _svg_to_pdf(self, ctx: ConversionContext) -> None:
        typst = find_tool("typst")
        if typst is None:
            raise ToolMissingError("Typst is niet gevonden; herinstalleer UniConv")
        work = ctx.output_path.parent
        svg = work / "in.svg"
        raw = ctx.input_path.read_bytes()
        try:  # Typst does not read .svgz (review #26)
            svg.write_bytes(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
        except (OSError, EOFError) as exc:
            raise ConversionError(f"SVG kan niet worden gelezen: {exc}") from exc
        _svg_size(svg)  # readable at all? gives a clear error before Typst does
        if _only_generic_fonts(svg):
            ctx.warn("Tekst met een algemeen lettertype (zoals 'sans-serif') kan in de PDF als "
                     "schreefletter verschijnen.")  # review #10
        main = work / "main.typ"
        main.write_text('#set page(width: auto, height: auto, margin: 0pt, fill: none)\n'
                        '#image("in.svg")\n', encoding="utf-8")
        try:
            run_tool([str(typst), "compile", "--root", str(work), str(main),
                      str(ctx.output_path)], timeout_s=ctx.timeout_s, cancel=ctx.cancel,
                     cwd=work)
        except ConversionError as exc:
            if "linked image" not in str(exc) and "<image>" not in str(exc):
                raise
            # The SVG links external image files that Typst may not read: fall back to a
            # raster PDF via resvg (which resolves them) and img2pdf (review #26).
            ctx.warn("De SVG verwijst naar losse afbeeldingsbestanden; de PDF is daarom als "
                     "afbeelding gemaakt in plaats van als vector.")
            self._raster_pdf(ctx)

    def _raster_pdf(self, ctx: ConversionContext) -> None:
        png = self._render(ctx, scale_to=_RASTER_PDF_SCALE)
        dpi = 96 * _RASTER_PDF_SCALE  # the page gets the SVG's own size at 96 px per inch
        try:
            data = img2pdf.convert([png.read_bytes()],
                                   layout_fun=img2pdf.get_fixed_dpi_layout_fun((dpi, dpi)))
        except Exception as exc:  # img2pdf raises plain ValueError and its own types
            raise ConversionError(f"Kan geen PDF maken: {exc}") from exc
        ctx.output_path.write_bytes(data)

    def _trace(self, ctx: ConversionContext) -> None:
        opts: ImageOptions = ctx.options  # type: ignore[assignment]
        try:
            with Image.open(ctx.input_path) as im:
                if im.width * im.height > opts.max_megapixels * 1_000_000:
                    raise ConversionError(
                        f"Afbeelding is groter dan {opts.max_megapixels} megapixel "
                        "(aan te passen in config.json)")
                img = ImageOps.exif_transpose(im).convert("RGBA")
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
            raise ConversionError(f"Afbeelding kan niet worden gelezen: {exc}") from exc
        limit = opts.trace_max_megapixels * 1_000_000
        if img.width * img.height > limit:  # review #3: tracing time grows much faster than size
            factor = (limit / (img.width * img.height)) ** 0.5
            img = img.resize((max(1, int(img.width * factor)), max(1, int(img.height * factor))),
                             Image.Resampling.LANCZOS)
            ctx.warn(f"Afbeelding verkleind tot {img.width}×{img.height} px voor tracing.")
        src = ctx.output_path.with_name("trace-in.png")
        img.save(src)
        run_isolated(_trace_worker, str(src), str(ctx.output_path), opts.trace_colormode,
                     opts.trace_filter_speckle, timeout_s=ctx.timeout_s, cancel=ctx.cancel)


def _trace_worker(src: str, dst: str, colormode: str, speckle: int) -> None:
    """Runs in a child process (core.isolate). Module level, so it can be found by name."""
    import vtracer  # imported here: the parent process never needs it

    vtracer.convert_image_to_svg_py(src, dst, colormode=colormode, filter_speckle=speckle)


def _length(value: str | None) -> float | None:
    """'10cm' -> px; None for missing, '%' or unreadable values."""
    if not value:
        return None
    m = re.fullmatch(r"\s*([0-9]*\.?[0-9]+(?:[eE][+-]?\d+)?)\s*([a-z]*)\s*", value)
    if not m or m.group(2) not in _UNIT_PX:
        return None
    return float(m.group(1)) * _UNIT_PX[m.group(2)]


def _svg_size(path: Path) -> tuple[float, float]:
    """Size in px from the root <svg>; only the first element is parsed."""
    try:
        opener = gzip.open if path.read_bytes()[:2] == b"\x1f\x8b" else open
        with opener(path, "rb") as fh:
            _, root = next(ET.iterparse(fh, events=("start",)))  # noqa: S314 - root tag only
    except (ET.ParseError, StopIteration, OSError, EOFError) as exc:
        raise ConversionError(f"SVG kan niet worden gelezen: {exc}") from exc
    if not root.tag.endswith("svg"):
        raise ConversionError("Dit bestand is geen SVG")
    try:
        vb = [float(v) for v in re.split(r"[\s,]+", root.get("viewBox", "").strip()) if v][2:4]
    except ValueError:
        vb = []
    w, h = _length(root.get("width")), _length(root.get("height"))
    if w is None or h is None:  # missing or "100%": fall back to the viewBox, like resvg
        w, h = (vb[0], vb[1]) if len(vb) == 2 else (100.0, 100.0)
    return max(w, 1.0), max(h, 1.0)


def _only_generic_fonts(path: Path) -> bool:
    """True when the SVG has text and names no concrete font (review #10)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if "<text" not in text:
        return False
    families = [f.strip().strip("\"'").lower()
                for value in _FONT_FAMILY.findall(text)
                for f in value.strip().strip("\"'").split(",")]
    return all(f in _GENERIC for f in families if f)
