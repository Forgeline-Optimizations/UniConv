"""Drag & drop and click-to-choose emit the same signal, so the window has one code path."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QVBoxLayout, QWidget

# palette() colours follow light/dark mode on both OSes; a .qss file would only be one more
# data file for PyInstaller to bundle.
_STYLE = """
#DropZone { border: 2px dashed palette(mid); border-radius: 12px; min-height: 160px; }
#DropZone[dragActive="true"] { border-color: palette(highlight);
                               background: palette(alternate-base); }
#DropZone:disabled { border-style: dotted; }
"""


class DropZone(QFrame):
    file_chosen = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setStyleSheet(_STYLE)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._name_filter = self.tr("Alle bestanden (*)")
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        self.reset()

    def reset(self) -> None:
        self._label.setText(self.tr("Sleep een bestand hierheen of klik om te kiezen"))

    def show_file(self, name: str, label: str) -> None:
        self._label.setText(f"<b>{_escape(name)}</b><br>{_escape(label)}")

    def set_extensions(self, label: str, extensions: list[str]) -> None:
        self._name_filter = f"{label} ({' '.join('*' + e for e in extensions)})"

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:  # noqa: N802 - Qt override
        if e.mimeData().hasUrls() and any(u.isLocalFile() for u in e.mimeData().urls()):
            self._set_active(True)
            e.acceptProposedAction()

    def dragLeaveEvent(self, e: QDragLeaveEvent) -> None:  # noqa: N802
        self._set_active(False)

    def dropEvent(self, e: QDropEvent) -> None:  # noqa: N802
        self._set_active(False)
        files = [Path(u.toLocalFile()) for u in e.mimeData().urls() if u.isLocalFile()]
        files = [p for p in files if p.is_file()]  # folders are ignored in v1
        if files:
            e.acceptProposedAction()
            self.file_chosen.emit(files[0])  # v1: first file only (batch later)

    def mousePressEvent(self, e: QMouseEvent) -> None:  # noqa: N802
        if e.button() != Qt.MouseButton.LeftButton:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Kies een bestand"), "", self._name_filter
        )
        if path:
            self.file_chosen.emit(Path(path))

    def _set_active(self, on: bool) -> None:
        self.setProperty("dragActive", on)
        self.style().unpolish(self)  # re-apply the stylesheet for the property selector
        self.style().polish(self)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
