import sys
import threading
import time

import pytest

from uniconv.core import tools
from uniconv.core.converter import CancelToken
from uniconv.core.errors import ConversionCancelled, ConversionError, ConversionTimeout

PY = sys.executable


def test_platform_tag_shape():
    os_part, arch = tools.platform_tag().split("-", 1)
    assert os_part == sys.platform
    assert arch in ("x86_64", "arm64")


def test_success_returns_stderr_and_streams_stdout():
    lines = []
    err = tools.run_tool(
        [PY, "-c", "import sys; print('a'); print('b'); sys.stderr.write('note\\n')"],
        timeout_s=30, cancel=CancelToken(), on_stdout_line=lines.append,
    )
    assert lines == ["a", "b"]
    assert "note" in err


def test_nonzero_exit_reports_last_stderr_line():
    with pytest.raises(ConversionError, match="the real reason"):
        tools.run_tool(
            [PY, "-c", "import sys; sys.stderr.write('noise\\nthe real reason\\n'); sys.exit(3)"],
            timeout_s=30, cancel=CancelToken(),
        )


def test_timeout_kills_process_quickly():
    start = time.monotonic()
    with pytest.raises(ConversionTimeout, match="langer dan 1 s"):  # a ConversionError too
        tools.run_tool([PY, "-c", "import time; time.sleep(30)"], timeout_s=1,
                       cancel=CancelToken())
    assert time.monotonic() - start < 3


def test_cancel_stops_process_within_a_second():
    cancel = CancelToken()
    threading.Timer(0.3, cancel.cancel).start()
    start = time.monotonic()
    with pytest.raises(ConversionCancelled):
        tools.run_tool([PY, "-c", "import time; time.sleep(30)"], timeout_s=60, cancel=cancel)
    assert time.monotonic() - start < 1.5


def test_large_output_does_not_deadlock():
    """Both pipes are drained on threads; a full stderr buffer must not block the child."""
    tools.run_tool([PY, "-c", "import sys; sys.stderr.write('x' * 2_000_000)"],
                   timeout_s=30, cancel=CancelToken())


def test_missing_executable_is_a_readable_error(tmp_path):
    with pytest.raises(ConversionError, match="niet starten"):
        tools.run_tool([str(tmp_path / "nope.exe")], timeout_s=5, cancel=CancelToken())


def test_find_tool_prefers_bundled_copy(monkeypatch, tmp_path):
    exe = "faketool.exe" if sys.platform == "win32" else "faketool"
    (tmp_path / exe).write_bytes(b"")
    monkeypatch.setattr(tools, "bundled_bin_dir", lambda: tmp_path)
    tools.find_tool.cache_clear()
    try:
        assert tools.find_tool("faketool") == tmp_path / exe
        assert tools.find_tool("definitely-not-installed-xyz") is None
    finally:
        tools.find_tool.cache_clear()


def test_cwd_is_used(tmp_path):
    lines = []
    tools.run_tool([PY, "-c", "import os; print(os.getcwd())"], timeout_s=30,
                   cancel=CancelToken(), on_stdout_line=lines.append, cwd=tmp_path)
    assert lines and lines[0].lower() == str(tmp_path).lower()


def test_timeout_is_a_conversion_error():
    assert issubclass(ConversionTimeout, ConversionError)


def test_returns_when_a_grandchild_keeps_the_pipes_open():
    """Browsers leave helper processes (crashpad) behind that inherit stdout/stderr; the
    tool has exited, so run_tool must not wait for EOF on the pipes forever."""
    code = ("import subprocess, sys; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)']); "
            "print('parent done')")
    start = time.monotonic()
    tools.run_tool([PY, "-c", code], timeout_s=60, cancel=CancelToken())
    assert time.monotonic() - start < 10
