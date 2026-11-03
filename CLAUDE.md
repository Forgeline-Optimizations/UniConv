# UniConv

UniConv is a local, installable desktop app (Windows + Apple Silicon macOS) that converts
one file at a time within one family: image, data, document or audio/video. Sprint 0
(this memory workspace) is done; Sprint 1 builds the scaffolding, the UI-free core, the
image converter and a CLI. The single most important constraint: the core never imports
the UI, and only `Workspace.finalize()` writes to the user's folder.

Repo: https://github.com/Forgeline-Optimizations/uniconv (license GPL-3.0-or-later).

## Soul (always loaded)
@.claude/SOUL.md

## Repo map: where to find what
| Need | Location |
|------|----------|
| Why this exists, invariants, doc tone | `.claude/SOUL.md` (imported above) |
| The full step-by-step plan with code per file (Dutch) | v1: `docs/implementation-plan.md` (steps 1-37); 0.2: `docs/extension-plan-0.2.md` (steps 1-29) |
| Known pitfalls and their fixes | v1 review #1-#18 and 0.2 review #1-#26, each plan's section "Review: wat kan er misgaan" (numbers overlap: say which plan) |
| What happened last session, what is unfinished | `.claude/memory/session-log.md` (newest entry first) |
| Why an architectural choice was made | `.claude/decisions/ADR-NNN-*.md` (template: `ADR-TEMPLATE.md`) |
| Module responsibilities and interfaces | `src/uniconv/<module>/CLAUDE.md`, `tests/CLAUDE.md` (load when you work there) |
| Current sprint, tasks, conventions | this file |
| Re-run the orientation | `/onboard` |

The plan is the source of truth for file contents. Read only the steps for the task at
hand (search for `### Stap N`); do not load the whole plan up front.

## Session start
A SessionStart hook injects an "orientation" block when a session begins. When you see
it, open your FIRST reply with a short orientation (max 8 lines): what this repo is,
the current sprint and its next open task, anything unfinished from the last session,
and where to look for more. Then answer the user's actual request. If their first
message is a concrete task, give the orientation in 2-3 lines and proceed. Do not read
every file up front: rely on the loaded context, and open module files only when
needed.

