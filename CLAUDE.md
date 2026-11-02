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
| The full step-by-step plan with code per file (Dutch) | `docs/implementation-plan.md` (steps 1-37) |
| Known pitfalls and their fixes (review #1-#18) | `docs/implementation-plan.md`, section "Review: wat kan er misgaan" |
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
| Images | Pillow + pillow-heif | >=10.4 / >=0.18 | HEIC source only, PDF target only |
| Data | pandas, openpyxl, PyYAML, tomli-w, xmltodict | see pyproject | Table vs tree model |
| Documents | Pandoc | 3.x, bundled | Called via `core/tools.py` |
| Audio/video | ffmpeg + ffprobe | GPL build, bundled | Needs libx264, libvpx-vp9, libopus, libmp3lame, libvorbis |
| Detection | filetype | >=1.2 | Magic bytes, extension fallback |
| Config | pydantic v2 + JSON | >=2.7 | Defaults in code, user file holds overrides only |
| Paths | platformdirs | >=4.2 | Per-user config/cache/log dirs |
| Packaging | PyInstaller onedir, Inno Setup, DMG | >=6.6 | macOS arm64 only, ad-hoc signed |
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
- Each `Converter` declares `family`, `family_label`, `formats` (with MIME types),
  `Options` (pydantic model) and implements `convert(ctx)`. The registry builds the
  format index, detection and option validation from that; there is no global format table.
- Flow per item: size check -> `registry.detect()` -> `registry.find()` ->
  `registry.options_for()` -> `conv.convert(ctx)` into the job's work dir ->
  `workspace.finalize()` (temp name + `os.replace`) -> work dir discarded in `finally`.
- Families whose tool is missing (`available() == False`) are simply not registered and
  therefore not shown. This is also the release fallback if ffmpeg for macOS fails.
- Config: `AppConfig` (paths, behavior, limits) has defaults in code; `defaults.<family>`
  is validated by that converter's `Options`. The app writes `config.defaults.json` at start
  as a reference; users override keys in `config.json`.

## Current Sprint: Sprint 1 - "Core, images and CLI"
**Goal:** `uniconv convert photo.heic --to png --out <dir>` works end to end on Windows and
macOS, CI is green on both, and every image conversion in the registry passes the matrix test.
Covers plan phases "Fase 0" and "Fase 1".

**Tasks (plan step in brackets):**
- [ ] Start the binary sourcing audit first, in parallel: pick + pin Pandoc and a static GPL ffmpeg for win32-x86_64 and darwin-arm64; record URLs, versions, sha256 (step 21 Audit) - scripts
- [ ] `pyproject.toml` (1), `.gitignore`, `LICENSE` GPL-3.0, README stub (2) - root
- [ ] `src/uniconv/__init__.py` + `__main__.py` with `--version` (3) - package root
- [ ] `config.py`: `AppConfig`, `load_config`, `save_user_overrides`, `write_reference_copy` (4) - package root
- [ ] `paths.py`: config file, work dir, default output dir (5) - package root
- [ ] `.github/workflows/ci.yml`, Windows + macOS matrix (6) - root
- [ ] `core/errors.py` (7), `core/converter.py` (8), `core/registry.py` incl. detection (9) - core
- [ ] `core/workspace.py` with `os.replace` finalize and readable `OSError`s (10) - core
- [ ] `core/jobs.py` with `Job`, `ItemResult`, `JobRunner` (11) - core
- [ ] `converters/image.py` with `_normalize_mode`, ICC rule, megapixel limit (12) - converters
- [ ] `cli.py` (13) and CLI branch in `__main__.py` (14) - package root
- [ ] `tests/conftest.py` (34), unit tests (35), integration `test_matrix.py`, `test_jobs.py`, `test_image.py` (36) - tests
- [ ] Audit: verify the MIME strings `filetype` returns for each image format (step 9 Audit) - core

**Blockers / open decisions:** none. Assumption: the macOS-arm64 ffmpeg audit may fail;
then media ships later and nothing in Sprint 1 changes.

## Milestone history
- Sprint 0 - Project Initialization: memory workspace scaffolded from the plan. done

## Sprint 2 preview
- PySide6 UI: `ui/drop_zone.py`, `ui/worker.py`, `ui/main_window.py`, `ui/app.py` (steps 15-18)
- GUI branch + `-psn_` filter in `__main__.py` (step 19)
- All inputs disabled while a job runs (review #10); progress bar indeterminate until reported
- pytest-qt tests (step 37)
- Keep the core API stable: the UI only uses `Registry`, `Job`, `JobRunner`, `CancelToken`.

## Module map
| Module | Responsibility | Sprint | Status |
|--------|---------------|--------|--------|
| `src/uniconv/` (root files) | Entry point, CLI, config, paths | 1 | In progress |
| `src/uniconv/core` | Contracts, registry + detection, work dir, job runner, tool runner | 1 (tools.py: 3) | In progress |
| `src/uniconv/converters` | One converter per family: image (1), data + document (3), media (4) | 1-4 | In progress |
| `tests` | Unit, integration matrix, UI tests | 1-5 | In progress |
| `src/uniconv/ui` | PySide6 window, drop zone, worker thread, bootstrap | 2 | Upcoming |
| `scripts` | `fetch_binaries.py`: pinned Pandoc/ffmpeg into `vendor/<tag>/` | 3 (audit in 1) | Stub |
| `packaging` | PyInstaller spec, Inno Setup, DMG script | 5 | Stub |

## Conventions
**Naming:** package `uniconv`, app name `UniConv`, CLI `uniconv`. Format keys are short
lowercase extensions (`jpg`, `xlsx`, `m4a`) and must be unique across ALL families.
Family keys: `image`, `data`, `document`, `media`. Work-dir job folders: `<job.id>-<index>`.
**Testing:** write the tests of a sprint in that sprint. Every review fix (#1-#15) has its
own test. The matrix test is parametrized over `registry.targets()`, so new formats are
tested automatically. Tests needing tools are marked `needs_pandoc` / `needs_ffmpeg` and
skip when `find_tool()` finds nothing. Run `ruff check . && pytest -q` before finishing.
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

## Session end
Before finishing a work session, add an entry to `.claude/memory/session-log.md`
(template inside that file). Tick finished tasks above. Create an ADR for any
architectural decision that deviates from or adds to `docs/implementation-plan.md`.

## What NOT to do
- Do not import PySide6 or `uniconv.ui` anywhere under `core/` or `converters/`.
- Do not write to the user's folder from a converter; write to `ctx.output_path` only.
- Do not call subprocess directly or use `shell=True`; use `core/tools.py`.
- Do not use `yaml.load`; always `yaml.safe_load`.
- Do not add a global format table or hard-code formats in the UI; ask the registry.
- Do not read `cfg.paths` inside the runner.
- Do not add features listed under "What this must never become" in SOUL.md.
- Do not commit anything in `vendor/`, `build/` or `dist/`.
