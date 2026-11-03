# Module: tests

**Responsibility:** prove that every offered conversion produces a valid file, that the
right provider wins, that loss is announced, and that no partial or wrong file ever
reaches the user's folder and no input can crash or hang the app. It does NOT contain
binary sample files; samples are generated.
**Sprint:** 1-5, 0.2 - Status: Done

## Interface
- `conftest.py`: fixtures `cfg` (defaults, work dir in `tmp_path`), `registry`,
  `registry_without(*provider_classes)` (default registry with those providers registered
  as unavailable: tests fallbacks on machines that have LibreOffice/Chrome), `workspace`,
  `runner`, `out_dir`, `make_sample(key, **kw) -> Path`; helpers `make_image`,
  `make_media`, `make_model`, `make_protected_docx`, `run_pandoc`, `run_soffice`.
  Collection hook skips `needs_pandoc` / `needs_ffmpeg` / `needs_typst` / `needs_resvg`
  (via `find_tool()`) and `needs_libreoffice` / `needs_browser` (via `find_app()`).
- `unit/`: `test_config`, `test_registry` (providers, priority, hints, refusals),
  `test_detect` (MIME audit, weak MIMEs, protected DOCX, PDF target-only, real Office
  files), `test_workspace`, `test_tools` (incl. cwd, ConversionTimeout, grandchild pipes,
  error-line parsing), `test_isolate` (+ `_isolate_targets.py`: spawn imports by name),
  `test_apps` (incl. two CI-only audit tests), `test_fetch_binaries` (tar/zip members),
  `test_vector_helpers`, `test_model3d_worker`, `test_layering`.
- `integration/`: `test_matrix` (every pair of every live provider), `test_jobs`,
  `test_image` (incl. lossless PDF), `test_data`, `test_document`, `test_media`, `test_cli`,
  `test_pdf` (Typst route + provider priority, the key 0.2 test), `test_office`
  (needs_libreoffice; runs in the CI LibreOffice job), `test_browser`, `test_vector`,
  `test_model3d`.
- `ui/test_main_window.py` (pytest-qt; incl. five families, install hint, loss hint from
  the chosen provider).

Full inventory: `docs/implementation-plan.md` steps 34-37 and `docs/extension-plan-0.2.md`
steps 26-29.

## Key design choices
- Samples are generated: Pillow (images, HEIC via pillow-heif), text (data, Markdown,
  HTML, LaTeX, RTF, SVG), Pandoc (DOCX/ODT/EPUB/PPTX), LibreOffice (DOC/XLS/PPT/ODS/ODP,
  only where installed), msoffcrypto (password-protected DOCX), ffmpeg lavfi (media),
  trimesh (a box + sphere scene for every 3D format).
- `make_sample` accepts overrides (`size`, `mode`, `text`, `encoding`; for media `seconds`,
  `size`, `inputs=` for extra inputs such as subtitles, `extra=` for output options,
  `audio=`/`video=` to drop a stream), so review-fix cases are one line.
- `test_jobs.py` registers a `FailingConverter` in its own family that writes half a file
  then raises; `out_dir` and the work dir must end up empty (also proves extensibility).
- `test_workspace.py` runs the overwrite case on Windows in CI (v1 #1); `test_layering.py`
  scans `core/` and `converters/` with `ast` for PySide6 / `uniconv.ui` imports.
- `tests/` and its subfolders are packages, so tests import helpers from `..conftest`.
- `test_matrix.py` is parametrized over `registry.sources(family)` x `targets()`; binary
  targets must be recognised by `filetype`. New formats and providers are tested
  automatically, but only where their engine is available on that machine.
- Each review fix has a test with its number in the docstring (v1 #n and 0.2 #n).
- Timing tests (cancel within 1 s, time-outs) leave generous margins for slow runners.
- `test_isolate.py` targets live in `_isolate_targets.py` because spawn re-imports by name;
  a quick script run from stdin cannot use `run_isolated` for the same reason.

## Dependencies
- **Depends on:** pytest, pytest-qt, pypdfium2 (render PDFs), pikepdf (inspect PDFs),
  msoffcrypto-tool, the whole `uniconv` package, optional binaries in `vendor/` and
  optional LibreOffice / Chrome / Edge.
- **Consumed by:** CI (`.github/workflows/ci.yml`: job `test` on every push, job
  `libreoffice` weekly and on `workflow_dispatch`).

## Current state
0.2: ~520 tests; 494 passed per OS in CI with 26 skips (LibreOffice tests, platform-only
tests). The LibreOffice job runs the 24 `needs_libreoffice` tests on both OSes.

## Known issues / deliberate shortcuts
- No coverage target; the rule is one test per review fix plus the matrix.
- The full suite takes ~1.5-2.5 min (3D pairs spawn a process each; media encodes).
