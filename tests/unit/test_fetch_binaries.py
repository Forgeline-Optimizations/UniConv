"""scripts/fetch_binaries.py: archives are read member by member, never extracted wholesale."""

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "fetch_binaries", Path(__file__).resolve().parents[2] / "scripts" / "fetch_binaries.py")
fb = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(fb)


def test_extract_from_tar_xz(tmp_path):
    """Review #19: Typst for macOS ships as .tar.xz."""
    archive = tmp_path / "typst-aarch64-apple-darwin.tar.xz"
    with tarfile.open(archive, "w:xz") as tf:
        data = b"#!binary"
        info = tarfile.TarInfo("typst-aarch64-apple-darwin/typst")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    fb.extract(archive, "typst-aarch64-apple-darwin/typst", tmp_path / "typst")
    assert (tmp_path / "typst").read_bytes() == b"#!binary"


def test_tar_member_must_be_a_regular_file(tmp_path):
    archive = tmp_path / "evil.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        link = tarfile.TarInfo("bin/typst")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        tf.addfile(link)
    with pytest.raises(SystemExit, match="not a regular file"):
        fb.extract(archive, "bin/typst", tmp_path / "typst")


def test_extract_from_zip(tmp_path):
    archive = tmp_path / "resvg-win-x86_64.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("resvg.exe", b"MZ")
    fb.extract(archive, "resvg.exe", tmp_path / "resvg.exe")
    assert (tmp_path / "resvg.exe").read_bytes() == b"MZ"


def test_every_platform_pins_typst_and_resvg():
    for tag, archives in fb.MANIFEST.items():
        names = {n for a in archives for n in a.members}
        assert {"typst", "resvg"} <= {n.removesuffix(".exe") for n in names}, tag
        assert all(len(a.sha256) == 64 for a in archives)
