import os
import sys
import time
from datetime import timedelta
from uuid import uuid4

import pytest

from uniconv.core.errors import ConversionError
from uniconv.core.workspace import PARTIAL_SUFFIX, Workspace


@pytest.fixture
def ws(tmp_path):
    return Workspace(tmp_path / "work")


def _tmp_file(ws, content=b"new"):
    d = ws.job_dir(f"job-{uuid4().hex}")
    f = d / "out.png"
    f.write_bytes(content)
    return f


def _no_partials(d):
    return not [p for p in d.iterdir() if p.name.endswith(PARTIAL_SUFFIX)]


def test_rename_policy_numbers_the_file(ws, out_dir):
    (out_dir / "foto.png").write_bytes(b"old")
    first = ws.finalize(_tmp_file(ws), out_dir, "foto", ".png", "rename")
    second = ws.finalize(_tmp_file(ws), out_dir, "foto", ".png", "rename")
    assert first.name == "foto (1).png"
    assert second.name == "foto (2).png"
    assert (out_dir / "foto.png").read_bytes() == b"old"


def test_skip_policy_keeps_existing_file(ws, out_dir):
    (out_dir / "foto.png").write_bytes(b"old")
    assert ws.finalize(_tmp_file(ws), out_dir, "foto", ".png", "skip") is None
    assert (out_dir / "foto.png").read_bytes() == b"old"


def test_overwrite_replaces_existing_file(ws, out_dir):
    """Review #1: shutil.move alone refuses this on Windows."""
    (out_dir / "foto.png").write_bytes(b"old")
    dest = ws.finalize(_tmp_file(ws, b"new"), out_dir, "foto", ".png", "overwrite")
    assert dest == out_dir / "foto.png"
    assert dest.read_bytes() == b"new"
    assert _no_partials(out_dir)


def test_unwritable_destination_gives_readable_error(ws, tmp_path):
    """Review #7: the user sees a ConversionError, not a raw OSError."""
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"a file where a folder should be")
    with pytest.raises(ConversionError, match="Kan niet opslaan"):
        ws.finalize(_tmp_file(ws), blocker / "sub", "foto", ".png", "overwrite")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file locking")
def test_file_open_elsewhere_gives_readable_error_on_windows(ws, out_dir):
    target = out_dir / "foto.png"
    target.write_bytes(b"old")
    with open(target, "rb"):  # Python opens without FILE_SHARE_DELETE: replace must fail
        with pytest.raises(ConversionError, match="geopend"):
            ws.finalize(_tmp_file(ws), out_dir, "foto", ".png", "overwrite")
    assert _no_partials(out_dir)
    assert target.read_bytes() == b"old"


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0,  # type: ignore[attr-defined]
                    reason="POSIX permissions")
def test_read_only_folder_gives_readable_error_on_posix(ws, out_dir):
    out_dir.chmod(0o500)
    try:
        with pytest.raises(ConversionError):
            ws.finalize(_tmp_file(ws), out_dir, "foto", ".png", "overwrite")
    finally:
        out_dir.chmod(0o700)


def test_cleanup_stale_keeps_young_dirs(ws):
    """Review #14: a second app instance must not delete a running job."""
    young = ws.job_dir("young")
    old = ws.job_dir("old")
    past = time.time() - timedelta(hours=25).total_seconds()
    os.utime(old, (past, past))
    ws.cleanup_stale()
    assert young.exists()
    assert not old.exists()