## Stack
| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Language | Python | 3.12 | `src/` layout, hatchling build |
| UI | PySide6 (Qt 6) | >=6.7 | One window, worker on a `QThread` |
| Images | Pillow + pillow-heif, img2pdf (+pikepdf) | >=10.4 / >=0.18 / >=0.6.3 | HEIC source only; PDF via img2pdf (lossless, multi-page) |
| Vector | resvg 0.49 (bundled), Typst, vtracer | pinned / >=0.6.15 | SVG -> raster/PDF, raster -> SVG (tracing in a child process) |
| 3D | trimesh + scipy, networkx, lxml | >=5.2 | STL, OBJ, PLY, OFF, GLB, glTF, 3MF; runs in a child process |
| Data | pandas, openpyxl, PyYAML, tomli-w, xmltodict | see pyproject | Table vs tree model |
| Documents | Pandoc 3.13 + Typst 0.15.1 | bundled | PDF = Pandoc -> Typst source -> Typst (two steps, review 0.2 #25) |
| Detected apps | LibreOffice, Chrome/Edge/Chromium | user-installed, never bundled | `core/apps.py`; Office/HTML -> PDF with original layout |
| Audio/video | ffmpeg + ffprobe | GPL build, bundled | Needs libx264, libvpx-vp9, libopus, libmp3lame, libvorbis |
| Detection | filetype | >=1.2 | Magic bytes, extension fallback |
| Config | pydantic v2 + JSON | >=2.7 | Defaults in code, user file holds overrides only |
| Paths | platformdirs | >=4.2 | Per-user config/cache/log dirs |
| Packaging | PyInstaller onedir, Inno Setup, DMG | >=6.6 | macOS 14+ arm64 only, ad-hoc signed |
| CI/CD | GitHub Actions | - | Tests on push (Windows + macOS), release on tag `v*` |
| Tests | pytest, pytest-qt | >=8 / >=4.4 | `QT_QPA_PLATFORM=offscreen` in CI |
| Lint | ruff | >=0.6 | Rule set includes `S` (bandit) |

## Architecture
- Layers: `ui/` and `cli.py` -> `core/jobs.py` (`JobRunner`) -> `core/registry.py` ->
  `converters/*`. Nothing below `ui/` imports Qt (enforced by `tests/unit/test_layering.py`).
- A `Job` is `(family, target, inputs: list[Path], output_dir | None)`. v1 UI always sends
  one input; the core already handles lists, so batch is UI-only work later.
- The caller resolves `output_dir` from the CURRENT settings (`None` = next to each input).
  The runner never reads `cfg.paths` (review #3).
- Each `Converter` is a **provider**: it declares `family`, `family_label`, `formats`
  (shared definitions in `converters/formats.py`), `Options`, optional `options_key` and
  `install_hint`, and implements `convert(ctx)`. A family has several providers in priority
  order (`core/registry.py::default_providers()`); `find()` picks the first available one
  that offers the pair (ADR-003). No global format table.
- Flow per item: size check -> `registry.detect()` -> `registry.find()` ->
  `registry.options_for(conv, cfg)` -> `conv.convert(ctx)` into the job's work dir ->
  `workspace.finalize()` (temp name + `os.replace`) -> work dir discarded in `finally`.
- Unavailable providers stay registered: formats are still detected, no targets offered,
  `registry.hints()` names what to install. A family with no live provider has no button.
- Engines that can crash or run for minutes never run in the app process: binaries via
  `core/tools.py::run_tool`, Python engines (vtracer, trimesh) via `core/isolate.py::
  run_isolated` (spawn). `main()` calls `multiprocessing.freeze_support()` first.
- Config: `AppConfig` (paths, behavior, limits) has defaults in code; `defaults.<section>`
  (`image`, `data`, `document`, `media`, `office`, `browser`) is validated by that
  provider's `Options`. The app writes `config.defaults.json` at start as a reference.

## Current Sprint: 0.2: medium conversions
**Goal:** implement `docs/extension-plan-0.2.md` (steps 1-29) on branch
`feature/0.2-medium-conversions`: providers per family, lossless image PDF, PDF via Typst,
Office/browser PDF via detected apps, vector (resvg, Typst, vtracer), new 3D family.
Running log: top entry of `.claude/memory/session-log.md`. Do not tag or merge to `main`.

**Phase 0 - foundation**
- [x] 1 `__main__.py`: `multiprocessing.freeze_support()` first (#7)
- [x] 2 `core/converter.py`: `NoOptions`, `options_key`, `install_hint`, `config_section()`
- [x] 3 `converters/formats.py`: shared `Format` constants
- [x] 4 `core/registry.py`: providers per family, weak MIMEs, `hints()` (#6, #13)
- [x] 5 `core/jobs.py`, `cli.py`, `ui/main_window.py`, `ui/app.py`: new registry API
- [x] 6 `core/isolate.py`: `run_isolated()` (#3)
- [x] 7 `core/apps.py`: `find_app()` for LibreOffice and Chrome/Edge

**Phase 1 - PDF from images and text**
- [x] 8 `pyproject.toml`, `__init__.py`: 0.2.0 and new dependencies
- [x] 9 `converters/image.py`: image to PDF via img2pdf (#1, #18)
- [x] 10 `scripts/fetch_binaries.py`: Typst + resvg, `.tar.xz` (#19)
- [x] 11 ADR-002: Typst, resvg and detected apps
- [x] 12 `core/tools.py` `cwd`, `converters/document.py` PDF via Typst (#25, #11, #12)

**Phase 2 - Office and browser to PDF**
- [x] 13 `converters/office.py` + `ConversionTimeout` (#4, #5, #13, #14, #17)
- [x] 14 `converters/browser.py` (#15)
- [x] 15 registry order: Office and browser before Pandoc

**Phase 3 - vector**
- [x] 16 `converters/vector.py` + `encode_raster()` (#2, #3, #9, #10, #26)
- [x] 17 register `VectorConverter`

**Phase 4 - 3D models**
- [x] 18 `converters/model3d.py` (#16)
- [x] 19 register `Model3DConverter`

**Phase 5 - packaging, CI, licenses, memory**
- [x] 20 `packaging/uniconv.spec`: trimesh data, licenses, macOS 14.0 (#8)
- [x] 21 `packaging/licenses/`, `THIRD_PARTY_LICENSES.md` (#20)
- [x] 22 `ci.yml`: otool for Typst/resvg, LibreOffice job
- [x] 23 `release.yml`: smoke test of the new routes
- [x] 24 `README.md`
- [x] 25 memory files, ADR-003

**Tests (written in the phase they belong to)**
- [x] 26 `conftest.py` + markers, samples, `registry_without()`
- [x] 27 unit tests
- [x] 28 integration tests
- [x] 29 UI tests

## Milestone history
- Sprint 0 - Project Initialization: memory workspace scaffolded from the plan. done
- Sprint 1 - Core, images and CLI (steps 1-14, 34-36, audits 9 + 21): done 2026-11-02.
  Binary sources pinned in [ADR-001](.claude/decisions/ADR-001-pinned-binary-sources.md).
- Sprint 2 - UI (steps 15-19, 37): done 2026-11-02.
- Sprint 3 - Data and documents (steps 20-25): done 2026-11-02.
- Sprint 4 - Audio and video (steps 26-27): done 2026-11-02.
- Sprint 5 - Packaging and release (steps 28-33): done 2026-11-02 (not yet tagged).

## Module map
| Module | Responsibility | Sprint | Status |
|--------|---------------|--------|--------|
| `src/uniconv/` (root files) | Entry point, CLI, config, paths | 1 | Done |
| `src/uniconv/core` | Contracts, registry with providers + detection, work dir, job runner, tool runner, `isolate.py`, `apps.py` | 1, 3, 0.2 | Done |
| `src/uniconv/converters` | Providers: image, vector, data, office, browser, document, media, model3d; shared `formats.py` | 1-4, 0.2 | Done |
| `tests` | Unit, integration matrix, UI tests | 1-5 | Done |
| `src/uniconv/ui` | PySide6 window, drop zone, worker thread, bootstrap | 2 | Done |
| `scripts` | `fetch_binaries.py`: pinned Pandoc, ffmpeg, Typst, resvg into `vendor/<tag>/` (zip + tar) | 3, 0.2 | Done |
| `packaging` | PyInstaller spec, Inno Setup, DMG script | 5 | Done |

## Conventions
**Naming:** package `uniconv`, app name `UniConv`, CLI `uniconv`. Format keys are short
lowercase extensions (`jpg`, `xlsx`, `m4a`); a key has ONE definition everywhere and a
source key belongs to one family (targets such as `pdf` may appear in several).
Family keys: `image`, `data`, `document`, `media`, `model3d`. Work-dir job folders:
`<job.id>-<index>`.
**Testing:** write the tests of a sprint in that sprint. Every review fix (#1-#15) has its
own test. The matrix test is parametrized over `registry.targets()`, so new formats are
tested automatically. Tests needing tools are marked `needs_pandoc` / `needs_ffmpeg` /
`needs_typst` / `needs_resvg` (via `find_tool()`) or `needs_libreoffice` / `needs_browser`
(via `find_app()`) and skip when absent. Fallback routes are tested with the
`registry_without(*classes)` fixture. Run `ruff check . && pytest -q` before finishing.
**Error handling:** raise a `UniconvError` subclass with a Dutch, user-readable message.
The runner turns expected errors into `ItemResult(status="failed", error=...)`; unexpected
exceptions are logged with traceback and shown as "Onverwachte fout: ...".
**Commits:** small, imperative English subject, reference the plan step (`step 10: ...`).
**Paths:** always `pathlib.Path`; never assume the install dir is writable.

## Key decisions
- **PySide6 desktop app, not a web UI:** one language, native drag & drop and file dialogs,
  installable; Tauri/Electron would add a second language and a Python sidecar.
- **UI-free core + CLI:** testable without Qt, CLI reproduces bug reports.
- **Converters own formats and options:** a new family touches one file plus one line;
  the first draft needed five files.
- **Job carries an explicit output dir:** prevents the stale-config bug (review #3).
- **Finalize via temp name + `os.replace`:** `shutil.move` cannot overwrite on Windows
  (review #1), and the final name never holds a partial file.
- **Defaults in code, user JSON holds overrides only:** no second defaults file that can
  drift; updates bring new defaults automatically.
- **GPL-3.0 with a GPL ffmpeg build:** LGPL builds lack x264, so no usable MP4 output.
- **Per-user dirs, no portable mode, arm64-only macOS:** scope cut to fit one night.
- **Providers per family (ADR-003):** several engines per family in priority order; the
  better route wins when installed, the fallback says what it loses.
- **Isolate risky engines:** anything that can crash or run for minutes runs via
  `run_tool` (binaries) or `run_isolated` (Python engines), so cancel and time-outs work.
- **Detect, never bundle, LibreOffice and browsers (ADR-002):** Typst and resvg are bundled
  (small, permissive); LibreOffice would add hundreds of MB.

## Session end
Before finishing a work session, add an entry to `.claude/memory/session-log.md`
(template inside that file). Tick finished tasks above. Create an ADR for any
architectural decision that deviates from or adds to `docs/implementation-plan.md`.

## What NOT to do
- Do not import PySide6 or `uniconv.ui` anywhere under `core/` or `converters/`.
- Do not write to the user's folder from a converter; write to `ctx.output_path` only.
- Do not call subprocess directly or use `shell=True`; use `core/tools.py`. Run Python
  engines that can crash or run long via `core/isolate.py::run_isolated`, never in-process.
- Do not use `registry.converter()`: it no longer exists. Use `find()`, `providers()`,
  `sources()`, `targets()`, `hints()`.
- Do not bundle LibreOffice or a browser; find them with `core/apps.py::find_app`.
- Do not use `yaml.load`; always `yaml.safe_load`.
- Do not add a global format table or hard-code formats in the UI; ask the registry.
- Do not read `cfg.paths` inside the runner.
- Do not add features listed under "What this must never become" in SOUL.md.
- Do not commit anything in `vendor/`, `build/` or `dist/`.
