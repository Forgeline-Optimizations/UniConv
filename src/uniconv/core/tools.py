"""Find and run Pandoc/ffmpeg: argument list, never a shell, always a timeout, cancellable."""

import platform
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable
from functools import cache
from pathlib import Path

from uniconv.core.converter import CancelToken
from uniconv.core.errors import ConversionCancelled, ConversionError, ConversionTimeout
from uniconv.paths import install_dir, is_frozen

# Without this a console window flashes up for every conversion in the windowed Windows build.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_ARCH = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64", "aarch64": "arm64"}


def platform_tag() -> str:
    machine = platform.machine().lower()
    return f"{sys.platform}-{_ARCH.get(machine, machine)}"  # win32-x86_64, darwin-arm64


def bundled_bin_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", install_dir())) / "bin"
    return install_dir() / "vendor" / platform_tag()


@cache
def find_tool(name: str) -> Path | None:
    """Bundled copy first (frozen: <_MEIPASS>/bin, dev: vendor/<tag>), then PATH."""
    exe = f"{name}.exe" if sys.platform == "win32" else name
    candidate = bundled_bin_dir() / exe
    if candidate.is_file():
        return candidate
    found = shutil.which(name)
    return Path(found) if found else None


def _pump(stream: Iterable[str], on_line: Callable[[str], None] | None) -> None:
    for line in stream:
        if on_line is not None:
            on_line(line.rstrip("\r\n"))


def _last_meaningful_line(stderr: str) -> str:
    """The final non-noise stderr line is usually the actual error message."""
    for line in reversed(stderr.splitlines()):
        line = line.strip()
        if line and not line.startswith(("Conversion failed", "Exiting with")):
            return line
    return ""


def run_tool(cmd: list[str], *, timeout_s: int, cancel: CancelToken,
             on_stdout_line: Callable[[str], None] | None = None,
             cwd: Path | None = None) -> str:
    """Run an external tool; returns stderr. Raises ConversionError / ConversionCancelled."""
    try:
        proc = subprocess.Popen(  # list argv, never shell=True (ruff S602 enforces this)
            cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", creationflags=_NO_WINDOW,
        )
    except OSError as exc:
        raise ConversionError(f"Kan {Path(cmd[0]).name} niet starten: {exc.strerror}") from exc
    err_lines: list[str] = []
    t_err = threading.Thread(target=lambda: err_lines.extend(proc.stderr), daemon=True)
    t_out = threading.Thread(target=_pump, args=(proc.stdout, on_stdout_line), daemon=True)
    t_err.start()  # drain both pipes so the child never blocks on a full buffer
    t_out.start()

    deadline = time.monotonic() + timeout_s
    while proc.poll() is None:
        if cancel.cancelled or time.monotonic() > deadline:
            proc.kill()
            proc.wait()
            t_err.join(1)
            t_out.join(1)
            if cancel.cancelled:
                raise ConversionCancelled("Conversie geannuleerd")
            raise ConversionTimeout(f"Conversie duurde langer dan {timeout_s} s en is gestopt")
        time.sleep(0.1)
    t_err.join()
    t_out.join()
    stderr = "".join(err_lines)
    if proc.returncode != 0:
        raise ConversionError(
            _last_meaningful_line(stderr) or f"Tool stopte met code {proc.returncode}"
        )
    return stderr
