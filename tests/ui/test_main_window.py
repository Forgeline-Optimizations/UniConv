"""pytest-qt tests: the UI is thin, but its wiring to the registry and worker thread can break."""

import threading
from pathlib import Path

import pytest
from pydantic import BaseModel

pytest.importorskip("pytestqt")

from uniconv.core.converter import Converter, Format  # noqa: E402
from uniconv.ui.main_window import MainWindow  # noqa: E402


class _Options(BaseModel):
    pass


class SlowConverter(Converter):
    """Blocks until released, so the busy state can be inspected."""
    family, family_label, Options = "slow", "Traag", _Options
    formats = (Format("slowin", "Traag-in", (".slowin",), target=False),
               Format("slowout", "Traag-uit", (".slowout",), source=False))

    def __init__(self) -> None:
        self.release = threading.Event()

    def convert(self, ctx):
        while not self.release.wait(0.02):
            ctx.cancel.raise_if_cancelled()
        ctx.output_path.write_bytes(b"done")


@pytest.fixture
def window(qtbot, registry, runner, cfg, tmp_path):
    win = MainWindow(registry, runner, cfg, config_path=tmp_path / "cfg" / "config.json")
    qtbot.addWidget(win)
    return win


def _targets(win) -> list[str]:
    return [win.target_combo.itemData(i) for i in range(win.target_combo.count())]


def test_family_buttons_come_from_registry(window, registry):
    assert [b.text() for b in window.family_buttons] == [lbl for _, lbl in registry.families()]


def test_drop_fills_target_combo(window, make_sample):
    window.drop_zone.file_chosen.emit(make_sample("png"))
    targets = _targets(window)
    assert "jpg" in targets
    assert "png" not in targets and "heic" not in targets
    assert window.convert_btn.isEnabled()


def test_loss_hint_shows_for_lossy_target(window, make_sample):
    window.drop_zone.file_chosen.emit(make_sample("png"))
    window.target_combo.setCurrentIndex(_targets(window).index("jpg"))
    assert window.loss_label.isVisibleTo(window)
    assert "transparantie" in window.loss_label.text().lower()


def test_wrong_family_shows_error(window, tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4\n")
    window.drop_zone.file_chosen.emit(f)
    assert window.status_label.text()
    assert not window.convert_btn.isEnabled()
    assert window.target_combo.count() == 0


def test_convert_end_to_end(window, qtbot, make_sample, tmp_path):
    window._on_output_settings_changed({"output_dir": str(tmp_path / "result"),
                                        "output_mode": "fixed"})
    window.drop_zone.file_chosen.emit(make_sample("png", name="foto"))
    window.target_combo.setCurrentIndex(_targets(window).index("jpg"))
    window.convert_btn.click()
    qtbot.waitUntil(lambda: window._worker is None, timeout=10_000)
    assert "foto.jpg" in window.status_label.text()
    assert window.open_folder_btn.isVisibleTo(window)
    assert (tmp_path / "result" / "foto.jpg").is_file()


def test_beside_source_checkbox_is_used_by_next_job(window, qtbot, make_sample):
    """Review #3: toggling the setting must affect the very next job."""
    src: Path = make_sample("png", name="naast")
    window.beside_checkbox.setChecked(True)
    window.drop_zone.file_chosen.emit(src)
    window.target_combo.setCurrentIndex(_targets(window).index("bmp"))
    window.convert_btn.click()
    qtbot.waitUntil(lambda: window._worker is None, timeout=10_000)
    assert src.with_suffix(".bmp").is_file()
    assert window._config_path.is_file()


def test_inputs_disabled_while_busy(window, qtbot, registry, tmp_path):
    """Review #10: clicking around during a job must not scramble the UI state."""
    slow = SlowConverter()
    registry.register(slow)  # after window creation: no button, but selectable by key
    window._select_family("slow")
    src = tmp_path / "in.slowin"
    src.write_bytes(b"x")
    window.drop_zone.file_chosen.emit(src)
    window.convert_btn.click()
    try:
        for w in (*window.family_buttons, window.drop_zone, window.target_combo,
                  window.choose_dir_btn, window.beside_checkbox):
            assert not w.isEnabled()
        assert window.convert_btn.isEnabled()
        assert window.convert_btn.text() == "Annuleer"
    finally:
        slow.release.set()
    qtbot.waitUntil(lambda: window._worker is None, timeout=10_000)
    assert window.drop_zone.isEnabled()
    assert window.convert_btn.text() == "Converteer"


def test_cancel_button_cancels(window, qtbot, registry, tmp_path):
    slow = SlowConverter()
    registry.register(slow)
    window._select_family("slow")
    src = tmp_path / "in.slowin"
    src.write_bytes(b"x")
    window.drop_zone.file_chosen.emit(src)
    window.convert_btn.click()
    window.convert_btn.click()  # now "Annuleer"
    qtbot.waitUntil(lambda: window._worker is None, timeout=10_000)
    assert window.status_label.text() == "Geannuleerd"
    assert not src.with_suffix(".slowout").exists()


# ---- 0.2: providers -------------------------------------------------------------------

def test_five_family_buttons(window):
    labels = [b.text() for b in window.family_buttons]
    expected = ["Afbeelding", "Data", "Document", "Audio/video", "3D-model"]
    assert [x for x in expected if x in labels] == labels  # order kept; missing tools hide one
    assert labels[0] == "Afbeelding" and labels[-1] == "3D-model"


def test_hint_when_no_targets(qtbot, registry_without, runner, cfg, tmp_path, make_sample):
    """Without LibreOffice a PowerPoint has no targets; the status says what to install."""
    from uniconv.converters.office import OfficeDocumentConverter
    from uniconv.core.tools import find_tool

    if find_tool("pandoc") is None:
        pytest.skip("pandoc missing: cannot make a PPTX sample")
    reg = registry_without(OfficeDocumentConverter)
    win = MainWindow(reg, runner, cfg, config_path=tmp_path / "cfg2" / "config.json")
    qtbot.addWidget(win)
    win._select_family("document")
    win.drop_zone.file_chosen.emit(make_sample("pptx"))
    assert win.target_combo.count() == 0
    assert not win.convert_btn.isEnabled()
    assert "LibreOffice" in win.status_label.text()


def test_loss_hint_from_chosen_provider(window, make_sample):
    """SVG -> JPG runs on VectorConverter, so its hint ('vaste afmetingen') must show."""
    if not window.registry.targets("image", "svg"):
        pytest.skip("resvg missing")
    window.drop_zone.file_chosen.emit(make_sample("svg"))
    window.target_combo.setCurrentIndex(_targets(window).index("jpg"))
    assert "vaste afmetingen" in window.loss_label.text()
