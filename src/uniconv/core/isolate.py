"""Run a module-level Python function in a separate process: crash-proof, cancellable,
with a time-out. For in-process engines that can run long or abort (vtracer, trimesh)."""

import multiprocessing as mp
import time
from collections.abc import Callable
from typing import Any

from uniconv.core.converter import CancelToken
from uniconv.core.errors import ConversionCancelled, ConversionError, UniconvError

# spawn everywhere: never fork a process that holds Qt state; same behaviour on all OSes
_CTX = mp.get_context("spawn")
_CRASHED = "De conversie is onverwacht gestopt; het bestand is te groot of beschadigd"


def _child(fn: Callable[..., Any], args: tuple, conn) -> None:
    try:
        conn.send(("ok", fn(*args)))
    except UniconvError as exc:          # expected failure: keep the user message
        conn.send(("user", str(exc)))
    except BaseException as exc:         # engine bug, MemoryError, ...
        conn.send(("bug", f"{type(exc).__name__}: {exc}"))
    finally:
        conn.close()


def run_isolated(fn: Callable[..., Any], *args: Any, timeout_s: int, cancel: CancelToken) -> Any:
    """Return fn(*args) from a child process. fn must be importable by name and never import Qt.

    The child writes its real output (a file in the job dir) itself and only returns small
    values through the pipe, e.g. a list of warnings.
    """
    recv, send = _CTX.Pipe(duplex=False)
    proc = _CTX.Process(target=_child, args=(fn, args, send), daemon=True)
    proc.start()
    send.close()  # only the child holds the sending end: EOF once it exits
    deadline = time.monotonic() + timeout_s
    try:
        while not recv.poll(0.1):
            # poll again after is_alive(): the child may have answered and exited in between
            if not proc.is_alive() and not recv.poll(0):
                raise ConversionError(_CRASHED)
            if cancel.cancelled:
                raise ConversionCancelled("Conversie geannuleerd")
            if time.monotonic() > deadline:
                raise ConversionError(f"Conversie duurde langer dan {timeout_s} s en is gestopt")
        try:
            kind, value = recv.recv()
        except (EOFError, OSError):  # pipe closed without an answer: the child died
            raise ConversionError(_CRASHED) from None
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join(5)
        recv.close()
    if kind == "user":
        raise ConversionError(value)
    if kind == "bug":
        raise ConversionError(f"Onverwachte fout: {value}")
    return value
