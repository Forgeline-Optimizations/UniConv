# Module: core

**Responsibility:** the UI-free engine: contracts (`Format`, `Converter`, `ConversionContext`,
`CancelToken`), errors, the registry (incl. format detection and option validation), the
work dir and the job runner. From Sprint 3 also `tools.py` (finding and running Pandoc/ffmpeg).
It does NOT know any concrete format, codec or Qt type.
**Sprint:** 1 (`tools.py` in 3) - Status: In progress

## Interface
- `errors.py`: `UniconvError` (base, `str()` = Dutch user message) and subclasses
  `UnsupportedFormatError`, `WrongFamilyError`, `UnsupportedConversionError`,
  `ConversionError`, `ToolMissingError`, `ConversionCancelled`, `InputTooLargeError`.
- `converter.py`: `Format(key, label, extensions, mimes=(), source=True, target=True)`,
  `CancelToken.cancel()/.cancelled/.raise_if_cancelled()`, `ConversionContext`
  (`input_path`, `output_path`, `source`, `target`, `options`, `timeout_s`, `cancel`,
  `on_progress`, `warnings`, `warn()`), abstract `Converter` (`family`, `family_label`,
  `formats`, `Options`, `available()`, `sources()`, `targets(src)`,
  `expected_losses(src, dst)`, `convert(ctx)`).
- `registry.py`: `Registry.register/families/format/extensions/targets/find/detect/
  options_for/default_options`; `build_default_registry()`.
- `workspace.py`: `Workspace(root).job_dir/discard/cleanup_stale/finalize`.
- `jobs.py`: `Job(family, target, inputs, output_dir)`, `ItemResult`,
  `JobRunner(registry, workspace, cfg).run(job, cancel, on_progress)` and `update_config(cfg)`.
- `tools.py` (Sprint 3): `platform_tag()`, `find_tool(name)`, `run_tool(cmd, timeout_s=, cancel=, on_stdout_line=)`.

Full code per file: `docs/implementation-plan.md`, steps 7-11 and 20.

## Key design choices
- One converter per family; format keys unique across all families. `register()` raises
  `ValueError` on a duplicate key so mistakes fail at start-up and in tests.
- Detection order: `filetype` MIME -> extension -> family check -> `source` check.
  ZIP containers that `filetype` reports as plain zip fall back to the extension.
- `options_for()` validates `cfg.defaults[family]` against the converter's `Options` and
  names the exact config key in the error (`defaults.image.jpeg_quality`).
- `finalize()`: `shutil.move` to `.<name>.uniconv-partial` in the dest dir, then
  `os.replace` to the final name. `shutil.move` alone fails on Windows when the target
  exists (review #1). Wrap `PermissionError`/`OSError` in `ConversionError` (review #7);
  remove a leftover partial file in `finally`.
- `cleanup_stale()` only removes job dirs older than 24 h, so a second app instance does
  not delete a running video job (review #14).
- The runner never reads `cfg.paths`; `Job.output_dir` is resolved by the caller (review #3).
  `None` means "next to each input".
- The runner always discards the job's work dir in `finally`, success or not.
- One failed item never stops the others (batch-ready).
- `run_tool` (Sprint 3): drains stdout and stderr on threads (no pipe deadlock), polls
  cancel/timeout every 100 ms, kills the process, uses `CREATE_NO_WINDOW` on Windows,
  and turns a non-zero exit into `ConversionError` with the last meaningful stderr line.

## Dependencies
- **Depends on:** `uniconv.config` (`AppConfig`), `uniconv.paths` (`install_dir`,
  `is_frozen` for `tools.py`), pydantic, filetype.
- **Consumed by:** `uniconv.cli`, `uniconv.ui`, `uniconv.converters` (contracts + tools).

## Current state
Sprint 1 done: errors, converter, registry, workspace, jobs implemented and tested.
Additions beyond the plan: `Registry.converter(family)` (CLI/UI need `sources()`),
`Registry.format()` raises `UnsupportedFormatError` for unknown keys, `detect()` prefers the
format whose extension matches when several share a MIME (MP4/M4A), the runner fails with a
readable error if a converter wrote no file, `ConversionContext.warn()` de-duplicates.
`tools.py` is next (Sprint 3).

## Known issues / deliberate shortcuts
- Image MIME strings are verified by `tests/unit/test_detect.py::test_filetype_mime_matches_declared_format`;
  extend the parametrize list when data/document/media formats arrive.
- Changing `Image.MAX_IMAGE_PIXELS` or any other global state is avoided; jobs run one at
  a time in v1, but keep it that way for future batch work.
