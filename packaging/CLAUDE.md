# Module: packaging

**Status:** Done (Sprint 5).
**Responsibility:** turn the source tree plus `vendor/<tag>/` into installable artefacts:
a PyInstaller onedir build, a per-user Windows installer and an ad-hoc signed arm64 DMG.
Built, smoke-tested and published by `.github/workflows/release.yml` (plan steps 28-32).

## Interface
- `uniconv.spec`: `pyinstaller packaging/uniconv.spec --noconfirm` (after
  `scripts/fetch_binaries.py`). Output `dist/UniConv/` (Windows) or `dist/UniConv.app`.
  Tools go to `<_MEIPASS>/bin` (`_internal/bin` on Windows, `Contents/Frameworks/bin` on
  macOS), which is where `core.tools.find_tool()` looks when frozen. `vendor/<tag>/licenses`
  and `packaging/licenses/` (resvg) go to `licenses/`, plus `LICENSE` and
  `THIRD_PARTY_LICENSES.md`. `collect_data_files("trimesh")` brings trimesh's resources;
  `LSMinimumSystemVersion` is 14.0 (PySide6, pikepdf and SciPy wheels need macOS 14).
- `windows/installer.iss`: `iscc /DAppVersion=<v> packaging\windows\installer.iss` ->
  `dist/UniConv-<v>-windows-x86_64-setup.exe`. Fixed AppId
  `{504A34CB-03E6-468D-B807-ABF6D6AC0117}` (review #13), per user, Dutch + English.
- `macos/build_dmg.sh <v>`: `codesign --deep --sign -`, verify, DMG with /Applications link.
- `make_icons.py`: regenerates `windows/icon.ico`, `macos/icon.icns`, `icon-256.png`.

## Key design choices
- `console=False`: the CLI still works from the frozen exe because `print()` to a missing
  stdout is a no-op; the release smoke test checks files, not output.
- `hiddenimports` lists `uniconv.cli` and `uniconv.ui.app` because `__main__` imports them
  lazily.
- `[InstallDelete]` wipes `{app}\_internal` so an upgrade leaves no stale files.
- Release workflow: build per OS, then the frozen app converts PNG, CSV, MD and WAV and the
  GUI must survive 10 s offscreen; tag must equal `uniconv.__version__`; `workflow_dispatch`
  runs everything except publishing. Inno Setup is installed via choco when missing.
- 0.2 smoke test adds md->pdf (Typst), png->pdf (img2pdf), svg->png (resvg), png->svg and
  stl->glb (both in a spawned child: proves `freeze_support()`), then fails if any UniConv
  process is still running.

## Current state
0.2 Windows build verified locally (789 MB onedir; the five new routes convert, no stray
processes). 0.1 build was 641 MB.
macOS build is only verified in CI; open the DMG on a real Mac before a public release
(review #18).
