"""Office -> PDF via the user's LibreOffice (plan 0.2 step 13). Runs in the CI LibreOffice job."""

import pikepdf
import pytest

from uniconv.converters.office import OfficeDocumentConverter
from uniconv.core.converter import CancelToken
from uniconv.core.jobs import Job

from ..conftest import make_protected_docx

pytestmark = pytest.mark.needs_libreoffice


def _pages(path) -> int:
    with pikepdf.open(path) as pdf:
        return len(pdf.pages)


def _to_pdf(runner, src, out_dir, family="document"):
    [result] = runner.run(Job(family, "pdf", [src], out_dir), CancelToken())
    return result


def test_find_prefers_libreoffice_for_word(registry):
    assert isinstance(registry.find("document", "docx", "pdf"), OfficeDocumentConverter)


def test_docx_with_accent_in_name(runner, make_sample, out_dir):
    src = make_sample("docx", name="één rapport")
    result = _to_pdf(runner, src, out_dir)
    assert result.status == "done", result.error
    assert result.output.name == "één rapport.pdf"
    assert _pages(result.output) >= 1


@pytest.mark.parametrize("key", ["pptx", "odt", "rtf", "doc", "ppt", "odp"])
def test_documents_and_presentations(runner, make_sample, out_dir, key):
    result = _to_pdf(runner, make_sample(key), out_dir)
    assert result.status == "done", result.error


def test_xlsx_with_two_sheets_gives_two_pages(runner, tmp_path, out_dir):
    import pandas as pd

    src = tmp_path / "boek.xlsx"
    with pd.ExcelWriter(src) as xw:
        pd.DataFrame({"x": [1, 2]}).to_excel(xw, sheet_name="Eerste", index=False)
        pd.DataFrame({"y": [3]}).to_excel(xw, sheet_name="Tweede", index=False)
    result = _to_pdf(runner, src, out_dir, family="data")
    assert result.status == "done", result.error
    assert _pages(result.output) >= 2


@pytest.mark.parametrize("key", ["xls", "ods"])
def test_old_and_open_spreadsheets(runner, make_sample, out_dir, key):
    result = _to_pdf(runner, make_sample(key), out_dir, family="data")
    assert result.status == "done", result.error


def test_same_stem_different_extension(runner, make_sample, tmp_path, out_dir):
    """Review #14: doc.odt and doc.rtf both become doc.pdf; each must be the right one."""
    odt = make_sample("odt", name="doc")
    rtf = make_sample("rtf", name="doc")
    first = _to_pdf(runner, odt, out_dir)
    second = _to_pdf(runner, rtf, out_dir)
    assert first.status == second.status == "done"
    assert {first.output.name, second.output.name} == {"doc.pdf", "doc (1).pdf"}


def test_truncated_docx_fails_cleanly(runner, make_sample, tmp_path, out_dir):
    """Review #4: LibreOffice exits 0 without output; we must not report success."""
    good = make_sample("docx")
    src = tmp_path / "kapot.docx"
    src.write_bytes(good.read_bytes()[:200])
    result = _to_pdf(runner, src, out_dir)
    assert result.status == "failed"
    assert "beschadigd" in result.error or "geen PDF" in result.error
    assert list(out_dir.iterdir()) == []


def test_password_protected_docx_fails_cleanly(runner, tmp_path, out_dir):
    """Review #4 + #13."""
    src = make_protected_docx(tmp_path / "geheim.docx")
    result = _to_pdf(runner, src, out_dir)
    assert result.status == "failed"
    assert "wachtwoord" in result.error or "geen PDF" in result.error
    assert list(out_dir.iterdir()) == []


def test_job_profile_stays_in_the_work_dir(runner, workspace, make_sample, out_dir):
    """Review #5: an own profile per job, removed with the job dir."""
    _to_pdf(runner, make_sample("odt"), out_dir)
    assert list(workspace.root.iterdir()) == []


def test_soffice_waits_until_the_pdf_exists(make_sample, tmp_path):
    """Step 13 audit: soffice (soffice.com on Windows) must return only after writing the PDF;
    otherwise converters/office.py relies on its 10 s polling fallback."""
    from uniconv.core.apps import find_app
    from uniconv.core.tools import run_tool

    src = make_sample("odt")
    out_lines: list[str] = []
    stderr = run_tool([str(find_app("libreoffice")),
                       f"-env:UserInstallation={(tmp_path / 'prof').as_uri()}",
                       "--headless", "--norestore", "--convert-to", "pdf",
                       "--outdir", str(tmp_path / "o"), str(src)],
                      timeout_s=180, cancel=CancelToken(), on_stdout_line=out_lines.append)
    print("soffice stdout:", out_lines, "stderr:", stderr.strip()[:300])
    assert (tmp_path / "o" / f"{src.stem}.pdf").is_file()


def test_where_the_error_line_goes(tmp_path):
    """Step 13 audit: report which stream carries 'could not be loaded' (stdout or stderr)."""
    from uniconv.core.apps import find_app
    from uniconv.core.tools import run_tool

    bad = tmp_path / "kapot.docx"
    bad.write_bytes(b"PK\x03\x04 broken")
    out_lines: list[str] = []
    stderr = run_tool([str(find_app("libreoffice")),
                       f"-env:UserInstallation={(tmp_path / 'prof').as_uri()}",
                       "--headless", "--norestore", "--convert-to", "pdf",
                       "--outdir", str(tmp_path / "o"), str(bad)],
                      timeout_s=180, cancel=CancelToken(), on_stdout_line=out_lines.append)
    print("AUDIT stdout:", out_lines, "| stderr:", stderr.strip()[:300])
    assert any("could not be loaded" in s for s in [*out_lines, stderr])
