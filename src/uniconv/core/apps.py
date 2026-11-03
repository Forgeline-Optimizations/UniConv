"""Find applications the user installed (never bundled): LibreOffice and a Chromium browser."""

import os
import shutil
import sys
from functools import cache
from pathlib import Path


def _win(*parts: str) -> list[Path]:
    roots = [os.environ.get(v) for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    return [Path(r, *parts) for r in roots if r]


def _candidates(app: str) -> list[Path]:
    home = Path.home()
    if app == "libreoffice":
        if sys.platform == "win32":  # soffice.com waits and prints to stdout; .exe as fallback
            return (_win("LibreOffice", "program", "soffice.com")
                    + _win("LibreOffice", "program", "soffice.exe"))
        if sys.platform == "darwin":
            return [Path(d, "LibreOffice.app/Contents/MacOS/soffice")
                    for d in ("/Applications", home / "Applications")]
    if app == "browser":
        if sys.platform == "win32":
            return (_win("Google", "Chrome", "Application", "chrome.exe")
                    + _win("Microsoft", "Edge", "Application", "msedge.exe"))
        if sys.platform == "darwin":
            return [Path(d, a) for d in ("/Applications", home / "Applications") for a in (
                "Google Chrome.app/Contents/MacOS/Google Chrome",
                "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "Chromium.app/Contents/MacOS/Chromium")]
    return []


_ON_PATH = {"libreoffice": ("soffice", "libreoffice"),
            "browser": ("google-chrome", "chromium", "chromium-browser", "microsoft-edge")}


@cache
def find_app(app: str) -> Path | None:
    """UNICONV_<APP> env var first, then the usual install locations, then PATH."""
    override = os.environ.get(f"UNICONV_{app.upper()}")
    if override and Path(override).is_file():
        return Path(override)
    for p in _candidates(app):
        if p.is_file():
            return p
    for name in _ON_PATH.get(app, ()):
        if found := shutil.which(name):
            return Path(found)
    return None
