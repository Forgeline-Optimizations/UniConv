"""converters/vector.py helpers that need no engine."""

import gzip

import pytest

from uniconv.converters import vector
from uniconv.core.errors import ConversionError


@pytest.mark.parametrize(("value", "px"), [("240", 240), ("240px", 240), ("72pt", 96),
                                           ("1in", 96), ("2.54cm", 96), ("1e2", 100)])
def test_length_units(value, px):
    assert vector._length(value) == pytest.approx(px)


@pytest.mark.parametrize("value", [None, "", "100%", "auto", "12furlong"])
def test_length_unreadable(value):
    assert vector._length(value) is None


def test_size_from_attributes_and_viewbox(tmp_path):
    a = tmp_path / "a.svg"
    a.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10cm" height="5cm"/>')
    assert vector._svg_size(a) == pytest.approx((96 / 2.54 * 10, 96 / 2.54 * 5))
    b = tmp_path / "b.svg"
    b.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 300 150"/>')
    assert vector._svg_size(b) == (300, 150)


def test_size_of_svgz(tmp_path):
    z = tmp_path / "c.svgz"
    z.write_bytes(gzip.compress(b'<svg xmlns="http://www.w3.org/2000/svg" width="40" '
                                b'height="20"/>'))
    assert vector._svg_size(z) == (40, 20)


@pytest.mark.parametrize("content", ["<svg", "<html></html>", "not xml at all"])
def test_size_of_broken_svg_is_a_readable_error(tmp_path, content):
    f = tmp_path / "kapot.svg"
    f.write_text(content)
    with pytest.raises(ConversionError):
        vector._svg_size(f)


@pytest.mark.parametrize(("svg", "generic"), [
    ('<svg><text font-family="sans-serif">a</text></svg>', True),
    ('<svg><text style="font-family: serif, monospace">a</text></svg>', True),
    ('<svg><text>a</text></svg>', True),  # no family at all: the renderer picks one
    ('<svg><text font-family="Arial, sans-serif">a</text></svg>', False),
    ("<svg><text style=\"font-family:'DejaVu Sans'\">a</text></svg>", False),
    ('<svg><rect font-family="sans-serif"/></svg>', False),  # no text: nothing to warn about
])
def test_only_generic_fonts(tmp_path, svg, generic):
    """Review #10: Typst draws generic 'sans-serif' as a serif face."""
    f = tmp_path / "t.svg"
    f.write_text(svg)
    assert vector._only_generic_fonts(f) is generic


def test_missing_font_warning_is_parsed():
    """Review #9: resvg's stderr names the missing family."""
    stderr = ("Warning (in usvg::text:153): No match for '\"Comic Neue\"' font-family.\n"
              "Warning (in usvg::text:153): No match for 'Fira' font-family.\n")
    assert sorted(set(vector._FONT_MISSING.findall(stderr))) == ["Comic Neue", "Fira"]
