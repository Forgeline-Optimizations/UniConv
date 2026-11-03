"""Target functions for test_isolate.py. They live in their own module because the spawn
start method imports them by name in the child process."""

import os
import time

from uniconv.core.errors import ConversionError


def add(a: int, b: int) -> int:
    return a + b


def user_error() -> None:
    raise ConversionError("Dit bestand is kapot")


def bug() -> None:
    raise ValueError("engine bug")


def hard_crash() -> None:
    os.abort()  # like a Rust panic or a segfault in an engine


def sleep_forever() -> None:
    time.sleep(60)
