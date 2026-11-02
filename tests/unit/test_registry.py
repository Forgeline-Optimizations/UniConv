import pytest

from uniconv.config import AppConfig
from uniconv.converters.image import ImageConverter
from uniconv.core.errors import ConversionError, UnsupportedConversionError
from uniconv.core.registry import Registry


def test_duplicate_format_key_is_refused():
    reg = Registry()
    reg.register(ImageConverter())

    class Clash(ImageConverter):
        family = "clash"

    with pytest.raises(ValueError, match="registered twice"):
        reg.register(Clash())


def test_targets_never_contain_the_source(registry):
    for family, _ in registry.families():
        conv = registry.converter(family)
        for src in conv.sources():
            assert src not in registry.targets(family, src)


def test_heic_is_no_target_and_pdf_no_source(registry):
    assert "heic" not in registry.targets("image", "png")
    assert "pdf" not in registry.converter("image").sources()
    assert "pdf" in registry.targets("image", "png")


def test_find_rejects_unsupported_pair(registry):
    with pytest.raises(UnsupportedConversionError):
        registry.find("image", "png", "heic")


def test_options_error_names_the_config_key(registry):
    cfg = AppConfig(defaults={"image": {"jpeg_quality": 120}})
    with pytest.raises(ConversionError, match=r"defaults\.image\.jpeg_quality"):
        registry.options_for("image", cfg)


def test_default_options_cover_every_family(registry):
    assert set(registry.default_options()) == {f for f, _ in registry.families()}
