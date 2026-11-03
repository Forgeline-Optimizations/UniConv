"""HTML -> PDF via the user's Chrome/Edge (plan 0.2 step 14). Also the step 14 CI audit."""

import time

import pypdfium2 as pdfium
import pytest

from uniconv.config import AppConfig, PathsConfig
from uniconv.converters.browser import BrowserPdfConverter
from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job, JobRunner
from uniconv.core.workspace import Workspace

pytestmark = pytest.mark.needs_browser


def _has_red(path) -> bool:
    pdf = pdfium.PdfDocument(str(path))
    try:
        img = pdf[0].render(scale=1).to_pil().convert("RGB")
    finally:
        pdf.close()
    return any(r > 200 and g < 60 and b < 60 for r, g, b in img.getdata())


def test_find_prefers_the_browser_for_html(registry):
    assert isinstance(registry.find("document", "html", "pdf"), BrowserPdfConverter)


def test_css_is_kept(runner, tmp_path, out_dir):
    """Review #11: the Pandoc route drops CSS; the browser keeps it."""
    src = tmp_path / "rapport met spatie.html"
    src.write_text("<html><head><style>h1 { color: red; font-size: 60px }</style></head>"
                   "<body><h1>Rood</h1></body></html>", encoding="utf-8")
    [result] = runner.run(Job("document", "pdf", [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    assert _has_red(result.output)


def test_profile_stays_in_the_job_dir(runner, workspace, make_sample, tmp_path, out_dir):
    """Review #15: never the user's own browser profile; nothing left behind."""
    [result] = runner.run(Job("document", "pdf", [make_sample("html")], out_dir), CancelToken())
    assert result.status == "done", result.error
    assert list(workspace.root.iterdir()) == []
    assert not list(tmp_path.rglob("browser-profile"))


def test_endless_script_still_gives_a_pdf(registry, tmp_path, out_dir):
    """Review #15: --timeout captures the page even if it never finishes loading."""
    src = tmp_path / "eindeloos.html"
    src.write_text("<html><body><h1>Bezig</h1><script>"
                   "function tick(){ setTimeout(tick, 10); } tick();"
                   "fetch('http://10.255.255.1/never');"  # a request that never answers
                   "</script></body></html>", encoding="utf-8")
    cfg = AppConfig(paths=PathsConfig(work_dir=tmp_path / "work"),
                    defaults={"browser": {"page_timeout_ms": 3000}})
    runner = JobRunner(registry, Workspace(cfg.paths.work_dir), cfg)
    start = time.monotonic()
    [result] = runner.run(Job("document", "pdf", [src], out_dir), CancelToken())
    assert result.status == "done", result.error
    assert time.monotonic() - start < 3 + 30
