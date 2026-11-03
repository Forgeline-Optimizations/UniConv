"""Office documents, presentations and spreadsheets to PDF via the user's own LibreOffice.
Never bundled: found by core.apps.find_app("libreoffice")."""

import shutil
import time

from pydantic import BaseModel, ConfigDict, Field

from uniconv.converters import formats as F
from uniconv.core.apps import find_app
from uniconv.core.converter import ConversionContext, Converter
from uniconv.core.errors import ConversionError, ConversionTimeout, ToolMissingError
from uniconv.core.tools import run_tool

_HINT = ("Installeer LibreOffice (gratis, libreoffice.org) en start UniConv opnieuw "
         "voor PDF met de originele opmaak.")
# If soffice returns before the file is written (step 13 audit), wait this long for it.
_OUTPUT_GRACE_S = 10


class OfficeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Shorter than limits.timeout_seconds: a LibreOffice that macOS blocks on first start
    # should not keep the user waiting 15 minutes (review #17).
    timeout_seconds: int = Field(180, ge=10, le=3600)


class _OfficeToPdf(Converter):
    Options = OfficeOptions
    options_key = "office"
    install_hint = _HINT

    def available(self) -> bool:
        return find_app("libreoffice") is not None

    def targets(self, source: str) -> list[str]:
        return ["pdf"]

    def expected_losses(self, source: str, target: str) -> list[str]:
        return ["Lettertypen die niet op deze computer staan, worden vervangen door gelijkende."]

    def convert(self, ctx: ConversionContext) -> None:
        _soffice_to_pdf(ctx)


class OfficeDocumentConverter(_OfficeToPdf):
    family = "document"
    family_label = "Document"
    formats = (F.DOCX, F.DOC, F.ODT, F.RTF, F.PPTX, F.PPT, F.ODP, F.PDF)


class OfficeSheetConverter(_OfficeToPdf):
    family = "data"
    family_label = "Data"
    formats = (F.XLSX, F.XLS, F.ODS, F.PDF)

    def expected_losses(self, source: str, target: str) -> list[str]:
        return [*super().expected_losses(source, target),
                "Alle werkbladen komen in de PDF; brede bladen worden over pagina's verdeeld."]


def _soffice_to_pdf(ctx: ConversionContext) -> None:
    opts: OfficeOptions = ctx.options  # type: ignore[assignment]
    soffice = find_app("libreoffice")
    if soffice is None:
        raise ToolMissingError(_HINT)
    work = ctx.output_path.parent
    # Fixed ASCII name: no clashes between doc.odt/doc.rtf, no odd characters (review #14)
    src = work / f"input{ctx.input_path.suffix.lower()}"
    shutil.copyfile(ctx.input_path, src)
    outdir = work / "lo-out"
    out_lines: list[str] = []
    cmd = [str(soffice),
           f"-env:UserInstallation={(work / 'lo-profile').as_uri()}",  # own profile (review #5)
           "--headless", "--norestore", "--nologo",
           "--convert-to", "pdf", "--outdir", str(outdir), str(src)]
    try:
        stderr = run_tool(cmd, timeout_s=opts.timeout_seconds, cancel=ctx.cancel,
                          on_stdout_line=out_lines.append)
    except ConversionTimeout as exc:
        raise ConversionError(
            "LibreOffice reageert niet. Open LibreOffice één keer zelf (macOS vraagt dan om "
            "toestemming) en probeer het opnieuw.") from exc
    produced = outdir / "input.pdf"
    deadline = time.monotonic() + _OUTPUT_GRACE_S
    while not produced.is_file() and time.monotonic() < deadline and _may_still_appear(out_lines):
        ctx.cancel.raise_if_cancelled()
        time.sleep(0.2)
    if not produced.is_file():  # exit code is 0 even on failure (review #4)
        output = "\n".join(out_lines) + "\n" + stderr  # versions differ in which stream
        if "could not be loaded" in output:
            raise ConversionError("LibreOffice kan dit bestand niet openen. Het is beschadigd "
                                  "of beveiligd met een wachtwoord.")  # review #13
        line = next((x.strip() for x in output.splitlines() if x.strip().startswith("Error")),
                    "")
        raise ConversionError("LibreOffice maakte geen PDF" + (f": {line}" if line else ""))
    produced.replace(ctx.output_path)


def _may_still_appear(out_lines: list[str]) -> bool:
    """Only wait for the file when LibreOffice did not already report an error."""
    return not any(x.strip().startswith("Error") for x in out_lines)
