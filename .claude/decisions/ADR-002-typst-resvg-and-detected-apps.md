# ADR-002: Bundle Typst and resvg; detect LibreOffice and Chromium browsers

**Date:** 2026-11-03
**Sprint:** 0.2 (plan `docs/extension-plan-0.2.md`, steps 10-14)
**Status:** Accepted

## Context
0.2 adds PDF output for text documents, Office and HTML, plus SVG rendering. Two of the
engines are small static binaries with permissive licenses; two others (LibreOffice, a
Chromium browser) are large applications many users already have. ADR-001 covers bundled
binaries only; this ADR adds a second category: apps we use but never ship.

## Decision
Bundled, pinned in `scripts/fetch_binaries.py` (hashes compared with GitHub's published
digests and re-verified by downloading both platforms on 2026-11-03):

| Platform | Tool | Source | Version | SHA-256 of archive | Member |
|---|---|---|---|---|---|
| win32-x86_64 | typst | `https://github.com/typst/typst/releases/download/v0.15.1/typst-x86_64-pc-windows-msvc.zip` | 0.15.1 | `19ce3551153c2fe7ee9fa2f95208310c8f4d3209fedb699e0333faf8913f6736` | `typst-x86_64-pc-windows-msvc/typst.exe` |
| win32-x86_64 | resvg | `https://github.com/linebender/resvg/releases/download/v0.49.0/resvg-win-x86_64.zip` | 0.49.0 | `38af9631b37e61118a32a5ef31e6be6af083eda63b4c17ffc4fdc63e449277df` | `resvg.exe` |
| darwin-arm64 | typst | `https://github.com/typst/typst/releases/download/v0.15.1/typst-aarch64-apple-darwin.tar.xz` | 0.15.1 | `48f62ed034aa3a7978309579ac6ca00045e2ef0da73114e8af27cfd8e74dc05a` | `typst-aarch64-apple-darwin/typst` |
| darwin-arm64 | resvg | `https://github.com/linebender/resvg/releases/download/v0.49.0/resvg-macos-aarch64.zip` | 0.49.0 | `847acb5210c7c6244b5e8f07dd62fa1ce596108cce8193628ebfd5750504b259` | `resvg` |

Typst's `LICENSE` and `NOTICE` are copied from the archive into `vendor/<tag>/licenses/`;
resvg's archives contain no license text, so its texts live in `packaging/licenses/`.

**Detected, never bundled** (`src/uniconv/core/apps.py`): LibreOffice (`soffice.com` on
Windows, `soffice` elsewhere) and Chrome / Edge / Chromium. `UNICONV_<APP>` overrides the
search. Without those apps the registry falls back to Pandoc + Typst (with a loss hint
naming the app) or does not offer the pair, and the UI shows the provider's `install_hint`.

## Rationale
- Typst (45-52 MB) and resvg (4-5 MB) are single static binaries under Apache-2.0
  (resvg: Apache-2.0 OR MIT), compatible with GPL-3.0-or-later.
- LibreOffice would add several hundred MB to every installer; users who need faithful
  Office-to-PDF usually have it, and everyone else still gets a PDF via Typst.
- Chrome or Edge is on nearly every machine (Edge ships with Windows); headless printing
  keeps the page's CSS, which Pandoc cannot.

## Alternatives considered
- **WeasyPrint:** needs Pango/GTK; bundling those on Windows and macOS is fragile.
- **LaTeX for PDF:** hundreds of MB, slow, and fonts/Unicode need extra setup.
- **resvg-py in-process:** a huge or malformed SVG aborts the whole app (Rust panic).
- **Bundling LibreOffice:** installer size; also its own update cadence and CVEs.

## Consequences
- CI checks `typst` and `resvg` with `otool -L` on macOS (step 22).
- Providers that need an installed app declare `install_hint`; `available()` is evaluated
  at start-up, so installing LibreOffice while UniConv runs requires a restart.
- A weekly CI job with LibreOffice installed keeps the Office route tested (step 22).
