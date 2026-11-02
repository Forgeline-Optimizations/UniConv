import pytest
from pydantic import BaseModel

from uniconv.core.converter import Converter, Format
from uniconv.core.errors import (
    UnsupportedConversionError,
    UnsupportedFormatError,
    WrongFamilyError,
)


class _Options(BaseModel):
    pass


class _FakeAudio(Converter):
    """Stands in for the media family so detection can be tested before Sprint 4."""
    family, family_label, Options = "fakeaudio", "Nep-audio", _Options
    formats = (Format("fakemp3", "MP3-test", (".fakemp3",)),)

    def convert(self, ctx):  # pragma: no cover - never called
        raise NotImplementedError


def test_png_named_jpg_is_detected_as_png(registry, make_sample, tmp_path):
    src = make_sample("png")
    renamed = src.rename(tmp_path / "liar.jpg")
    assert registry.detect(renamed, "image").key == "png"


def test_extension_fallback(registry, tmp_path):
    f = tmp_path / "plain.tiff"
    f.write_bytes(b"not really a tiff")  # filetype finds nothing: extension decides
    assert registry.detect(f, "image").key == "tiff"


def test_wrong_family_names_format_and_family(registry, tmp_path):
    registry.register(_FakeAudio())
    f = tmp_path / "song.fakemp3"
    f.write_bytes(b"\x00" * 16)
    with pytest.raises(WrongFamilyError) as exc:
        registry.detect(f, "image")
    assert "MP3-test" in str(exc.value) and "Nep-audio" in str(exc.value)


def test_mp3_in_image_family_names_audio_video(registry, tmp_path):
    if "media" not in dict(registry.families()):
        pytest.skip("media family not available (ffmpeg missing)")
    f = tmp_path / "song.mp3"
    f.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 64)
    with pytest.raises(WrongFamilyError) as exc:
        registry.detect(f, "image")
    assert "MP3" in str(exc.value) and "Audio/video" in str(exc.value)


def test_unknown_extension(registry, tmp_path):
    f = tmp_path / "thing.xyz123"
    f.write_bytes(b"hello")
    with pytest.raises(UnsupportedFormatError):
        registry.detect(f, "image")


def test_target_only_format_is_refused_as_source(registry, tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    with pytest.raises(UnsupportedConversionError):
        registry.detect(f, "image")


@pytest.mark.parametrize("key", ["jpg", "png", "webp", "gif", "bmp", "tiff", "heic", "xlsx",
                                 "docx", "odt", "epub", "rtf"])
def test_filetype_mime_matches_declared_format(registry, make_sample, key):
    """Step 9 audit: the MIME string filetype returns must be listed in Format.mimes."""
    import filetype

    if key in ("docx", "odt", "epub") and "document" not in dict(registry.families()):
        pytest.skip("pandoc missing")
    src = make_sample(key)
    kind = filetype.guess(str(src))
    assert kind is not None, f"filetype does not recognise {key}"
    assert kind.mime in registry.format(key).mimes
