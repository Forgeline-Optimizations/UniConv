# Module: scripts

**Status:** Done (Sprint 3).
**Responsibility:** `fetch_binaries.py` downloads the Pandoc, ffmpeg and ffprobe builds pinned
in [ADR-001](../.claude/decisions/ADR-001-pinned-binary-sources.md) for `win32-x86_64` or
`darwin-arm64`, verifies SHA-256 while streaming, extracts the named zip members into a
staging dir and renames it to `vendor/<platform_tag>/` (so a half-finished fetch never looks
complete), sets `chmod +x` off Windows, and copies license files to `vendor/<tag>/licenses/`.

## Interface
- `python scripts/fetch_binaries.py [--tag <platform_tag>]`; stdlib only, no install needed.
- `MANIFEST: dict[tag, list[Archive(url, sha256, members, licenses)]]`.
- Idempotent: `vendor/<tag>/.manifest-hash` = sha256 of the manifest entries for that tag.

## Key design choices
- `platform_tag()` is duplicated from `uniconv.core.tools` on purpose: the script must run
  before `pip install` in CI and packaging.
- The CI cache key hashes this file, so editing a pin invalidates the cached `vendor/`.

## Upgrading a binary
Change URL + sha256 here and in ADR-001 (or a superseding ADR), update
`THIRD_PARTY_LICENSES.md`, push, and watch CI (incl. the macOS `otool -L` step).
