# ADR-001: Pinned Pandoc and ffmpeg sources per platform

**Date:** 2026-11-02
**Sprint:** 1 (step 21 audit)
**Status:** Accepted

## Context
The plan leaves the ffmpeg build source open ("a known GPL build with libx264, libvpx,
libopus, libmp3lame and libvorbis") and flags a missing static macOS arm64 build as the
biggest risk (review #16). Pandoc publishes official zips for both platforms.

## Decision
| Platform | Tool | Source | Version | SHA-256 of archive | Member |
|---|---|---|---|---|---|
| win32-x86_64 | pandoc | `https://github.com/jgm/pandoc/releases/download/3.13/pandoc-3.13-windows-x86_64.zip` | 3.13 | `23e1f2e978a3df80db8bf65c9c59534f41a23140480cfb4f783a882ab7dc6a4e` | `pandoc-3.13/pandoc.exe` |
| win32-x86_64 | ffmpeg, ffprobe | `https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip` (gyan.dev) | 9.0.2 | `60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba` | `ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe`, `.../ffprobe.exe` |
| darwin-arm64 | pandoc | `https://github.com/jgm/pandoc/releases/download/3.13/pandoc-3.13-arm64-macOS.zip` | 3.13 | `f436d18bebbfb3ddd326597686dacab9fac5dc23bd060495020f35a28a43a7c3` | `pandoc-3.13-arm64/bin/pandoc` |
| darwin-arm64 | ffmpeg | `https://ffmpeg.martin-riedl.de/download/macos/arm64/1789931890_9.0.2/ffmpeg.zip` | 9.0.2 | `c8ed4c4e6978a03c485edbfe4e0a5dc2380f8a30bba5150531b31b094492d924` | `ffmpeg` |
| darwin-arm64 | ffprobe | `https://ffmpeg.martin-riedl.de/download/macos/arm64/1789931890_9.0.2/ffprobe.zip` | 9.0.2 | `fcbe839537485eaee7a7a8bc5cbc0f90d53617e80943e8a5b2e31cb851197ea6` | `ffprobe` |

Both ffmpeg builds are configured with `--enable-gpl --enable-version3` (GPLv3), compatible
with our GPL-3.0-or-later. The macOS build is linked with `--pkg-config-flags=--static`
and its published `codecs.txt` lists libx264, libvpx-vp9, libmp3lame, libopus and libvorbis
encoders. The gyan.dev README lists the same libraries.

## Rationale
- Numbered releases with immutable URLs and published hashes, not rolling "latest" builds.
- gyan.dev is the build ffmpeg.org links to for Windows; Martin Riedl's builds are the
  static arm64 builds ffmpeg.org links to for macOS.
- Same ffmpeg version (9.0.2) on both platforms keeps behaviour identical.

## Alternatives considered
- **BtbN FFmpeg-Builds:** Windows/Linux only, rolling tags.
- **eugeneware/ffmpeg-static darwin-arm64 (6.1.1):** old version, build flags undocumented.
- **evermeet.cx / osxexperts:** Intel-only or no stable pinned URLs.
- **Drop media on macOS:** not needed now that a static arm64 build exists.

## Consequences
- `scripts/fetch_binaries.py` (Sprint 3) uses exactly this manifest.
- `otool -L` could not be run on the Windows dev machine; CI on macOS runs it after fetching
  and fails if ffmpeg links anything outside `/usr/lib` or `/System`.
- `THIRD_PARTY_LICENSES.md` (step 31) cites these sources and versions.
- Upgrading = new URLs + hashes here and in the script; the CI cache key follows the script.
