"""The only thing the runner and UI know about converters. Also does format detection."""

from pathlib import Path

import filetype
from pydantic import BaseModel, ValidationError

from uniconv.config import AppConfig
from uniconv.core.converter import Converter, Format
from uniconv.core.errors import (
    ConversionError,
    UnsupportedConversionError,
    UnsupportedFormatError,
    WrongFamilyError,
)


class Registry:
    def __init__(self) -> None:
        self._convs: dict[str, Converter] = {}            # insertion order = UI order
        self._formats: dict[str, tuple[Format, Converter]] = {}

    def register(self, conv: Converter) -> None:
        if conv.family in self._convs:
            raise ValueError(f"family {conv.family!r} registered twice")
        for f in conv.formats:
            if f.key in self._formats:  # programming error: fail loudly at start-up and in tests
                raise ValueError(f"format key {f.key!r} registered twice")
        for f in conv.formats:
            self._formats[f.key] = (f, conv)
        self._convs[conv.family] = conv

    def families(self) -> list[tuple[str, str]]:
        return [(c.family, c.family_label) for c in self._convs.values()]

    def converter(self, family: str) -> Converter:
        return self._convs[family]

    def format(self, key: str) -> Format:
        try:
            return self._formats[key][0]
        except KeyError:
            raise UnsupportedFormatError(f"Onbekend doelformaat: {key}") from None

    def extensions(self, family: str) -> list[str]:
        return [e for f in self._convs[family].formats if f.source for e in f.extensions]

    def targets(self, family: str, source: str) -> list[str]:
        return self._convs[family].targets(source)

    def find(self, family: str, source: str, target: str) -> Converter:
        conv = self._convs.get(family)
        if conv is None or target not in conv.targets(source):
            raise UnsupportedConversionError(
                f"{source.upper()} naar {target.upper()} wordt niet ondersteund"
            )
        return conv

    def detect(self, path: Path, family: str) -> Format:
        try:
            kind = filetype.guess(str(path))
        except OSError as exc:
            raise ConversionError(f"Kan {path.name} niet lezen: {exc.strerror}") from exc
        hit = None
        if kind is not None:
            matches = [v for v in self._formats.values() if kind.mime in v[0].mimes]
            # Containers share MIME types (e.g. MP4 and M4A): prefer the one the extension names.
            ext = path.suffix.lower()
            hit = next((v for v in matches if ext in v[0].extensions), None) or next(
                iter(matches), None
            )
        if hit is None:  # text formats, or a ZIP container filetype reports as plain zip
            ext = path.suffix.lower()
            hit = next((v for v in self._formats.values() if ext in v[0].extensions), None)
        if hit is None:
            raise UnsupportedFormatError(f"Onbekend bestandstype: {path.name}")
        fmt, conv = hit
        if conv.family != family:
            raise WrongFamilyError(
                f"{path.name} is een {fmt.label}-bestand. Kies '{conv.family_label}'."
            )
        if not fmt.source:
            raise UnsupportedConversionError(f"{fmt.label} kan in deze versie alleen als doel")
        return fmt

    def options_for(self, family: str, cfg: AppConfig) -> BaseModel:
        try:
            return self._convs[family].Options.model_validate(cfg.defaults.get(family, {}))
        except ValidationError as exc:
            loc = ".".join(str(p) for p in exc.errors()[0]["loc"])
            raise ConversionError(
                f"Ongeldige instelling defaults.{family}.{loc} in config.json"
            ) from exc

    def default_options(self) -> dict[str, dict]:
        return {fam: c.Options().model_dump(mode="json") for fam, c in self._convs.items()}


def build_default_registry() -> Registry:
    from uniconv.converters.data import DataConverter
    from uniconv.converters.document import DocumentConverter
    from uniconv.converters.image import ImageConverter

    reg = Registry()
    for conv in (ImageConverter(), DataConverter(), DocumentConverter()):
        if conv.available():
            reg.register(conv)
    return reg
