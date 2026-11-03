# Session Log

> **Protocol:** Add new entries at the top (below this header). One entry per session.
> Each entry starts with `## Sprint ...` and ends with a `---` line (the SessionStart
> hook reads the first entry).

---

## Sprint 0.2 - Session 1
**Date:** 2026-11-03
**Goal:** implement `docs/extension-plan-0.2.md` (steps 1-29) on branch
`feature/0.2-medium-conversions`; no tag, no merge to `main`.
**Completed:**
- Setup: plan file moved from `docs/Uitbreidingsplan UniConv 0.2, gemiddelde conversies.md`
  to `docs/extension-plan-0.2.md`; branch created; checklist in CLAUDE.md.
- Step 1 (__main__.py): freeze_support() as first call (#7); tests: added test_main_calls_freeze_support_first, test_cli 5 passed
- Step 2 (core/converter.py): NoOptions, options_key, install_hint, config_section(); tests: test_config_section_defaults_to_family added, test_registry 7 passed
- Step 3 (converters/formats.py, image/data/document.py): shared Format constants incl. new SVG/XLS/ODS/DOC/PPT(X)/ODP; tests: full suite 328 passed
- Step 4 (core/registry.py): providers per family, shared formats, weak MIMEs, hints(), options per section; tests: test_registry rewritten (13 tests), full suite 334 passed
- Step 5 (core/jobs.py, cli.py, ui/main_window.py, ui/app.py): options from the chosen provider, CLI shows hints, UI shows install hint (grey line or status when no targets), loss hint from find(); tests: full suite 334 passed
- Step 6 (core/isolate.py): run_isolated with spawn, cancel, time-out, crash detection (also EOF without answer) (#3); tests: test_isolate.py (6) + _isolate_targets.py added, passed 3x in a row
- Step 7 (core/apps.py): find_app with env override, install dirs, PATH; tests: test_apps.py (6 + 2 CI-only audit tests); locally Chrome found, no LibreOffice
- Phase 0 done: registry with providers, run_isolated, find_app, freeze_support; 349 passed per OS, step 7 browser audit passed on both runners; CI green https://github.com/Forgeline-Optimizations/UniConv/actions/runs/41554296346
- Step 8 (pyproject.toml, __init__.py): version 0.2.0; img2pdf, vtracer, trimesh, scipy, networkx, lxml; dev pypdfium2, msoffcrypto-tool (installed: trimesh 5.2.0, vtracer 0.6.15, img2pdf 0.6.3, pikepdf 10.17); tests: test_version reads __version__, full suite passed
- Step 9 (converters/image.py): image -> PDF via img2pdf, JPEG as-is, rest via PNG frames, multi-page, size check factored out (#1, #18); tests: 6 PDF tests in test_image.py (Flate, byte-identical JPEG, WebP alpha, 3-page GIF, EXIF portrait, CMYK/16-bit), full suite passed
- Step 10 (scripts/fetch_binaries.py): Typst 0.15.1 + resvg 0.49.0 for both platforms, tar support via extractfile() (#19); all 4 plan hashes matched GitHub digests AND were re-verified by downloading both tags locally; tests: test_fetch_binaries.py (4) added
- Step 10 follow-up: test caught extractfile() following a symlink member; script now checks getmember().isfile() first; test_fetch_binaries 4 passed
- Step 11 (.claude/decisions/ADR-002-typst-resvg-and-detected-apps.md): pins, bundle-vs-detect rule, alternatives; tests: n/a (docs)
- Step 12 (core/tools.py cwd, converters/document.py): two-step PDF route, A4/nl options, missing-image warnings, loss hints naming LibreOffice/browser (#25, #11, #12); input path resolved because cwd=jobdir; tests: test_pdf.py (9), test_cwd_is_used; step 26 partly: markers needs_typst/resvg/libreoffice/browser, registry_without() fixture, registry.default_providers(); full suite passed. Windows path audit passed locally (../ and absolute images)
- Phase 1 done: lossless image PDF (img2pdf), Typst+resvg pinned, document PDF via Pandoc->Typst; 376 passed per OS, Typst PDF tests pass on Windows and macOS (step 12 audit answered); CI green https://github.com/Forgeline-Optimizations/UniConv/actions/runs/41555521366
**Decisions made:**
- Steps 4+5 committed together: the new registry API breaks the old call sites, so a separate step-4 commit would be red. Additions beyond the plan: Registry.family_label(family) (UI needs the label of a family whose providers may all be unavailable) and a check that refuses registering the same provider class twice.
- Step 9: palette frames become RGB/RGBA before img2pdf, and a frame's ICC profile is dropped when its colour space changed (same rule as the raster path, review #4).
- Step 12: registry.default_providers() added so the registry_without() fixture (step 26) can rebuild the default provider list; input path is resolve()d in _to_pdf because Pandoc runs with cwd=jobdir.
**Left unfinished:** Phases 2-5 (steps 13-25) and remaining test steps 26-29 (partly done).
**Notes for next session:** local machine has Chrome + Edge, no LibreOffice (office tests
only run in the CI LibreOffice job). Use `.venv` (Python 3.12). Resume from the first
unticked step in CLAUDE.md.

---

## Sprint 5 - Session 1
**Date:** 2026-11-02
**Goal:** Packaging and release (plan steps 28-33).
**Completed:**
- `packaging/uniconv.spec`, `windows/installer.iss`, `macos/build_dmg.sh`, icons generated by
  `packaging/make_icons.py`; `THIRD_PARTY_LICENSES.md` with versions and source links;
  `.github/workflows/release.yml`; full README with screenshot (`docs/screenshot.png`).
- Local Windows build: frozen exe converts PNG/CSV/MD/WAV and the GUI starts offscreen.
- Release dry run via `workflow_dispatch` green on both OSes: frozen-app smoke test in four
  families plus a 10 s GUI survival check, Inno Setup installer (136 MB artifact), DMG
  (173 MB artifact). Nothing was published.
- Fixed a QThread teardown race found by a flaky Windows CI run (see ui/CLAUDE.md).
**Decisions made:** none beyond the plan. Release workflow additions: tag/version check,
`workflow_dispatch` dry run, separate publish job, GUI start check, Inno Setup via choco
fallback.
**Left unfinished:** manual checks on a real Mac (#18) and of the Windows installer; tagging
`v0.1.0` is left to the maintainer because it publishes a public release.
**Notes for next session:** local `dist/` and `build/` (ignored) hold the last Windows
build. All plan steps 1-37 are done.

---

## Sprint 4 - Session 1
**Date:** 2026-11-02
**Goal:** Audio/video family (plan steps 26-27).
**Completed:**
- `converters/media.py` with the plan's codec table and review fixes #2, #6, #12;
  registered as the fourth family.
- Encoder audit (step 26) is a test, so CI checks both pinned builds on every push.
- `test_media.py`: odd 63x47 video (#2), MKV with subtitles (#6), MP4 to MP3 has no video,
  progress rises monotonically, cancel within 1 s with nothing left behind, readable errors
  for silent video to MP3 and corrupt input. Real MP3 WrongFamily test now runs.
**Decisions made:** none (hardening beyond the plan noted in converters/CLAUDE.md).
**Left unfinished:** nothing in scope.
**Notes for next session:** 325 tests take ~35 s locally; media pairs dominate.

---

## Sprint 3 - Session 1
**Date:** 2026-11-02
**Goal:** Data and documents (plan steps 20-25) plus their tests.
**Completed:**
- `core/tools.py`, `scripts/fetch_binaries.py` (ADR-001 manifest, staged extract, licenses),
  CI fetch + cache + macOS `otool -L` guard; actions bumped to checkout@v7,
  setup-python@v7, cache@v6 (Node 20 deprecation warnings).
- `converters/data.py`, `converters/document.py`, both registered.
- Tests: `test_tools.py`, `test_data.py` (#5, #8), `test_document.py` (#11), MIME audit
  extended to xlsx/docx/odt/epub/rtf. 238 passed locally.
**Decisions made:** none beyond the plan (small hardening listed in converters/CLAUDE.md).
**Left unfinished:** nothing in scope.
**Notes for next session:** running downloaded binaries by hand was refused by the
auto-mode sandbox, but running them through pytest works. `vendor/win32-x86_64` is fetched
locally (Pandoc 3.13, ffmpeg 9.0.2).

---

## Sprint 2 - Session 1
**Date:** 2026-11-02
**Goal:** PySide6 UI (plan steps 15-19, 37).
**Completed:**
- `ui/drop_zone.py`, `ui/worker.py`, `ui/main_window.py`, `ui/app.py`; GUI branch and
  `-psn_` filter in `__main__.py`.
- 8 pytest-qt tests incl. busy-state (#10), cancel, and settings-affect-next-job (#3).
- Offscreen screenshot checked: layout and dark-mode palette render correctly.
**Decisions made:** none
**Left unfinished:** real drag & drop from Explorer/Finder only tested via the signal;
try it manually once (`.venv/Scripts/python -m uniconv`).
**Notes for next session:** `gh` CLI is installed and authenticated; use `gh run list` /
`gh run watch` to confirm CI after each push.

---

## Sprint 1 - Session 1
**Date:** 2026-11-02
**Goal:** Core, images and CLI (plan steps 1-14, 34-36, audits of steps 9 and 21).
**Completed:**
- Repo pushed to `github.com/Forgeline-Optimizations/UniConv` (`main`); MIT LICENSE from
  GitHub's initial commit replaced by GPL-3.0; `.gitattributes` forces LF.
- Python 3.12.12 project venv at `.venv` (created with `uv venv --python 3.12`); `uv pip install
  -e ".[dev,build]"`. System `python` is 3.11, `py` defaults to 3.15: always use `.venv`.
- Steps 1-14 implemented; tests: unit (config, registry, detect, workspace, layering),
  integration (matrix, jobs, image, cli). `ruff check .` clean, 113 passed / 2 skipped.
- `uniconv convert photo.heic --to png --out <dir>` verified end to end.
- Binary audit done: Pandoc 3.13 + ffmpeg 9.0.2 pinned for both platforms (ADR-001).
**Decisions made:** [ADR-001](.claude/decisions/ADR-001-pinned-binary-sources.md)
**Left unfinished:** CI on GitHub not yet observed green (check the Actions tab after push).
macOS `otool -L` check moves into CI in Sprint 3.
**Notes for next session:** Bug found and fixed: Pillow writers reuse `img.info["icc_profile"]`.
The auto-mode sandbox refused to execute downloaded ffmpeg on this machine; binaries will
be exercised via `fetch_binaries.py` + tests. Added `paths.output_dir_for(cfg)` for callers
building a `Job` (review #3).

---

## Sprint 0 - Project Initialization
**Date:** 2026-10-30
**Action:** Memory workspace scaffolded from `docs/implementation-plan.md` (37 steps, review #1-#18).
**Files created:** `.claude/SOUL.md`, `CLAUDE.md`, `docs/implementation-plan.md`,
`src/uniconv/core/CLAUDE.md`, `src/uniconv/converters/CLAUDE.md`, `src/uniconv/ui/CLAUDE.md`,
`tests/CLAUDE.md`, `scripts/CLAUDE.md` (stub), `packaging/CLAUDE.md` (stub),
`.claude/settings.json`, `.claude/hooks/session-start.sh`, `.claude/commands/onboard.md`,
`.claude/decisions/ADR-TEMPLATE.md`
**Sprint mapping:** Sprint 1 = plan Fase 0 + Fase 1 (steps 1-14 + tests), Sprint 2 = Fase 2 (UI),
Sprint 3 = Fase 3 (data, documents, tools), Sprint 4 = Fase 4 (media), Sprint 5 = Fase 5 (release).
**Decided before coding:** repo `Forgeline-Optimizations/uniconv`, GPL-3.0, Inno AppId
`{504A34CB-03E6-468D-B807-ABF6D6AC0117}`.
**Sprint 1 ready:** Yes. Start the binary sourcing audit (step 21) in parallel with step 1.

---
<!-- SESSION TEMPLATE

## Sprint N - Session M
**Date:** YYYY-MM-DD
**Goal:** <what this session set out to accomplish>
**Completed:**
- <item>
**Decisions made:** <"none" or [ADR-001](.claude/decisions/ADR-001-slug.md)>
**Left unfinished:** <specific enough to pick up without re-reading all the code>
**Notes for next session:** <anything critical to know before continuing>

---
-->
