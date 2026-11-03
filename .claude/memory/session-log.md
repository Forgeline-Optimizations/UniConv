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
- Step 13 (converters/office.py, core/errors.py, core/tools.py): OfficeDocumentConverter + OfficeSheetConverter via soffice, own profile, input<ext> copy, output check, Dutch errors, timeout hint; run_tool raises ConversionTimeout (#4, #5, #13, #14, #17); tests: test_tools timeout type; end-to-end test_office.py lands with step 15 registration
- Step 14 (converters/browser.py, core/tools.py): BrowserPdfConverter via Chrome/Edge headless, own profile, page timeout + process limit (#15); verified locally with Chrome (0.6 s); run_tool now waits max 3 s for pipe EOF after the tool exits; tests: test_returns_when_a_grandchild_keeps_the_pipes_open (failed before the fix: 20 s), test_tools 11 passed
- Step 15 (core/registry.py default_providers): Image; Data, OfficeSheet; OfficeDocument, BrowserPdf, Document; Media; tests: test_office.py (needs_libreoffice, incl. 2 audit tests), test_browser.py (4, pass locally with Chrome incl. CSS red pixel and endless script), provider-priority test in test_pdf.py, detect tests for protected DOCX (#13, filetype says PowerPoint), PDF target-only, real office files; Office samples via soffice + msoffcrypto in conftest; LibreOffice CI job added early (step 22 part)
- Phase 2 done: LibreOffice + browser providers registered before Pandoc. Audits on real runners: soffice.com waits for the PDF and is found by find_app (Windows); 'could not be loaded' goes to stderr with a NON-ZERO exit on both OSes (plan assumed 0); browser CSS test passes on both. First LibreOffice run failed: profile inside the job dir exceeded the Windows path limit (fixed: short temp profile). CI green incl. LibreOffice job: https://github.com/Forgeline-Optimizations/UniConv/actions/runs/41557581786
- Step 16 (converters/vector.py, converters/image.py): resvg render with size guard + font-warning parsing, Typst vector PDF with svgz/linked-image fallback, vtracer tracing in run_isolated with downscale; encode_raster() shared; 4 new ImageOptions fields (#2, #3, #9, #10, #26); manual run on Windows: svg->png 512x256, ->jpg, ->pdf ok; tests: test_vector_helpers.py (23)
- Step 17 (core/registry.py): VectorConverter registered; tests: test_vector.py (12: 512x256 scaling, huge SVG refused #2, font never lost silently #9, broken SVG, svgz->png/pdf, vector PDF 180pt, linked image fallback #26, generic font warning #10, logo trace, 4MP downscale #3, cancel trace <1 s), SVG sample in conftest; run_tool error messages now prefer 'error:' lines and skip code-frame noise (Typst), tests added; full suite passed
- Phase 3 done: VectorConverter (resvg, Typst, vtracer in run_isolated); 439 passed per OS; CI green https://github.com/Forgeline-Optimizations/UniConv/actions/runs/41558778800
- Step 18 (converters/model3d.py): Model3DConverter, 7 formats, worker in run_isolated, merge/axes/texture loss hints (#16), worker returns warnings (merged N objects), empty mesh refused; tests: test_model3d_worker.py (2)
- Step 19 (core/registry.py): Model3DConverter registered last; tests: test_model3d.py (7: merge warning, single-file glTF with data: buffers, OBJ without .mtl, axes hint #16, empty/garbage files, 3MF zip detected), 3D samples (box + sphere scene) in conftest, matrix now image 57 / data 30 / document 56 / media 66 / model3d 42; offscreen screenshot: five family buttons fit at 520 px; full suite passed
- Step 29 (tests/ui/test_main_window.py): test_five_family_buttons, test_hint_when_no_targets (PPTX without LibreOffice -> status names LibreOffice), test_loss_hint_from_chosen_provider (SVG->JPG hint from VectorConverter); tests: 11 UI passed
- Phase 4 done: 3D family (trimesh in run_isolated), 42 matrix pairs; UI tests of step 29 added; 494 passed per OS; CI green https://github.com/Forgeline-Optimizations/UniConv/actions/runs/41559722856
- Step 20 (packaging/uniconv.spec): collect_data_files('trimesh'), packaging/licenses, LSMinimumSystemVersion 14.0 (#8); local Windows build OK (typst/resvg in bin, trimesh resources present); frozen smoke test: md->pdf, png->pdf, svg->png, png->svg (spawn child), stl->glb (spawn child) all OK, no runaway UniConv processes
- Step 21 (packaging/licenses/resvg-LICENSE-{MIT,APACHE}.txt from tag v0.49.0, THIRD_PARTY_LICENSES.md): Typst, resvg, img2pdf, pikepdf (+qpdf), vtracer, trimesh, SciPy, NetworkX, lxml with versions and checked source links; 'Detected, not bundled' section for LibreOffice/Chrome/Edge (#20)
- Step 22 (.github/workflows/ci.yml): otool -L guard covers ffmpeg, ffprobe, typst, resvg; LibreOffice job (weekly + workflow_dispatch) was added early in phase 2 and is green on both OSes
- Step 23 (.github/workflows/release.yml): frozen app converts md->pdf, png->pdf, svg->png, png->svg (child process), stl->glb (child process); no stray UniConv processes allowed (tasklist/pgrep); YAML validated; verified locally on the Windows build before writing
- Step 24 (README.md): formats incl. SVG, Office sources, PDF targets, 3D; 'Better PDFs' (LibreOffice, Chrome/Edge); system requirements macOS 14+ (#8) and measured size (+~150 MB, Windows build 789 MB; plan estimated ~110 MB, #21); privacy exceptions (#22); new config keys; dev notes on vendor/, app env overrides, LibreOffice CI job; architecture with providers
- Step 26 (tests/conftest.py, pyproject.toml): checked complete: markers needs_typst/resvg/libreoffice/browser, samples svg/pptx/doc/xls/ppt/ods/odp/3D, protected DOCX, registry_without() (built during phases 1-4)
- Step 27 (tests/unit): checked complete: test_registry rewritten, test_detect, test_isolate + _isolate_targets, test_apps, test_tools (cwd, ConversionTimeout), plus test_fetch_binaries, test_vector_helpers, test_model3d_worker
- Step 28 (tests/integration): checked complete: test_matrix (sources()), test_image (PDF), test_pdf, test_office, test_browser, test_vector, test_model3d, test_document line 82
- Step 25 (ADR-003-providers-per-family.md, CLAUDE.md, core/converters/tests/scripts/packaging CLAUDE.md): providers, isolation, detected apps, audit findings and pitfalls recorded; docs/extension-plan-0.2.md committed at sprint start
- Phase 5 done: spec (trimesh data, licenses, macOS 14), licenses, CI otool for typst/resvg, release smoke of 5 new routes + stray-process check, README, memory + ADR-003. Final: CI push green https://github.com/Forgeline-Optimizations/UniConv/actions/runs/41560992735 ; CI + LibreOffice job green https://github.com/Forgeline-Optimizations/UniConv/actions/runs/41560999904 ; release dry run 0.2.0 green on both OSes (9 smoke conversions, no stray processes, GUI starts; installer artifact 177 MB, DMG artifact 222 MB) https://github.com/Forgeline-Optimizations/UniConv/actions/runs/41561003122
- Post-sprint (2026-11-03): installed 0.2.0 on the dev PC (0.1.0 uninstalled), all 251 offered conversions passed through the installed exe; after installing LibreOffice 26.8.2 (winget) all 258 passed, Office PDFs produced by LibreOffice, HTML by Chrome (Skia), MD/TEX/EPUB by Typst. Fixed tests/conftest.py run_soffice: profile in a short temp dir (inside a deep samples dir LibreOffice crashed with 0xC0000409, same Windows path-limit issue as the app).
- Released 2026-11-03: PR #1 merged into main (e8a1765), tag v0.2.0 pushed; release workflow published https://github.com/Forgeline-Optimizations/UniConv/releases/tag/v0.2.0 with UniConv-0.2.0-windows-x86_64-setup.exe (178 MB) and UniConv-0.2.0-macos-arm64.dmg (226 MB); CI green on main and on the tag.
**Decisions made:**
- Steps 4+5 committed together: the new registry API breaks the old call sites, so a separate step-4 commit would be red. Additions beyond the plan: Registry.family_label(family) (UI needs the label of a family whose providers may all be unavailable) and a check that refuses registering the same provider class twice.
- Step 9: palette frames become RGB/RGBA before img2pdf, and a frame's ICC profile is dropped when its colour space changed (same rule as the raster path, review #4).
- Step 12: registry.default_providers() added so the registry_without() fixture (step 26) can rebuild the default provider list; input path is resolve()d in _to_pdf because Pandoc runs with cwd=jobdir.
- Step 13: soffice output is matched on stdout AND stderr (plan text says stdout, plan code reads stderr); after soffice returns we poll up to 10 s for input.pdf unless an Error line was printed (plan's audit fallback, harmless when soffice.com waits). Steps 13/14 are committed without registration; their end-to-end tests come with step 15 so every commit stays green.
- Step 14: run_tool joins its pipe readers with a 3 s grace after the tool exits instead of waiting for EOF; browser helper processes can inherit the pipes and keep them open (reproduced with a grandchild process in a test).
- Step 15/22: the LibreOffice CI job runs on schedule + workflow_dispatch only (plan text says not on every push; the plan's if: only excluded PRs). ruff S105-S107 ignored under tests/ for test passwords.
- Step 13 (after audit): LibreOffice profile lives in tempfile.mkdtemp('uniconv-lo-') and is removed in finally, not in the job dir (Windows MAX_PATH); non-zero soffice exits go through the same Dutch error analysis; missing PDFs log LibreOffice's output.
- Step 16: on Windows resvg falls back to an installed font when a family is missing (text drawn, no stderr), so review #9's silent loss only happens on font-less systems; the warning stays and is tested on resvg's message format, and the integration test asserts text is never lost silently. Text without any font-family counts as generic for #10. The general max_megapixels limit also applies to trace sources before downscaling.
- Step 17: _last_meaningful_line prefers the last 'error:' line and skips compiler-style code-frame lines; Typst's diagnostics end with a caret line that hid both the message and the linked-image fallback trigger.
- Step 18: the trimesh worker returns warnings (e.g. 'Alle 2 objecten zijn samengevoegd') that the parent passes to ctx.warn; an empty mesh (not only an empty scene) gives 'bevat geen 3D-geometrie'.
- Step 24: README stays English (repo documentation language), so 'Betere PDF's' became 'Better PDFs'; size stated from the measured local build (+148 MB), not the plan's ~110 MB estimate.
**Left unfinished:** Nothing. Open: the maintainer tests the DMG from the release on a real Mac (macOS 14+).
**Notes for next session:** 0.2.0 is released. If the Mac test finds problems: fix on a branch, bump to 0.2.1 in pyproject.toml and src/uniconv/__init__.py, merge, tag v0.2.1. Dev PC has UniConv 0.2.0, LibreOffice 26.8.2, Chrome and Edge installed.

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
