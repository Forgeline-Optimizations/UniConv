import os
import sys
from pathlib import Path

import pytest

from uniconv.core import apps


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    apps.find_app.cache_clear()
    for var in ("UNICONV_LIBREOFFICE", "UNICONV_BROWSER"):
        monkeypatch.delenv(var, raising=False)
    yield
    apps.find_app.cache_clear()


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def _no_install_dirs(monkeypatch, tmp_path):
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        monkeypatch.setenv(var, str(tmp_path / "empty" / var))
    monkeypatch.setattr(apps.Path, "home", lambda: tmp_path / "home")
    monkeypatch.setattr(apps.shutil, "which", lambda name: None)


def test_env_override_wins(monkeypatch, tmp_path):
    exe = _touch(tmp_path / "custom" / "soffice")
    monkeypatch.setenv("UNICONV_LIBREOFFICE", str(exe))
    assert apps.find_app("libreoffice") == exe


def test_windows_prefers_soffice_com(monkeypatch, tmp_path):
    _no_install_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "pf"))
    prog = tmp_path / "pf" / "LibreOffice" / "program"
    _touch(prog / "soffice.exe")
    com = _touch(prog / "soffice.com")
    assert apps.find_app("libreoffice") == com


def test_windows_finds_edge_when_chrome_is_missing(monkeypatch, tmp_path):
    _no_install_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("ProgramFiles(x86)", str(tmp_path / "pf86"))
    edge = _touch(tmp_path / "pf86" / "Microsoft" / "Edge" / "Application" / "msedge.exe")
    assert apps.find_app("browser") == edge


def test_macos_user_applications(monkeypatch, tmp_path):
    _no_install_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    soffice = _touch(tmp_path / "home" / "Applications" / "LibreOffice.app" / "Contents"
                     / "MacOS" / "soffice")
    if Path("/Applications/LibreOffice.app/Contents/MacOS/soffice").is_file():
        pytest.skip("a real LibreOffice in /Applications wins")
    assert apps.find_app("libreoffice") == soffice


def test_path_is_the_last_resort(monkeypatch, tmp_path):
    _no_install_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    exe = _touch(tmp_path / "bin" / "soffice")
    monkeypatch.setattr(apps.shutil, "which", lambda name: str(exe) if name == "soffice" else None)
    assert apps.find_app("libreoffice") == exe


def test_nothing_found(monkeypatch, tmp_path):
    _no_install_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "platform", "linux")
    assert apps.find_app("libreoffice") is None
    assert apps.find_app("unknown-app") is None


@pytest.mark.skipif(not os.environ.get("CI"), reason="audit on CI runners only")
def test_ci_runner_has_a_browser():
    """Step 7 audit: Windows runners ship Chrome and Edge, macOS runners Chrome."""
    found = apps.find_app("browser")
    assert found is not None
    print(f"browser found: {found}")


@pytest.mark.skipif(not os.environ.get("UNICONV_EXPECT_LIBREOFFICE"),
                    reason="audit in the CI LibreOffice job only")
def test_ci_libreoffice_is_found():
    """Step 7 audit: on Windows the console launcher soffice.com must be chosen."""
    found = apps.find_app("libreoffice")
    assert found is not None
    if sys.platform == "win32":
        assert found.name == "soffice.com"
