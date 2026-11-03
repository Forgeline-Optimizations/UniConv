"""HTML to PDF the way a browser shows it, via the user's Chrome/Edge/Chromium.
Never bundled: found by core.apps.find_app("browser")."""

from pydantic import BaseModel, ConfigDict, Field

from uniconv.converters import formats as F
from uniconv.core.apps import find_app
from uniconv.core.converter import ConversionContext, Converter
from uniconv.core.errors import ConversionError, ToolMissingError
from uniconv.core.tools import run_tool


class BrowserOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_timeout_ms: int = Field(15000, ge=1000, le=120000)  # capture after this, loaded or not


class BrowserPdfConverter(Converter):
    family = "document"
    family_label = "Document"
    formats = (F.HTML, F.PDF)
    Options = BrowserOptions
    options_key = "browser"
    install_hint = "Installeer Chrome of Edge voor HTML naar PDF met de opmaak van de webpagina."

    def available(self) -> bool:
        return find_app("browser") is not None

    def targets(self, source: str) -> list[str]:
        return ["pdf"]

    def expected_losses(self, source: str, target: str) -> list[str]:
        return ["De pagina wordt geopend zoals in een browser: scripts draaien en externe "
                "afbeeldingen of lettertypen worden van internet gehaald.",
                "Zonder @page-regel in de CSS wordt het papierformaat US Letter."]

    def convert(self, ctx: ConversionContext) -> None:
        opts: BrowserOptions = ctx.options  # type: ignore[assignment]
        browser = find_app("browser")
        if browser is None:
            raise ToolMissingError(self.install_hint or "")
        work = ctx.output_path.parent
        cmd = [str(browser), "--headless", "--disable-gpu", "--no-first-run",
               "--no-default-browser-check", "--disable-extensions", "--disable-sync",
               "--disable-background-networking",
               f"--user-data-dir={work / 'browser-profile'}",  # never the user's own (#15)
               "--no-pdf-header-footer", f"--timeout={opts.page_timeout_ms}",
               f"--print-to-pdf={ctx.output_path}", ctx.input_path.resolve().as_uri()]
        # Process limit = page limit + start-up margin; a hung browser is killed (review #15)
        run_tool(cmd, timeout_s=min(ctx.timeout_s, opts.page_timeout_ms // 1000 + 60),
                 cancel=ctx.cancel)
        if not ctx.output_path.is_file() or ctx.output_path.stat().st_size == 0:
            raise ConversionError("De browser maakte geen PDF")
