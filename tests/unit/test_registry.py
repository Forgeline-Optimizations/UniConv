import pytest
from pydantic import BaseModel, ConfigDict

from uniconv.config import AppConfig
from uniconv.converters.formats import PDF
from uniconv.converters.image import ImageConverter
from uniconv.core.converter import Converter, Format, NoOptions
from uniconv.core.errors import ConversionError, UnsupportedConversionError
from uniconv.core.registry import Registry

SRC = Format("fsrc", "Bron", (".fsrc",), target=False)
OUT = Format("fout", "Doel", (".fout",), source=False)


class _Fake(Converter):
    family, family_label, Options = "fake", "Nep", NoOptions
    formats = (SRC, OUT)
    ok = True

    def available(self) -> bool:
        return self.ok

    def convert(self, ctx):  # pragma: no cover - never run
        raise NotImplementedError


class FirstProvider(_Fake):
    options_key = "first"


class SecondProvider(_Fake):
    options_key = "second"


class MissingProvider(_Fake):
    options_key = "missing"
    ok = False
    install_hint = "Installeer NepTool (gratis) en start UniConv opnieuw."


def test_first_registered_provider_wins():
    reg = Registry()
    reg.register(FirstProvider())
    reg.register(SecondProvider())
    assert isinstance(reg.find("fake", "fsrc", "fout"), FirstProvider)
    assert reg.targets("fake", "fsrc") == ["fout"]  # deduplicated


def test_second_definition_of_a_key_is_refused():
    """Review #6: one key, one definition; shared formats live in converters/formats.py."""
    reg = Registry()
    reg.register(ImageConverter())

    class OtherPdf(_Fake):
        formats = (SRC, Format("pdf", "Ander PDF", (".pdf",), source=False))

    with pytest.raises(ValueError, match="two definitions"):
        reg.register(OtherPdf())


def test_same_shared_format_in_two_families_is_fine():
    reg = Registry()
    reg.register(ImageConverter())

    class PdfToo(_Fake):
        formats = (SRC, PDF)

    reg.register(PdfToo())
    assert reg.targets("fake", "fsrc") == ["pdf"]


def test_source_in_two_families_is_refused():
    reg = Registry()
    reg.register(FirstProvider())

    class OtherFamily(_Fake):
        family, family_label, options_key = "other", "Ander", "other"

    with pytest.raises(ValueError, match="two families"):
        reg.register(OtherFamily())
    assert [f for f, _ in reg.families()] == ["fake"]  # failed register left no trace


def test_two_options_models_for_one_section_are_refused():
    class Opts(BaseModel):
        model_config = ConfigDict(extra="forbid")

    reg = Registry()
    reg.register(FirstProvider())

    class Clash(SecondProvider):
        options_key, Options = "first", Opts

    with pytest.raises(ValueError, match="two Options"):
        reg.register(Clash())


def test_unavailable_provider_is_recognised_but_offers_nothing():
    reg = Registry()
    reg.register(MissingProvider())
    assert reg.families() == []  # no live provider: no button in the UI
    assert reg.sources("fake") == ["fsrc"]
    assert reg.targets("fake", "fsrc") == []
    assert reg.hints("fake", "fsrc") == [MissingProvider.install_hint]
    with pytest.raises(UnsupportedConversionError):
        reg.find("fake", "fsrc", "fout")


def test_hint_disappears_when_another_provider_is_live():
    reg = Registry()
    reg.register(MissingProvider())
    reg.register(FirstProvider())
    assert [f for f, _ in reg.families()] == ["fake"]
    assert reg.targets("fake", "fsrc") == ["fout"]
    assert reg.hints("fake", "fsrc") == [MissingProvider.install_hint]  # still worth showing


def test_targets_never_contain_the_source(registry):
    for family, _ in registry.families():
        for src in registry.sources(family):
            assert src not in registry.targets(family, src)


def test_heic_is_no_target_and_pdf_no_source(registry):
    assert "heic" not in registry.targets("image", "png")
    assert "pdf" not in registry.sources("image")
    assert "pdf" in registry.targets("image", "png")


def test_find_rejects_unsupported_pair(registry):
    with pytest.raises(UnsupportedConversionError):
        registry.find("image", "png", "heic")


def test_options_error_names_the_config_key(registry):
    cfg = AppConfig(defaults={"image": {"jpeg_quality": 120}})
    conv = registry.find("image", "png", "jpg")
    with pytest.raises(ConversionError, match=r"defaults\.image\.jpeg_quality"):
        registry.options_for(conv, cfg)


def test_default_options_cover_every_config_section(registry):
    sections = {c.config_section() for f, _ in registry.families() for c in registry.providers(f)}
    assert sections <= set(registry.default_options())


def test_config_section_defaults_to_family():
    conv = ImageConverter()
    assert conv.config_section() == "image"

    class Keyed(ImageConverter):
        options_key = "custom"

    assert Keyed().config_section() == "custom"
    with pytest.raises(ValueError):
        NoOptions.model_validate({"typo": 1})
