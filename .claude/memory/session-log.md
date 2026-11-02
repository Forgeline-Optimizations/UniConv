# Session Log

> **Protocol:** Add new entries at the top (below this header). One entry per session.
> Each entry starts with `## Sprint ...` and ends with a `---` line (the SessionStart
> hook reads the first entry).

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
