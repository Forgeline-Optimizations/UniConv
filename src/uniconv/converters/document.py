"""Document family: Pandoc does the work, this maps format keys to Pandoc names and flags."""

import yaml
from pydantic import BaseModel, ConfigDict

from uniconv.converters.formats import DOCX, EPUB, HTML, MD, ODT, RTF, TEX, TXT
from uniconv.core.converter import ConversionContext, Converter
from uniconv.core.errors import ToolMissingError
from uniconv.core.tools import find_tool, run_tool


class DocumentOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    standalone: bool = True        # full document with <head>/preamble instead of a fragment
    embed_resources: bool = True   # HTML: images inlined, one self-contained file


_PANDOC = {"md": "markdown", "html": "html", "tex": "latex", "docx": "docx",
           "odt": "odt", "epub": "epub", "rtf": "rtf", "txt": "plain"}
_HAS_IMAGES = {"docx", "odt", "epub"}


class DocumentConverter(Converter):
    family = "document"
    family_label = "Document"
    Options = DocumentOptions
    formats = (MD, HTML, TEX, DOCX, ODT, EPUB, RTF, TXT)

    def available(self) -> bool:
        return find_tool("pandoc") is not None

    def expected_losses(self, source: str, target: str) -> list[str]:
        out = []
        if source in {"docx", "odt", "rtf"}:
            out.append("Opmaak zoals lettertypes, kleuren en marges gaat verloren.")
        if source in _HAS_IMAGES and target in {"md", "tex", "txt", "rtf"}:
            out.append("Afbeeldingen worden niet meegenomen.")
        if target == "txt":
            out.append("Platte tekst bevat geen opmaak, koppen of links.")
        return out

    def convert(self, ctx: ConversionContext) -> None:
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
