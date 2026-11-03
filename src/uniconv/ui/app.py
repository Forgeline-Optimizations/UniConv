"""GUI bootstrap: logging, config, work dir clean-up, then the window."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from uniconv import APP_NAME, __version__
from uniconv.config import load_config, write_reference_copy
from uniconv.core.errors import ConversionError
from uniconv.core.jobs import JobRunner
from uniconv.core.registry import build_default_registry
from uniconv.core.workspace import Workspace
from uniconv.paths import config_file, log_dir, resolve_work_dir
from uniconv.ui.main_window import MainWindow

log = logging.getLogger(__name__)


def _setup_logging(log_file: Path) -> None:
    # A windowed Windows build has no console, so the file is the only trace of a crash.
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = RotatingFileHandler(
            log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    except OSError:
        handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)


def run_gui() -> int:
    _setup_logging(log_dir() / "uniconv.log")
    log.info("%s %s starting", APP_NAME, __version__)
    cfg_path = config_file()
    cfg = load_config(cfg_path)
    registry = build_default_registry()
    try:
        write_reference_copy(cfg_path.parent, registry.default_options())
    except OSError:
        log.warning("Could not write config.defaults.json", exc_info=True)

    workspace = Workspace(resolve_work_dir(cfg))
    if cfg.behavior.cleanup_work_dir_on_start:
        workspace.cleanup_stale()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Forgeline Optimizations")
    win = MainWindow(registry, JobRunner(registry, workspace, cfg), cfg, cfg_path)

    problems: dict[str, str] = {}  # per config section, so one typo is reported once
    for family, _label in registry.families():
        for conv in registry.providers(family):
            try:
                registry.options_for(conv, cfg)
            except ConversionError as exc:
                problems.setdefault(conv.config_section(), str(exc))
    if problems:  # shown once; conversions of that family keep failing with the same message
        QMessageBox.warning(win, APP_NAME, "\n".join(problems.values()))

    win.show()
    return app.exec()
