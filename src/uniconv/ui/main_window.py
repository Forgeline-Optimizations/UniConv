"""The only place with UI state. Turns user actions into one Job and results into text."""

import logging
from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Slot
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from uniconv import APP_NAME
from uniconv.config import AppConfig, save_user_overrides
from uniconv.core.converter import Format
from uniconv.core.errors import UniconvError
from uniconv.core.jobs import ItemResult, Job, JobRunner
from uniconv.core.registry import Registry
from uniconv.paths import config_file, default_output_dir, log_dir, output_dir_for
from uniconv.ui.drop_zone import DropZone
from uniconv.ui.worker import JobWorker, start_job

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, registry: Registry, runner: JobRunner, cfg: AppConfig,
                 config_path: Path | None = None) -> None:
        super().__init__()
        self.registry, self.runner, self.cfg = registry, runner, cfg
        self._config_path = config_path or config_file()
        self._family = registry.families()[0][0]
        self._source: tuple[Path, Format] | None = None
        self._worker: JobWorker | None = None
        self._thread: QThread | None = None
        self._last_output: Path | None = None

        self.setWindowTitle(APP_NAME)
        self.setMinimumWidth(520)
        self._build_ui()
        self._build_menu()
        self._select_family(self._family)
        self._refresh_output_controls()

    # ---- layout -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setSpacing(12)

        families = QHBoxLayout()
        self.family_group = QButtonGroup(self)
        self.family_group.setExclusive(True)
        self.family_buttons: list[QPushButton] = []
        for family, label in self.registry.families():
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("family", family)
            btn.clicked.connect(lambda _=False, f=family: self._select_family(f))
            self.family_group.addButton(btn)
            self.family_buttons.append(btn)
            families.addWidget(btn)
        root.addLayout(families)

        self.drop_zone = DropZone(self)
        self.drop_zone.file_chosen.connect(self._on_file_chosen)
        root.addWidget(self.drop_zone)

        form = QFormLayout()
        self.target_combo = QComboBox()
        self.target_combo.currentIndexChanged.connect(self._update_loss_hint)
        form.addRow(self.tr("Converteer naar:"), self.target_combo)
        root.addLayout(form)

        self.loss_label = QLabel()
        self.loss_label.setWordWrap(True)
        self.loss_label.setStyleSheet("color: gray;")
        self.loss_label.setVisible(False)
        root.addWidget(self.loss_label)

        out_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)
        self.choose_dir_btn = QPushButton(self.tr("Kies…"))
        self.choose_dir_btn.clicked.connect(self._on_choose_dir)
        out_row.addWidget(QLabel(self.tr("Outputmap:")))
        out_row.addWidget(self.output_edit, 1)
        out_row.addWidget(self.choose_dir_btn)
        root.addLayout(out_row)
        self.beside_checkbox = QCheckBox(self.tr("Naast het bronbestand"))
        self.beside_checkbox.toggled.connect(self._on_beside_toggled)
        root.addWidget(self.beside_checkbox)

        self.convert_btn = QPushButton(self.tr("Converteer"))
        self.convert_btn.setEnabled(False)
        self.convert_btn.setDefault(True)
        self.convert_btn.clicked.connect(self._on_convert_clicked)
        root.addWidget(self.convert_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        status_row = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.open_folder_btn = QPushButton(self.tr("Open map"))
        self.open_folder_btn.setVisible(False)
        self.open_folder_btn.clicked.connect(self._open_folder)
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.open_folder_btn)
        root.addLayout(status_row)

        self.warnings_label = QLabel()
        self.warnings_label.setWordWrap(True)
        self.warnings_label.setStyleSheet("color: #b7791f;")
        root.addWidget(self.warnings_label)
        root.addStretch(1)
        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu(self.tr("Help"))
        open_cfg = QAction(self.tr("Open configmap"), self)
        open_cfg.triggered.connect(lambda: self._open_dir(self._config_path.parent))
        open_log = QAction(self.tr("Open logmap"), self)
        open_log.triggered.connect(lambda: self._open_dir(log_dir()))
        menu.addAction(open_cfg)
        menu.addAction(open_log)

    # ---- family and source ------------------------------------------------------------

    def _select_family(self, family: str) -> None:
        self._family = family
        for btn in self.family_buttons:
            btn.setChecked(btn.property("family") == family)
        self._source = None
        self.drop_zone.reset()
        label = dict(self.registry.families())[family]
        self.drop_zone.set_extensions(label, self.registry.extensions(family))
        self.target_combo.clear()
        self.convert_btn.setEnabled(False)
        self.open_folder_btn.setVisible(False)
        self.warnings_label.clear()
        self._update_loss_hint()
        self._show_status("")

    @Slot(Path)
    def _on_file_chosen(self, path: Path) -> None:
        self.open_folder_btn.setVisible(False)
        self.warnings_label.clear()
        self.progress.setValue(0)
        try:
            fmt = self.registry.detect(path, self._family)
        except UniconvError as exc:
            self._source = None
            self.drop_zone.reset()
            self.target_combo.clear()
            self.convert_btn.setEnabled(False)
            self._update_loss_hint()
            self._show_status(str(exc), error=True)  # e.g. the WrongFamilyError text
            return
        self._source = (path, fmt)
        self.drop_zone.show_file(path.name, fmt.label)
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        for key in self.registry.targets(self._family, fmt.key):
            self.target_combo.addItem(self.registry.format(key).label, key)
        self.target_combo.blockSignals(False)
        self._update_loss_hint()
        self.convert_btn.setEnabled(self.target_combo.count() > 0)
        self._show_status("")

    @Slot()
    def _update_loss_hint(self) -> None:
        losses: list[str] = []
        target = self.target_combo.currentData()
        if self._source is not None and target:
            conv = self.registry.converter(self._family)
            losses = conv.expected_losses(self._source[1].key, target)
        self.loss_label.setText("\n".join(losses))
        self.loss_label.setVisible(bool(losses))

    # ---- output folder ----------------------------------------------------------------

    def _output_dir(self) -> Path | None:
        # Resolved here from the CURRENT settings, never inside the runner (review #3)
        return output_dir_for(self.cfg)

    def _refresh_output_controls(self) -> None:
        beside = self.cfg.paths.output_mode == "beside_source"
        self.beside_checkbox.blockSignals(True)
        self.beside_checkbox.setChecked(beside)
        self.beside_checkbox.blockSignals(False)
        self.output_edit.setText(str(default_output_dir(self.cfg)))
        self.output_edit.setEnabled(not beside)
        self.choose_dir_btn.setEnabled(not beside and self._worker is None)

    def _on_output_settings_changed(self, changes: dict) -> None:
        try:
            self.cfg = save_user_overrides(self._config_path, {"paths": changes})
        except (OSError, ValueError) as exc:
            log.warning("Could not save settings", exc_info=True)
            self._show_status(self.tr("Instelling niet opgeslagen: {0}").format(exc), error=True)
        self.runner.update_config(self.cfg)
        self._refresh_output_controls()

    @Slot()
    def _on_choose_dir(self) -> None:
        start = str(default_output_dir(self.cfg))
        chosen = QFileDialog.getExistingDirectory(self, self.tr("Kies de outputmap"), start)
        if chosen:
            self._on_output_settings_changed({"output_dir": chosen, "output_mode": "fixed"})

    @Slot(bool)
    def _on_beside_toggled(self, checked: bool) -> None:
        self._on_output_settings_changed(
            {"output_mode": "beside_source" if checked else "fixed"}
        )

    # ---- running a job -----------------------------------------------------------------

    @Slot()
    def _on_convert_clicked(self) -> None:
        if self._worker is not None:          # the button doubles as Cancel
            self._worker.cancel_token.cancel()
            self.convert_btn.setEnabled(False)
            self._show_status(self.tr("Annuleren…"))
            return
        if self._source is None or not self.target_combo.currentData():
            return
        path, _ = self._source
        job = Job(self._family, self.target_combo.currentData(), [path], self._output_dir())
        self._thread, self._worker = start_job(self.runner, job, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._set_busy(True)
        self._show_status(self.tr("Bezig met converteren…"))

    def _set_busy(self, busy: bool) -> None:
        for w in (*self.family_buttons, self.drop_zone, self.target_combo,
                  self.choose_dir_btn, self.beside_checkbox):
            w.setEnabled(not busy)
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText(self.tr("Annuleer") if busy else self.tr("Converteer"))
        # indeterminate until a converter reports progress
        self.progress.setRange(0, 0 if busy else 100)
        if busy:
            self.open_folder_btn.setVisible(False)
            self.warnings_label.clear()
        else:
            self._refresh_output_controls()

    @Slot(float)
    def _on_progress(self, p: float) -> None:
        if self.progress.maximum() == 0:
            self.progress.setRange(0, 100)
        self.progress.setValue(int(p * 100))

    @Slot(list)
    def _on_finished(self, results: list[ItemResult]) -> None:
        if self._thread is not None:
            # The worker has returned, but the thread may still be winding down. Destroying
            # a running QThread (e.g. closing the window right now) aborts the process.
            self._thread.quit()
            self._thread.wait()
        self._worker = None
        self._thread = None
        self._set_busy(False)
        r = results[0]
        match r.status:
            case "done":
                self.progress.setValue(100)
                self._last_output = r.output
                self._show_status(self.tr("Klaar: {0}").format(r.output.name))
                self.open_folder_btn.setVisible(True)
                if self.cfg.behavior.open_folder_after_convert:
                    self._open_folder()
            case "skipped":
                self.progress.setValue(0)
                self._show_status(self.tr("Overgeslagen: bestand bestaat al"))
            case "cancelled":
                self.progress.setValue(0)
                self._show_status(self.tr("Geannuleerd"))
            case _:
                self.progress.setValue(0)
                self._show_status(r.error or self.tr("Mislukt"), error=True)
        self.warnings_label.setText("\n".join(r.warnings))

    # ---- helpers -----------------------------------------------------------------------

    def _show_status(self, text: str, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet("color: #c0392b;" if error else "")

    @Slot()
    def _open_folder(self) -> None:
        if self._last_output is not None:
            self._open_dir(self._last_output.parent)

    def _open_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def closeEvent(self, e: QCloseEvent) -> None:  # noqa: N802 - Qt override
        if self._worker is not None and self._thread is not None:
            # don't leave an ffmpeg process orphaned
            self._worker.cancel_token.cancel()
            self._thread.wait(5000)
        super().closeEvent(e)
