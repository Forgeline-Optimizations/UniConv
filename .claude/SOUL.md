# UniConv - Soul

## Problem
Converting a file from one format to another (HEIC to PNG, CSV to JSON, DOCX to
Markdown, MKV to MP4) usually means uploading private files to an ad-ridden website,
or learning a command-line tool like ffmpeg or Pandoc. Neither is acceptable for
everyday users who just want the file in another format, on their own machine.

## Who this is for
Ordinary Windows and macOS users who drag a file into a window, pick a target format
and get the result in a folder they chose. They do not know what a codec, encoding or
colour profile is. Failure for them is: a crash, a silently broken or wrong-coloured
file, a file landing somewhere unexpected, or a cryptic error message.

## Core value proposition
One local, installable app that converts the common formats of four families (image,
data, document, audio/video) with sensible defaults, without anything leaving the
machine.

## Architecture spirit
- Local-first: files never leave the machine; no network calls at runtime.
- The core knows nothing about the UI. UI and CLI are thin layers that only build a
  `Job` and call `JobRunner.run()`.
- Converters own their formats and their options. Adding a family = one converter file
  plus one line in `build_default_registry()`. Nothing else may need to change.
- Use proven engines (Pillow, pandas, Pandoc, ffmpeg); our code is routing, safety and
  UX, not codecs.
- Simplicity over cleverness: this was planned to be buildable in one night.

## Non-negotiables
- Never leave a half-written or wrong file in the user's folder. Converters write only
  to the work dir; only `Workspace.finalize()` writes to the user's folder.
- Information loss is always announced (`expected_losses()` before, `ctx.warn()` during).
- Every expected failure is a `UniconvError` whose `str()` is a readable Dutch message.
- External tools run only via `core/tools.py`: argument list, never `shell=True`,
  always a timeout, always cancellable.
- A bad `config.json` never crashes the app; it falls back to defaults and says so.
- GPL-3.0: Pandoc and ffmpeg (with x264) are GPL; ship their licenses.

## What this must never become
- Not a cloud or web service.
- Not a cross-family converter in v1 (no JPG to DOCX, no OCR, no PDF to DOCX, no tracing).
- Not an editor: no cropping, trimming or per-file tweaking beyond the config.
- Not a codec playground: one well-chosen default per target format.

## Documentation tone
- Audience: developers comfortable with Python; the repo is public on GitHub.
- Style: direct and technical, no marketing language.
- Code, comments and commit messages in English. User-facing strings in Dutch via
  `self.tr()` / plain strings, so translation can be added later.
- Comments explain why, not what.
