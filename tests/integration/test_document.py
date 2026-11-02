import base64
import zipfile

import pytest

from uniconv.config import AppConfig, PathsConfig
from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job, JobRunner

pytestmark = pytest.mark.needs_pandoc

_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def test_md_to_html_has_heading(runner, make_sample, out_dir):
    [result] = runner.run(Job("document", "html", [make_sample("md")], out_dir), CancelToken())
    assert result.status == "done", result.error
    html = result.output.read_text(encoding="utf-8")
    assert "<h1" in html and "Titel" in html
    assert "<html" in html  # standalone by default


def test_md_with_image_embeds_data_uri(runner, tmp_path, out_dir):
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "dot.png").write_bytes(_PNG_1PX)
    src = tmp_path / "met-plaatje.md"
    src.write_text("# Foto\n\n![punt](img/dot.png)\n", encoding="utf-8")
    [result] = runner.run(Job("document", "html", [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    assert "data:image/png;base64" in result.output.read_text(encoding="utf-8")


def test_embed_without_standalone_does_not_fail(registry, workspace, make_sample, out_dir,
                                                tmp_path):
    """Review #11: --embed-resources requires --standalone; the converter adds it."""
    cfg = AppConfig(paths=PathsConfig(work_dir=tmp_path / "work"),
                    defaults={"document": {"standalone": False, "embed_resources": True}})
    [result] = JobRunner(registry, workspace, cfg).run(
        Job("document", "html", [make_sample("md")], out_dir), CancelToken())
    assert result.status == "done", result.error


def test_fragment_when_not_standalone_and_not_embedded(registry, workspace, make_sample,
                                                       out_dir, tmp_path):
    cfg = AppConfig(paths=PathsConfig(work_dir=tmp_path / "work"),
                    defaults={"document": {"standalone": False, "embed_resources": False}})
    [result] = JobRunner(registry, workspace, cfg).run(
        Job("document", "html", [make_sample("md")], out_dir), CancelToken())
    html = result.output.read_text(encoding="utf-8")
    assert "<h1" in html and "<html" not in html


def test_docx_to_md_announces_formatting_loss(registry, runner, make_sample, out_dir):
    conv = registry.find("document", "docx", "md")
    assert any("Opmaak" in w for w in conv.expected_losses("docx", "md"))
    [result] = runner.run(Job("document", "md", [make_sample("docx")], out_dir), CancelToken())
    assert "Titel" in result.output.read_text(encoding="utf-8")


def test_epub_keeps_document_title(runner, tmp_path, out_dir):
    src = tmp_path / "boek.md"
    src.write_text("---\ntitle: Eigen titel\n---\n\n# Hoofdstuk\n\nTekst.\n", encoding="utf-8")
    [result] = runner.run(Job("document", "epub", [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    with zipfile.ZipFile(result.output) as zf:
        opf = next(n for n in zf.namelist() if n.endswith(".opf"))
        assert "Eigen titel" in zf.read(opf).decode("utf-8")


def test_broken_docx_fails_readably(runner, tmp_path, out_dir):
    src = tmp_path / "kapot.docx"
    src.write_bytes(b"PK\x03\x04 this is not a real docx")
    [result] = runner.run(Job("document", "md", [src], out_dir), CancelToken())
    assert result.status == "failed"
    assert result.error and not result.error.startswith("Onverwachte fout")
    assert list(out_dir.iterdir()) == []


def test_txt_is_target_only(registry):
    assert "txt" not in registry.converter("document").sources()
    assert "txt" in registry.targets("document", "md")
