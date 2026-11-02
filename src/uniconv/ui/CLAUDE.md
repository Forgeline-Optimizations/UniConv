# Module: ui

**Responsibility:** the PySide6 desktop window: family choice, drop zone, target dropdown,
loss hint, output folder, convert/cancel, progress and status. It turns user actions into
one `Job` and results into text. It does NOT contain conversion logic or know any format;
everything comes from the `Registry`.
**Sprint:** 2 - Status: Done

## Interface
- `app.py`: `run_gui() -> int` (called from `__main__.py` when there are no arguments).
- `main_window.py`: `MainWindow(registry, runner, cfg, config_path=None)`; `config_path`
  defaults to `paths.config_file()` and lets tests keep settings out of the real config.
- `drop_zone.py`: `DropZone(QFrame)` with signal `file_chosen(Path)`,
  `set_extensions(label, extensions)`, `show_file(name, label)`.
- `worker.py`: `JobWorker(QObject)` with signals `progress(float)` and `finished(list)`,
  attribute `cancel_token`; `start_job(runner, job, parent) -> (QThread, JobWorker)`.

Full code per file: `docs/implementation-plan.md`, steps 15-19.

## Key design choices
- Window layout top to bottom: family toggle buttons from `registry.families()`, drop zone,
  target dropdown from `registry.targets()`, loss hint, output folder (read-only field,
  "Kies...", checkbox "Naast het bronbestand"), convert button that becomes "Annuleer",
  progress bar, status line, "Open map" after success, runtime warnings.
- The drop zone emits the same signal for drag & drop and click-to-choose. v1 takes only
  the first file; folders are ignored. Stylesheet is a constant in `drop_zone.py`
  (`palette()` colours follow light/dark mode), no separate `.qss` file.
- Conversions run on a `QThread` via `JobWorker`; Cancel only sets the `CancelToken`.
- `_output_dir()` resolves the folder from the current settings and passes it in the
  `Job`; after saving settings call `runner.update_config(cfg)` (review #3).
- `_set_busy(True)` disables family buttons, drop zone, dropdown and output controls
  (review #10) and makes the progress bar indeterminate until a converter reports progress.
- `closeEvent` cancels a running job and waits up to 5 s, so no ffmpeg process is orphaned.
- `app.py` sets up a rotating log file first (windowed Windows builds have no stdout),
  writes `config.defaults.json`, cleans the work dir, and shows one warning dialog if
  `registry.options_for()` fails for any family.
- `__main__.py` filters macOS Finder `-psn_` arguments before choosing CLI vs GUI.
- Help menu: "Open configmap" and "Open logmap".

## Dependencies
- **Depends on:** PySide6, `uniconv.core` (`Registry`, `Job`, `JobRunner`, `ItemResult`,
  `CancelToken`, `Workspace`, errors), `uniconv.config`, `uniconv.paths`.
- **Consumed by:** `uniconv.__main__`.

## Current state
Sprint 2 done (steps 15-19, 37). Additions: `DropZone.reset()`, `_select_family()` resets
source/combo/hint, `_output_dir()` delegates to `paths.output_dir_for(cfg)`, saving
settings failures show in the status line instead of crashing. Tests in
`tests/ui/test_main_window.py` use a `SlowConverter` family (blocks on an Event) for the
busy/cancel cases; run with `QT_QPA_PLATFORM=offscreen`.
Sprint 5 fix: `_on_finished` calls `thread.quit(); thread.wait()` before clearing state.
Without it, closing the window (or a test tearing it down) right after a job destroyed a
still-running QThread and Qt aborted the process (seen once on Windows CI).

## Known issues / deliberate shortcuts
- Single file per job in the UI; batch is a later UI-only change.
- UI strings are Dutch literals wrapped in `self.tr()`; no translation files yet.
- No settings dialog beyond the output folder; quality is set in `config.json`.
