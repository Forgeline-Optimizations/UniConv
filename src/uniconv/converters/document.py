"""Document family: Pandoc does the work, this maps format keys to Pandoc names and flags."""

import re
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from uniconv.converters.formats import DOCX, EPUB, HTML, MD, ODT, PDF, RTF, TEX, TXT
from uniconv.core.converter import ConversionContext, Converter
from uniconv.core.errors import ToolMissingError
from uniconv.core.tools import find_tool, run_tool


class DocumentOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    standalone: bool = True        # full document with <head>/preamble instead of a fragment
    embed_resources: bool = True   # HTML: images inlined, one self-contained file
    pdf_papersize: Literal["a4", "a5", "us-letter"] = "a4"
    pdf_lang: str = Field("nl", pattern=r"^[a-z]{2}$")  # captions: "Figuur 1", hyphenation


_PANDOC = {"md": "markdown", "html": "html", "tex": "latex", "docx": "docx",
           "odt": "odt", "epub": "epub", "rtf": "rtf", "txt": "plain"}
_HAS_IMAGES = {"docx", "odt", "epub"}
_PDF_SOURCES = {"md", "html", "tex", "epub", "docx", "odt", "rtf"}
_LAYOUT_LOST = {"docx", "odt", "rtf"}
_MISSING_RESOURCE = re.compile(r"\[WARNING\] Could not fetch resource '?([^':]+)")


class DocumentConverter(Converter):
    family = "document"
    family_label = "Document"
    Options = DocumentOptions
    formats = (MD, HTML, TEX, DOCX, ODT, EPUB, RTF, TXT, PDF)

    def available(self) -> bool:
        return find_tool("pandoc") is not None

    def targets(self, source: str) -> list[str]:
        keys = super().targets(source)
        if source not in _PDF_SOURCES or find_tool("typst") is None:
            keys = [k for k in keys if k != "pdf"]
        return keys

    def expected_losses(self, source: str, target: str) -> list[str]:
        if target == "pdf":  # only reached when the better provider is missing (#11, #12)
            if source == "html":
                return ["Opmaak uit CSS gaat verloren. Met Chrome of Edge geïnstalleerd "
                        "lijkt de PDF op de webpagina."]
            if source in _LAYOUT_LOST:
                return ["De lay-out van het origineel gaat verloren. Installeer LibreOffice "
                        "(gratis) voor een getrouwe PDF."]
            return []
        out = []
        if source in {"docx", "odt", "rtf"}:
            out.append("Opmaak zoals lettertypes, kleuren en marges gaat verloren.")
        if source in _HAS_IMAGES and target in {"md", "tex", "txt", "rtf"}:
            out.append("Afbeeldingen worden niet meegenomen.")
        if target == "txt":
            out.append("Platte tekst bevat geen opmaak, koppen of links.")
        return out

    def convert(self, ctx: ConversionContext) -> None:
        if ctx.target.key == "pdf":
            self._to_pdf(ctx)
            return
        opts: DocumentOptions = ctx.options  # type: ignore[assignment]
        pandoc = find_tool("pandoc")
        if pandoc is None:
            raise ToolMissingError("Pandoc is niet gevonden; herinstalleer UniConv")
        dst = ctx.target.key
        cmd = [str(pandoc), "-f", _PANDOC[ctx.source.key], "-t", _PANDOC[dst],
               "-o", str(ctx.output_path),
               f"--resource-path={ctx.input_path.parent}",  # resolve relative image paths
               "--", str(ctx.input_path)]  # "--": a file name can never become an option
        if dst == "html" and opts.embed_resources:
            cmd[1:1] = ["--standalone", "--embed-resources"]  # embed needs standalone (#11)
        elif opts.standalone and dst in {"html", "tex", "rtf"}:
            cmd.insert(1, "--standalone")
        if dst == "epub":
            # EPUB needs a title. A metadata file only fills the gap: the document's own
            # title wins, unlike --metadata which would override it.
            meta = ctx.output_path.with_name("default-meta.yaml")
            meta.write_text(yaml.safe_dump({"title": ctx.input_path.stem}, allow_unicode=True),
                            encoding="utf-8")
            cmd[1:1] = [f"--metadata-file={meta}"]
        run_tool(cmd, timeout_s=ctx.timeout_s, cancel=ctx.cancel)

    def _to_pdf(self, ctx: ConversionContext) -> None:
        opts: DocumentOptions = ctx.options  # type: ignore[assignment]
        pandoc, typst = find_tool("pandoc"), find_tool("typst")
        if pandoc is None or typst is None:
            raise ToolMissingError("Pandoc of Typst is niet gevonden; herinstalleer UniConv")
        work = ctx.output_path.parent  # the job's own directory
        source = work / "main.typ"
        src = ctx.input_path.resolve()  # cwd changes below: relative paths would break
        # Step 1: Pandoc -> Typst source. cwd=work makes --extract-media write RELATIVE paths;
        # Pandoc's own `-t pdf` writes absolute temp paths that Typst cannot resolve (#25).
        stderr = run_tool(
            [str(pandoc), "-s", "-f", _PANDOC[ctx.source.key], "-t", "typst",
             "--extract-media=media", f"--resource-path={src.parent}",
             "-V", f"papersize={opts.pdf_papersize}", "-V", f"lang={opts.pdf_lang}",
             "-o", str(source), "--", str(src)],
            timeout_s=ctx.timeout_s, cancel=ctx.cancel, cwd=work)
        for name in dict.fromkeys(_MISSING_RESOURCE.findall(stderr)):
            ctx.warn(f"Afbeelding niet gevonden en weggelaten: {name}")
        ctx.cancel.raise_if_cancelled()
        # Step 2: Typst -> PDF. --root confines Typst to the job directory.
        run_tool([str(typst), "compile", "--root", str(work), str(source),
                  str(ctx.output_path)],
                 timeout_s=ctx.timeout_s, cancel=ctx.cancel, cwd=work)
