# Module: core

**Responsibility:** the UI-free engine: contracts (`Format`, `Converter`, `ConversionContext`,
`CancelToken`), errors, the registry with providers per family (incl. format detection,
option validation and install hints), the work dir, the job runner, running external tools
(`tools.py`), running Python engines in a child process (`isolate.py`) and finding apps the
user installed (`apps.py`). It does NOT know any concrete format, codec or Qt type.
**Sprint:** 1, 3 (`tools.py`), 0.2 (providers, `isolate.py`, `apps.py`) - Status: Done

## Interface
- `errors.py`: `UniconvError` (base, `str()` = Dutch user message) and subclasses
  `UnsupportedFormatError`, `WrongFamilyError`, `UnsupportedConversionError`,
  `ConversionError` (subclass `ConversionTimeout`), `ToolMissingError`,
  `ConversionCancelled`, `InputTooLargeError`.
- `converter.py`: `Format(key, label, extensions, mimes=(), source=True, target=True)`,
  `CancelToken.cancel()/.cancelled/.raise_if_cancelled()`, `ConversionContext`
  (`input_path`, `output_path`, `source`, `target`, `options`, `timeout_s`, `cancel`,
  `on_progress`, `warnings`, `warn()` de-duplicates), `NoOptions`, abstract `Converter`
  (`family`, `family_label`, `formats`, `Options`, `options_key`, `install_hint`,
  `config_section()`, `available()`, `sources()`, `targets(src)`,
  `expected_losses(src, dst)`, `convert(ctx)`).
- `registry.py`: `Registry.register/families/family_label/providers/format/sources/
  extensions/targets/find/hints/detect/options_for(conv, cfg)/default_options`;
  `default_providers()` (THE priority order) and `build_default_registry()`.
  `registry.converter()` no longer exists.
- `workspace.py`: `Workspace(root).job_dir/discard/cleanup_stale/finalize`.
- `jobs.py`: `Job(family, target, inputs, output_dir)`, `ItemResult`,
  `JobRunner(registry, workspace, cfg).run(job, cancel, on_progress)`, `update_config(cfg)`.
- `tools.py`: `platform_tag()`, `bundled_bin_dir()` (patch point for tests),
  `find_tool(name)` (cached), `run_tool(cmd, timeout_s=, cancel=, on_stdout_line=, cwd=)`
  returning stderr.
- `isolate.py`: `run_isolated(fn, *args, timeout_s=, cancel=)` runs `fn(*args)` in a spawn
  child and returns its value; `fn` must be module-level and Qt-free, and should return
  small values only (it writes its real output to the job dir itself).
- `apps.py`: `find_app("libreoffice" | "browser")` (cached): `UNICONV_<APP>` env var, the
  usual install dirs (Windows prefers `soffice.com`), then PATH.

Full code per file: `docs/implementation-plan.md` (v1 steps 7-11, 20) and
`docs/extension-plan-0.2.md` (steps 2, 4-7, 12, 13).

## Key design choices
- Providers (ADR-003): `find()` = first available provider, in `default_providers()`
  order, that offers the pair. Unavailable providers stay registered for detection and
  `hints()`; a family without a live provider is not in `families()`. `register()` refuses
  two definitions of one key, a source key in two families, two Options models for one
  config section, the same provider class twice, and two labels for one family; all checks
  run before any mutation.
- Detection: `filetype` MIME -> prefer the match whose extension fits -> extension. Weak
  MIMEs (`application/zip`, OLE `msword`/`ms-excel`/`ms-powerpoint`) never beat a known
  extension (0.2 review #13: a password-protected .docx looks like PowerPoint). PDF is a
  target only: "kan alleen als doel" in every family.
- `options_for(conv, cfg)` validates `cfg.defaults[conv.config_section()]` and names the
  exact key in the error (`defaults.image.jpeg_quality`).
- `finalize()`: `shutil.move` to `.<name>.uniconv-partial` in the destination, then
  `os.replace` (v1 #1); `OSError` -> readable `ConversionError` (v1 #7); partial removed in
  `finally`. `cleanup_stale()` only removes job dirs older than 24 h (v1 #14).
- The runner never reads `cfg.paths`; `Job.output_dir` comes from the caller (v1 #3). It
  always discards the job dir in `finally`; one failed item never stops the others; a
  converter that wrote no file fails with a readable error.
- `run_tool`: list argv, never a shell, `CREATE_NO_WINDOW`, drains both pipes on threads,
  polls cancel/timeout every 100 ms, raises `ConversionTimeout` at the deadline. After the
  tool exits it waits at most 3 s for pipe EOF (browser helper processes inherit the
  pipes). Error text = the last `error:` line if any (Typst, LibreOffice), else the last
  line that is not noise (ffmpeg summaries, Typst code-frame carets).
- `run_isolated`: spawn context everywhere (never fork a process holding Qt state). A crash
  (abort, EOF without answer) -> "onverwacht gestopt"; a `UniconvError` keeps its message;
  other exceptions -> "Onverwachte fout: ...". The frozen app needs
  `multiprocessing.freeze_support()` as the first line of `main()` (0.2 #7).

## Dependencies
- **Depends on:** `uniconv.config`, `uniconv.paths` (`install_dir`, `is_frozen`),
  pydantic, filetype.
- **Consumed by:** `uniconv.cli`, `uniconv.ui`, `uniconv.converters`.

## Current state
Done through 0.2. `available()` is evaluated once at start-up: installing LibreOffice
while UniConv runs needs a restart (the install hint says so).

## Known issues / deliberate shortcuts
- MIME strings are verified by `tests/unit/test_detect.py::test_filetype_mime_matches_declared_format`;
  extend its list when formats with magic bytes arrive.
- Global state such as `Image.MAX_IMAGE_PIXELS` is never changed; jobs run one at a time.
- A spawn child costs ~0.3-1 s start-up on Windows (imports); fine for tracing and 3D.
