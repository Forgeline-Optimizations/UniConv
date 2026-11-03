import threading
import time

import pytest

from uniconv.core.converter import CancelToken
from uniconv.core.errors import ConversionCancelled, ConversionError
from uniconv.core.isolate import run_isolated

from . import _isolate_targets as t


def test_returns_the_value():
    assert run_isolated(t.add, 2, 3, timeout_s=60, cancel=CancelToken()) == 5


def test_expected_error_keeps_its_message():
    with pytest.raises(ConversionError) as exc:
        run_isolated(t.user_error, timeout_s=60, cancel=CancelToken())
    assert str(exc.value) == "Dit bestand is kapot"


def test_engine_bug_becomes_unexpected_error():
    with pytest.raises(ConversionError, match="Onverwachte fout: ValueError: engine bug"):
        run_isolated(t.bug, timeout_s=60, cancel=CancelToken())


def test_hard_crash_does_not_take_the_app_down():
    """Review #3: an abort in the engine only kills the child process."""
    with pytest.raises(ConversionError, match="onverwacht gestopt"):
        run_isolated(t.hard_crash, timeout_s=60, cancel=CancelToken())
    assert run_isolated(t.add, 1, 1, timeout_s=60, cancel=CancelToken()) == 2  # still alive


def test_cancel_stops_within_a_second():
    cancel = CancelToken()
    threading.Timer(0.3, cancel.cancel).start()
    start = time.monotonic()
    with pytest.raises(ConversionCancelled):
        run_isolated(t.sleep_forever, timeout_s=60, cancel=cancel)
    assert time.monotonic() - start < 0.3 + 1.0


def test_timeout_stops_a_sleeping_child():
    start = time.monotonic()
    with pytest.raises(ConversionError, match="langer dan 1 s"):
        run_isolated(t.sleep_forever, timeout_s=1, cancel=CancelToken())
    assert time.monotonic() - start < 1 + 1.5
