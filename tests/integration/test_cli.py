import pytest

from uniconv import cli
from uniconv.__main__ import main


@pytest.fixture(autouse=True)
def _isolated_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "config_file", lambda: tmp_path / "cfg" / "config.json")
    monkeypatch.setattr(cli, "resolve_work_dir", lambda cfg: tmp_path / "work")


def test_main_calls_freeze_support_first(monkeypatch, capsys):
    """Review #7: without it the frozen app re-spawns itself for every worker process."""
    import multiprocessing

    calls = []
    monkeypatch.setattr(multiprocessing, "freeze_support", lambda: calls.append("freeze"))
    monkeypatch.setattr("sys.argv", ["uniconv", "--version"])
    assert main() == 0
    assert calls == ["freeze"]


def test_version(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "0.1.0"


def test_formats_lists_image_family(capsys):
    assert main(["formats"]) == 0
    out = capsys.readouterr().out
    assert "Afbeelding (image)" in out
    assert "heic" in out


def test_convert_heic_to_png(make_sample, out_dir, capsys):
    src = make_sample("heic", name="photo")
    assert main(["convert", str(src), "--to", "png", "--out", str(out_dir)]) == 0
    assert (out_dir / "photo.png").is_file()
    assert "OK" in capsys.readouterr().out


def test_convert_failure_exit_code(make_sample, out_dir, capsys):
    src = make_sample("png")
    assert main(["convert", str(src), "--to", "heic", "--out", str(out_dir)]) == 1
    assert "niet ondersteund" in capsys.readouterr().err
