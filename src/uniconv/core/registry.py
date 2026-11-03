"""The only thing the runner and UI know about converters. Also does format detection.

A family has an ordered list of providers (one converter class per engine); the first
available provider that offers a pair wins. Unavailable providers stay registered so their
formats are still recognised and the UI can say what to install.
"""

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

_WEAK_MIMES = frozenset({
    # Containers whose MIME says little: a password-protected .docx is an OLE file that
    # filetype reports as PowerPoint (review #13); 3MF is a plain zip. The extension wins.
    "application/zip", "application/msword", "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
})


class Registry:
    def __init__(self) -> None:
        # family -> [(provider, available)], insertion order = UI order and provider priority
        self._providers: dict[str, list[tuple[Converter, bool]]] = {}
        self._formats: dict[str, Format] = {}           # key -> the single shared definition
        self._source_family: dict[str, str] = {}        # source key -> its family
        self._options: dict[str, type[BaseModel]] = {}  # config section -> Options class

    def register(self, conv: Converter) -> None:
        """Order matters: earlier providers win when two offer the same pair."""
        provs = self._providers.get(conv.family, [])
        if provs and provs[0][0].family_label != conv.family_label:
            raise ValueError(f"family {conv.family!r} has two labels")
        if any(type(c) is type(conv) for c, _ in provs):
            raise ValueError(f"{type(conv).__name__} registered twice")
        for f in conv.formats:
            if f.key in self._formats and self._formats[f.key] != f:
                raise ValueError(
                    f"format {f.key!r} has two definitions; use converters/formats.py")
        for key in conv.sources():
            if self._source_family.get(key, conv.family) != conv.family:
                raise ValueError(f"source format {key!r} claimed by two families")
        section = conv.config_section()
        if self._options.get(section, conv.Options) is not conv.Options:
            raise ValueError(f"config section {section!r} used with two Options models")
        # all checks passed: only now mutate, so a failed register() leaves no trace
        self._formats.update({f.key: f for f in conv.formats})
        self._source_family.update({k: conv.family for k in conv.sources()})
        self._options[section] = conv.Options
        # available() is evaluated once, at start-up
        self._providers.setdefault(conv.family, []).append((conv, conv.available()))

    def _live(self, family: str) -> list[Converter]:
        return [c for c, ok in self._providers.get(family, []) if ok]

    def families(self) -> list[tuple[str, str]]:
        return [(fam, p[0][0].family_label) for fam, p in self._providers.items()
                if self._live(fam)]

    def family_label(self, family: str) -> str:
        return self._providers[family][0][0].family_label

    def providers(self, family: str) -> list[Converter]:
        return self._live(family)

    def format(self, key: str) -> Format:
        try:
            return self._formats[key]
        except KeyError:
            raise UnsupportedFormatError(f"Onbekend doelformaat: {key}") from None

    def sources(self, family: str) -> list[str]:
        """All readable keys, also those whose provider is missing (so a hint can be shown)."""
        return list(dict.fromkeys(
            k for c, _ in self._providers.get(family, []) for k in c.sources()))

    def extensions(self, family: str) -> list[str]:
        return [e for k in self.sources(family) for e in self._formats[k].extensions]

    def targets(self, family: str, source: str) -> list[str]:
        return list(dict.fromkeys(
            t for c in self._live(family) if source in c.sources() for t in c.targets(source)))

    def find(self, family: str, source: str, target: str) -> Converter:
        for c in self._live(family):
            if source in c.sources() and target in c.targets(source):
                return c
        raise UnsupportedConversionError(
            f"{source.upper()} naar {target.upper()} wordt niet ondersteund")

    def hints(self, family: str, source: str) -> list[str]:
        """What to install to get more targets for this source, e.g. LibreOffice."""
        return list(dict.fromkeys(
            c.install_hint for c, ok in self._providers.get(family, [])
            if not ok and c.install_hint and source in c.sources()))

    def detect(self, path: Path, family: str) -> Format:
        try:
            kind = filetype.guess(str(path))
        except OSError as exc:
            raise ConversionError(f"Kan {path.name} niet lezen: {exc.strerror}") from exc
        ext = path.suffix.lower()
        by_ext = next((f for f in self._formats.values() if ext in f.extensions), None)
        fmt = None
        if kind is not None:
            matches = [f for f in self._formats.values() if kind.mime in f.mimes]
            # Containers share MIME types (e.g. MP4 and M4A): prefer the one the extension names.
            fmt = next((f for f in matches if ext in f.extensions), None)
            if fmt is None and matches and not (kind.mime in _WEAK_MIMES and by_ext):
                fmt = matches[0]
        fmt = fmt or by_ext  # text formats, or a container whose MIME is weak
        if fmt is None:
            raise UnsupportedFormatError(f"Onbekend bestandstype: {path.name}")
        fam = self._source_family.get(fmt.key)
        if fam is None:  # PDF: a target in three families, a source in none
            raise UnsupportedConversionError(f"{fmt.label} kan in deze versie alleen als doel")
        if fam != family:
            raise WrongFamilyError(
                f"{path.name} is een {fmt.label}-bestand. Kies '{self.family_label(fam)}'.")
        return fmt

    def options_for(self, conv: Converter, cfg: AppConfig) -> BaseModel:
        section = conv.config_section()
        try:
            return conv.Options.model_validate(cfg.defaults.get(section, {}))
        except ValidationError as exc:
            loc = ".".join(str(p) for p in exc.errors()[0]["loc"])
            raise ConversionError(
                f"Ongeldige instelling defaults.{section}.{loc} in config.json"
            ) from exc

    def default_options(self) -> dict[str, dict]:
        return {s: o().model_dump(mode="json") for s, o in self._options.items()}


def default_providers() -> list[Converter]:
    """Every provider, in UI order and priority (earlier wins within a family)."""
    from uniconv.converters.browser import BrowserPdfConverter
    from uniconv.converters.data import DataConverter
    from uniconv.converters.document import DocumentConverter
    from uniconv.converters.image import ImageConverter
    from uniconv.converters.media import MediaConverter
    from uniconv.converters.model3d import Model3DConverter
    from uniconv.converters.office import OfficeDocumentConverter, OfficeSheetConverter
    from uniconv.converters.vector import VectorConverter

    return [
        ImageConverter(), VectorConverter(),
        DataConverter(), OfficeSheetConverter(),  # pandas for everything except PDF
        OfficeDocumentConverter(), BrowserPdfConverter(), DocumentConverter(),  # best PDF first
        MediaConverter(),
        Model3DConverter(),
    ]


def build_default_registry() -> Registry:
    reg = Registry()
    # All providers are registered, available or not; unavailable ones still detect formats.
    for conv in default_providers():
        reg.register(conv)
    return reg
