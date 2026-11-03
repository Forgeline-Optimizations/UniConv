"""The contract every family implements. A converter owns its formats and its options."""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from uniconv.core.errors import ConversionCancelled


@dataclass(frozen=True)
class Format:
    key: str                      # unique across ALL families: "jpg"
    label: str                    # UI text: "JPEG"
    extensions: tuple[str, ...]   # first one is used for output: (".jpg", ".jpeg")
    mimes: tuple[str, ...] = ()   # what filetype.guess() reports; empty = extension only
    source: bool = True           # may be converted FROM
    target: bool = True           # may be converted TO


class CancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise ConversionCancelled("Conversie geannuleerd")


def _no_progress(_: float) -> None:
    pass


@dataclass
class ConversionContext:
    input_path: Path
    output_path: Path             # always inside the job's work dir
    source: Format
    target: Format
    options: BaseModel            # an instance of the converter's Options
    timeout_s: int
    cancel: CancelToken
    on_progress: Callable[[float], None] = _no_progress  # 0.0..1.0
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)


class NoOptions(BaseModel):
    """For providers without settings; still validated, so typos in config.json are caught."""
    model_config = ConfigDict(extra="forbid")


class Converter(ABC):
    family: ClassVar[str]                   # "image"
    family_label: ClassVar[str]             # "Afbeelding"
    formats: ClassVar[tuple[Format, ...]]
    Options: ClassVar[type[BaseModel]]      # its section under "defaults" in config.json
    options_key: ClassVar[str | None] = None   # section under "defaults"; None = family
    install_hint: ClassVar[str | None] = None  # shown when available() is False

    def config_section(self) -> str:
        return self.options_key or self.family

    def available(self) -> bool:
        """False when a required external tool is missing; the family is then hidden."""
        return True

    def sources(self) -> list[str]:
        return [f.key for f in self.formats if f.source]

    def targets(self, source: str) -> list[str]:
        return [f.key for f in self.formats if f.target and f.key != source]

    def expected_losses(self, source: str, target: str) -> list[str]:
        return []

    @abstractmethod
    def convert(self, ctx: ConversionContext) -> None:
        """Write ctx.output_path or raise a UniconvError. Never touch other paths."""
