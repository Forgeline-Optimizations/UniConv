# Module: tests

**Responsibility:** prove that every offered conversion produces a valid file, that loss
is announced, and that no partial or wrong file ever reaches the user's folder. It does
NOT contain binary sample files; samples are generated.
**Sprint:** 1 (grows every sprint) - Status: In progress

## Interface
- `conftest.py`: fixtures `cfg` (defaults, work dir in `tmp_path`), `registry`, `runner`,
  `out_dir`, `make_sample(key, **kw) -> Path`; collection hook that skips `needs_pandoc` /
  `needs_ffmpeg` tests when `find_tool()` finds nothing.
- `unit/`: `test_config.py`, `test_registry.py`, `test_detect.py`, `test_workspace.py`,
  `test_tools.py` (Sprint 3), `test_layering.py`.
- `integration/`: `test_matrix.py`, `test_jobs.py`, `test_image.py`, `test_data.py` (3),
  `test_document.py` (3), `test_media.py` (4).
- `ui/test_main_window.py` (Sprint 2, pytest-qt).

Full inventory with what each test proves: `docs/implementation-plan.md`, steps 34-37.

## Key design choices
- Samples are generated: Pillow for images (pillow-heif can write HEIC), text for data and
  Markdown, Pandoc for DOCX/ODT/EPUB, ffmpeg lavfi (`sine=duration=1`,
  `testsrc=duration=1:size=64x64`) for media. `make_sample` accepts overrides such as
  size, mode, encoding, so review-fix cases (CMYK, 16-bit, 63x47 video, cp1252 CSV) are easy.
- `test_matrix.py` is parametrized over every family and every pair from
  `registry.targets()`: asserts success, non-empty output, and for binary targets that
  `filetype` recognises the target format. New formats are tested automatically.
- `test_jobs.py` registers a `FailingConverter` in its own test family that writes half a
  file then raises; asserts `out_dir` and the work dir end up empty. This also proves
  extensibility.
- `test_workspace.py` runs the overwrite case on Windows in CI (review #1).
- `test_layering.py` scans `uniconv/core` and `uniconv/converters` with `ast` for imports of
  `PySide6` or `uniconv.ui`.
- Every critical review fix (#1-#6) and most others have a named test; keep that mapping
  when adding tests.

## Dependencies
- **Depends on:** pytest, pytest-qt, the whole `uniconv` package, optional Pandoc/ffmpeg.
- **Consumed by:** CI (`.github/workflows/ci.yml`, Windows + macOS).

## Current state
Sprints 1-3 done. `make_sample` covers images, all data formats (text via `text=`/`encoding=`
overrides, xlsx via pandas) and documents (md/html/tex/rtf as text; docx/odt/epub via
Pandoc). Skip hook `pytest_collection_modifyitems` marks `needs_pandoc`/`needs_ffmpeg` tests
as skipped when `find_tool()` finds nothing. Matrix: 122 pairs (image 43, data 30,
document 49). 238 passed locally with `vendor/` fetched. Next: media samples via ffmpeg
lavfi and `test_media.py` (Sprint 4).

## Known issues / deliberate shortcuts
- No coverage target; the rule is one test per review fix plus the matrix.
- Media tests skip locally without `vendor/`; CI fetches binaries from Sprint 3 on.
