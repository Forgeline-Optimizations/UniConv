"""Text documents -> PDF via Pandoc + Typst (plan 0.2 step 12) and provider priority."""

import pikepdf
import pypdfium2 as pdfium
import pytest
from PIL import Image

from uniconv.config import AppConfig, PathsConfig
from uniconv.converters.document import DocumentConverter
from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job, JobRunner
from uniconv.core.workspace import Workspace

pytestmark = [pytest.mark.needs_pandoc, pytest.mark.needs_typst]

# Providers that beat Pandoc for PDF when their app is installed (steps 13-14).
BETTER_PDF_PROVIDERS: tuple[type, ...] = ()


def _pdf_text(path) -> str:
    pdf = pdfium.PdfDocument(str(path))
    try:
        return "\n".join(page.get_textpage().get_text_range() for page in pdf)
    finally:
        pdf.close()


def _image_count(path) -> int:
    with pikepdf.open(path) as pdf:
        return sum(len(page.get_images()) for page in pdf.pages)


def _pandoc_runner(registry_without, tmp_path):
    reg = registry_without(*BETTER_PDF_PROVIDERS)
    cfg = AppConfig(paths=PathsConfig(work_dir=tmp_path / "work-pandoc"))
    return reg, JobRunner(reg, Workspace(cfg.paths.work_dir), cfg)


def test_md_with_image_gives_a4_pdf_with_caption(runner, tmp_path, out_dir):
    (tmp_path / "img").mkdir()
    Image.new("RGB", (40, 20), "red").save(tmp_path / "img" / "rood.png")
    src = tmp_path / "notities.md"
    src.write_text("# Titel é €\n\n![Een rood vlak](img/rood.png)\n\nTekst.\n", encoding="utf-8")

    [result] = runner.run(Job("document", "pdf", [src], out_dir), CancelToken())

    assert result.status == "done", result.error
    with pikepdf.open(result.output) as pdf:
        box = [round(float(v)) for v in pdf.pages[0].mediabox]
    assert box[2:] == [595, 842]  # A4 in points
    assert _image_count(result.output) == 1
    text = _pdf_text(result.output)
    assert "Figuur" in text  # lang=nl
    assert "é" in text and "€" in text


def test_images_via_parent_and_absolute_paths(runner, tmp_path, out_dir, monkeypatch):
    """Review #25: Pandoc's own PDF route writes absolute temp paths Typst cannot read."""
    docs, img = tmp_path / "docs", tmp_path / "img"
    docs.mkdir()
    img.mkdir()
    Image.new("RGB", (20, 20), "blue").save(img / "a.png")
    Image.new("RGB", (20, 20), "green").save(img / "b.png")
    src = docs / "rapport.md"
    src.write_text(f"# R\n\n![A](../img/a.png)\n\n![B]({(img / 'b.png').as_posix()})\n",
                   encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)  # the app's working directory is never the document's

    [result] = runner.run(Job("document", "pdf", [src], out_dir), CancelToken())

    assert result.status == "done", result.error
    assert _image_count(result.output) == 2


def test_missing_image_warns(runner, tmp_path, out_dir):
    src = tmp_path / "kapot.md"
    src.write_text("# T\n\n![Weg](bestaat-niet.png)\n", encoding="utf-8")
    [result] = runner.run(Job("document", "pdf", [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    assert any("bestaat-niet.png" in w for w in result.warnings)


@pytest.mark.parametrize("key", ["tex", "epub", "odt", "rtf"])
def test_other_sources_to_pdf(runner, make_sample, out_dir, key):
    [result] = runner.run(Job("document", "pdf", [make_sample(key)], out_dir), CancelToken())
    assert result.status == "done", result.error
    assert "Titel" in _pdf_text(result.output)


def test_docx_falls_back_to_pandoc_with_libreoffice_hint(registry_without, make_sample,
                                                         tmp_path, out_dir):
    """Review #12: without LibreOffice Word -> PDF still works, but says what is lost."""
    reg, runner = _pandoc_runner(registry_without, tmp_path)
    conv = reg.find("document", "docx", "pdf")
    assert isinstance(conv, DocumentConverter)
    assert any("LibreOffice" in m for m in conv.expected_losses("docx", "pdf"))
    [result] = runner.run(Job("document", "pdf", [make_sample("docx")], out_dir), CancelToken())
    assert result.status == "done", result.error


def test_html_falls_back_to_pandoc_with_browser_hint(registry_without, make_sample, tmp_path,
                                                     out_dir):
    """Review #11: without a browser HTML -> PDF loses its CSS and says so."""
    reg, runner = _pandoc_runner(registry_without, tmp_path)
    conv = reg.find("document", "html", "pdf")
    assert isinstance(conv, DocumentConverter)
    assert any("Chrome of Edge" in m for m in conv.expected_losses("html", "pdf"))
    [result] = runner.run(Job("document", "pdf", [make_sample("html")], out_dir), CancelToken())
    assert result.status == "done", result.error
